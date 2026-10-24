"""Seed definitions shared by the mock client and scripts/seed_zoho.py (live)."""
from datetime import datetime, timedelta, timezone
from typing import Callable

IST = timezone(timedelta(hours=5, minutes=30))

PRIYA_PHONE = "+919820011002"
ANITA_PHONE = "+919833022003"
RAJESH_PHONE = "+919810055001"
BOOKING_ID = "MAH-9921"


def _ist(days: int, hour: int) -> datetime:
    d = datetime.now(IST) + timedelta(days=days)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def seed_specs() -> list[dict]:
    """Ordered specs: key is the natural lookup (module, field, value) used to keep seeding idempotent."""
    td = _ist(3, 11).isoformat(timespec="seconds")
    eta = _ist(9, 0).date().isoformat()
    return [
        {"ref": "priya", "module": "Contacts", "key": ("Phone", PRIYA_PHONE),
         "data": {"First_Name": "Priya", "Last_Name": "Patel", "Phone": PRIYA_PHONE, "Email": "priya.patel@example.com"}},
        {"ref": "anita", "module": "Contacts", "key": ("Phone", ANITA_PHONE),
         "data": {"First_Name": "Anita", "Last_Name": "Desai", "Phone": ANITA_PHONE, "Email": "anita.desai@example.com"}},
        {"ref": "rajesh", "module": "Leads", "key": ("Phone", RAJESH_PHONE),
         "data": {"First_Name": "Rajesh", "Last_Name": "Sharma", "Phone": RAJESH_PHONE, "Email": "rajesh.sharma@example.com",
                  "City": "Pune", "Vehicle_Model": "Thar", "Lead_Source": "Web Research"}},
        {"ref": "deal_priya", "module": "Deals", "key": ("Deal_Name", "Priya Patel - XUV700 Test Drive"),
         "data": {"Deal_Name": "Priya Patel - XUV700 Test Drive", "Stage": "Test Drive Scheduled",
                  "Contact_Name": "@priya", "Vehicle_Model": "XUV700", "Variant": "AX7 Diesel AT",
                  "Test_Drive_DateTime": td, "Quotation_Amount": 2349000, "Quotation_Ref": "QT-2026-0457",
                  "Dealer_Name": "Mahindra Sample Motors, Mumbai", "Dealer_Phone": "+912225550123",
                  "Follow_Up_Preference": "Call after 6 PM"}},
        {"ref": "deal_booking", "module": "Deals", "key": ("Booking_ID", BOOKING_ID),
         "data": {"Deal_Name": "Anita Desai - Scorpio-N Z8L Booking", "Stage": "Closed Won - Booking Done",
                  "Contact_Name": "@anita", "Vehicle_Model": "Scorpio-N", "Variant": "Z8L",
                  "Booking_ID": BOOKING_ID, "Delivery_Stage": "In Transit", "VIN": "MA1ZZ8L0000MAH992",
                  "Expected_Delivery_Date": eta, "Balance_Amount": 1650000,
                  "Dealer_Name": "Mahindra Sample Motors, Mumbai", "Dealer_Phone": "+912225550123"}},
    ]


def seed_records(new_id: Callable[[str], str]) -> list[tuple[str, dict]]:
    """Materialise specs with IDs for the in-memory mock."""
    ids: dict[str, str] = {}
    out = []
    for spec in seed_specs():
        rid = new_id(spec["module"])
        ids[spec["ref"]] = rid
        data = dict(spec["data"])
        if data.get("Contact_Name", "").startswith("@"):
            cref = data["Contact_Name"][1:]
            first = next(s for s in seed_specs() if s["ref"] == cref)["data"]
            data["Contact_Name"] = {"id": ids[cref], "name": f"{first['First_Name']} {first['Last_Name']}"}
        out.append((spec["module"], {**data, "id": rid}))
    return out
