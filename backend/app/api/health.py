from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    s = request.app.state.settings
    out: dict = {"status": "ok", "zoho_mode": s.zoho_mode,
                 "llm": {"primary": s.llm_primary, "groq_configured": bool(s.groq_api_key),
                         "gemini_configured": bool(s.gemini_api_key)}}
    try:
        async with request.app.state.sm() as db:
            await db.execute(text("SELECT 1"))
        out["db"] = "ok"
    except Exception as exc:
        out["db"], out["status"] = f"error: {type(exc).__name__}", "degraded"
    try:
        tokens = getattr(request.app.state.transport, "tokens", None)
        if tokens:
            await tokens.check()
        out["zoho"] = "ok"
    except Exception as exc:
        out["zoho"], out["status"] = f"error: {type(exc).__name__}", "degraded"
    try:
        out["retry_queue_depth"] = await request.app.state.crm.queue_depth()
    except Exception:
        out["retry_queue_depth"] = None
    return out
