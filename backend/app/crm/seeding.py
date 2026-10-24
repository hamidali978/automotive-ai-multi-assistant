"""Idempotent seeding through any ZohoTransport (live or mock). Used by scripts/seed_zoho.py and tests."""
from dataclasses import dataclass

from app.crm.mapper import crit
from app.crm.seed_data import seed_specs
from app.crm.transport import ZohoTransport


@dataclass
class SeedResult:
    ref: str
    module: str
    record_id: str
    created: bool


async def apply_seed(transport: ZohoTransport) -> list[SeedResult]:
    ids: dict[str, str] = {}
    results: list[SeedResult] = []
    for spec in seed_specs():
        data = dict(spec["data"])
        if isinstance(data.get("Contact_Name"), str) and data["Contact_Name"].startswith("@"):
            data["Contact_Name"] = {"id": ids[data["Contact_Name"][1:]]}
        field, value = spec["key"]
        existing = await transport.search(spec["module"], crit(field, value))
        if existing:
            rid, created = str(existing[0]["id"]), False
        else:
            rid, created = await transport.create(spec["module"], data), True
        ids[spec["ref"]] = rid
        results.append(SeedResult(spec["ref"], spec["module"], rid, created))
    return results
