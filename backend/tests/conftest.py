import os
import tempfile

# Must be set before app modules read settings.
_DB = os.path.join(tempfile.mkdtemp(prefix="autoagent-test-"), "test.sqlite3")
# Default: throwaway SQLite file. Set TEST_DATABASE_URL to run the suite against Postgres (it drops/recreates tables).
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_DB}"
os.environ["ZOHO_MODE"] = "mock"
os.environ["ZOHO_RETRY_BASE_S"] = "0"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import pytest_asyncio  # noqa: E402

from app.config import Settings  # noqa: E402
from app.crm.service import CRMService  # noqa: E402
from app.crm.zoho_mock import ZohoMockClient  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def settings() -> Settings:
    return Settings(database_url=os.environ["DATABASE_URL"], zoho_mode="mock", zoho_retry_base_s=0.0,
                    zoho_max_retries=2, _env_file=None)


@pytest_asyncio.fixture
async def sm(settings):
    engine = make_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield make_sessionmaker(engine)
    await engine.dispose()


@pytest_asyncio.fixture
async def zoho() -> ZohoMockClient:
    return ZohoMockClient()


@pytest_asyncio.fixture
async def crm(zoho, sm, settings) -> CRMService:
    async def no_sleep(_): return None
    return CRMService(zoho, sm, settings, sleep=no_sleep)


@pytest_asyncio.fixture
async def agent(crm, sm, settings):
    from app.agent.orchestrator import Orchestrator
    return Orchestrator(None, crm, sm, settings)
