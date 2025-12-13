"""Settings API router."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.db.session import get_db
from app.dependencies import require_auth, UserInfo
from app.models.document import Document
from app.models.exception import Exception as DocumentException
from app.models.audit import AuditLog
from app.schemas.settings import (
    AllSettings,
    DatabaseStats,
    DocumentTypeInfo,
    NotificationSettings,
    ProcessingSettings,
    SettingsUpdate,
    ValidationSettings,
)

logger = structlog.get_logger(__name__)

router = APIRouter()

# In-memory settings store (for MVP - would use database table in production)
_settings_store = {
    "processing": ProcessingSettings(
        confidence_threshold=app_settings.processing_confidence_threshold,
        fallback_to_claude=True,
        max_retries=app_settings.processing_max_retries,
    ),
    "validation": ValidationSettings(),
    "notifications": NotificationSettings(),
}

# Document type configurations
DOCUMENT_TYPES = [
    DocumentTypeInfo(type="Portfolio Financials", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Covenant Compliance", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Borrowing Base", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Capital Call", processor="Document AI Invoice", fallback="Claude"),
    DocumentTypeInfo(type="Distribution Notice", processor="Document AI Invoice", fallback="Claude"),
    DocumentTypeInfo(type="NAV Statement", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="AR Aging", processor="Document AI Form", fallback="OCR"),
    DocumentTypeInfo(type="Bank Statement", processor="Document AI Form", fallback="OCR"),
    DocumentTypeInfo(type="Invoice", processor="Document AI Invoice", fallback="Form Parser"),
    DocumentTypeInfo(type="Insurance Certificate", processor="Document AI Invoice", fallback="Claude"),
    DocumentTypeInfo(type="Tax Document", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Legal Agreement", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Financial Statement", processor="Document AI Form", fallback="Claude"),
    DocumentTypeInfo(type="Audit Report", processor="Document AI Form", fallback="Claude"),
]


@router.get("", response_model=AllSettings)
async def get_settings(
    user: UserInfo = Depends(require_auth),
) -> AllSettings:
    """Get all application settings."""
    return AllSettings(
        processing=_settings_store["processing"],
        validation=_settings_store["validation"],
        notifications=_settings_store["notifications"],
    )


@router.put("", response_model=AllSettings)
async def update_settings(
    settings_update: SettingsUpdate,
    user: UserInfo = Depends(require_auth),
) -> AllSettings:
    """Update application settings."""
    if settings_update.processing:
        _settings_store["processing"] = settings_update.processing
    if settings_update.validation:
        _settings_store["validation"] = settings_update.validation
    if settings_update.notifications:
        _settings_store["notifications"] = settings_update.notifications

    logger.info(
        "Settings updated",
        actor=user.email or user.uid,
        updated_sections=[
            k for k, v in {
                "processing": settings_update.processing,
                "validation": settings_update.validation,
                "notifications": settings_update.notifications,
            }.items() if v is not None
        ],
    )

    return AllSettings(
        processing=_settings_store["processing"],
        validation=_settings_store["validation"],
        notifications=_settings_store["notifications"],
    )


@router.get("/processing", response_model=ProcessingSettings)
async def get_processing_settings(
    user: UserInfo = Depends(require_auth),
) -> ProcessingSettings:
    """Get processing settings."""
    return _settings_store["processing"]


@router.put("/processing", response_model=ProcessingSettings)
async def update_processing_settings(
    settings: ProcessingSettings,
    user: UserInfo = Depends(require_auth),
) -> ProcessingSettings:
    """Update processing settings."""
    _settings_store["processing"] = settings
    logger.info("Processing settings updated", actor=user.email or user.uid)
    return settings


@router.get("/validation", response_model=ValidationSettings)
async def get_validation_settings(
    user: UserInfo = Depends(require_auth),
) -> ValidationSettings:
    """Get validation settings."""
    return _settings_store["validation"]


@router.put("/validation", response_model=ValidationSettings)
async def update_validation_settings(
    settings: ValidationSettings,
    user: UserInfo = Depends(require_auth),
) -> ValidationSettings:
    """Update validation settings."""
    _settings_store["validation"] = settings
    logger.info("Validation settings updated", actor=user.email or user.uid)
    return settings


@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    user: UserInfo = Depends(require_auth),
) -> NotificationSettings:
    """Get notification settings."""
    return _settings_store["notifications"]


@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    user: UserInfo = Depends(require_auth),
) -> NotificationSettings:
    """Update notification settings."""
    _settings_store["notifications"] = settings
    logger.info("Notification settings updated", actor=user.email or user.uid)
    return settings


@router.get("/database", response_model=DatabaseStats)
async def get_database_stats(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DatabaseStats:
    """Get database statistics."""
    # Get counts
    docs_count = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0
    exc_count = (await db.execute(select(func.count()).select_from(DocumentException))).scalar() or 0
    audit_count = (await db.execute(select(func.count()).select_from(AuditLog))).scalar() or 0

    # Check connection
    try:
        await db.execute(text("SELECT 1"))
        connection_status = "connected"
    except Exception:
        connection_status = "error"

    return DatabaseStats(
        documents_count=docs_count,
        exceptions_count=exc_count,
        audit_logs_count=audit_count,
        connection_status=connection_status,
        database_type="PostgreSQL 15",
        instance_name=app_settings.gcp_project_id.replace("-mvp", "-dev") if "mvp" in app_settings.gcp_project_id else "capitalspring-dev",
        region=app_settings.gcp_region,
    )


@router.get("/document-types", response_model=list[DocumentTypeInfo])
async def get_document_types(
    user: UserInfo = Depends(require_auth),
) -> list[DocumentTypeInfo]:
    """Get supported document types and their configurations."""
    return DOCUMENT_TYPES
