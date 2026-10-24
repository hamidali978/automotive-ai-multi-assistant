"""In-memory Zoho stand-in used for ZOHO_MODE=mock, tests and the offline demo."""
import asyncio
import itertools
import re

from app.crm.errors import ZohoPermanentError, ZohoTransientError
from app.crm.seed_data import seed_records
from app.crm.transport import Record

_COND = re.compile(r"\(([\w.]+):equals:((?:\\.|[^)\\])*)\)")


class ZohoMockClient:
    def __init__(self, seed: bool = True):
        self.store: dict[str, dict[str, Record]] = {}
        self._ids = itertools.count(5000000000000001000)
        self.calls: list[tuple[str, str]] = []
        self.down = False          # simulate a full Zoho outage
        self.fail_next = 0         # fail the next N calls with a transient error
        self.latency_s = 0.0
        if seed:
            self.load_seed()

    def load_seed(self) -> None:
        for module, rec in seed_records(lambda m: self._new_id(m)):
            self.store.setdefault(module, {})[rec["id"]] = rec

    def _new_id(self, module: str) -> str:
        return str(next(self._ids))

    async def _gate(self, op: str, module: str) -> None:
        self.calls.append((op, module))
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        if self.down:
            raise ZohoTransientError("mock Zoho is down")
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ZohoTransientError("mock transient failure")

    async def aclose(self) -> None:
        return None

    async def search(self, module: str, criteria: str) -> list[Record]:
        await self._gate("search", module)
        conds = [(f, re.sub(r"\\(.)", r"\1", v)) for f, v in _COND.findall(criteria)]
        use_or = " or " in criteria
        out = []
        for rec in self.store.get(module, {}).values():
            hits = [str(rec.get(f)) == v for f, v in conds]
            if hits and (any(hits) if use_or else all(hits)):
                out.append(dict(rec))
        return out

    async def get(self, module: str, record_id: str) -> Record | None:
        await self._gate("get", module)
        rec = self.store.get(module, {}).get(record_id)
        return dict(rec) if rec else None

    async def related(self, module: str, record_id: str, related_list: str) -> list[Record]:
        await self._gate("related", module)
        if module == "Contacts" and related_list == "Deals":
            return [dict(r) for r in self.store.get("Deals", {}).values()
                    if (r.get("Contact_Name") or {}).get("id") == record_id]
        return []

    async def create(self, module: str, record: Record) -> str:
        await self._gate("create", module)
        if module in ("Leads", "Contacts") and not record.get("Last_Name"):
            raise ZohoPermanentError("Last_Name is required", code="MANDATORY_NOT_FOUND")
        rid = self._new_id(module)
        self.store.setdefault(module, {})[rid] = {**record, "id": rid}
        return rid

    async def update(self, module: str, record_id: str, fields: Record) -> str:
        await self._gate("update", module)
        rec = self.store.get(module, {}).get(record_id)
        if rec is None:
            raise ZohoPermanentError("record not found", code="INVALID_DATA")
        rec.update(fields)
        return record_id
