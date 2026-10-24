import pytest
from sqlalchemy import select

from app.crm.errors import CRMUnavailable
from app.crm.seed_data import PRIYA_PHONE
from app.models import AuditLog, RetryQueue

DRAFT = {"full_name": "Neha Kulkarni", "phone": "+919811122233", "email": "neha@example.com",
         "city": "Mumbai", "vehicle_model": "Thar"}


async def test_read_retries_then_succeeds_on_transient_blip(crm, zoho):
    zoho.fail_next = 2  # max_retries=2 -> 3 attempts, third succeeds
    contact = await crm.find_contact_by_phone(PRIYA_PHONE)
    assert contact["full_name"] == "Priya Patel"


async def test_read_raises_unavailable_when_zoho_down(crm, zoho):
    zoho.down = True
    with pytest.raises(CRMUnavailable):
        await crm.find_contact_by_phone(PRIYA_PHONE)
    assert len([c for c in zoho.calls if c[0] == "search"]) == 3  # initial + 2 retries


async def test_write_is_queued_when_zoho_down_then_replayed_once(crm, zoho, sm):
    zoho.down = True
    out = await crm.create_lead("s1", DRAFT)
    assert out.status == "queued" and out.record_id is None
    assert await crm.queue_depth() == 1
    # same request again must not double-queue
    again = await crm.create_lead("s1", DRAFT)
    assert again.status == "queued" and await crm.queue_depth() == 1

    async with sm() as db:
        audit = (await db.execute(select(AuditLog).where(AuditLog.status == "queued"))).scalars().all()
        assert len(audit) == 1
        assert "+919811122233" not in str(audit[0].__dict__)  # no values in audit log

    # still down: stays pending
    stats = await crm.process_queue(force=True)
    assert stats["retry"] == 1 and await crm.queue_depth() == 1

    zoho.down = False
    stats = await crm.process_queue(force=True)
    assert stats["done"] == 1 and await crm.queue_depth() == 0
    leads = [r for r in zoho.store["Leads"].values() if r.get("Phone") == DRAFT["phone"]]
    assert len(leads) == 1  # exactly one lead created

    async with sm() as db:
        row = (await db.execute(select(RetryQueue))).scalars().one()
        assert row.status == "done" and row.payload == {}  # business data dropped after sync


async def test_queue_marks_dead_after_max_attempts(crm, zoho, sm, settings):
    settings.queue_max_attempts = 2
    zoho.down = True
    await crm.create_lead("s2", DRAFT)
    await crm.process_queue(force=True)
    stats = await crm.process_queue(force=True)
    assert stats["dead"] == 1 and await crm.queue_depth() == 0


async def test_idempotent_replay_returns_same_record(crm, zoho):
    a = await crm.create_lead("s3", DRAFT)
    b = await crm.create_lead("s3", DRAFT)
    assert a.status == "created" and b.status == "already_done" and a.record_id == b.record_id
    assert len([r for r in zoho.store["Leads"].values() if r.get("Phone") == DRAFT["phone"]]) == 1


async def test_lead_dedupe_by_phone_across_sessions(crm, zoho):
    first = await crm.create_lead("sA", DRAFT)
    second = await crm.create_lead("sB", {**DRAFT, "full_name": "Neha K"})
    assert second.status == "existing" and second.record_id == first.record_id


async def test_permanent_rejection_is_not_queued(crm, zoho, sm):
    from app.crm.errors import ZohoPermanentError

    async def reject(module, record):
        raise ZohoPermanentError("bad field", code="INVALID_DATA")

    zoho.create = reject
    out = await crm.create_lead("s4", DRAFT)
    assert out.status == "failed"
    assert await crm.queue_depth() == 0
    async with sm() as db:
        row = (await db.execute(select(AuditLog).where(AuditLog.status == "failed"))).scalars().one()
        assert "INVALID_DATA" in row.error
