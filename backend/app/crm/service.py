"""CRM integration service: the ONLY component that talks to Zoho.

Responsibilities: retries with backoff, timeouts (in transport), idempotency, audit log, retry queue,
field mapping. Reads raise CRMUnavailable; writes fall back to the retry queue.
"""
import asyncio
import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.crm import mapper
from app.crm.errors import CRMUnavailable, ZohoAuthError, ZohoPermanentError, ZohoTransientError
from app.crm.transport import ZohoTransport
from app.models import AuditLog, RetryQueue

log = logging.getLogger(__name__)


@dataclass
class WriteOutcome:
    status: str  # created | existing | updated | queued | already_done | failed
    record_id: str | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "record_id": self.record_id, "message": self.message}


def idempotency_key(session_id: str, action: str, payload: dict) -> str:
    raw = json.dumps([session_id, action, payload], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


class CRMService:
    def __init__(self, transport: ZohoTransport, sessionmaker: async_sessionmaker[AsyncSession],
                 settings: Settings, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self.t = transport
        self._sm = sessionmaker
        self.s = settings
        self._sleep = sleep

    # ------------------------------------------------------------------ plumbing
    async def _audit(self, *, session_id, action, module, status, record_id=None, key=None,
                     fields=None, started: float | None = None, error: str | None = None) -> None:
        try:
            async with self._sm() as db:
                db.add(AuditLog(session_id=session_id, action=action, module=module, status=status,
                                record_id=record_id, idempotency_key=key,
                                field_names=sorted(fields) if fields else None,
                                duration_ms=int((time.monotonic() - started) * 1000) if started else 0,
                                error=(error or None) and error[:500]))
                await db.commit()
        except Exception:  # auditing must never break the request path
            log.exception("audit log write failed")

    async def _call(self, fn: Callable[..., Awaitable[Any]], *args) -> Any:
        """Retry transient failures with exponential backoff + jitter; map exhaustion to CRMUnavailable."""
        attempts = self.s.zoho_max_retries + 1
        last: Exception | None = None
        for i in range(attempts):
            try:
                return await fn(*args)
            except ZohoTransientError as exc:
                last = exc
                if i < attempts - 1:
                    delay = self.s.zoho_retry_base_s * (2 ** i)
                    await self._sleep(delay + random.uniform(0, delay * 0.25))
            except ZohoAuthError as exc:
                raise CRMUnavailable(f"Zoho authentication failed: {exc}") from exc
        raise CRMUnavailable(f"Zoho unavailable after {attempts} attempts: {last}")

    async def _read(self, session_id: str | None, action: str, module: str, fn, *args) -> Any:
        started = time.monotonic()
        try:
            result = await self._call(fn, *args)
        except CRMUnavailable as exc:
            await self._audit(session_id=session_id, action=action, module=module, status="error",
                              started=started, error=str(exc))
            raise
        rid = result["id"] if isinstance(result, dict) and "id" in result else None
        await self._audit(session_id=session_id, action=action, module=module, status="success",
                          record_id=rid, started=started)
        return result

    # ------------------------------------------------------------------ reads
    async def find_contact_by_phone(self, phone: str, session_id: str | None = None) -> dict | None:
        recs = await self._read(session_id, "search", "Contacts", self.t.search, "Contacts",
                                mapper.crit("Phone", phone))
        return mapper.contact_view(recs[0]) if recs else None

    async def get_contact(self, contact_id: str, session_id: str | None = None) -> dict | None:
        rec = await self._read(session_id, "get", "Contacts", self.t.get, "Contacts", contact_id)
        return mapper.contact_view(rec) if rec else None

    async def get_deal(self, deal_id: str, session_id: str | None = None) -> dict | None:
        rec = await self._read(session_id, "get", "Deals", self.t.get, "Deals", deal_id)
        return mapper.deal_view(rec) if rec else None

    async def find_booking(self, booking_id: str, session_id: str | None = None) -> dict | None:
        recs = await self._read(session_id, "search", "Deals", self.t.search, "Deals",
                                mapper.crit("Booking_ID", booking_id.strip().upper()))
        return mapper.deal_view(recs[0]) if recs else None

    async def contact_deals(self, contact_id: str, session_id: str | None = None) -> list[dict]:
        recs = await self._read(session_id, "related", "Deals", self.t.related, "Contacts", contact_id, "Deals")
        return [mapper.deal_view(r) for r in recs]

    async def lead_exists(self, phone: str, session_id: str | None = None) -> dict | None:
        recs = await self._read(session_id, "search", "Leads", self.t.search, "Leads", mapper.crit("Phone", phone))
        return {"id": str(recs[0]["id"])} if recs else None

    # ------------------------------------------------------------------ writes
    async def create_lead(self, session_id: str, draft: dict) -> WriteOutcome:
        return await self._write(session_id, "create_lead", "Leads", {"draft": draft},
                                 sorted(["Last_Name", "Phone", "Email", "City", "Vehicle_Model"]))

    async def update_followup(self, session_id: str, deal_id: str, preference: str) -> WriteOutcome:
        return await self._write(session_id, "update_followup", "Deals",
                                 {"deal_id": deal_id, "preference": preference}, ["Follow_Up_Preference"])

    async def create_case(self, session_id: str, contact_id: str, draft: dict) -> WriteOutcome:
        return await self._write(session_id, "create_case", self.s.zoho_cases_module,
                                 {"contact_id": contact_id, "draft": draft},
                                 ["Subject", "Related_To", "Registration_Number", "Odometer_KM", "Service_Center"])

    async def _dispatch(self, action: str, payload: dict, session_id: str | None, key: str) -> WriteOutcome:
        if action == "create_lead":
            draft = payload["draft"]
            existing = await self._call(self.t.search, "Leads", mapper.crit("Phone", draft["phone"]))
            if existing:  # dedupe by phone
                return WriteOutcome("existing", str(existing[0]["id"]))
            rec = mapper.lead_to_zoho(draft, session_id or "", self.s.zoho_lead_source)
            try:
                return WriteOutcome("created", await self._call(self.t.create, "Leads", rec))
            except ZohoPermanentError as exc:
                if exc.code == "DUPLICATE_DATA" and exc.existing_id:
                    return WriteOutcome("existing", exc.existing_id)
                raise
        if action == "update_followup":
            rid = await self._call(self.t.update, "Deals", payload["deal_id"],
                                   mapper.followup_to_zoho(payload["preference"]))
            return WriteOutcome("updated", rid)
        if action == "create_case":
            module = self.s.zoho_cases_module
            existing = await self._call(self.t.search, module, mapper.crit("Chat_Ref", key))
            if existing:  # replay after a crash between Zoho commit and audit write
                return WriteOutcome("already_done", str(existing[0]["id"]))
            rec = mapper.case_to_zoho(payload["contact_id"], payload["draft"], session_id or "", key)
            return WriteOutcome("created", await self._call(self.t.create, module, rec))
        raise ValueError(f"unknown write action {action}")

    async def _write(self, session_id: str, action: str, module: str, payload: dict, fields: list[str]) -> WriteOutcome:
        key = idempotency_key(session_id, action, payload)
        async with self._sm() as db:
            done = (await db.execute(select(AuditLog).where(AuditLog.idempotency_key == key,
                                                            AuditLog.status == "success"))).scalars().first()
            if done:
                return WriteOutcome("already_done", done.record_id)
            queued = (await db.execute(select(RetryQueue).where(RetryQueue.idempotency_key == key,
                                                                RetryQueue.status == "pending"))).scalars().first()
            if queued:
                return WriteOutcome("queued", None, "This request is already queued and will be synced shortly.")
        started = time.monotonic()
        try:
            outcome = await self._dispatch(action, payload, session_id, key)
        except CRMUnavailable as exc:
            await self._enqueue(session_id, key, action, payload)
            await self._audit(session_id=session_id, action=action, module=module, status="queued", key=key,
                              fields=fields, started=started, error=str(exc))
            return WriteOutcome("queued", None, "CRM is temporarily unreachable; the request was queued for retry.")
        except ZohoPermanentError as exc:
            await self._audit(session_id=session_id, action=action, module=module, status="failed", key=key,
                              fields=fields, started=started, error=f"{exc.code}: {exc}")
            return WriteOutcome("failed", None, "The CRM rejected the request.")
        await self._audit(session_id=session_id, action=action, module=module, status="success",
                          record_id=outcome.record_id, key=key, fields=fields, started=started)
        return outcome

    # ------------------------------------------------------------------ retry queue
    async def _enqueue(self, session_id: str, key: str, action: str, payload: dict) -> None:
        async with self._sm() as db:
            if (await db.execute(select(RetryQueue).where(RetryQueue.idempotency_key == key))).scalars().first():
                return
            db.add(RetryQueue(idempotency_key=key, session_id=session_id, action=action, payload=payload,
                              next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=self.s.queue_poll_s)))
            await db.commit()

    async def queue_depth(self) -> int:
        async with self._sm() as db:
            rows = (await db.execute(select(RetryQueue.id).where(RetryQueue.status == "pending"))).all()
            return len(rows)

    async def process_queue(self, force: bool = False) -> dict[str, int]:
        """Replay due writes. `force` ignores next_attempt_at (used by tests and on startup)."""
        stats = {"done": 0, "retry": 0, "dead": 0}
        now = datetime.now(timezone.utc)
        async with self._sm() as db:
            items = (await db.execute(select(RetryQueue).where(RetryQueue.status == "pending")
                                      .order_by(RetryQueue.id))).scalars().all()
        for item in items:
            nxt = item.next_attempt_at if item.next_attempt_at.tzinfo else item.next_attempt_at.replace(tzinfo=timezone.utc)
            if not force and nxt > now:
                continue
            started = time.monotonic()
            module = {"create_lead": "Leads", "update_followup": "Deals"}.get(item.action, self.s.zoho_cases_module)
            try:
                outcome = await self._dispatch(item.action, item.payload, item.session_id, item.idempotency_key)
                new_status, err = "done", None
            except CRMUnavailable as exc:
                outcome, err = None, str(exc)
                new_status = "dead" if item.attempts + 1 >= self.s.queue_max_attempts else "pending"
            except ZohoPermanentError as exc:
                outcome, err, new_status = None, f"{exc.code}: {exc}", "dead"
            async with self._sm() as db:
                row = await db.get(RetryQueue, item.id)
                row.attempts += 1
                row.status = new_status
                row.last_error = err[:500] if err else None
                if new_status == "pending":
                    row.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(900, 30 * 2 ** row.attempts))
                if new_status == "done":
                    row.payload = {}  # drop business data as soon as Zoho has it
                await db.commit()
            await self._audit(session_id=item.session_id, action=f"{item.action}(queued)", module=module,
                              status="success" if outcome else ("failed" if new_status == "dead" else "queued"),
                              record_id=outcome.record_id if outcome else None,
                              key=item.idempotency_key if outcome else None, started=started, error=err)
            stats["done" if new_status == "done" else "dead" if new_status == "dead" else "retry"] += 1
        return stats
