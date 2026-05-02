from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parents[3] / ".env"  # dars/.env, resolved relative to this file


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./test.db"
    debug: bool = False
    admin_secret: str = "dev-secret"
    lp_assistant_url: str = "https://lp-assistant.taleemabad.com"
    lp_assistant_api_key: str = ""
    eg_assistant_url: str = "https://eg-assistant.taleemabad.com"
    eg_assistant_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "https://truthful-renewal-production-c9ce.up.railway.app"]

    anthropic_api_key: str = ""

    # taleemabad-core DB (used for curriculum import)
    core_db_url: str = ""  # postgresql://user:pass@host/dbname for taleemabad-core


settings = Settings()
