"""Exception database model for tracking validation and processing exceptions."""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.document import JSONType, UUIDType

if TYPE_CHECKING:
    from app.models.document import Document


class ExceptionStatus(str, Enum):
    """Exception resolution status."""
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ExceptionCategory(str, Enum):
    """Exception category types."""
    VALIDATION_ERROR = "validation_error"
    EXTRACTION_ERROR = "extraction_error"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_FIELD = "missing_field"
    INVALID_FORMAT = "invalid_format"
    BUSINESS_RULE = "business_rule"
    CROSS_FIELD = "cross_field"
    UNKNOWN_DOC_TYPE = "unknown_doc_type"
    PROCESSING_FAILURE = "processing_failure"
    OTHER = "other"


class ExceptionPriority(str, Enum):
    """Exception priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Exception(Base):
    """Exception model for tracking issues requiring manual review."""

    __tablename__ = "exceptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Document reference
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Exception details
    category: Mapped[str] = mapped_column(
        String(50),
        default=ExceptionCategory.OTHER.value,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    expected_value: Mapped[Optional[str]] = mapped_column(Text)
    actual_value: Mapped[Optional[str]] = mapped_column(Text)

    # Priority and status
    priority: Mapped[str] = mapped_column(
        String(20),
        default=ExceptionPriority.MEDIUM.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=ExceptionStatus.OPEN.value,
        index=True,
    )

    # Resolution
    resolution: Mapped[Optional[dict]] = mapped_column(JSONType())
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(255))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Auto-resolution tracking
    auto_resolvable: Mapped[bool] = mapped_column(default=False)
    suggested_resolution: Mapped[Optional[dict]] = mapped_column(JSONType())

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="exceptions",
    )

    # Indexes
    __table_args__ = (
        Index("ix_exceptions_status_priority", "status", "priority"),
        Index("ix_exceptions_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Exception(id={self.id}, category={self.category}, status={self.status})>"
