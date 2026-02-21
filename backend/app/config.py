"""Configuration settings for LabTrack."""

from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = Field(default="LabTrack", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="APP_ENV")
    app_env: str = Field(default="development", env="APP_ENV")

    # Database
    database_url: str = Field(
        default="sqlite:///./labtrack.db", env="DATABASE_URL"
    )

    # Security
    secret_key: str = Field(
        default="your-secret-key-here-change-in-production", env="SECRET_KEY"
    )
    jwt_secret_key: str = Field(
        default="your-jwt-secret-key-here", env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # AI Configuration
    ai_provider: str = Field(default="mock", env="AI_PROVIDER")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")

    # File paths
    watch_folder_path: Path = Field(default=Path("./pdf_watch"), env="WATCH_FOLDER")
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

    # PDF Monitoring
    enable_folder_monitoring: bool = Field(default=True, env="ENABLE_MONITORING")
    watch_interval: int = Field(default=5, env="WATCH_INTERVAL")
    pdf_watch_folder: str = Field(default="./pdf_watch", env="PDF_WATCH_FOLDER")

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create global settings instance
settings = Settings()
