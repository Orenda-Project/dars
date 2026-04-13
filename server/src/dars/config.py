from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
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

    # taleemabad-core DB (used for books/chapters sync)
    core_db_host: str = "localhost"
    core_db_port: int = 5432
    core_db_name: str = "taleemabad"
    core_db_user: str = "postgres"
    core_db_password: str = ""


settings = Settings()
