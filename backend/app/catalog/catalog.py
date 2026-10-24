"""Local vehicle catalog: the ONLY source for specs and prices."""
import json
import re
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("vehicles.json")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache
def _data() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))


def disclaimer() -> str:
    return _data()["disclaimer"]


def list_models() -> list[dict]:
    return [{"name": m["name"], "segment": m["segment"], "variant_count": len(m["variants"]),
             "starting_ex_showroom_inr": min(v["ex_showroom_inr"] for v in m["variants"])} for m in _data()["models"]]


def find_model(query: str) -> dict | None:
    q = _norm(query)
    for m in _data()["models"]:
        if _norm(m["name"]) == q or _norm(m["name"]) in q:
            return m
    return None


def get_info(model: str, variant: str | None = None) -> dict | None:
    m = find_model(model)
    if not m:
        return None
    variants = m["variants"]
    if variant:
        v = _norm(variant)
        variants = [x for x in variants if v in _norm(x["name"])] or []
        if not variants:
            return {"model": m["name"], "error": "variant_not_found",
                    "available_variants": [x["name"] for x in m["variants"]]}
    return {"model": m["name"], "segment": m["segment"], "seating": m["seating"], "highlights": m["highlights"],
            "variants": variants, "currency": "INR", "disclaimer": disclaimer()}
