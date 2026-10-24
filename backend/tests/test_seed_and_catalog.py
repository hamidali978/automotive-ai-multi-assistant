from app.catalog import catalog
from app.crm.seed_data import ANITA_PHONE, BOOKING_ID, PRIYA_PHONE, RAJESH_PHONE
from app.crm.seeding import apply_seed
from app.crm.zoho_mock import ZohoMockClient


async def test_seed_is_idempotent_and_links_deals_to_contacts():
    z = ZohoMockClient(seed=False)
    first = await apply_seed(z)
    assert all(r.created for r in first) and len(first) == 5
    second = await apply_seed(z)
    assert not any(r.created for r in second)
    assert {r.record_id for r in first} == {r.record_id for r in second}
    assert len(z.store["Leads"]) == 1 and len(z.store["Deals"]) == 2 and len(z.store["Contacts"]) == 2
    priya = [c for c in z.store["Contacts"].values() if c["Phone"] == PRIYA_PHONE][0]
    deals = await z.related("Contacts", priya["id"], "Deals")
    assert [d["Vehicle_Model"] for d in deals] == ["XUV700"]
    booking = (await z.search("Deals", f"(Booking_ID:equals:{BOOKING_ID})"))[0]
    assert booking["Stage"] == "Closed Won - Booking Done" and booking["Variant"] == "Z8L"
    lead = (await z.search("Leads", f"(Phone:equals:{RAJESH_PHONE})"))[0]
    assert lead["Vehicle_Model"] == "Thar"
    assert ANITA_PHONE  # seeded contact exists


def test_catalog_lookup_is_fuzzy_and_complete():
    assert catalog.find_model("scorpio n")["name"] == "Scorpio-N"
    assert catalog.find_model("Mahindra XUV 700 please")["name"] == "XUV700"
    assert catalog.get_info("Scorpio-N", "z8l")["variants"][0]["name"] == "Z8L Diesel AT"
    assert catalog.get_info("Thar", "nonexistent")["error"] == "variant_not_found"
    assert catalog.find_model("Bolero") is None
    assert {m["name"] for m in catalog.list_models()} == {"XUV700", "Thar", "Scorpio-N"}
