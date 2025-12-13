"""Document API router."""

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document import (
    DocumentFilter,
    DocumentList,
    DocumentMetrics,
    DocumentRead,
    DocumentUpdate,
    DocumentUploadResponse,
)
from app.services.storage import StorageService
from app.services.processor import DocumentProcessor
from app.dependencies import require_auth, UserInfo

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    fund_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentUploadResponse:
    """
    Upload a document for processing.

    The document will be uploaded to Cloud Storage and queued for processing.
    """
    logger.info("Uploading document", filename=file.filename, content_type=file.content_type)

    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "image/png",
        "image/jpeg",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}",
        )

    try:
        # Upload to GCS
        storage = StorageService()
        gcs_path = await storage.upload_file(file)

        # Get file size
        await file.seek(0)
        content = await file.read()
        file_size = len(content)

        # Create document record
        document = Document(
            id=uuid.uuid4(),
            gcs_path=gcs_path,
            original_filename=file.filename or "unknown",
            mime_type=file.content_type,
            file_size_bytes=file_size,
            status=DocumentStatus.PENDING.value,
            fund_id=fund_id,
            company_id=company_id,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        logger.info("Document uploaded", document_id=str(document.id), gcs_path=gcs_path)

        return DocumentUploadResponse(
            document_id=document.id,
            gcs_path=gcs_path,
            status="pending",
            message="Document uploaded successfully and queued for processing",
        )

    except Exception as e:
        logger.error("Failed to upload document", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )


@router.get("", response_model=DocumentList)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[DocumentStatus] = None,
    doc_type: Optional[DocumentType] = None,
    fund_id: Optional[uuid.UUID] = None,
    company_id: Optional[uuid.UUID] = None,
    requires_review: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentList:
    """
    List documents with filtering and pagination.
    """
    # Build query
    query = select(Document)

    # Apply filters
    if status:
        query = query.where(Document.status == status.value)
    if doc_type:
        query = query.where(Document.doc_type == doc_type.value)
    if fund_id:
        query = query.where(Document.fund_id == fund_id)
    if company_id:
        query = query.where(Document.company_id == company_id)
    if requires_review is not None:
        query = query.where(Document.requires_review == requires_review)
    if date_from:
        query = query.where(Document.created_at >= date_from)
    if date_to:
        query = query.where(Document.created_at <= date_to)
    if search:
        query = query.where(Document.original_filename.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentList(
        items=[DocumentRead.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/metrics", response_model=DocumentMetrics)
async def get_document_metrics(
    fund_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentMetrics:
    """
    Get document processing metrics.
    """
    # Build base query
    base_query = select(Document)
    if fund_id:
        base_query = base_query.where(Document.fund_id == fund_id)
    if date_from:
        base_query = base_query.where(Document.created_at >= date_from)
    if date_to:
        base_query = base_query.where(Document.created_at <= date_to)

    # Get total count
    total_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(total_query)).scalar() or 0

    # Get counts by status
    status_counts = {}
    for s in DocumentStatus:
        status_query = base_query.where(Document.status == s.value)
        count_query = select(func.count()).select_from(status_query.subquery())
        status_counts[s.value] = (await db.execute(count_query)).scalar() or 0

    # Get counts by type
    type_query = select(Document.doc_type, func.count()).group_by(Document.doc_type)
    type_result = await db.execute(type_query)
    type_counts = {row[0] or "unknown": row[1] for row in type_result}

    # Get processor usage
    processor_query = select(Document.processor_used, func.count()).group_by(Document.processor_used)
    processor_result = await db.execute(processor_query)
    processor_counts = {row[0] or "none": row[1] for row in processor_result}

    # Calculate averages
    avg_query = select(
        func.avg(Document.confidence),
        func.avg(Document.processing_time_ms),
    ).where(Document.status == DocumentStatus.PROCESSED.value)
    avg_result = await db.execute(avg_query)
    avg_row = avg_result.first()
    avg_confidence = float(avg_row[0] or 0) if avg_row else 0
    avg_processing_time = float(avg_row[1] or 0) if avg_row else 0

    # Calculate automation rate
    processed_without_review = status_counts.get(DocumentStatus.PROCESSED.value, 0)
    total_processed = processed_without_review + status_counts.get(DocumentStatus.NEEDS_REVIEW.value, 0)
    automation_rate = (processed_without_review / total_processed * 100) if total_processed > 0 else 0

    return DocumentMetrics(
        total_documents=total,
        processed_count=status_counts.get(DocumentStatus.PROCESSED.value, 0),
        pending_count=status_counts.get(DocumentStatus.PENDING.value, 0),
        failed_count=status_counts.get(DocumentStatus.FAILED.value, 0),
        needs_review_count=status_counts.get(DocumentStatus.NEEDS_REVIEW.value, 0),
        automation_rate=automation_rate,
        avg_confidence=avg_confidence,
        avg_processing_time_ms=avg_processing_time,
        documents_by_type=type_counts,
        documents_by_status=status_counts,
        processor_usage=processor_counts,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentRead:
    """
    Get a specific document by ID.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    return DocumentRead.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: uuid.UUID,
    update: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentRead:
    """
    Update document extracted data or status.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(document, field):
            setattr(document, field, value.value if hasattr(value, "value") else value)

    await db.commit()
    await db.refresh(document)

    logger.info("Document updated", document_id=str(document_id), updates=list(update_data.keys()))

    return DocumentRead.model_validate(document)


@router.post("/{document_id}/reprocess", response_model=DocumentRead)
async def reprocess_document(
    document_id: uuid.UUID,
    force_claude: bool = False,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> DocumentRead:
    """
    Trigger reprocessing of a document.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Reset status and trigger reprocessing
    document.status = DocumentStatus.PENDING.value
    document.processing_error = None
    await db.commit()

    # Trigger async processing
    processor = DocumentProcessor()
    await processor.process_document(document_id, force_claude=force_claude)

    await db.refresh(document)
    logger.info("Document reprocessing triggered", document_id=str(document_id))

    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> None:
    """
    Delete a document and its associated data.
    """
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Delete from GCS
    try:
        storage = StorageService()
        await storage.delete_file(document.gcs_path)
    except Exception as e:
        logger.warning("Failed to delete file from GCS", error=str(e), gcs_path=document.gcs_path)

    # Delete from database (cascades to exceptions and audit logs)
    await db.delete(document)
    await db.commit()

    logger.info("Document deleted", document_id=str(document_id))
