"""Configuration settings for LabTrack."""

from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

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
    database_url: str = Field(
        default="sqlite:///./labtrack.db", env="DATABASE_URL"
    )

    # Security
    secret_key: str = Field(
        default=_DEFAULT_SECRET_KEY, env="SECRET_KEY"
    )
    jwt_secret_key: str = Field(
        default=_DEFAULT_JWT_SECRET_KEY, env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # AI Configuration
    ai_provider: str = Field(default="mock", env="AI_PROVIDER")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="google/gemini-2.5-flash", env="OPENROUTER_MODEL")

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
    coa_output_folder: Path = Field(
        default=Path("./COAs"), env="COA_OUTPUT_FOLDER"
    )
    upload_path: Path = Field(default=Path("./uploads"), env="UPLOAD_PATH")
    export_path: Path = Field(default=Path("./exports"), env="EXPORT_PATH")

    # Cloudflare R2 Storage
    r2_account_id: str = Field(default="", env="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", env="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", env="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(default="coa-files", env="R2_BUCKET_NAME")
    r2_endpoint: str = Field(default="", env="R2_ENDPOINT")
    storage_backend: str = Field(default="local", env="STORAGE_BACKEND")  # "local" or "r2"
    presigned_url_expiry: int = Field(default=3600, env="PRESIGNED_URL_EXPIRY")  # 1 hour

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

    # Limits
    max_upload_size_mb: int = Field(default=10, env="MAX_UPLOAD_SIZE_MB")
    session_timeout_minutes: int = Field(default=60, env="SESSION_TIMEOUT")

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
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
settings = Settings()
