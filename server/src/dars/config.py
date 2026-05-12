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
    eg_assistant_url: str = "https://exam-generator.taleemabad.com"
    eg_assistant_api_key: str = ""
    cors_origins: str = "http://localhost:3000,https://truthful-renewal-production-c9ce.up.railway.app"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    anthropic_api_key: str = ""

    # taleemabad-core DB — set CORE_DB_URL directly, or set the 5 CORE_STAGING_DB_* parts
    core_db_url: str = ""
    core_staging_db_host: str = ""
    core_staging_db_port: str = "5432"
    core_staging_db_name: str = ""
    core_staging_db_user: str = ""
    core_staging_db_password: str = ""

    @property
    def effective_core_db_url(self) -> str:
        """Return CORE_DB_URL if set, otherwise build it from the 5-part env vars."""
        if self.core_db_url:
            return self.core_db_url
        if self.core_staging_db_host and self.core_staging_db_name:
            from urllib.parse import quote_plus
            pw = quote_plus(self.core_staging_db_password)
            user = quote_plus(self.core_staging_db_user)
            return (
                f"postgresql://{user}:{pw}"
                f"@{self.core_staging_db_host}:{self.core_staging_db_port}"
                f"/{self.core_staging_db_name}"
            )
        return ""


settings = Settings()
