import asyncio

import httpx
import pytest

from app.config import Settings
from app.crm.errors import ZohoAuthError, ZohoPermanentError, ZohoTransientError
from app.crm.zoho_live import TokenManager, ZohoLiveClient


def settings() -> Settings:
    return Settings(zoho_mode="live", zoho_client_id="cid", zoho_client_secret="sec", zoho_refresh_token="rt",
                    zoho_accounts_url="https://accounts.test", zoho_api_domain="https://api.test", _env_file=None)


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def make(handler, clock=None):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ZohoLiveClient(settings(), http=http, clock=clock or Clock()), http


async def test_refresh_sends_oauth_form_and_caches_token():
    seen = []

    def handler(req: httpx.Request):
        if req.url.path == "/oauth/v2/token":
            seen.append(dict(httpx.QueryParams(req.content.decode())))
            return httpx.Response(200, json={"access_token": "tok1", "expires_in": 3600})
        assert req.headers["Authorization"] == "Zoho-oauthtoken tok1"
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    client, _ = make(handler)
    await client.search("Leads", "(Phone:equals:+911)")
    await client.search("Leads", "(Phone:equals:+912)")
    assert client.tokens.refresh_count == 1  # cached
    assert seen[0] == {"grant_type": "refresh_token", "refresh_token": "rt", "client_id": "cid", "client_secret": "sec"}


async def test_refreshes_when_token_expires():
    clock = Clock()
    n = {"c": 0}

    def handler(req):
        if req.url.path == "/oauth/v2/token":
            n["c"] += 1
            return httpx.Response(200, json={"access_token": f"tok{n['c']}", "expires_in": 3600})
        return httpx.Response(200, json={"data": []})

    client, _ = make(handler, clock)
    await client.search("Leads", "(Phone:equals:1)")
    clock.t += 3600  # past expiry (minus skew)
    await client.search("Leads", "(Phone:equals:1)")
    assert client.tokens.refresh_count == 2


async def test_concurrent_callers_trigger_single_refresh():
    n = {"c": 0}

    async def slow_handler(req):
        return None

    def handler(req):
        if req.url.path == "/oauth/v2/token":
            n["c"] += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx.Response(200, json={"data": []})

    client, _ = make(handler)
    await asyncio.gather(*[client.search("Leads", "(Phone:equals:1)") for _ in range(10)])
    assert n["c"] == 1


async def test_401_forces_refresh_and_retries_once():
    state = {"tokens": 0, "api": 0}

    def handler(req):
        if req.url.path == "/oauth/v2/token":
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok{state['tokens']}", "expires_in": 3600})
        state["api"] += 1
        if req.headers["Authorization"].endswith("tok1"):
            return httpx.Response(401, json={"code": "INVALID_TOKEN"})
        return httpx.Response(200, json={"data": [{"id": "9", "Last_Name": "X"}]})

    client, _ = make(handler)
    recs = await client.search("Leads", "(Phone:equals:1)")
    assert recs[0]["id"] == "9" and state == {"tokens": 2, "api": 2}


async def test_persistent_401_raises_auth_error():
    def handler(req):
        if req.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(401, json={})

    client, _ = make(handler)
    with pytest.raises(ZohoAuthError):
        await client.search("Leads", "(Phone:equals:1)")


async def test_invalid_refresh_token_error_body_in_200():
    client, _ = make(lambda req: httpx.Response(200, json={"error": "invalid_code"}))
    with pytest.raises(ZohoAuthError, match="invalid_code"):
        await client.tokens.get_token()


async def test_token_endpoint_5xx_is_transient():
    client, _ = make(lambda req: httpx.Response(503))
    with pytest.raises(ZohoTransientError):
        await client.tokens.get_token()


async def test_missing_credentials():
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    tm = TokenManager("https://a", "", "", "", http)
    with pytest.raises(ZohoAuthError):
        await tm.get_token()


async def test_live_api_mapping_204_429_and_write_errors():
    def handler(req):
        if req.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        p = req.url.path
        if p.endswith("/Leads/search"):
            return httpx.Response(204)
        if p.endswith("/Deals/search"):
            return httpx.Response(429)
        if req.method == "POST" and p.endswith("/Leads"):
            return httpx.Response(202, json={"data": [{"code": "SUCCESS", "details": {"id": "77"}}]})
        if req.method == "POST" and p.endswith("/Cases"):
            return httpx.Response(202, json={"data": [{"code": "DUPLICATE_DATA", "message": "dup", "details": {"id": "5"}}]})
        if req.method == "GET" and p.endswith("/Deals/123"):
            return httpx.Response(400, json={"code": "INVALID_DATA", "message": "bad id"})
        return httpx.Response(500)

    client, _ = make(handler)
    assert await client.search("Leads", "(Phone:equals:1)") == []
    with pytest.raises(ZohoTransientError):
        await client.search("Deals", "(x:equals:1)")
    assert await client.create("Leads", {"Last_Name": "A"}) == "77"
    with pytest.raises(ZohoPermanentError) as ei:
        await client.create("Cases", {})
    assert ei.value.code == "DUPLICATE_DATA" and ei.value.existing_id == "5"
    assert await client.get("Deals", "123") is None


async def test_timeout_is_transient():
    def handler(req):
        if req.url.path == "/oauth/v2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        raise httpx.ReadTimeout("slow", request=req)

    client, _ = make(handler)
    with pytest.raises(ZohoTransientError):
        await client.search("Leads", "(Phone:equals:1)")
