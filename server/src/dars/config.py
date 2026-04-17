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
    supabase_url: str = ""
    supabase_anon_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]

    anthropic_api_key: str = ""

    # taleemabad-core staging DB (used for SLO import scripts)
    core_staging_db_host: str = "localhost"
    core_staging_db_port: int = 5432
    core_staging_db_name: str = "taleemabad"
    core_staging_db_user: str = "postgres"
    core_staging_db_password: str = ""


settings = Settings()
