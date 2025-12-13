"""Audit log database model for tracking all actions."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.document import JSONType, UUIDType

if TYPE_CHECKING:
    from app.models.document import Document


class AuditAction(str, Enum):
    """Audit log action types."""
    # Document lifecycle
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSING_STARTED = "document_processing_started"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"
    DOCUMENT_REPROCESSED = "document_reprocessed"
    DOCUMENT_DELETED = "document_deleted"

    # Extraction
    EXTRACTION_COMPLETED = "extraction_completed"
    EXTRACTION_FALLBACK = "extraction_fallback"  # When falling back to Claude
    EXTRACTION_MANUAL = "extraction_manual"

    # Validation
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"

    # Exception handling
    EXCEPTION_CREATED = "exception_created"
    EXCEPTION_RESOLVED = "exception_resolved"
    EXCEPTION_IGNORED = "exception_ignored"
    EXCEPTION_ESCALATED = "exception_escalated"

    # Data modifications
    DATA_MODIFIED = "data_modified"
    FIELD_UPDATED = "field_updated"
    DATA_APPROVED = "data_approved"

    # Export
    EXPORT_GENERATED = "export_generated"
    EXPORT_DOWNLOADED = "export_downloaded"

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # System
    SYSTEM_EVENT = "system_event"


class AuditLog(Base):
    """Audit log for tracking all system actions and changes."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Document reference (optional - some actions are not document-specific)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUIDType(),
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[Optional[str]] = mapped_column(String(255))  # User email or "system"
    actor_type: Mapped[str] = mapped_column(String(50), default="user")  # user, system, webhook

    # Additional context
    details: Mapped[Optional[dict]] = mapped_column(JSONType())

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    request_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # Relationship
    document: Mapped[Optional["Document"]] = relationship(
        "Document",
        back_populates="audit_logs",
    )

    # Indexes
    __table_args__ = (
        Index("ix_audit_log_action_created", "action", "created_at"),
        Index("ix_audit_log_actor_created", "actor", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, actor={self.actor})>"
