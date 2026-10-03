from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://jobhunter:jobhunter@localhost:5432/jobhunter"
    SQL_ECHO: bool = False
    REDIS_CACHE_URL: str = "redis://localhost:6379/0"
    REDIS_BROKER_URL: str = "redis://localhost:6379/1"
    JWT_SECRET: str = "change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    # Secret code for the sign-in page's "Forgot password?" form. Set it as a
    # Railway variable (12+ characters); the form is disabled while empty.
    PASSWORD_RESET_CODE: str = ""
    # Email (Brevo HTTP API; Railway Hobby blocks SMTP). See app/core/email.py.
    BREVO_API_KEY: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "Ascend"
    BREVO_API_URL: str = "https://api.brevo.com/v3/smtp/email"
    # Where links in emails point (the website)
    APP_URL: str = "https://web-production-382435.up.railway.app"
    # shown on the privacy notice as the contact for privacy questions
    # (defaults to EMAIL_FROM when not set)
    PRIVACY_CONTACT_EMAIL: str = ""
    # where "Send feedback" messages go (defaults to PRIVACY_CONTACT_EMAIL, then EMAIL_FROM)
    FEEDBACK_EMAIL: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Railway/Heroku-style hosts inject postgres:// or postgresql:// URLs;
        the async engine and Alembic env both need the asyncpg driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v


settings = Settings()
