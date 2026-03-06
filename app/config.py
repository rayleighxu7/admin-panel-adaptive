from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./sqlite.db"
    DEBUG: bool = False
    ENABLE_AUTH: bool = Field(
        default=True,
        validation_alias=AliasChoices("ENABLE_AUTH", "AUTH_ENABLED"),
    )
    SECRET_KEY: str = "change-me-in-production"
    SESSION_COOKIE_NAME: str = "admin_panel_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 8
    SESSION_HTTPS_ONLY: bool = True
    ENABLE_SCHEMA_BROWSER: bool = True
    ENABLE_SCHEMA_SAMPLE_ROWS: bool = True
    SCHEMA_SAMPLE_LIMIT: int = 10
    SCHEMA_INCLUDE_ROW_COUNTS: bool = True
    SCHEMA_EXPORT_MAX_ROWS: int = 5000

    BRAND_PRIMARY: str = "#206bc4"
    BRAND_SIDEBAR_BG: str = "#1b2434"
    BRAND_SIDEBAR_TEXT: str = "#ffffff"
    BRAND_LOGO_URL: str = "/images/freelanxur-logo-transparent.PNG"
    BRAND_ACCENT: str = "#206bc4"
    BRAND_DANGER: str = "#d63939"
    BRAND_SUCCESS: str = "#2fb344"


settings = Settings()
