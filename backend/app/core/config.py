from functools import lru_cache

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reping"
    environment: str = "development"
    public_base_url: AnyHttpUrl = "http://localhost:8000"
    frontend_url: AnyHttpUrl = "http://localhost:5173"
    root_domain: str = "pingback.localhost"

    database_url: str = "postgresql+asyncpg://reping:reping@postgres:5432/reping"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = Field(default="change-me-in-production", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24

    retention_days: int = 7
    subscription_price_usd: str = "4.99"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_plan_id: str = ""
    paypal_webhook_id: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    dns_listen_host: str = "0.0.0.0"
    dns_listen_port: int = 5353
    dns_ttl_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("root_domain")
    @classmethod
    def normalize_root_domain(cls, value: str) -> str:
        return value.strip().strip(".").lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()
