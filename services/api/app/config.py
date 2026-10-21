from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PAYPAL_SANDBOX_API_BASE = "https://api-m.sandbox.paypal.com"
DEV_ENCRYPTION_SEED = "backit-development-only-key-do-not-use-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "production"] = "development"
    db_server: str = "localhost:5432"
    db_username: str = "indrajit"
    db_password: str | None = None
    db_name: str = "backit"
    cors_origins: str = "http://localhost:3000"
    web_base_url: str = "http://localhost:3000"

    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_issuer: str = "http://localhost:3000"
    auth_audience: str | None = None
    auth_algorithms: str = "EdDSA,ES256,RS256"

    paypal_mode: Literal["mock", "sandbox"] = "mock"
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_webhook_id: str | None = None
    paypal_partner_merchant_id: str | None = None
    paypal_bn_code: str | None = None

    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ai_timeout_seconds: float = 20.0

    # Used to encrypt builder webhook secrets at rest and to derive public ledger refs.
    app_encryption_key: str | None = None

    platform_fee_bps: int = Field(default=800, ge=0, le=5000)
    hold_days: int = Field(default=30, ge=0)
    payout_minimum_cents: int = Field(default=100, ge=1)
    reservation_minutes: int = 15
    payout_preview_ttl_minutes: int = 30
    sandbox_payout_budget_cents: int = 100_000
    webhook_max_attempts: int = 8
    webhook_timeout_seconds: float = 5.0
    webhook_response_max_bytes: int = 4096
    job_max_attempts: int = 6

    @property
    def database_url(self) -> URL:
        host, _, port = self.db_server.partition(":")
        local = host in ("localhost", "127.0.0.1")
        return URL.create(
            "postgresql+psycopg",
            username=self.db_username,
            password=self.db_password or None,
            host=host,
            port=int(port) if port else 5432,
            database=self.db_name,
            query={} if local else {"sslmode": "require"},
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def jwt_algorithms(self) -> list[str]:
        return [a.strip() for a in self.auth_algorithms.split(",") if a.strip()]

    @property
    def jwt_audience(self) -> str:
        return self.auth_audience or self.auth_issuer

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def paypal_api_base(self) -> str:
        # Sandbox host is pinned; live endpoints are never used by this MVP.
        return PAYPAL_SANDBOX_API_BASE

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    def encryption_seed(self) -> str:
        if self.app_encryption_key:
            return self.app_encryption_key
        if self.is_development:
            return DEV_ENCRYPTION_SEED
        raise RuntimeError("APP_ENCRYPTION_KEY must be set outside development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
