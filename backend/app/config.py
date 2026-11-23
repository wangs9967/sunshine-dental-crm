from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None
    wechat_app_id: str = ""
    wechat_app_secret: SecretStr | None = None
    phone_encryption_key: SecretStr | None = None
    phone_lookup_hmac_key: SecretStr | None = None
    auth_access_ttl_seconds: int = Field(default=600, gt=0, le=900)
    auth_session_ttl_seconds: int = Field(default=604800, gt=0)

    @model_validator(mode="after")
    def validate_session_lifetime(self) -> "AuthSettings":
        if self.auth_session_ttl_seconds <= self.auth_access_ttl_seconds:
            raise ValueError("Session lifetime must exceed access token lifetime")
        return self


class LocalSettings(AuthSettings):
    business_timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "sunshine_dental"
    postgres_user: str = "sunshine"
    postgres_password: SecretStr

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
