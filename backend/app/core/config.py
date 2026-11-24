from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    app_name: str = "StockDash API"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    refresh_reuse_grace_seconds: int = 10
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    bcrypt_rounds: int = 12

    @field_validator("jwt_secret")
    @classmethod
    def secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v


settings = Settings()