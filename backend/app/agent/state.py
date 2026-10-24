"""Session state kept in Postgres: drafts + verified record IDs + pending confirmation. No CRM data."""
import hashlib
import json
from typing import Any

MAX_VERIFY_ATTEMPTS = 3

STAGE_LABELS = {
    "general": "Welcome",
    "new_lead": "New Lead",
    "ongoing_pipeline": "Ongoing Pipeline",
    "booked_vehicle": "Booked Vehicle",
    "service": "Post-Purchase / Service",
}


def new_state() -> dict[str, Any]:
    return {
        "turn": 0,                     # number of user messages so far
        "lead_draft": {},
        "service_draft": {},
        "verified": {"contact_ids": []},   # IDs only
        "verify_failures": 0,
        "pending": None,               # {"tool": str, "hash": str, "turn": int}
        "completed": [],               # e.g. ["lead:<id>", "followup:<id>", "case:<id>"]
    }


def args_hash(tool: str, payload: Any) -> str:
    return hashlib.sha256(json.dumps([tool, payload], sort_keys=True, default=str).encode()).hexdigest()[:16]


def public_state(stage: str, st: dict) -> dict:
    """Sanitised snapshot for the debug drawer."""
    lead = st.get("lead_draft", {})
    svc = st.get("service_draft", {})
    return {
        "stage": stage, "stage_label": STAGE_LABELS.get(stage, stage), "turn": st.get("turn", 0),
        "identity_verified": bool(st.get("verified", {}).get("contact_ids")),
        "verify_failures": st.get("verify_failures", 0),
        "lead_draft_fields": sorted(k for k, v in lead.items() if v),
        "service_draft_fields": sorted(k for k, v in svc.items() if v),
        "pending_confirmation": (st.get("pending") or {}).get("tool"),
        "completed": st.get("completed", []),
    }
