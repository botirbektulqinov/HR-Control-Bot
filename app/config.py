from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    super_admin_ids: str = Field("", alias="SUPER_ADMIN_IDS")
    default_timezone: str = Field("Asia/Tashkent", alias="DEFAULT_TIMEZONE")
    location_strictness: str = Field("medium", alias="LOCATION_STRICTNESS")
    location_max_age_seconds: int = Field(120, alias="LOCATION_MAX_AGE_SECONDS")
    dashboard_email: str = Field("", alias="DASHBOARD_EMAIL")
    dashboard_password: str = Field("", alias="DASHBOARD_PASSWORD")
    dashboard_origins: str = Field(
        "http://localhost:3000", alias="DASHBOARD_ORIGINS"
    )

    @property
    def super_admin_id_set(self) -> set[int]:
        return {int(x) for x in self.super_admin_ids.replace(" ", "").split(",") if x}

    @property
    def dashboard_origin_list(self) -> list[str]:
        return [x.strip() for x in self.dashboard_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
