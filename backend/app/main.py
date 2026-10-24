import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.crm.queue import QueueWorker
from app.crm.service import CRMService
from app.crm.zoho_live import ZohoLiveClient
from app.crm.zoho_mock import ZohoMockClient
from app.db import make_engine, make_sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_transport(settings: Settings):
    if settings.zoho_mode == "live":
        return ZohoLiveClient(settings)
    return ZohoMockClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    engine = make_engine(settings.database_url)
    sm = make_sessionmaker(engine)
    transport = app.state.transport_override or build_transport(settings)
    crm = CRMService(transport, sm, settings)
    app.state.engine, app.state.sm, app.state.transport, app.state.crm = engine, sm, transport, crm
    worker = QueueWorker(crm, settings.queue_poll_s)
    worker.start()
    try:
        yield
    finally:
        await worker.stop()
        await transport.aclose()
        await engine.dispose()


def create_app(settings: Settings | None = None, *, transport=None, llm=None) -> FastAPI:
    from app.agent.llm import build_llm
    from app.api import chat, health

    settings = settings or get_settings()
    app = FastAPI(title="Mahindra AI Assistant (prototype)", lifespan=lifespan)
    app.state.settings = settings
    app.state.transport_override = transport
    app.state.llm = llm or build_llm(settings)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["*"], allow_headers=["*"])
    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    return app


app = create_app()
