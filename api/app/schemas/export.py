"""Pydantic schemas for Export API."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    """Export file format options."""
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


class ExportTemplate(str, Enum):
    """Available export templates."""
    PORTFOLIO_FINANCIALS = "portfolio_financials"
    COVENANT_COMPLIANCE = "covenant_compliance"
    BORROWING_BASE = "borrowing_base"
    CAPITAL_ACTIVITY = "capital_activity"
    EXCEPTION_REPORT = "exception_report"
    CUSTOM = "custom"


class ExportRequest(BaseModel):
    """Schema for export request."""
    document_ids: list[UUID] = Field(..., min_length=1)
    template: ExportTemplate = ExportTemplate.CUSTOM
    format: ExportFormat = ExportFormat.XLSX
    include_raw_data: bool = False
    include_confidence_scores: bool = False
    custom_fields: Optional[list[str]] = None  # Specific fields to include


class ExportResponse(BaseModel):
    """Schema for export response."""
    export_id: UUID
    status: str  # pending, processing, completed, failed
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    file_name: str
    file_size_bytes: Optional[int] = None
    document_count: int
    created_at: datetime


class BulkExportRequest(BaseModel):
    """Schema for bulk export with filters."""
    template: ExportTemplate
    format: ExportFormat = ExportFormat.XLSX

    # Filters
    doc_type: Optional[str] = None
    fund_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: Optional[str] = None

    # Options
    include_raw_data: bool = False
    include_confidence_scores: bool = False


class TemplateConfig(BaseModel):
    """Schema for export template configuration."""
    template: ExportTemplate
    name: str
    description: str
    supported_doc_types: list[str]
    default_fields: list[str]
    available_fields: list[str]
    supports_multi_document: bool = True
