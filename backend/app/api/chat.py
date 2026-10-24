import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.orchestrator import Orchestrator

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


def orch(request: Request) -> Orchestrator:
    app = request.app
    if not hasattr(app.state, "orchestrator"):
        app.state.orchestrator = Orchestrator(app.state.llm, app.state.crm, app.state.sm, app.state.settings)
    return app.state.orchestrator


@router.post("/sessions")
async def create_session(request: Request):
    return {"session_id": await orch(request).create_session()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    data = await orch(request).get_session(session_id)
    if data is None:
        raise HTTPException(404, "Session not found")
    return data


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    o = orch(request)

    async def gen():
        async for ev in o.run_turn(body.session_id, body.message):
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
