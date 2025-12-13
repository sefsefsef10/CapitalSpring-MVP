"""Metrics API router for dashboard and analytics."""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case, extract, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import settings
from app.models.document import Document, DocumentStatus
from app.models.exception import Exception as DocumentException, ExceptionStatus
from app.dependencies import require_auth, UserInfo

logger = structlog.get_logger(__name__)


def is_sqlite() -> bool:
    """Check if we're using SQLite."""
    return settings.database_url.startswith("sqlite")


def date_trunc_expr(granularity: str, column):
    """
    Create a date truncation expression that works with both SQLite and PostgreSQL.

    Args:
        granularity: 'day', 'week', or 'month'
        column: The datetime column to truncate

    Returns:
        SQLAlchemy expression for date truncation
    """
    if is_sqlite():
        # SQLite uses strftime for date manipulation
        if granularity == "day":
            return func.date(column)
        elif granularity == "week":
            # SQLite: Get the Monday of the week (ISO week)
            return func.date(column, "weekday 0", "-6 days")
        else:  # month
            return func.strftime("%Y-%m-01", column)
    else:
        # PostgreSQL uses date_trunc
        return func.date_trunc(granularity, column)

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=365),
    fund_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Get comprehensive dashboard metrics for the specified time period.
    """
    date_from = datetime.utcnow() - timedelta(days=days)

    # Base document query
    doc_query = select(Document).where(Document.created_at >= date_from)
    if fund_id:
        doc_query = doc_query.where(Document.fund_id == fund_id)

    # Total documents
    total_query = select(func.count()).select_from(doc_query.subquery())
    total_docs = (await db.execute(total_query)).scalar() or 0

    # Documents by status
    status_query = select(
        Document.status,
        func.count().label("count")
    ).where(Document.created_at >= date_from).group_by(Document.status)
    status_result = await db.execute(status_query)
    status_counts = {row.status: row.count for row in status_result}

    # Processed without review (automation rate)
    processed_count = status_counts.get(DocumentStatus.PROCESSED.value, 0)
    needs_review_count = status_counts.get(DocumentStatus.NEEDS_REVIEW.value, 0)
    total_processed = processed_count + needs_review_count
    automation_rate = (processed_count / total_processed * 100) if total_processed > 0 else 0

    # Average confidence
    avg_conf_query = select(func.avg(Document.confidence)).where(
        Document.created_at >= date_from,
        Document.confidence.isnot(None)
    )
    avg_confidence = (await db.execute(avg_conf_query)).scalar() or 0

    # Average processing time
    avg_time_query = select(func.avg(Document.processing_time_ms)).where(
        Document.created_at >= date_from,
        Document.processing_time_ms.isnot(None)
    )
    avg_processing_time = (await db.execute(avg_time_query)).scalar() or 0

    # Documents by type
    type_query = select(
        Document.doc_type,
        func.count().label("count")
    ).where(Document.created_at >= date_from).group_by(Document.doc_type)
    type_result = await db.execute(type_query)
    type_counts = {row.doc_type or "unknown": row.count for row in type_result}

    # Processor usage
    processor_query = select(
        Document.processor_used,
        func.count().label("count")
    ).where(
        Document.created_at >= date_from,
        Document.processor_used.isnot(None)
    ).group_by(Document.processor_used)
    processor_result = await db.execute(processor_query)
    processor_counts = {row.processor_used: row.count for row in processor_result}

    # Open exceptions count
    exc_query = select(func.count()).where(
        DocumentException.status == ExceptionStatus.OPEN.value
    )
    open_exceptions = (await db.execute(exc_query)).scalar() or 0

    return {
        "period_days": days,
        "total_documents": total_docs,
        "documents_by_status": status_counts,
        "automation_rate": round(automation_rate, 2),
        "avg_confidence": round(float(avg_confidence) * 100, 2),  # As percentage
        "avg_processing_time_ms": round(float(avg_processing_time), 0),
        "documents_by_type": type_counts,
        "processor_usage": processor_counts,
        "open_exceptions": open_exceptions,
        "kpis": {
            "processed_count": processed_count,
            "pending_count": status_counts.get(DocumentStatus.PENDING.value, 0),
            "failed_count": status_counts.get(DocumentStatus.FAILED.value, 0),
            "needs_review_count": needs_review_count,
        }
    }


@router.get("/trends")
async def get_trend_metrics(
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Get trend data for charts over the specified time period.
    """
    date_from = datetime.utcnow() - timedelta(days=days)

    # Use cross-database compatible date truncation
    date_trunc = date_trunc_expr(granularity, Document.created_at)

    # Document counts over time
    trend_query = select(
        date_trunc.label("period"),
        func.count().label("total"),
        func.sum(case((Document.status == DocumentStatus.PROCESSED.value, 1), else_=0)).label("processed"),
        func.sum(case((Document.status == DocumentStatus.FAILED.value, 1), else_=0)).label("failed"),
        func.sum(case((Document.status == DocumentStatus.NEEDS_REVIEW.value, 1), else_=0)).label("needs_review"),
    ).where(
        Document.created_at >= date_from
    ).group_by(date_trunc).order_by(date_trunc)

    trend_result = await db.execute(trend_query)
    document_trends = [
        {
            "period": str(row.period) if row.period else None,
            "total": row.total,
            "processed": row.processed or 0,
            "failed": row.failed or 0,
            "needs_review": row.needs_review or 0,
        }
        for row in trend_result
    ]

    # Confidence trend
    conf_trend_query = select(
        date_trunc.label("period"),
        func.avg(Document.confidence).label("avg_confidence"),
    ).where(
        Document.created_at >= date_from,
        Document.confidence.isnot(None)
    ).group_by(date_trunc).order_by(date_trunc)

    conf_result = await db.execute(conf_trend_query)
    confidence_trends = [
        {
            "period": str(row.period) if row.period else None,
            "avg_confidence": round(float(row.avg_confidence or 0) * 100, 2),
        }
        for row in conf_result
    ]

    # Exception trends - use cross-database compatible date truncation
    exc_date_trunc = date_trunc_expr(granularity, DocumentException.created_at)
    exc_trend_query = select(
        exc_date_trunc.label("period"),
        func.count().label("created"),
        func.sum(case((DocumentException.status == ExceptionStatus.RESOLVED.value, 1), else_=0)).label("resolved"),
    ).where(
        DocumentException.created_at >= date_from
    ).group_by(exc_date_trunc).order_by(exc_date_trunc)

    exc_result = await db.execute(exc_trend_query)
    exception_trends = [
        {
            "period": str(row.period) if row.period else None,
            "created": row.created,
            "resolved": row.resolved or 0,
        }
        for row in exc_result
    ]

    return {
        "period_days": days,
        "granularity": granularity,
        "document_trends": document_trends,
        "confidence_trends": confidence_trends,
        "exception_trends": exception_trends,
    }


