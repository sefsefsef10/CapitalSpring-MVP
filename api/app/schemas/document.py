"""Pydantic schemas for Document API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, DocumentType, ProcessorType


class DocumentBase(BaseModel):
    """Base document schema."""
    doc_type: Optional[DocumentType] = None
    fund_id: Optional[UUID] = None
    company_id: Optional[UUID] = None


class DocumentCreate(DocumentBase):
    """Schema for creating a document record."""
    gcs_path: str
    original_filename: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    uploaded_by: Optional[str] = None


class DocumentUpdate(BaseModel):
    """Schema for updating document extracted data."""
    extracted_data: Optional[dict[str, Any]] = None
    doc_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None
    requires_review: Optional[bool] = None
    reviewed_by: Optional[str] = None


class DocumentRead(DocumentBase):
    """Schema for reading a document."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    gcs_path: str
    original_filename: str
    mime_type: Optional[str]
    file_size_bytes: Optional[int]
    status: DocumentStatus
    extracted_data: Optional[dict[str, Any]]
    confidence: Optional[float]
    field_confidences: Optional[dict[str, float]]
    requires_review: bool
    processor_used: Optional[ProcessorType]
    processing_time_ms: Optional[int]
    processing_error: Optional[str]
    uploaded_by: Optional[str]
    reviewed_by: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    updated_at: datetime


class DocumentList(BaseModel):
    """Schema for paginated document list response."""
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentProcessingResult(BaseModel):
    """Schema for document processing result."""
    document_id: UUID
    status: DocumentStatus
    doc_type: Optional[DocumentType]
    extracted_data: Optional[dict[str, Any]]
    confidence: Optional[float]
    field_confidences: Optional[dict[str, float]]
    processor_used: Optional[ProcessorType]
    processing_time_ms: int
    validation_errors: list[str] = Field(default_factory=list)
    exceptions_created: int = 0


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""
    document_id: UUID
    gcs_path: str
    status: str = "pending"
    message: str = "Document uploaded successfully and queued for processing"


class DocumentMetrics(BaseModel):
    """Schema for document processing metrics."""
    total_documents: int
    processed_count: int
    pending_count: int
    failed_count: int
    needs_review_count: int
    automation_rate: float  # Percentage of docs processed without manual review
    avg_confidence: float
    avg_processing_time_ms: float
    documents_by_type: dict[str, int]
    documents_by_status: dict[str, int]
    processor_usage: dict[str, int]


class DocumentFilter(BaseModel):
    """Schema for document filtering."""
    status: Optional[DocumentStatus] = None
    doc_type: Optional[DocumentType] = None
    fund_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    requires_review: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None  # Search in filename
