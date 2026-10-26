from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_base_url: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://emotion:emotion@localhost:5432/emotion"
    session_token_pepper: str = ""
    privacy_ledger_key: str = ""
    privacy_ledger_root: Path = ROOT / ".runtime" / "privacy"
    cookie_secure: bool = False
    allow_insecure_http: bool = False
    session_ttl_seconds: int = 604800
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    ai_enabled: bool = False
    ai_provider: Literal["disabled", "fake", "openai_compatible"] = "disabled"
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_policy_description: str = "AI 未启用；启用前请由部署者填写实际供应商及数据保留说明。"
    ai_timeout_seconds: int = 30
    ai_max_attempts: int = 2
    ai_user_hourly_limit: int = 10
    ai_user_daily_limit: int = 30
    ai_global_daily_budget: str = "0"
    ai_price_currency: str = ""
    ai_input_price_per_million: str = "0"
    ai_output_price_per_million: str = "0"
    job_lease_seconds: int = 90
    job_heartbeat_seconds: int = 20
    content_root: Path = ROOT / "content"
    backup_retention_days: int = 7
    log_level: str = "INFO"

    @property
    def origins(self):
        return [s.strip() for s in self.allowed_origins.split(",") if s.strip()]

    @model_validator(mode="after")
    def validate_settings(self):
        if len(self.session_token_pepper) < 32:
            raise ValueError(
                "SESSION_TOKEN_PEPPER must contain at least 32 characters; run scripts/setup.py"
            )
        from cryptography.fernet import Fernet

        Fernet(self.privacy_ledger_key.encode())
        if self.job_lease_seconds < self.ai_timeout_seconds + 10:
            raise ValueError("Job lease must exceed provider timeout by at least 10 seconds")
        if self.app_env == "production":
            https_enabled = self.cookie_secure and self.app_base_url.startswith("https://")
            http_opt_in = (
                self.allow_insecure_http
                and not self.cookie_secure
                and self.app_base_url.startswith("http://")
            )
            if not (https_enabled or http_opt_in):
                raise ValueError(
                    "Production requires HTTPS and secure cookies, or explicit "
                    "ALLOW_INSECURE_HTTP=true with HTTP and COOKIE_SECURE=false"
                )
            if self.ai_provider == "fake" or ":emotion@" in self.database_url:
                raise ValueError(
                    "Production cannot use fake provider or demonstration database password"
                )
        if self.ai_enabled and self.ai_provider not in {"fake", "disabled"}:
            from decimal import Decimal

            if not all(
                (
                    self.ai_api_key,
                    self.ai_model,
                    self.ai_base_url.startswith("https://"),
                    self.ai_price_currency,
                )
            ):
                raise ValueError(
                    "Real AI requires HTTPS provider URL, key, model and pricing configuration"
                )
            if Decimal(self.ai_global_daily_budget) <= 0:
                raise ValueError("Real AI requires a positive budget")
            if (
                min(
                    Decimal(self.ai_input_price_per_million),
                    Decimal(self.ai_output_price_per_million),
                )
                <= 0
            ):
                raise ValueError("Real AI requires positive input/output prices")
        return self


@lru_cache
def get_settings():
    return Settings()
