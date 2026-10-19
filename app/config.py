from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Feature Flag Platform API"
    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://feature_flags:feature_flags@localhost:5432/feature_flags"
    auth_secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    cors_origins: str = "http://localhost:3000"
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    allowed_hosts: str = ""
    max_request_body_bytes: int = Field(default=2_097_152, ge=65_536, le=16_777_216)
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=1, le=120)
    db_pool_recycle: int = Field(default=1800, ge=60, le=86_400)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.app_env.lower() == "production":
            if not self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must contain at least one origin in production")
            if not self.allowed_host_list:
                raise ValueError("ALLOWED_HOSTS must contain at least one host in production")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
