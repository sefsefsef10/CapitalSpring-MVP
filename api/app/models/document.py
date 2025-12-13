"""Document database model."""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Index, Numeric, String, Text, Boolean, Integer, func, TypeDecorator
from sqlalchemy.types import TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# Cross-database JSON type that works with both SQLite and PostgreSQL
class JSONType(TypeDecorator):
    """JSON type that works with both SQLite (JSON stored as TEXT) and PostgreSQL (JSONB)."""
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


# UUID type that stores as string in SQLite
class UUIDType(TypeDecorator):
    """UUID type that works with both SQLite (stored as TEXT) and PostgreSQL (native UUID)."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return None

if TYPE_CHECKING:
    from app.models.exception import Exception
    from app.models.audit import AuditLog


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class DocumentType(str, Enum):
    """Document type categories."""
    # Portfolio Company Financials
    MONTHLY_FINANCIALS = "monthly_financials"
    QUARTERLY_FINANCIALS = "quarterly_financials"
    ANNUAL_FINANCIALS = "annual_financials"
    MANAGEMENT_ACCOUNTS = "management_accounts"
    BOARD_DECK = "board_deck"

    # Covenant Compliance
    COVENANT_COMPLIANCE = "covenant_compliance"
    COVENANT_CALCULATIONS = "covenant_calculations"
    CURE_NOTICE = "cure_notice"

    # Borrowing Base
    BORROWING_BASE = "borrowing_base"
    AR_AGING = "ar_aging"
    INVENTORY_REPORT = "inventory_report"
    CONCENTRATION_REPORT = "concentration_report"

    # Fund Administration
    CAPITAL_CALL = "capital_call"
    DISTRIBUTION_NOTICE = "distribution_notice"
    NAV_STATEMENT = "nav_statement"
    INVESTOR_STATEMENT = "investor_statement"
    FEE_CALCULATION = "fee_calculation"

    # Legal & Compliance
    AMENDMENT = "amendment"
    WAIVER_REQUEST = "waiver_request"
    UCC_FILING = "ucc_filing"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    ORGANIZATIONAL_DOC = "organizational_doc"

    # Valuations
    THIRD_PARTY_VALUATION = "third_party_valuation"
    COLLATERAL_APPRAISAL = "collateral_appraisal"
    MARK_TO_MARKET = "mark_to_market"

    # Banking & Treasury
    BANK_STATEMENT = "bank_statement"
    LOCKBOX_REPORT = "lockbox_report"
    WIRE_CONFIRMATION = "wire_confirmation"

    # Other
    INVOICE = "invoice"
    OTHER = "other"
    UNKNOWN = "unknown"


class ProcessorType(str, Enum):
    """Document processor type used."""
    DOCUMENT_AI_INVOICE = "document_ai_invoice"
    DOCUMENT_AI_FORM = "document_ai_form"
    DOCUMENT_AI_OCR = "document_ai_ocr"
    DOCUMENT_AI_CUSTOM = "document_ai_custom"
    CLAUDE = "claude"
    MANUAL = "manual"


class Document(Base):
    """Document model for tracking uploaded and processed documents."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # File information
    gcs_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    # Classification
    doc_type: Mapped[Optional[str]] = mapped_column(String(100), default=DocumentType.UNKNOWN.value)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(50),
        default=DocumentStatus.PENDING.value,
        index=True,
    )

    # Extracted data
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONType())
    raw_extraction: Mapped[Optional[dict]] = mapped_column(JSONType())  # Original extraction before normalization

    # Confidence and quality
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    field_confidences: Mapped[Optional[dict]] = mapped_column(JSONType())  # Per-field confidence scores
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Processing metadata
    processor_used: Mapped[Optional[str]] = mapped_column(String(50))
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)

    # Multi-tenancy
    fund_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType(), index=True)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType(), index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # User tracking
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    exceptions: Mapped[list["Exception"]] = relationship(
        "Exception",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_documents_status_created", "status", "created_at"),
        Index("ix_documents_doc_type", "doc_type"),
        Index("ix_documents_fund_company", "fund_id", "company_id"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.original_filename}, status={self.status})>"
