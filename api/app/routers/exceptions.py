"""Exception API router."""

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.document import Document
from app.models.exception import Exception as DocumentException, ExceptionStatus, ExceptionCategory, ExceptionPriority
from app.models.audit import AuditLog, AuditAction
from app.schemas.exception import (
    ExceptionList,
    ExceptionMetrics,
    ExceptionRead,
    ExceptionResolve,
    ExceptionUpdate,
    ExceptionWithDocument,
)
from app.dependencies import require_auth, UserInfo

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("", response_model=ExceptionList)
async def list_exceptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[ExceptionStatus] = None,
    category: Optional[ExceptionCategory] = None,
    priority: Optional[ExceptionPriority] = None,
    document_id: Optional[uuid.UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionList:
    """
    List exceptions with filtering and pagination.
    """
    # Build query with document relationship
    query = select(DocumentException).options(selectinload(DocumentException.document))

    # Apply filters
    if status:
        query = query.where(DocumentException.status == status.value)
    if category:
        query = query.where(DocumentException.category == category.value)
    if priority:
        query = query.where(DocumentException.priority == priority.value)
    if document_id:
        query = query.where(DocumentException.document_id == document_id)
    if date_from:
        query = query.where(DocumentException.created_at >= date_from)
    if date_to:
        query = query.where(DocumentException.created_at <= date_to)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering (priority desc, then created_at desc)
    query = query.order_by(
        DocumentException.priority.desc(),
        DocumentException.created_at.desc(),
    )
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    exceptions = result.scalars().all()

    # Build response with document details
    items = []
    for exc in exceptions:
        items.append(
            ExceptionWithDocument(
                **ExceptionRead.model_validate(exc).model_dump(),
                document_filename=exc.document.original_filename if exc.document else "Unknown",
                document_type=exc.document.doc_type if exc.document else None,
                document_status=exc.document.status if exc.document else "unknown",
            )
        )

    return ExceptionList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/metrics", response_model=ExceptionMetrics)
async def get_exception_metrics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionMetrics:
    """
    Get exception metrics and statistics.
    """
    # Build base query
    base_query = select(DocumentException)
    if date_from:
        base_query = base_query.where(DocumentException.created_at >= date_from)
    if date_to:
        base_query = base_query.where(DocumentException.created_at <= date_to)

    # Get total count
    total_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(total_query)).scalar() or 0

    # Get counts by status
    status_counts = {}
    for s in ExceptionStatus:
        status_query = base_query.where(DocumentException.status == s.value)
        count_query = select(func.count()).select_from(status_query.subquery())
        status_counts[s.value] = (await db.execute(count_query)).scalar() or 0

    # Get counts by category
    category_query = select(
        DocumentException.category, func.count()
    ).group_by(DocumentException.category)
    category_result = await db.execute(category_query)
    category_counts = {row[0]: row[1] for row in category_result}

    # Get counts by priority
    priority_query = select(
        DocumentException.priority, func.count()
    ).group_by(DocumentException.priority)
    priority_result = await db.execute(priority_query)
    priority_counts = {row[0]: row[1] for row in priority_result}

    # Calculate average resolution time for resolved exceptions
    resolution_time_query = select(
        func.avg(
            func.extract("epoch", DocumentException.resolved_at) -
            func.extract("epoch", DocumentException.created_at)
        ) / 3600  # Convert to hours
    ).where(DocumentException.status == ExceptionStatus.RESOLVED.value)
    resolution_result = await db.execute(resolution_time_query)
    avg_resolution_hours = resolution_result.scalar() or 0

    # Count auto-resolved
    auto_resolved_query = base_query.where(
        DocumentException.auto_resolvable == True,
        DocumentException.status == ExceptionStatus.RESOLVED.value,
    )
    auto_resolved_count_query = select(func.count()).select_from(auto_resolved_query.subquery())
    auto_resolved = (await db.execute(auto_resolved_count_query)).scalar() or 0

    return ExceptionMetrics(
        total_exceptions=total,
        open_count=status_counts.get(ExceptionStatus.OPEN.value, 0),
        in_review_count=status_counts.get(ExceptionStatus.IN_REVIEW.value, 0),
        resolved_count=status_counts.get(ExceptionStatus.RESOLVED.value, 0),
        ignored_count=status_counts.get(ExceptionStatus.IGNORED.value, 0),
        exceptions_by_category=category_counts,
        exceptions_by_priority=priority_counts,
        avg_resolution_time_hours=float(avg_resolution_hours),
        auto_resolved_count=auto_resolved,
    )


@router.get("/{exception_id}", response_model=ExceptionWithDocument)
async def get_exception(
    exception_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionWithDocument:
    """
    Get a specific exception by ID with document details.
    """
    query = select(DocumentException).options(
        selectinload(DocumentException.document)
    ).where(DocumentException.id == exception_id)

    result = await db.execute(query)
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found",
        )

    return ExceptionWithDocument(
        **ExceptionRead.model_validate(exception).model_dump(),
        document_filename=exception.document.original_filename if exception.document else "Unknown",
        document_type=exception.document.doc_type if exception.document else None,
        document_status=exception.document.status if exception.document else "unknown",
    )


