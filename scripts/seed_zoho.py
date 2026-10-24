#!/usr/bin/env python
"""Seed Zoho CRM with the assessment's mock data (idempotent).

  Lead     Rajesh Sharma  - interested in Thar
  Deal     Priya Patel    - XUV700 test drive scheduled (+ Contact)
  Booking  MAH-9921       - Scorpio-N Z8L (Deal in stage 'Closed Won - Booking Done', + Contact Anita Desai)

Usage:  python scripts/seed_zoho.py [--check-only] [--force] [--mock]
Reads credentials from backend/.env (ZOHO_MODE must be 'live' unless --mock is passed).
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.crm.errors import CRMError, ZohoPermanentError  # noqa: E402
from app.crm.seeding import apply_seed  # noqa: E402
from app.crm.zoho_live import ZohoLiveClient  # noqa: E402
from app.crm.zoho_mock import ZohoMockClient  # noqa: E402

REQUIRED_FIELDS = {
    "Leads": ["Vehicle_Model", "Chat_Session_ID"],
    "Deals": ["Vehicle_Model", "Variant", "Test_Drive_DateTime", "Quotation_Amount", "Quotation_Ref", "Dealer_Name",
              "Dealer_Phone", "Follow_Up_Preference", "Booking_ID", "Delivery_Stage", "VIN",
              "Expected_Delivery_Date", "Balance_Amount", "Payment_Link"],
    "Cases": ["Registration_Number", "Odometer_KM", "Service_Center", "Chat_Ref"],
}
REQUIRED_PICKLIST_VALUES = {("Deals", "Stage"): ["Test Drive Scheduled", "Closed Won - Booking Done"]}


async def check_fields(client: ZohoLiveClient, cases_module: str) -> list[str]:
    problems: list[str] = []
    for module, names in REQUIRED_FIELDS.items():
        real = cases_module if module == "Cases" else module
        try:
            fields = {f["api_name"]: f for f in await client.list_fields(real)}
        except ZohoPermanentError as exc:
            problems.append(f"{real}: cannot read field list ({exc.code}: {exc}). "
                            + ("Enable/create the Cases module." if module == "Cases" else ""))
            continue
        for n in names:
            if n not in fields:
                problems.append(f"{real}.{n} is missing")
        for (m, fname), wanted in REQUIRED_PICKLIST_VALUES.items():
            if m == module and fname in fields:
                have = {v.get("display_value") for v in fields[fname].get("pick_list_values", [])}
                problems += [f"{real}.{fname} picklist lacks value '{w}'" for w in wanted if w not in have]
    return problems


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="only verify custom fields, create nothing")
    ap.add_argument("--force", action="store_true", help="seed even if the field check reports problems")
    ap.add_argument("--mock", action="store_true", help="dry run against the in-memory mock")
    args = ap.parse_args()
    s = get_settings()

    if args.mock:
        client = ZohoMockClient(seed=False)
    else:
        if s.zoho_mode != "live":
            print("ZOHO_MODE is not 'live' in backend/.env. Set it (and the Zoho credentials) or pass --mock.")
            return 2
        client = ZohoLiveClient(s)
        try:
            await client.tokens.check()
        except CRMError as exc:
            print(f"Could not obtain a Zoho access token: {exc}\nCheck ZOHO_CLIENT_ID/SECRET/REFRESH_TOKEN and the data-centre URLs.")
            return 2
        problems = await check_fields(client, s.zoho_cases_module)
        if problems:
            print("Zoho setup problems:\n  - " + "\n  - ".join(problems))
            print("See README 'Custom Zoho fields to create'.")
            if not args.force or args.check_only:
                await client.aclose()
                return 1
        elif args.check_only:
            print("Field check passed.")
    if args.check_only:
        return 0
    try:
        results = await apply_seed(client)
    except ZohoPermanentError as exc:
        print(f"Zoho rejected a seed record: {exc.code}: {exc}\nUsually a missing custom field or picklist value.")
        return 1
    finally:
        await client.aclose()
    for r in results:
        print(f"{'created' if r.created else 'exists '}  {r.module:<9} {r.ref:<13} id={r.record_id}")
    print("\nSeed complete. Try in chat: phone +91 98200 11002 (name Priya Patel) or Booking ID MAH-9921 (last 4 digits 2003).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
