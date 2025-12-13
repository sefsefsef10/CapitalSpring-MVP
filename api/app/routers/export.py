"""Export API router."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import Document
from app.schemas.export import (
    BulkExportRequest,
    ExportFormat,
    ExportRequest,
    ExportResponse,
    ExportTemplate,
    TemplateConfig,
)
from app.services.export import ExportService
from app.dependencies import require_auth, UserInfo

logger = structlog.get_logger(__name__)

router = APIRouter()


# Template configurations
TEMPLATE_CONFIGS = {
    ExportTemplate.PORTFOLIO_FINANCIALS: TemplateConfig(
        template=ExportTemplate.PORTFOLIO_FINANCIALS,
        name="Portfolio Company Financial Summary",
        description="Financial summary with P&L, Balance Sheet, and key metrics",
        supported_doc_types=["monthly_financials", "quarterly_financials", "annual_financials"],
        default_fields=[
            "company_name", "period_end_date", "revenue", "gross_profit",
            "ebitda", "net_income", "total_assets", "total_liabilities",
        ],
        available_fields=[
            "company_name", "period_end_date", "period_type", "revenue",
            "revenue_growth_yoy", "gross_profit", "gross_margin", "ebitda",
            "ebitda_margin", "net_income", "total_assets", "total_liabilities",
            "total_equity", "cash_and_equivalents", "total_debt", "capex",
            "working_capital",
        ],
    ),
    ExportTemplate.COVENANT_COMPLIANCE: TemplateConfig(
        template=ExportTemplate.COVENANT_COMPLIANCE,
        name="Covenant Compliance Report",
        description="Covenant compliance status and calculations",
        supported_doc_types=["covenant_compliance", "covenant_calculations"],
        default_fields=[
            "company_name", "reporting_period", "leverage_ratio",
            "interest_coverage_ratio", "overall_compliance",
        ],
        available_fields=[
            "company_name", "reporting_period", "leverage_ratio", "leverage_covenant",
            "leverage_compliant", "interest_coverage_ratio", "coverage_covenant",
            "coverage_compliant", "fixed_charge_coverage", "fcc_covenant",
            "fcc_compliant", "minimum_liquidity", "liquidity_covenant",
            "liquidity_compliant", "capex_actual", "capex_limit", "capex_compliant",
            "overall_compliance", "cure_required", "cure_amount",
        ],
    ),
    ExportTemplate.BORROWING_BASE: TemplateConfig(
        template=ExportTemplate.BORROWING_BASE,
        name="Borrowing Base Certificate",
        description="BBC summary with AR, Inventory, and availability",
        supported_doc_types=["borrowing_base", "ar_aging", "inventory_report"],
        default_fields=[
            "company_name", "certificate_date", "eligible_ar", "eligible_inventory",
            "total_availability", "excess_availability",
        ],
        available_fields=[
            "company_name", "certificate_date", "gross_accounts_receivable",
            "ineligible_ar", "eligible_ar", "ar_advance_rate", "ar_availability",
            "gross_inventory", "ineligible_inventory", "eligible_inventory",
            "inventory_advance_rate", "inventory_availability", "total_availability",
            "outstanding_loans", "outstanding_lcs", "excess_availability",
            "minimum_availability_covenant", "availability_compliant",
        ],
    ),
    ExportTemplate.CAPITAL_ACTIVITY: TemplateConfig(
        template=ExportTemplate.CAPITAL_ACTIVITY,
        name="Capital Activity Report",
        description="Capital calls and distributions summary",
        supported_doc_types=["capital_call", "distribution_notice"],
        default_fields=[
            "notice_date", "due_date", "call_amount", "call_purpose",
            "cumulative_called",
        ],
        available_fields=[
            "notice_date", "due_date", "call_number", "call_amount",
            "call_purpose", "cumulative_called", "remaining_commitment",
            "investor_allocations",
        ],
    ),
    ExportTemplate.EXCEPTION_REPORT: TemplateConfig(
        template=ExportTemplate.EXCEPTION_REPORT,
        name="Exception Report",
        description="Summary of processing exceptions",
        supported_doc_types=[],  # Works with all types
        default_fields=[
            "document_name", "exception_category", "reason", "status", "created_at",
        ],
        available_fields=[
            "document_name", "document_type", "exception_category", "reason",
            "field_name", "expected_value", "actual_value", "priority",
            "status", "resolution", "resolved_by", "created_at", "resolved_at",
        ],
    ),
}


@router.get("/templates", response_model=list[TemplateConfig])
async def list_templates(
    user: UserInfo = Depends(require_auth),
) -> list[TemplateConfig]:
    """
    Get list of available export templates.
    """
    return list(TEMPLATE_CONFIGS.values())


@router.get("/templates/{template}", response_model=TemplateConfig)
async def get_template(
    template: ExportTemplate,
    user: UserInfo = Depends(require_auth),
) -> TemplateConfig:
    """
    Get configuration for a specific export template.
    """
    if template not in TEMPLATE_CONFIGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template.value} not found",
        )
    return TEMPLATE_CONFIGS[template]


@router.post("/excel", response_model=ExportResponse)
async def export_to_excel(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExportResponse:
    """
    Export selected documents to Excel file.
    """
    # Fetch documents
    query = select(Document).where(Document.id.in_(request.document_ids))
    result = await db.execute(query)
    documents = result.scalars().all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No documents found with the provided IDs",
        )

    # Generate export
    export_service = ExportService()
    export_id = uuid.uuid4()

    try:
        file_path, file_size = await export_service.generate_excel(
            documents=documents,
            template=request.template,
            include_raw_data=request.include_raw_data,
            include_confidence_scores=request.include_confidence_scores,
            custom_fields=request.custom_fields,
        )

        # Generate signed URL for download
        download_url = await export_service.get_download_url(file_path)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        logger.info(
            "Export generated",
            export_id=str(export_id),
            document_count=len(documents),
            template=request.template.value,
        )

        return ExportResponse(
            export_id=export_id,
            status="completed",
            download_url=download_url,
            expires_at=expires_at,
            file_name=f"export_{export_id}.xlsx",
            file_size_bytes=file_size,
            document_count=len(documents),
            created_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error("Export failed", error=str(e), export_id=str(export_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate export: {str(e)}",
        )


@router.post("/bulk", response_model=ExportResponse)
async def bulk_export(
    request: BulkExportRequest,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExportResponse:
    """
    Export documents matching filter criteria.
    """
    # Build query based on filters
    query = select(Document)

    if request.doc_type:
        query = query.where(Document.doc_type == request.doc_type)
    if request.fund_id:
        query = query.where(Document.fund_id == request.fund_id)
    if request.company_id:
        query = query.where(Document.company_id == request.company_id)
    if request.status:
        query = query.where(Document.status == request.status)
    if request.date_from:
        query = query.where(Document.created_at >= request.date_from)
    if request.date_to:
        query = query.where(Document.created_at <= request.date_to)

    result = await db.execute(query)
    documents = result.scalars().all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No documents found matching the criteria",
        )

    # Generate export
    export_service = ExportService()
    export_id = uuid.uuid4()

    try:
        file_path, file_size = await export_service.generate_excel(
            documents=documents,
            template=request.template,
            include_raw_data=request.include_raw_data,
            include_confidence_scores=request.include_confidence_scores,
        )

        download_url = await export_service.get_download_url(file_path)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        logger.info(
            "Bulk export generated",
            export_id=str(export_id),
            document_count=len(documents),
        )

        return ExportResponse(
            export_id=export_id,
            status="completed",
            download_url=download_url,
            expires_at=expires_at,
            file_name=f"bulk_export_{export_id}.xlsx",
            file_size_bytes=file_size,
            document_count=len(documents),
            created_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error("Bulk export failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate export: {str(e)}",
        )


@router.get("/download/{export_id}")
async def download_export(
    export_id: uuid.UUID,
    user: UserInfo = Depends(require_auth),
) -> StreamingResponse:
    """
    Download a generated export file.
    """
    export_service = ExportService()

    try:
        file_stream, filename, content_type = await export_service.get_file_stream(export_id)

        return StreamingResponse(
            file_stream,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export {export_id} not found or has expired",
        )