@router.patch("/{exception_id}", response_model=ExceptionRead)
async def update_exception(
    exception_id: uuid.UUID,
    update: ExceptionUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionRead:
    """
    Update an exception's status or priority.
    """
    query = select(DocumentException).where(DocumentException.id == exception_id)
    result = await db.execute(query)
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found",
        )

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(exception, field):
            setattr(exception, field, value.value if hasattr(value, "value") else value)

    await db.commit()
    await db.refresh(exception)

    logger.info("Exception updated", exception_id=str(exception_id), updates=list(update_data.keys()))

    return ExceptionRead.model_validate(exception)


@router.post("/{exception_id}/resolve", response_model=ExceptionRead)
async def resolve_exception(
    exception_id: uuid.UUID,
    resolution: ExceptionResolve,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionRead:
    """
    Resolve an exception with the provided resolution data.
    """
    query = select(DocumentException).options(
        selectinload(DocumentException.document)
    ).where(DocumentException.id == exception_id)

    result = await db.execute(query)
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found",
        )

    if exception.status == ExceptionStatus.RESOLVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exception is already resolved",
        )

    # Update exception
    exception.status = ExceptionStatus.RESOLVED.value
    exception.resolution = resolution.resolution
    exception.resolution_notes = resolution.resolution_notes
    exception.resolved_by = resolution.resolved_by
    exception.resolved_at = datetime.utcnow()

    # Optionally update the document with resolution data
    if resolution.apply_to_document and exception.document:
        if exception.field_name and exception.document.extracted_data:
            # Update the specific field in extracted data
            extracted_data = dict(exception.document.extracted_data)
            if exception.field_name in resolution.resolution:
                extracted_data[exception.field_name] = resolution.resolution[exception.field_name]
            exception.document.extracted_data = extracted_data

    # Create audit log entry
    audit_entry = AuditLog(
        document_id=exception.document_id,
        action=AuditAction.EXCEPTION_RESOLVED.value,
        actor=user.email or user.uid,
        actor_type="user",
        details={
            "exception_id": str(exception_id),
            "exception_type": exception.exception_type,
            "category": exception.category,
            "resolution": resolution.resolution,
            "resolution_notes": resolution.resolution_notes,
            "apply_to_document": resolution.apply_to_document,
        },
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(exception)

    logger.info(
        "Exception resolved",
        exception_id=str(exception_id),
        resolved_by=resolution.resolved_by,
    )

    return ExceptionRead.model_validate(exception)


@router.post("/{exception_id}/ignore", response_model=ExceptionRead)
async def ignore_exception(
    exception_id: uuid.UUID,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> ExceptionRead:
    """
    Mark an exception as ignored.
    """
    query = select(DocumentException).where(DocumentException.id == exception_id)
    result = await db.execute(query)
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found",
        )

    exception.status = ExceptionStatus.IGNORED.value
    exception.resolution_notes = reason or "Ignored by user"
    exception.resolved_by = user.email or user.uid
    exception.resolved_at = datetime.utcnow()

    # Create audit log entry
    audit_entry = AuditLog(
        document_id=exception.document_id,
        action=AuditAction.EXCEPTION_IGNORED.value,
        actor=user.email or user.uid,
        actor_type="user",
        details={
            "exception_id": str(exception_id),
            "exception_type": exception.exception_type,
            "category": exception.category,
            "reason": reason or "Ignored by user",
        },
    )
    db.add(audit_entry)

    await db.commit()
    await db.refresh(exception)

    logger.info("Exception ignored", exception_id=str(exception_id), ignored_by=user.email or user.uid)

    return ExceptionRead.model_validate(exception)


@router.post("/bulk-resolve", response_model=dict)
async def bulk_resolve_exceptions(
    exception_ids: list[uuid.UUID],
    resolution: ExceptionResolve,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Resolve multiple exceptions at once.
    """
    resolved_count = 0
    failed_ids = []
    resolved_by = user.email or user.uid

    for exc_id in exception_ids:
        query = select(DocumentException).where(DocumentException.id == exc_id)
        result = await db.execute(query)
        exception = result.scalar_one_or_none()

        if exception and exception.status != ExceptionStatus.RESOLVED.value:
            exception.status = ExceptionStatus.RESOLVED.value
            exception.resolution = resolution.resolution
            exception.resolution_notes = resolution.resolution_notes
            exception.resolved_by = resolved_by
            exception.resolved_at = datetime.utcnow()
            resolved_count += 1

            # Create audit log entry for each resolved exception
            audit_entry = AuditLog(
                document_id=exception.document_id,
                action=AuditAction.EXCEPTION_RESOLVED.value,
                actor=resolved_by,
                actor_type="user",
                details={
                    "exception_id": str(exc_id),
                    "exception_type": exception.exception_type,
                    "category": exception.category,
                    "resolution": resolution.resolution,
                    "resolution_notes": resolution.resolution_notes,
                    "bulk_operation": True,
                },
            )
            db.add(audit_entry)
        else:
            failed_ids.append(str(exc_id))

    await db.commit()

    logger.info(
        "Bulk exception resolution",
        resolved_count=resolved_count,
        failed_count=len(failed_ids),
    )

    return {
        "resolved_count": resolved_count,
        "failed_ids": failed_ids,
        "total_requested": len(exception_ids),
    }
