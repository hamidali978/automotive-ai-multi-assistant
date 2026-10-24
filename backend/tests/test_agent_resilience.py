import json

import httpx
import pytest
from sqlalchemy import select

from app.agent.llm import LLMError, LLMRouter, TextDelta, ToolCall, ToolCallsEvent
from app.agent.orchestrator import FALLBACK_TEXT
from app.crm.seed_data import PRIYA_PHONE
from app.main import create_app
from app.models import AuditLog, RetryQueue
from tests.helpers import ScriptedLLM, T, chat, step
from tests.test_workflows import NEW


# ------------------------------------------------------------------ Zoho-down through the agent
async def test_zoho_down_lead_is_queued_and_user_told_honestly(agent, zoho, sm):
    sid, *_ = await chat(agent, None, "x", [step(T("save_lead_details", **NEW)), step(T("create_lead")), "confirm?"])
    zoho.down = True
    _, _, calls, ev = await chat(agent, sid, "yes", [step(T("create_lead", user_confirmed=True)), "Saved, not yet in CRM."])
    r = calls[0]["result"]
    assert r["status"] == "queued" and r["reference"] is None and "not yet in the CRM" in r["note"]
    assert not any(l["Phone"] == "+919811122233" for l in zoho.store["Leads"].values())
    async with sm() as db:
        assert len((await db.execute(select(RetryQueue).where(RetryQueue.status == "pending"))).scalars().all()) == 1
        assert (await db.execute(select(AuditLog).where(AuditLog.status == "queued"))).scalars().first()
    # LLM saw the honest tool result and the turn completed without error events
    assert not any(e["event"] == "error" for e in ev)

    zoho.down = False  # Zoho recovers -> background worker would replay; do it explicitly
    assert (await agent.crm.process_queue(force=True))["done"] == 1
    assert any(l["Phone"] == "+919811122233" for l in zoho.store["Leads"].values())


async def test_zoho_down_read_returns_crm_unavailable_and_no_data_leaks(agent, zoho):
    zoho.down = True
    _, _, calls, _ = await chat(agent, None, "x", [
        step(T("verify_identity", lookup_type="phone", lookup_value=PRIYA_PHONE, challenge_answer="Priya Patel")),
        "I'm unable to reach our systems right now."])
    assert calls[0]["result"]["error"] == "crm_unavailable" and "Priya" not in json.dumps(calls[0]["result"])
    zoho.down = False
    # nothing was marked verified while down
    _, _, calls, _ = await chat(agent, None, "x", [step(T("get_deal_status")), "verify first"])
    assert calls[0]["result"]["error"] == "identity_not_verified"


async def test_zoho_down_case_creation_is_queued_without_duplicates(agent, zoho):
    sid, *_ = await chat(agent, None, "x", [
        step(T("verify_identity", lookup_type="phone", lookup_value=PRIYA_PHONE, challenge_answer="Priya Patel")), "hi"])
    sid, *_ = await chat(agent, sid, "details", [
        step(T("save_service_details", registration_number="MH01AB1111", odometer_km=900, issue="Periodic service",
               service_center="Worli", request_type="periodic_service")), step(T("create_service_case")), "confirm?"])
    zoho.down = True
    _, _, calls, _ = await chat(agent, sid, "yes", [step(T("create_service_case", user_confirmed=True)), "queued"])
    assert calls[0]["result"]["status"] == "queued" and calls[0]["result"]["case_reference"] is None
    zoho.down = False
    await agent.crm.process_queue(force=True)
    await agent.crm.process_queue(force=True)
    assert len(zoho.store["Cases"]) == 1


# ------------------------------------------------------------------ LLM fallback
class Boom:
    def __init__(self, name, exc, emit_first=False):
        self.name, self.exc, self.emit_first, self.calls = name, exc, emit_first, 0

    async def stream(self, messages, tools):
        self.calls += 1
        if self.emit_first:
            yield TextDelta("partial ")
        raise self.exc


