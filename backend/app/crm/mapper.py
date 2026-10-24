"""Field mapper: the only place that knows Zoho API field names. Business shapes <-> Zoho records."""
import re
from typing import Any

# Fields requested on GET (Zoho API v6 requires an explicit `fields` list).
FIELDS: dict[str, list[str]] = {
    "Contacts": ["id", "First_Name", "Last_Name", "Full_Name", "Phone", "Mobile", "Email"],
    "Leads": ["id", "First_Name", "Last_Name", "Phone", "Email", "City", "Vehicle_Model"],
    "Deals": ["id", "Deal_Name", "Stage", "Contact_Name", "Vehicle_Model", "Variant", "Test_Drive_DateTime",
              "Quotation_Amount", "Quotation_Ref", "Dealer_Name", "Dealer_Phone", "Follow_Up_Preference",
              "Booking_ID", "Delivery_Stage", "VIN", "Expected_Delivery_Date", "Balance_Amount", "Payment_Link"],
}

STAGE_BOOKED = "Closed Won - Booking Done"


def digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_phone(raw: str) -> str | None:
    """Indian mobile numbers -> +91XXXXXXXXXX. Returns None when it does not look like one."""
    d = digits(raw)
    if len(d) == 12 and d.startswith("91"):
        d = d[2:]
    elif len(d) == 11 and d.startswith("0"):
        d = d[1:]
    if len(d) == 10 and d[0] in "6789":
        return f"+91{d}"
    return None


def esc(value: str) -> str:
    """Escape characters that are special inside a Zoho search criteria value."""
    return re.sub(r"([\\(),])", r"\\\1", value)


def crit(field: str, value: str) -> str:
    return f"({field}:equals:{esc(value)})"


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    return (" ".join(parts[:-1]), parts[-1]) if len(parts) > 1 else ("", parts[0])


# ---- outbound (business -> Zoho) -------------------------------------------------------------
def lead_to_zoho(draft: dict[str, Any], session_id: str, lead_source: str) -> dict[str, Any]:
    first, last = split_name(draft["full_name"])
    rec = {
        "Last_Name": last, "Phone": draft["phone"], "Email": draft["email"], "City": draft["city"],
        "Lead_Source": lead_source, "Vehicle_Model": draft["vehicle_model"], "Chat_Session_ID": session_id,
        "Description": f"Captured by the AI chat assistant. Interested in {draft['vehicle_model']}."
                       + (" Wants to book a test drive." if draft.get("test_drive") else ""),
    }
    if first:
        rec["First_Name"] = first
    return rec


def followup_to_zoho(preference: str) -> dict[str, Any]:
    return {"Follow_Up_Preference": preference}


def case_to_zoho(contact_id: str, draft: dict[str, Any], session_id: str, chat_ref: str) -> dict[str, Any]:
    service_type = draft.get("service_type") or "Service request"
    return {
        "Subject": f"{service_type} - {draft['registration_number']}",
        "Related_To": {"id": contact_id},
        "Status": "New", "Priority": "Medium", "Case_Origin": "Web",
        "Registration_Number": draft["registration_number"], "Odometer_KM": draft["odometer_km"],
        "Service_Center": draft["service_center"], "Chat_Ref": chat_ref,
        "Description": f"{draft['issue']}\n\n(Logged via AI chat assistant, session {session_id})",
    }


# ---- inbound (Zoho -> business views) --------------------------------------------------------
def _lookup(v: Any) -> dict[str, str | None]:
    return {"id": (v or {}).get("id"), "name": (v or {}).get("name")} if isinstance(v, dict) else {"id": None, "name": None}


def contact_view(r: dict[str, Any]) -> dict[str, Any]:
    name = r.get("Full_Name") or " ".join(x for x in (r.get("First_Name"), r.get("Last_Name")) if x)
    return {"id": str(r["id"]), "full_name": name, "phone": r.get("Phone") or r.get("Mobile")}


def deal_view(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["id"]), "name": r.get("Deal_Name"), "stage": r.get("Stage"),
        "contact": _lookup(r.get("Contact_Name")), "vehicle_model": r.get("Vehicle_Model"),
        "variant": r.get("Variant"), "test_drive_datetime": r.get("Test_Drive_DateTime"),
        "quotation_amount_inr": r.get("Quotation_Amount"), "quotation_ref": r.get("Quotation_Ref"),
        "dealer_name": r.get("Dealer_Name"), "dealer_phone": r.get("Dealer_Phone"),
        "follow_up_preference": r.get("Follow_Up_Preference"),
        "booking_id": r.get("Booking_ID"), "delivery_stage": r.get("Delivery_Stage"), "vin": r.get("VIN"),
        "expected_delivery_date": r.get("Expected_Delivery_Date"),
        "balance_amount_inr": r.get("Balance_Amount"), "payment_link": r.get("Payment_Link"),
    }
