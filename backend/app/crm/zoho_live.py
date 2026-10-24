"""Live Zoho CRM v6 REST client with OAuth 2.0 refresh-token management."""
import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.crm.errors import ZohoAuthError, ZohoPermanentError, ZohoTransientError
from app.crm.mapper import FIELDS
from app.crm.transport import Record

log = logging.getLogger(__name__)
API_VERSION = "v6"


class TokenManager:
    """Caches the access token; refreshes under a lock so concurrent callers trigger one refresh."""

    EXPIRY_SKEW_S = 60

    def __init__(self, accounts_url: str, client_id: str, client_secret: str, refresh_token: str,
                 http: httpx.AsyncClient, clock=time.monotonic):
        self._accounts_url = accounts_url.rstrip("/")
        self._client_id, self._client_secret, self._refresh_token = client_id, client_secret, refresh_token
        self._http = http
        self._clock = clock
        self._lock = asyncio.Lock()
        self._token: str | None = None
        self._expires_at = 0.0
        self.refresh_count = 0

    async def get_token(self) -> str:
        if self._token and self._clock() < self._expires_at - self.EXPIRY_SKEW_S:
            return self._token
        return await self.refresh(stale=self._token)

    async def refresh(self, stale: str | None) -> str:
        """`stale` is the token the caller saw fail. If another task already replaced it, reuse the new one."""
        async with self._lock:
            if self._token and self._token != stale and self._clock() < self._expires_at - self.EXPIRY_SKEW_S:
                return self._token
            if not (self._client_id and self._client_secret and self._refresh_token):
                raise ZohoAuthError("Zoho OAuth credentials are not configured")
            try:
                resp = await self._http.post(
                    f"{self._accounts_url}/oauth/v2/token",
                    data={"grant_type": "refresh_token", "refresh_token": self._refresh_token,
                          "client_id": self._client_id, "client_secret": self._client_secret},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise ZohoTransientError(f"token endpoint unreachable: {type(exc).__name__}") from exc
            if resp.status_code >= 500 or resp.status_code == 429:
                raise ZohoTransientError(f"token endpoint HTTP {resp.status_code}")
            try:
                body = resp.json()
            except ValueError:
                raise ZohoAuthError(f"token endpoint returned non-JSON (HTTP {resp.status_code})")
            if resp.status_code != 200 or "access_token" not in body:
                # Zoho reports errors as 200 {"error": "invalid_code"} as well as 4xx
                raise ZohoAuthError(f"token refresh rejected: {body.get('error', resp.status_code)}")
            self._token = body["access_token"]
            self._expires_at = self._clock() + float(body.get("expires_in", 3600))
            self.refresh_count += 1
            log.info("zoho access token refreshed")
            return self._token

    async def check(self) -> None:
        await self.get_token()


class ZohoLiveClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None, clock=time.monotonic):
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(settings.zoho_timeout_s, connect=5.0))
        self._base = f"{settings.zoho_api_domain.rstrip('/')}/crm/{API_VERSION}"
        self.tokens = TokenManager(settings.zoho_accounts_url, settings.zoho_client_id,
                                   settings.zoho_client_secret, settings.zoho_refresh_token, self._http, clock)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _request(self, method: str, path: str, *, params: dict | None = None, json: Any = None) -> Any:
        token = await self.tokens.get_token()
        for attempt in (1, 2):
            try:
                resp = await self._http.request(
                    method, f"{self._base}{path}", params=params, json=json,
                    headers={"Authorization": f"Zoho-oauthtoken {token}"},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise ZohoTransientError(f"{method} {path}: {type(exc).__name__}") from exc
            if resp.status_code == 401 and attempt == 1:
                token = await self.tokens.refresh(stale=token)
                continue
            break
        if resp.status_code == 401:
            raise ZohoAuthError("Zoho rejected the access token after refresh")
        if resp.status_code == 204:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ZohoTransientError(f"{method} {path}: HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            raise ZohoPermanentError(f"{method} {path}: non-JSON response (HTTP {resp.status_code})")
        if resp.status_code >= 400:
            raise ZohoPermanentError(f"{method} {path}: {body.get('message', resp.status_code)}",
                                     code=str(body.get("code", resp.status_code)))
        return body

    @staticmethod
    def _write_result(body: dict) -> str:
        item = (body.get("data") or [{}])[0]
        if item.get("code") != "SUCCESS":
            raise ZohoPermanentError(item.get("message", "write rejected"), code=item.get("code"),
                                     existing_id=(item.get("details") or {}).get("id"))
        return str(item["details"]["id"])

    async def search(self, module: str, criteria: str) -> list[Record]:
        body = await self._request("GET", f"/{module}/search", params={"criteria": criteria, "per_page": 10})
        return (body or {}).get("data", [])

    async def get(self, module: str, record_id: str) -> Record | None:
        try:
            body = await self._request("GET", f"/{module}/{record_id}",
                                       params={"fields": ",".join(FIELDS[module])})
        except ZohoPermanentError as exc:
            if exc.code in {"INVALID_DATA", "404", "INVALID_URL_PATTERN"}:
                return None
            raise
        data = (body or {}).get("data") or []
        return data[0] if data else None

    async def related(self, module: str, record_id: str, related_list: str) -> list[Record]:
        body = await self._request("GET", f"/{module}/{record_id}/{related_list}",
                                   params={"fields": ",".join(FIELDS[related_list])})
        return (body or {}).get("data", [])

    async def create(self, module: str, record: Record) -> str:
        body = await self._request("POST", f"/{module}", json={"data": [record], "trigger": []})
        return self._write_result(body)

    async def update(self, module: str, record_id: str, fields: Record) -> str:
        body = await self._request("PUT", f"/{module}/{record_id}", json={"data": [fields], "trigger": []})
        return self._write_result(body)

    async def list_fields(self, module: str) -> list[dict]:
        """Setup helper used by scripts/seed_zoho.py to verify custom fields exist."""
        body = await self._request("GET", "/settings/fields", params={"module": module})
        return (body or {}).get("fields", [])