class Ok:
    name = "gemini"

    async def stream(self, messages, tools):
        yield TextDelta("from gemini")
        yield ToolCallsEvent([ToolCall("1", "list_vehicles", "{}")])


async def collect(router):
    return [e async for e in router.stream([{"role": "user", "content": "hi"}], [])]


async def test_router_falls_back_to_gemini_when_groq_fails():
    groq = Boom("groq", RuntimeError("429 rate limit"))
    evs = await collect(LLMRouter([groq, Ok()]))
    assert isinstance(evs[0], TextDelta) and evs[0].text == "from gemini" and groq.calls == 1  # 429: no pointless retry


async def test_router_retries_groq_once_on_tool_use_failed_then_falls_back():
    groq = Boom("groq", RuntimeError("Error 400 tool_use_failed"))
    evs = await collect(LLMRouter([groq, Ok()]))
    assert groq.calls == 2 and evs[0].text == "from gemini"


async def test_router_does_not_stitch_after_partial_output():
    with pytest.raises(LLMError, match="dropped"):
        await collect(LLMRouter([Boom("groq", RuntimeError("conn reset"), emit_first=True), Ok()]))


async def test_router_all_providers_failed_and_none_configured():
    with pytest.raises(LLMError):
        await collect(LLMRouter([Boom("groq", RuntimeError("x")), Boom("gemini", RuntimeError("y"))]))
    with pytest.raises(LLMError, match="No LLM provider"):
        await collect(LLMRouter([]))


async def test_agent_survives_total_llm_outage(agent, sm):
    agent.llm = LLMRouter([Boom("groq", RuntimeError("down")), Boom("gemini", RuntimeError("down"))])
    events = [e async for e in agent.run_turn(None, "Hello")]
    assert any(e["event"] == "error" for e in events)
    assert "".join(e["data"]["text"] for e in events if e["event"] == "token") == FALLBACK_TEXT
    assert events[-1]["event"] == "done"


async def test_tool_loop_is_bounded(agent, settings):
    settings.max_tool_rounds = 3
    agent.llm = ScriptedLLM([step(T("list_vehicles"))] * 3)
    events = [e async for e in agent.run_turn(None, "loop")]
    assert [e["event"] for e in events].count("tool_call") == 3
    assert any(e["event"] == "error" and e["data"]["detail"] == "tool_round_limit" for e in events)


# ------------------------------------------------------------------ HTTP API (SSE + health)
@pytest.fixture
async def client(sm, settings, zoho):
    llm = ScriptedLLM([])
    app = create_app(settings, transport=zoho, llm=llm)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            c.llm = llm
            yield c


def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines() if ": " in l)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


async def test_health_endpoint(client):
    r = await client.get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok" and body["db"] == "ok"
    assert body["zoho_mode"] == "mock" and body["retry_queue_depth"] == 0


async def test_sse_chat_stream_session_history_and_state(client):
    client.llm.steps = [step(T("get_vehicle_info", model="Thar")), "The Thar LX 4x4 is a great choice."]
    r = await client.post("/api/chat/stream", json={"message": "Tell me about the Thar"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "session" and names[-1] == "done" and "tool_call" in names and "token" in names
    sid = events[0][1]["session_id"]
    h = await client.get(f"/api/sessions/{sid}")
    body = h.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"] and body["state"]["stage"] == "new_lead"
    assert (await client.get("/api/sessions/nope")).status_code == 404


async def test_api_validation_and_new_session_endpoint(client):
    assert (await client.post("/api/chat/stream", json={"message": ""})).status_code == 422
    assert (await client.post("/api/sessions")).json()["session_id"]
    client.llm.steps = ["hello"]
    r = await client.post("/api/chat/stream", json={"session_id": "unknown-id", "message": "hi"})
    assert parse_sse(r.text)[0][1]["session_id"] != "unknown-id"  # unknown ids are replaced, never trusted
