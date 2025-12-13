"""Pydantic schemas for Exception API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.exception import ExceptionCategory, ExceptionPriority, ExceptionStatus


class ExceptionBase(BaseModel):
    """Base exception schema."""
    category: ExceptionCategory = ExceptionCategory.OTHER
    reason: str
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    priority: ExceptionPriority = ExceptionPriority.MEDIUM


class ExceptionCreate(ExceptionBase):
    """Schema for creating an exception."""
    document_id: UUID
    auto_resolvable: bool = False
    suggested_resolution: Optional[dict[str, Any]] = None


class ExceptionUpdate(BaseModel):
    """Schema for updating an exception."""
    priority: Optional[ExceptionPriority] = None
    status: Optional[ExceptionStatus] = None
    resolution_notes: Optional[str] = None


class ExceptionResolve(BaseModel):
    """Schema for resolving an exception."""
    resolution: dict[str, Any]
    resolution_notes: Optional[str] = None
    resolved_by: str
    apply_to_document: bool = True  # Whether to update the document with resolution


class ExceptionRead(ExceptionBase):
    """Schema for reading an exception."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: ExceptionStatus
    resolution: Optional[dict[str, Any]]
    resolution_notes: Optional[str]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    auto_resolvable: bool
    suggested_resolution: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ExceptionWithDocument(ExceptionRead):
    """Schema for exception with document details."""
    document_filename: str
    document_type: Optional[str]
    document_status: str


class ExceptionList(BaseModel):
    """Schema for paginated exception list response."""
    items: list[ExceptionWithDocument]
    total: int
    page: int
    page_size: int
    pages: int


class ExceptionFilter(BaseModel):
    """Schema for exception filtering."""
    status: Optional[ExceptionStatus] = None
    category: Optional[ExceptionCategory] = None
    priority: Optional[ExceptionPriority] = None
    document_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ExceptionMetrics(BaseModel):
    """Schema for exception metrics."""
    total_exceptions: int
    open_count: int
    in_review_count: int
    resolved_count: int
    ignored_count: int
    exceptions_by_category: dict[str, int]
    exceptions_by_priority: dict[str, int]
    avg_resolution_time_hours: float
    auto_resolved_count: int
