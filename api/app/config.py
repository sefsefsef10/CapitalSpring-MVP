"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "CapitalSpring Data Ingestion"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"])

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/capitalspring_dev"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_echo: bool = False

    # GCP
    use_gcp: bool = False  # Set True + configure credentials to use real GCP
    gcp_project_id: str = "capitalspring-dev"
    gcp_region: str = "us-central1"
    google_application_credentials: str = ""  # Path to service account JSON

    # Cloud Storage
    gcs_bucket_name: str = "capitalspring-data"
    gcs_inbox_prefix: str = "inbox/"
    gcs_processing_prefix: str = "processing/"
    gcs_complete_prefix: str = "complete/"
    gcs_failed_prefix: str = "failed/"
    gcs_archive_prefix: str = "archive/"

    # Document AI
    document_ai_location: str = "us"
    document_ai_invoice_processor_id: str = ""
    document_ai_form_processor_id: str = ""
    document_ai_ocr_processor_id: str = ""

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096
    claude_confidence_threshold: float = 0.85

    # Firebase Auth
    firebase_project_id: str = ""
    firebase_api_key: str = ""

    # Pub/Sub
    pubsub_document_uploaded_topic: str = "document-uploaded"
    pubsub_document_processed_topic: str = "document-processed"

    # BigQuery
    bigquery_dataset: str = "capitalspring_analytics"

    # Processing
    processing_confidence_threshold: float = 0.85
    processing_max_retries: int = 3
    processing_timeout_seconds: int = 300

    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @computed_field
    @property
    def gcs_bucket_uri(self) -> str:
        """Get the full GCS bucket URI."""
        return f"gs://{self.gcs_bucket_name}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
