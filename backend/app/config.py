from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "https://automotive-ai-multi-assistant.onrender.com"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/autoagent"

    zoho_mode: str = "mock"  # live | mock
    zoho_accounts_url: str = "https://accounts.zoho.in"
    zoho_api_domain: str = "https://www.zohoapis.in"
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_refresh_token: str = ""
    zoho_timeout_s: float = 10.0
    zoho_max_retries: int = 3
    zoho_retry_base_s: float = 0.5
    zoho_lead_source: str = "Web Research"
    zoho_cases_module: str = "Cases"

    llm_primary: str = "groq"  # groq | gemini
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    max_tool_rounds: int = 6
    history_messages: int = 24
    queue_poll_s: float = 20.0
    queue_max_attempts: int = 8

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
