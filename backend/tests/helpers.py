import json

from app.agent.llm import TextDelta, ToolCall, ToolCallsEvent


def T(name: str, **args):
    return (name, args)


def step(*calls, text: str = ""):
    """One LLM round that calls tools."""
    return (text, list(calls))


class ScriptedLLM:
    """Deterministic LLM stand-in: each stream() call consumes one scripted step."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.seen: list[list[dict]] = []

    async def stream(self, messages, tools):
        self.seen.append(messages)
        assert self.steps, "ScriptedLLM ran out of steps (agent looped more than the test expected)"
        s = self.steps.pop(0)
        if isinstance(s, str):
            yield TextDelta(s)
            return
        text, calls = s
        if text:
            yield TextDelta(text)
        yield ToolCallsEvent([ToolCall(f"call_{i}", n, json.dumps(a)) for i, (n, a) in enumerate(calls)])


async def chat(agent, sid, text, steps):
    """Run one user turn with scripted LLM steps; returns (session_id, reply_text, tool_calls, events)."""
    agent.llm = ScriptedLLM(steps)
    events = [e async for e in agent.run_turn(sid, text)]
    sid = events[0]["data"]["session_id"]
    reply = "".join(e["data"]["text"] for e in events if e["event"] == "token")
    calls = [e["data"] for e in events if e["event"] == "tool_call"]
    assert not agent.llm.steps, f"unused scripted steps: {agent.llm.steps}"
    return sid, reply, calls, events


def last_state(events):
    return [e["data"] for e in events if e["event"] == "state"][-1]
