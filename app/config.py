from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./sqlite.db"
    DEBUG: bool = False
    ENABLE_AUTH: bool = True
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-me-now"
    ENABLE_SCHEMA_BROWSER: bool = True
    ENABLE_SCHEMA_SAMPLE_ROWS: bool = True
    SCHEMA_SAMPLE_LIMIT: int = 10

    BRAND_PRIMARY: str = "#206bc4"
    BRAND_SIDEBAR_BG: str = "#1b2434"
    BRAND_SIDEBAR_TEXT: str = "#ffffff"
    BRAND_ACCENT: str = "#206bc4"
    BRAND_DANGER: str = "#d63939"
    BRAND_SUCCESS: str = "#2fb344"


settings = Settings()
