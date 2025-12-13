"""Settings API schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class ProcessingSettings(BaseModel):
    """Processing configuration settings."""
    confidence_threshold: float = Field(default=0.85, ge=0.5, le=0.99)
    fallback_to_claude: bool = True
    max_retries: int = Field(default=3, ge=1, le=10)


class ValidationSettings(BaseModel):
    """Validation configuration settings."""
    strict_mode: bool = True
    required_fields_only: bool = False
    auto_create_exceptions: bool = True


class NotificationSettings(BaseModel):
    """Notification configuration settings."""
    email_on_exception: bool = True
    email_on_batch_complete: bool = False
    slack_webhook_url: str = ""


class AllSettings(BaseModel):
    """Combined settings response."""
    processing: ProcessingSettings
    validation: ValidationSettings
    notifications: NotificationSettings


class SettingsUpdate(BaseModel):
    """Settings update request."""
    processing: Optional[ProcessingSettings] = None
    validation: Optional[ValidationSettings] = None
    notifications: Optional[NotificationSettings] = None


class DatabaseStats(BaseModel):
    """Database statistics."""
    documents_count: int
    exceptions_count: int
    audit_logs_count: int
    connection_status: str = "connected"
    database_type: str = "PostgreSQL 15"
    instance_name: str = "capitalspring-dev"
    region: str = "us-central1"


class DocumentTypeInfo(BaseModel):
    """Document type configuration."""
    type: str
    processor: str
    fallback: str
    status: str = "Active"
