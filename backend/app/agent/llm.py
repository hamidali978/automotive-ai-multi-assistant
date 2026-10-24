"""LLM providers (direct SDK tool calling, no LangChain) behind one streaming interface.

Internal message format (OpenAI-like):
  {"role": "system"|"user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments": <json str>, "extra": {}}]}
  {"role": "tool", "tool_call_id", "name", "content": <json str>}
"""
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

from app.config import Settings

log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string
    extra: dict = field(default_factory=dict)


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCallsEvent:
    calls: list[ToolCall]


LLMEvent = TextDelta | ToolCallsEvent


class LLMProvider(Protocol):
    name: str

    def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]: ...


# ------------------------------------------------------------------ Groq
class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str, client: Any = None):
        from groq import AsyncGroq
        self._client = client or AsyncGroq(api_key=api_key, timeout=30.0, max_retries=1)
        self._model = model

    @staticmethod
    def convert(messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in m["tool_calls"]]})
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return out

    async def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]:
        resp = await self._client.chat.completions.create(
            model=self._model, messages=self.convert(messages), stream=True, temperature=0.3, max_tokens=900,
            tools=[{"type": "function", "function": t} for t in tools], tool_choice="auto")
        acc: dict[int, dict] = {}
        async for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextDelta(delta.content)
            for tc in delta.tool_calls or []:
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments
        if acc:
            yield ToolCallsEvent([ToolCall(s["id"] or f"call_{uuid.uuid4().hex[:12]}", s["name"], s["arguments"] or "{}")
                                  for _, s in sorted(acc.items())])


# ------------------------------------------------------------------ Gemini
class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: Any = None):
        from google import genai
        self._client = client or genai.Client(api_key=api_key)
        self._model = model

    @staticmethod
    def convert(messages: list[dict]) -> tuple[str, list[Any]]:
        from google.genai import types
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents: list[Any] = []

        def push(role: str, parts: list[Any]) -> None:
            if contents and contents[-1].role == role:   # Gemini wants merged same-role turns
                contents[-1].parts.extend(parts)
            else:
                contents.append(types.Content(role=role, parts=parts))

        for m in messages:
            if m["role"] == "user":
                push("user", [types.Part(text=m["content"])])
            elif m["role"] == "assistant":
                parts = [types.Part(text=m["content"])] if m.get("content") else []
                for c in m.get("tool_calls") or []:
                    sig = c.get("extra", {}).get("thought_signature")
                    parts.append(types.Part(function_call=types.FunctionCall(name=c["name"], args=json.loads(c["arguments"] or "{}")),
                                            thought_signature=base64.b64decode(sig) if sig else None))
                if parts:
                    push("model", parts)
            elif m["role"] == "tool":
                push("user", [types.Part.from_function_response(name=m["name"], response={"result": json.loads(m["content"])})])
        return system, contents

    async def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]:
        from google.genai import types
        system, contents = self.convert(messages)
        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=0.3, max_output_tokens=900,
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in tools])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        calls: list[ToolCall] = []
        stream = await self._client.aio.models.generate_content_stream(model=self._model, contents=contents, config=cfg)
        async for chunk in stream:
            for cand in chunk.candidates or []:
                for part in (cand.content.parts if cand.content and cand.content.parts else []):
                    if part.function_call:
                        extra = {"thought_signature": base64.b64encode(part.thought_signature).decode()} \
                            if part.thought_signature else {}
                        calls.append(ToolCall(f"call_{uuid.uuid4().hex[:12]}", part.function_call.name,
                                              json.dumps(dict(part.function_call.args or {})), extra))
                    elif part.text and not part.thought:
                        yield TextDelta(part.text)
        if calls:
            yield ToolCallsEvent(calls)


# ------------------------------------------------------------------ router with fallback
class LLMRouter:
    """Try providers in order. Falls back only if the failing provider has not yet emitted anything,
    so the user never sees a half-answer stitched from two models."""

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    @property
    def configured(self) -> list[str]:
        return [p.name for p in self.providers]

    async def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[LLMEvent]:
        if not self.providers:
            raise LLMError("No LLM provider is configured (set GROQ_API_KEY and/or GEMINI_API_KEY).")
        last: Exception | None = None
        for provider in self.providers:
            attempts = 2 if provider.name == "groq" else 1   # Groq occasionally emits a malformed tool call
            for _ in range(attempts):
                emitted = False
                try:
                    async for ev in provider.stream(messages, tools):
                        emitted = True
                        yield ev
                    return
                except Exception as exc:
                    last = exc
                    log.warning("LLM provider %s failed (%s: %s)", provider.name, type(exc).__name__, str(exc)[:160])
                    if emitted:
                        raise LLMError("The model connection dropped mid-answer.") from exc
                    if "tool_use_failed" not in str(exc) and "400" not in str(exc):
                        break  # no point retrying the same provider on 429/5xx/timeouts
        raise LLMError(f"All LLM providers failed: {type(last).__name__ if last else 'unknown'}") from last


def build_llm(settings: Settings) -> LLMRouter:
    providers: dict[str, LLMProvider] = {}
    if settings.groq_api_key:
        providers["groq"] = GroqProvider(settings.groq_api_key, settings.groq_model)
    if settings.gemini_api_key:
        providers["gemini"] = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    order = sorted(providers, key=lambda n: n != settings.llm_primary)
    return LLMRouter([providers[n] for n in order])
