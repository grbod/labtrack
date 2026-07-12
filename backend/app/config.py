"""Configuration settings for LabTrack."""

import logging
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

_config_logger = logging.getLogger("app.config")

# Shipped defaults for secrets — must be overridden in production.
_DEFAULT_SECRET_KEY = "your-secret-key-here-change-in-production"
_DEFAULT_JWT_SECRET_KEY = "your-jwt-secret-key-here"


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = Field(default="LabTrack", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    app_env: str = Field(default="development", env="APP_ENV")

    @property
    def environment(self) -> str:
        return self.app_env

    # Database
    database_url: str = Field(default="sqlite:///./labtrack.db", env="DATABASE_URL")

    # Security
    secret_key: str = Field(default=_DEFAULT_SECRET_KEY, env="SECRET_KEY")
    jwt_secret_key: str = Field(default=_DEFAULT_JWT_SECRET_KEY, env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # AI Configuration
    ai_provider: str = Field(default="mock", env="AI_PROVIDER")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="google/gemini-2.5-flash", env="OPENROUTER_MODEL"
    )

    @model_validator(mode="after")
    def validate_production_ai_provider(self) -> "Settings":
        if self.app_env.lower() == "production" and self.ai_provider.lower() == "mock":
            raise ValueError(
                "AI_PROVIDER=mock is not allowed when APP_ENV=production; configure a live extraction provider"
            )
        return self

    # File paths
    template_folder: Path = Field(default=Path("./templates"), env="TEMPLATE_FOLDER")
    templates_path: Path = Field(default=Path("./templates"), env="TEMPLATES_PATH")
    coa_output_folder: Path = Field(default=Path("./COAs"), env="COA_OUTPUT_FOLDER")
    upload_path: Path = Field(default=Path("./uploads"), env="UPLOAD_PATH")
    export_path: Path = Field(default=Path("./exports"), env="EXPORT_PATH")

    # Cloudflare R2 Storage
    r2_account_id: str = Field(default="", env="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", env="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", env="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(default="coa-files", env="R2_BUCKET_NAME")
    r2_endpoint: str = Field(default="", env="R2_ENDPOINT")
    storage_backend: str = Field(
        default="local", env="STORAGE_BACKEND"
    )  # "local" or "r2"
    presigned_url_expiry: int = Field(
        default=3600, env="PRESIGNED_URL_EXPIRY"
    )  # 1 hour

    # Aliases for compatibility
    @property
    def COA_OUTPUT_FOLDER(self):
        return str(self.coa_output_folder)

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default="app.log", env="LOG_FILE")

    # Email (for notifications)
    smtp_host: Optional[str] = Field(default=None, env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, env="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    from_email: str = Field(default="noreply@labtrack.com", env="FROM_EMAIL")

    # Feature flags
    enable_email_notifications: bool = Field(default=False, env="ENABLE_EMAIL")
    enable_audit_logging: bool = Field(default=True, env="ENABLE_AUDIT")
    enable_ai_parsing: bool = Field(default=True, env="ENABLE_AI_PARSING")
    workflow_enforce_transitions: bool = Field(
        default=True, env="WORKFLOW_ENFORCE_TRANSITIONS"
    )

    # Limits
    max_upload_size_mb: int = Field(default=10, env="MAX_UPLOAD_SIZE_MB")
    session_timeout_minutes: int = Field(default=60, env="SESSION_TIMEOUT")

    # Email intake (forward lab-report PDFs to the results importer via the
    # Cloudflare Email Worker webhook, POST /api/v1/result-imports/intake).
    # Comma-separated senders or @domains allowed to submit results
    # (e.g. "reports@daanelabs.com,@bodynutrition.com"). Empty = DENY ALL:
    # intake rejects every sender until an allowlist is configured.
    email_intake_allowed_senders: str = Field(
        default="", env="EMAIL_INTAKE_ALLOWED_SENDERS"
    )
    # Username that email uploads are attributed to in the import ledger.
    # Defaults to the low-privilege `email_intake` service account (seeded).
    # Note: underscore, not hyphen — the username validator rejects hyphens.
    email_intake_upload_username: str = Field(
        default="email_intake", env="EMAIL_INTAKE_UPLOAD_USERNAME"
    )
    # Per-sender hourly cap on intake PDFs (each accepted PDF is a paid LLM
    # call). A sender exceeding this in the trailing hour is rejected (429).
    email_intake_sender_hourly_cap: int = Field(
        default=20, env="EMAIL_INTAKE_SENDER_HOURLY_CAP"
    )
    # Shared secret for the unauthenticated intake webhook
    # (POST /api/v1/result-imports/intake, used by the Cloudflare Email
    # Worker). Unset = endpoint disabled. Generate: openssl rand -hex 32
    intake_webhook_token: Optional[str] = Field(
        default=None, env="INTAKE_WEBHOOK_TOKEN"
    )

    @model_validator(mode="after")
    def _validate_email_intake(self) -> "Settings":
        # A whitespace-only token is treated as unset so the endpoint stays
        # inert (matching the empty case) rather than active with a guessable
        # secret. Runs before _guard_production_secrets checks token strength.
        if self.intake_webhook_token is not None:
            stripped = self.intake_webhook_token.strip()
            self.intake_webhook_token = stripped or None

        # Deny-by-default: if intake is reachable (webhook token set) but no
        # allowlist is configured, EVERY sender is rejected. Warn loudly rather
        # than hard-fail — deny-all is the safe default.
        allowlist_configured = any(
            entry.strip() for entry in self.email_intake_allowed_senders.split(",")
        )
        if self.intake_webhook_token and not allowlist_configured:
            _config_logger.warning(
                "Email intake is reachable but EMAIL_INTAKE_ALLOWED_SENDERS is "
                "empty: intake will REJECT ALL senders until an allowlist is "
                "configured (deny-by-default)."
            )
        return self

    # COA Settings
    company_name: str = Field(default="Your Company Name", env="COMPANY_NAME")
    company_address: str = Field(
        default="123 Quality Street, Lab City, LC 12345", env="COMPANY_ADDRESS"
    )
    company_phone: str = Field(default="(555) 123-4567", env="COMPANY_PHONE")
    company_email: str = Field(default="lab@company.com", env="COMPANY_EMAIL")

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Refuse to start in production with shipped default secrets."""
        if self.environment.lower() == "production":
            offenders = []
            if self.secret_key == _DEFAULT_SECRET_KEY:
                offenders.append("SECRET_KEY")
            if self.jwt_secret_key == _DEFAULT_JWT_SECRET_KEY:
                offenders.append("JWT_SECRET_KEY")
            if offenders:
                raise ValueError(
                    "Refusing to start in production with default secret(s): "
                    f"{', '.join(offenders)}. Set a strong, unique value for each "
                    "via environment variables before deploying."
                )
            # A configured intake token is a shared secret guarding an
            # unauthenticated, paid endpoint; require real entropy in prod.
            # (Whitespace-only tokens are already normalized to None above.)
            if self.intake_webhook_token and len(self.intake_webhook_token) < 32:
                raise ValueError(
                    "Refusing to start in production with a weak "
                    "INTAKE_WEBHOOK_TOKEN (min 32 chars). Generate one with "
                    "`openssl rand -hex 32`."
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
settings = Settings()
