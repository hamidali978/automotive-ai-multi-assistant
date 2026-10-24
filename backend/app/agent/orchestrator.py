"""Agent orchestrator: LLM tool-calling loop, session state, SSE event stream."""
import asyncio
import copy
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.guardrails import clean_user_text, injection_suspected, mask_args
from app.agent.llm import LLMError, TextDelta, ToolCallsEvent
from app.agent.prompts import build_system_prompt
from app.agent.state import new_state, public_state
from app.agent.tools import TOOLS, ToolContext, execute_tool, tool_schemas
from app.config import Settings
from app.crm.service import CRMService
from app.models import ChatMessage, ChatSession

log = logging.getLogger(__name__)
FALLBACK_TEXT = ("I'm sorry, I could not complete that just now. Please try again in a moment, or contact your "
                 "nearest Mahindra dealer for immediate help.")


def _ev(event: str, **data: Any) -> dict:
    return {"event": event, "data": data}


class Orchestrator:
    def __init__(self, llm: Any, crm: CRMService, sm: async_sessionmaker[AsyncSession], settings: Settings):
        self.llm, self.crm, self.sm, self.s = llm, crm, sm, settings
        self._locks: dict[str, asyncio.Lock] = {}

    # ---------------------------------------------------------------- sessions
    async def create_session(self) -> str:
        sid = str(uuid.uuid4())
        async with self.sm() as db:
            db.add(ChatSession(id=sid, stage="general", state=new_state()))
            await db.commit()
        return sid

    async def get_session(self, sid: str) -> dict | None:
        async with self.sm() as db:
            sess = await db.get(ChatSession, sid)
            if not sess:
                return None
            msgs = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == sid)
                                     .order_by(ChatMessage.id))).scalars().all()
            return {"session_id": sid, "state": public_state(sess.stage, sess.state),
                    "messages": [{"role": m.role, "content": m.content, "tool_trace": m.tool_trace} for m in msgs]}

    # ---------------------------------------------------------------- turn
    async def run_turn(self, session_id: str | None, user_text: str) -> AsyncIterator[dict]:
        if not session_id or not await self.get_session(session_id):
            session_id = await self.create_session()
        yield _ev("session", session_id=session_id)
        text = clean_user_text(user_text)
        if not text:
            yield _ev("error", message="Please type a message.")
            return
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            async for ev in self._turn_locked(session_id, text):
                yield ev

    async def _turn_locked(self, sid: str, text: str) -> AsyncIterator[dict]:
        async with self.sm() as db:
            sess = await db.get(ChatSession, sid)
            state, stage = copy.deepcopy(sess.state), sess.stage
            state["turn"] = state.get("turn", 0) + 1
            db.add(ChatMessage(session_id=sid, role="user", content=text))
            await db.commit()
            hist = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == sid)
                                     .order_by(ChatMessage.id.desc()).limit(self.s.history_messages))).scalars().all()
        history = [{"role": m.role, "content": m.content} for m in reversed(hist) if m.content]
        injection = injection_suspected(text)
        if injection:
            yield _ev("security", message="Instruction-like text detected in the user message; rules unchanged.")

        ctx = ToolContext(crm=self.crm, session_id=sid, state=state)
        schemas = tool_schemas()
        answer, trace, error = "", [], None
        try:
            for round_no in range(1, self.s.max_tool_rounds + 1):
                messages = [{"role": "system", "content": build_system_prompt(stage, state, injection)}, *history]
                round_text, calls = "", []
                async for ev in self.llm.stream(messages, schemas):
                    if isinstance(ev, TextDelta):
                        round_text += ev.text
                        yield _ev("token", text=ev.text)
                    elif isinstance(ev, ToolCallsEvent):
                        calls = ev.calls
                if not calls:
                    answer += round_text
                    break
                answer += round_text
                history.append({"role": "assistant", "content": round_text,
                                "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments, "extra": c.extra}
                                               for c in calls]})
                for c in calls:
                    t0 = time.monotonic()
                    ctx.stage_override = None
                    result = await execute_tool(ctx, c.name, c.arguments)
                    ms = int((time.monotonic() - t0) * 1000)
                    tool = TOOLS.get(c.name)
                    new_stage = ctx.stage_override or (tool.stage if tool else None)
                    if new_stage and "error" not in result and new_stage != stage:
                        stage = new_stage
                    try:
                        parsed = json.loads(c.arguments) if c.arguments else {}
                    except ValueError:
                        parsed = {"_raw": c.arguments[:200]}
                    margs = mask_args(parsed) if isinstance(parsed, dict) else {}
                    ok = "error" not in result
                    trace.append({"name": c.name, "args": margs, "ok": ok, "ms": ms})
                    yield _ev("tool_call", id=c.id, name=c.name, args=margs, ok=ok, ms=ms, round=round_no,
                              result=result)
                    yield _ev("state", **public_state(stage, state))
                    history.append({"role": "tool", "tool_call_id": c.id, "name": c.name,
                                    "content": json.dumps(result, default=str)})
            else:
                error = "tool_round_limit"
        except LLMError as exc:
            log.error("LLM failure: %s", exc)
            error = str(exc)
        except Exception:
            log.exception("turn crashed")
            error = "internal_error"

        if not answer.strip():
            answer = FALLBACK_TEXT
            yield _ev("token", text=answer)
        if error:
            yield _ev("error", message="The assistant had trouble completing this request.", detail=error)

        async with self.sm() as db:
            sess = await db.get(ChatSession, sid)
            sess.state, sess.stage = state, stage
            db.add(ChatMessage(session_id=sid, role="assistant", content=answer.strip(), tool_trace=trace or None))
            await db.commit()
        yield _ev("state", **public_state(stage, state))
        yield _ev("done", session_id=sid)
