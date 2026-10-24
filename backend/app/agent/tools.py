"""Typed tools. The LLM's choice of tool IS the intent routing; each tool maps to a lifecycle stage.

Security rules enforced here in code (not just in the prompt):
  * identity must be verified (two factors) before any CRM data is returned;
  * every write needs a confirmation prompt on an earlier turn plus user_confirmed=true;
  * the vehicle catalog is the only source for specs/prices.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from app.agent.guardrails import clean_user_text
from app.agent.state import MAX_VERIFY_ATTEMPTS, args_hash
from app.catalog import catalog
from app.crm.errors import CRMUnavailable
from app.crm.mapper import STAGE_BOOKED, digits, normalize_phone
from app.crm.service import CRMService

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
REG_RE = re.compile(r"^([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{1,2})$")


@dataclass
class ToolContext:
    crm: CRMService
    session_id: str
    state: dict
    stage_override: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    model: type[BaseModel]
    handler: Callable[[ToolContext, Any], Awaitable[dict]]
    stage: str | None
    writes: bool = False


# ------------------------------------------------------------------ argument models
class NoArgs(BaseModel):
    pass


class VehicleInfoArgs(BaseModel):
    model: str = Field(description="Vehicle model name, e.g. XUV700, Thar, Scorpio-N")
    variant: str | None = Field(default=None, description="Optional variant name or fragment, e.g. AX7, Z8L")


class LeadDetailsArgs(BaseModel):
    full_name: str | None = Field(default=None, description="Customer's full name (first and last)")
    phone: str | None = Field(default=None, description="10-digit Indian mobile number")
    email: str | None = None
    city: str | None = Field(default=None, description="Preferred city for dealer / test drive")
    vehicle_model: str | None = Field(default=None, description="Model the customer is interested in")
    test_drive: bool | None = Field(default=None, description="True if the customer asked for a test drive")


class ConfirmArgs(BaseModel):
    user_confirmed: bool = Field(default=False, description=(
        "True ONLY if the customer's latest message explicitly says yes to the summary you showed. "
        "Otherwise false."))


class VerifyArgs(BaseModel):
    lookup_type: Literal["phone", "deal_id", "booking_id"]
    lookup_value: str = Field(description="The phone number, Deal ID, or Booking ID the customer gave")
    challenge_answer: str | None = Field(default=None, description=(
        "Second factor. For phone lookups: the customer's full name as registered. "
        "For deal_id/booking_id lookups: the last 4 digits of the registered phone number."))


class DealArgs(BaseModel):
    deal_id: str | None = Field(default=None, description="Only if the customer has several deals and chose one")


class FollowupArgs(ConfirmArgs):
    preference: str = Field(description="Follow-up preference in the customer's words (channel and/or time window)")
    deal_id: str | None = None


class BookingArgs(BaseModel):
    booking_id: str | None = Field(default=None, description="Booking ID such as MAH-9921, if the customer has several")


class ServiceDetailsArgs(BaseModel):
    registration_number: str | None = Field(default=None, description="Vehicle registration, e.g. MH12AB1234")
    odometer_km: int | None = Field(default=None, description="Current odometer reading in km")
    issue: str | None = Field(default=None, description="Reported issue, or the service type being requested")
    service_center: str | None = Field(default=None, description="Preferred service center / location")
    request_type: Literal["periodic_service", "complaint", "other"] | None = None


# ------------------------------------------------------------------ helpers
def fmt_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).strftime("%d %b %Y")
        return datetime.fromisoformat(value).astimezone(IST).strftime("%a, %d %b %Y, %I:%M %p IST")
    except ValueError:
        return value


def _names_match(a: str, b: str) -> bool:
    ta = set(re.findall(r"[a-z]+", a.lower()))
    tb = set(re.findall(r"[a-z]+", b.lower()))
    return bool(ta) and ta == tb


def _last4_ok(phone: str | None, answer: str) -> bool:
    ad, pd = digits(answer), digits(phone or "")
    return len(ad) >= 4 and len(pd) >= 4 and pd.endswith(ad[-4:]) and (len(ad) == 4 or pd[-10:] == ad[-10:])


def _confirm_gate(ctx: ToolContext, tool: str, payload: Any, user_confirmed: bool, summary: str) -> dict | None:
    """Return a confirmation_required result unless the customer confirmed on a LATER turn."""
    h = args_hash(tool, payload)
    p = ctx.state.get("pending")
    if user_confirmed and p and p["tool"] == tool and p["hash"] == h and p["turn"] < ctx.state["turn"]:
        ctx.state["pending"] = None
        return None
    if not (p and p["tool"] == tool and p["hash"] == h):
        ctx.state["pending"] = {"tool": tool, "hash": h, "turn": ctx.state["turn"]}
    return {"status": "confirmation_required", "summary": summary,
            "instruction": "Show this summary to the customer and ask them to reply 'yes' to confirm. "
                           "Do not call this tool again until they have replied."}


def _verified_ids(ctx: ToolContext) -> list[str]:
    return list(ctx.state.get("verified", {}).get("contact_ids", []))


NOT_VERIFIED = {"error": "identity_not_verified",
                "instruction": "Ask the customer for their phone number, Deal ID or Booking ID, then call verify_identity."}


async def _resolve_deal(ctx: ToolContext, deal_id: str | None, want_booking: bool) -> dict:
    """Return {"deal": view} or an error/choice dict. Enforces that the deal belongs to a verified contact."""
    ids = _verified_ids(ctx)
    if not ids:
        return NOT_VERIFIED
    if deal_id:
        deal = await (ctx.crm.find_booking(deal_id, ctx.session_id) if want_booking and not deal_id.isdigit()
                      else ctx.crm.get_deal(deal_id.strip(), ctx.session_id))
        if not deal or deal["contact"]["id"] not in ids:
            return {"error": "not_found_or_not_authorized"}
        return {"deal": deal}
    deals = []
    for cid in ids:
        deals += await ctx.crm.contact_deals(cid, ctx.session_id)
    is_booked = lambda d: bool(d.get("booking_id")) or d.get("stage") == STAGE_BOOKED  # noqa: E731
    deals = [d for d in deals if is_booked(d) == want_booking]
    if not deals:
        return {"status": "not_found", "message": "No matching record on this customer's account."}
    if len(deals) > 1:
        return {"status": "multiple_found", "choices": [{"id": d["id"], "name": d["name"], "booking_id": d["booking_id"]}
                                                       for d in deals], "instruction": "Ask which one they mean."}
    return {"deal": deals[0]}


# ------------------------------------------------------------------ handlers
async def h_list_vehicles(ctx: ToolContext, a: NoArgs) -> dict:
    return {"models": catalog.list_models(), "disclaimer": catalog.disclaimer()}


async def h_vehicle_info(ctx: ToolContext, a: VehicleInfoArgs) -> dict:
    info = catalog.get_info(a.model, a.variant)
    if info is None:
        return {"error": "model_not_in_catalog", "available_models": [m["name"] for m in catalog.list_models()],
                "instruction": "Do not guess specs or prices for unlisted models."}
    return info


async def h_save_lead(ctx: ToolContext, a: LeadDetailsArgs) -> dict:
    draft, errors = ctx.state["lead_draft"], {}
    if a.full_name is not None:
        n = " ".join(clean_user_text(a.full_name).split())
        if len(n) >= 2 and re.fullmatch(r"[A-Za-z][A-Za-z .'\-]+", n):
            draft["full_name"] = n.title() if n.islower() else n
        else:
            errors["full_name"] = "needs a valid name"
    if a.phone is not None:
        p = normalize_phone(a.phone)
        if p:
            draft["phone"] = p
        else:
            errors["phone"] = "not a valid 10-digit Indian mobile number"
    if a.email is not None:
        e = a.email.strip().lower()
        if EMAIL_RE.match(e):
            draft["email"] = e
        else:
            errors["email"] = "not a valid email address"
    if a.city is not None:
        c = clean_user_text(a.city)
        if 2 <= len(c) <= 60:
            draft["city"] = c.title() if c.islower() else c
        else:
            errors["city"] = "needs a valid city"
    if a.vehicle_model is not None:
        m = catalog.find_model(a.vehicle_model)
        if m:
            draft["vehicle_model"] = m["name"]
        else:
            errors["vehicle_model"] = "not in catalog: " + ", ".join(x["name"] for x in catalog.list_models())
    if a.test_drive is not None:
        draft["test_drive"] = a.test_drive
    missing = [f for f in ("full_name", "phone", "email", "city", "vehicle_model") if not draft.get(f)]
    return {"draft": draft, "missing": missing, "errors": errors,
            "next": "Ask for the missing fields one or two at a time." if missing else
                    "All fields collected: call create_lead to show the confirmation summary."}


async def h_create_lead(ctx: ToolContext, a: ConfirmArgs) -> dict:
    draft = ctx.state["lead_draft"]
    missing = [f for f in ("full_name", "phone", "email", "city", "vehicle_model") if not draft.get(f)]
    if missing:
        return {"status": "incomplete", "missing": missing}
    summary = (f"Name: {draft['full_name']}; Phone: {draft['phone']}; Email: {draft['email']}; "
               f"City: {draft['city']}; Interested in: {draft['vehicle_model']}"
               + ("; Test drive requested" if draft.get("test_drive") else ""))
    gate = _confirm_gate(ctx, "create_lead", draft, a.user_confirmed, summary)
    if gate:
        return gate
    out = await ctx.crm.create_lead(ctx.session_id, draft)
    if out.status in ("created", "existing", "already_done"):
        ctx.state["completed"].append(f"lead:{out.record_id}")
        ctx.state["lead_draft"] = {}
    elif out.status == "queued":
        ctx.state["lead_draft"] = {}
    return {**out.as_dict(), "reference": (out.record_id or "")[-6:] or None,
            "note": {"created": "New enquiry registered. A representative will contact the customer.",
                     "existing": "An enquiry with this phone number already exists; no duplicate was created. "
                                 "Tell the customer the team already has their details.",
                     "already_done": "Already registered earlier in this chat.",
                     "queued": "CRM was unreachable. The enquiry is saved safely and will sync automatically. "
                               "Tell the customer honestly it is not yet in the CRM and no reference exists yet.",
                     "failed": "CRM rejected the enquiry. Apologise and offer the dealer helpline."}[out.status]}


async def h_verify(ctx: ToolContext, a: VerifyArgs) -> dict:
    if ctx.state["verify_failures"] >= MAX_VERIFY_ATTEMPTS:
        return {"status": "locked", "instruction": "Too many failed attempts. Do not retry; offer the dealer helpline."}
    if not a.challenge_answer:
        what = "the full name registered on the account" if a.lookup_type == "phone" else \
               "the last 4 digits of the phone number registered on the account"
        return {"status": "challenge_required", "ask_for": what}
    value, contact = a.lookup_value.strip(), None
    ok = False
    if a.lookup_type == "phone":
        phone = normalize_phone(value)
        if not phone:
            return {"status": "invalid_input", "message": "That does not look like a valid 10-digit mobile number."}
        contact = await ctx.crm.find_contact_by_phone(phone, ctx.session_id)
        ok = bool(contact) and _names_match(contact["full_name"], a.challenge_answer)
    else:
        deal = None
        if a.lookup_type == "deal_id":
            if re.fullmatch(r"\d{10,22}", value):
                deal = await ctx.crm.get_deal(value, ctx.session_id)
        else:
            deal = await ctx.crm.find_booking(value.lstrip("#"), ctx.session_id)
        if deal and deal["contact"]["id"]:
            contact = await ctx.crm.get_contact(deal["contact"]["id"], ctx.session_id)
            ok = bool(contact) and _last4_ok(contact["phone"], a.challenge_answer)
    if not ok:
        ctx.state["verify_failures"] += 1
        left = MAX_VERIFY_ATTEMPTS - ctx.state["verify_failures"]
        return {"status": "verification_failed", "attempts_left": left,
                "message": "Details did not match our records. Do not say which part was wrong."}
    ids = ctx.state["verified"]["contact_ids"]
    if contact["id"] not in ids:
        ids.append(contact["id"])
    if a.lookup_type == "booking_id":
        ctx.stage_override = "booked_vehicle"
    elif a.lookup_type == "deal_id":
        ctx.stage_override = "ongoing_pipeline"
    deals = await ctx.crm.contact_deals(contact["id"], ctx.session_id)
    return {"status": "verified", "customer_first_name": contact["full_name"].split()[0],
            "records": [{"id": d["id"], "name": d["name"], "is_booking": bool(d["booking_id"])} for d in deals]}


async def h_deal_status(ctx: ToolContext, a: DealArgs) -> dict:
    r = await _resolve_deal(ctx, a.deal_id, want_booking=False)
    if "deal" not in r:
        return r
    d = r["deal"]
    return {"deal_id": d["id"], "name": d["name"], "stage": d["stage"], "vehicle_model": d["vehicle_model"],
            "variant": d["variant"], "test_drive": fmt_dt(d["test_drive_datetime"]),
            "quotation_amount_inr": d["quotation_amount_inr"], "quotation_ref": d["quotation_ref"],
            "dealer_name": d["dealer_name"], "dealer_phone": d["dealer_phone"],
            "follow_up_preference": d["follow_up_preference"],
            "note": "null means the CRM has no value. Say it is not available; never guess."}


async def h_update_followup(ctx: ToolContext, a: FollowupArgs) -> dict:
    pref = clean_user_text(a.preference)[:300]
    if len(pref) < 3:
        return {"error": "preference_too_short"}
    r = await _resolve_deal(ctx, a.deal_id, want_booking=False)
    if "deal" not in r:
        return r
    d = r["deal"]
    gate = _confirm_gate(ctx, "update_followup", {"deal": d["id"], "pref": pref}, a.user_confirmed,
                         f"Update follow-up preference for '{d['name']}' to: \"{pref}\"")
    if gate:
        return gate
    out = await ctx.crm.update_followup(ctx.session_id, d["id"], pref)
    if out.status in ("updated", "already_done"):
        ctx.state["completed"].append(f"followup:{d['id']}")
    return {**out.as_dict(), "note": "If queued, say the preference is saved but not yet in the CRM." if
            out.status == "queued" else None}


async def h_booking_status(ctx: ToolContext, a: BookingArgs) -> dict:
    r = await _resolve_deal(ctx, a.booking_id, want_booking=True)
    if "deal" not in r:
        return r
    d = r["deal"]
    return {"booking_id": d["booking_id"], "vehicle_model": d["vehicle_model"], "variant": d["variant"],
            "delivery_stage": d["delivery_stage"], "vin": d["vin"],
            "expected_delivery": fmt_dt(d["expected_delivery_date"]), "balance_amount_inr": d["balance_amount_inr"],
            "payment_link": d["payment_link"], "dealer_name": d["dealer_name"], "dealer_phone": d["dealer_phone"],
            "note": "null means the CRM has no value (e.g. VIN not allocated yet). Say so; never guess."}


async def h_save_service(ctx: ToolContext, a: ServiceDetailsArgs) -> dict:
    draft, errors = ctx.state["service_draft"], {}
    if a.registration_number is not None:
        reg = re.sub(r"[^A-Za-z0-9]", "", a.registration_number).upper()
        if REG_RE.match(reg):
            draft["registration_number"] = reg
        else:
            errors["registration_number"] = "expected format like MH12AB1234"
    if a.odometer_km is not None:
        if 0 <= a.odometer_km <= 999_999:
            draft["odometer_km"] = a.odometer_km
        else:
            errors["odometer_km"] = "must be between 0 and 999999 km"
    if a.issue is not None:
        t = clean_user_text(a.issue)
        if 3 <= len(t):
            draft["issue"] = t[:1000]
        else:
            errors["issue"] = "please describe the issue or service needed"
    if a.service_center is not None:
        t = clean_user_text(a.service_center)
        if 2 <= len(t) <= 120:
            draft["service_center"] = t
        else:
            errors["service_center"] = "needs a service center or city"
    if a.request_type:
        draft["service_type"] = {"periodic_service": "Periodic maintenance", "complaint": "Complaint",
                                 "other": "Service request"}[a.request_type]
    missing = [f for f in ("registration_number", "odometer_km", "issue", "service_center") if f not in draft]
    return {"draft": draft, "missing": missing, "errors": errors,
            "identity_verified": bool(_verified_ids(ctx)),
            "next": "Collect missing fields; verify identity if not verified; then call create_service_case."}


async def h_create_case(ctx: ToolContext, a: ConfirmArgs) -> dict:
    ids = _verified_ids(ctx)
    if not ids:
        return NOT_VERIFIED
    draft = ctx.state["service_draft"]
    missing = [f for f in ("registration_number", "odometer_km", "issue", "service_center") if f not in draft]
    if missing:
        return {"status": "incomplete", "missing": missing}
    contact_id = ids[-1]
    summary = (f"Registration: {draft['registration_number']}; Odometer: {draft['odometer_km']} km; "
               f"Request: {draft.get('service_type', 'Service request')} - {draft['issue']}; "
               f"Service center: {draft['service_center']}")
    gate = _confirm_gate(ctx, "create_service_case", {"c": contact_id, "d": draft}, a.user_confirmed, summary)
    if gate:
        return gate
    out = await ctx.crm.create_case(ctx.session_id, contact_id, draft)
    if out.status in ("created", "already_done"):
        ctx.state["completed"].append(f"case:{out.record_id}")
        ctx.state["service_draft"] = {}
    elif out.status == "queued":
        ctx.state["service_draft"] = {}
    return {**out.as_dict(), "case_reference": (out.record_id or "")[-6:] or None,
            "note": "If queued: the request is saved safely but NOT yet in the CRM; no case reference exists yet."
            if out.status == "queued" else None}


# ------------------------------------------------------------------ registry
TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("list_vehicles", "List the Mahindra models in the catalog with starting prices. Use for general "
         "'what do you have' questions.", NoArgs, h_list_vehicles, "new_lead"),
    Tool("get_vehicle_info", "Get specs, features and variant prices for one model (and optionally a variant) from the "
         "official catalog. The ONLY source for specs and prices.", VehicleInfoArgs, h_vehicle_info, "new_lead"),
    Tool("save_lead_details", "Record details a prospective customer has shared (name, phone, email, city, model of "
         "interest, test drive). Call whenever the user provides any of them; it validates and reports what is missing.",
         LeadDetailsArgs, h_save_lead, "new_lead"),
    Tool("create_lead", "Register the collected prospect in the CRM. First call returns a summary to confirm; call again "
         "with user_confirmed=true only after the customer says yes.", ConfirmArgs, h_create_lead, "new_lead", True),
    Tool("verify_identity", "Verify a returning customer before sharing ANY account data. Needs a phone, Deal ID or "
         "Booking ID plus a second factor (name for phone; last 4 phone digits for IDs).", VerifyArgs, h_verify, None),
    Tool("get_deal_status", "Read an existing prospect's active deal: stage, test drive time, quotation, dealer contact, "
         "follow-up preference. Requires verified identity.", DealArgs, h_deal_status, "ongoing_pipeline"),
    Tool("update_followup", "Update how/when the customer wants to be followed up on their deal. Needs verified identity; "
         "first call returns a summary to confirm.", FollowupArgs, h_update_followup, "ongoing_pipeline", True),
    Tool("get_booking_status", "Read a booked vehicle's delivery stage, VIN, expected delivery and balance payment. "
         "Requires verified identity.", BookingArgs, h_booking_status, "booked_vehicle"),
    Tool("save_service_details", "Record service/complaint details from an existing owner: registration number, odometer "
         "(km), issue or service type, preferred service center. Validates and reports what is missing.",
         ServiceDetailsArgs, h_save_service, "service"),
    Tool("create_service_case", "Create a service Case in the CRM linked to the verified customer. First call returns a "
         "summary to confirm; call again with user_confirmed=true only after the customer says yes.",
         ConfirmArgs, h_create_case, "service", True),
]}


def _clean_schema(node: Any) -> Any:
    """Flatten pydantic JSON schema into the simple subset both Groq and Gemini accept."""
    if isinstance(node, dict):
        if "anyOf" in node:
            non_null = [x for x in node["anyOf"] if x.get("type") != "null"]
            merged = {k: v for k, v in node.items() if k != "anyOf"}
            return _clean_schema({**merged, **(non_null[0] if non_null else {"type": "string"})})
        return {k: _clean_schema(v) for k, v in node.items() if k not in ("title", "default")}
    if isinstance(node, list):
        return [_clean_schema(x) for x in node]
    return node


def tool_schemas() -> list[dict]:
    out = []
    for t in TOOLS.values():
        schema = _clean_schema(t.model.model_json_schema())
        schema.setdefault("properties", {})
        out.append({"name": t.name, "description": t.description, "parameters": schema})
    return out


async def execute_tool(ctx: ToolContext, name: str, raw_args: Any) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": "unknown_tool", "available": list(TOOLS)}
    try:
        data = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})
        args = tool.model.model_validate(data)
    except (ValidationError, ValueError, TypeError) as exc:
        detail = [e["loc"][0] for e in exc.errors()] if isinstance(exc, ValidationError) else str(exc)[:100]
        return {"error": "invalid_arguments", "fields": detail}
    try:
        return await tool.handler(ctx, args)
    except CRMUnavailable:
        return {"error": "crm_unavailable",
                "instruction": "The CRM is temporarily unreachable. Tell the customer honestly, do not guess any "
                               "account details, and offer to try again shortly or to use the dealer helpline."}
    except Exception:
        log.exception("tool %s crashed", name)
        return {"error": "internal_error", "instruction": "Apologise briefly and ask the customer to try again."}