@router.get("/processing")
async def get_processing_metrics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Get detailed processing performance metrics.
    """
    date_from = datetime.utcnow() - timedelta(days=days)

    # Processing time distribution
    time_buckets = [
        (0, 1000, "< 1s"),
        (1000, 5000, "1-5s"),
        (5000, 10000, "5-10s"),
        (10000, 30000, "10-30s"),
        (30000, 60000, "30-60s"),
        (60000, None, "> 60s"),
    ]

    time_distribution = {}
    for min_ms, max_ms, label in time_buckets:
        query = select(func.count()).where(
            Document.created_at >= date_from,
            Document.processing_time_ms >= min_ms,
        )
        if max_ms:
            query = query.where(Document.processing_time_ms < max_ms)
        count = (await db.execute(query)).scalar() or 0
        time_distribution[label] = count

    # Processor performance
    processor_perf_query = select(
        Document.processor_used,
        func.count().label("count"),
        func.avg(Document.confidence).label("avg_confidence"),
        func.avg(Document.processing_time_ms).label("avg_time_ms"),
    ).where(
        Document.created_at >= date_from,
        Document.processor_used.isnot(None)
    ).group_by(Document.processor_used)

    perf_result = await db.execute(processor_perf_query)
    processor_performance = {
        row.processor_used: {
            "count": row.count,
            "avg_confidence": round(float(row.avg_confidence or 0) * 100, 2),
            "avg_time_ms": round(float(row.avg_time_ms or 0), 0),
        }
        for row in perf_result
    }

    # Failure analysis
    failure_query = select(
        Document.doc_type,
        func.count().label("count"),
    ).where(
        Document.created_at >= date_from,
        Document.status == DocumentStatus.FAILED.value
    ).group_by(Document.doc_type)

    failure_result = await db.execute(failure_query)
    failures_by_type = {row.doc_type or "unknown": row.count for row in failure_result}

    return {
        "period_days": days,
        "processing_time_distribution": time_distribution,
        "processor_performance": processor_performance,
        "failures_by_type": failures_by_type,
    }
