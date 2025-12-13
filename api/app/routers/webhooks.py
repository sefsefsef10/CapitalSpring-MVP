"""Webhook API router for Pub/Sub and external integrations."""

import base64
import json
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.services.processor import DocumentProcessor
from app.dependencies import require_auth, UserInfo

logger = structlog.get_logger(__name__)

router = APIRouter()


class PubSubMessage(BaseModel):
    """Pub/Sub push message format."""
    message: dict
    subscription: str


class GCSNotification(BaseModel):
    """GCS object notification payload."""
    kind: str
    id: str
    selfLink: Optional[str] = None
    name: str  # Object name (path)
    bucket: str
    generation: Optional[str] = None
    metageneration: Optional[str] = None
    contentType: Optional[str] = None
    timeCreated: Optional[str] = None
    updated: Optional[str] = None
    size: Optional[str] = None
    md5Hash: Optional[str] = None


@router.post("/pubsub/document-uploaded")
async def handle_document_uploaded(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Handle Pub/Sub push notification when a document is uploaded to GCS.

    This endpoint is triggered by Cloud Storage notifications via Pub/Sub.
    """
    try:
        # Parse the Pub/Sub message
        body = await request.json()
        logger.debug("Received Pub/Sub message", body=body)

        # Extract and decode the message data
        message_data = body.get("message", {}).get("data", "")
        if message_data:
            decoded_data = base64.b64decode(message_data).decode("utf-8")
            notification = json.loads(decoded_data)
        else:
            notification = body.get("message", {}).get("attributes", {})

        logger.info(
            "Processing GCS notification",
            bucket=notification.get("bucket") or notification.get("bucketId"),
            object_name=notification.get("name") or notification.get("objectId"),
        )

        # Extract relevant information
        bucket_name = notification.get("bucket") or notification.get("bucketId")
        object_name = notification.get("name") or notification.get("objectId")
        content_type = notification.get("contentType")
        size = notification.get("size")

        if not object_name:
            logger.warning("No object name in notification")
            return {"status": "ignored", "reason": "no object name"}

        # Only process files in the inbox
        if not object_name.startswith(settings.gcs_inbox_prefix):
            logger.info("Ignoring file outside inbox", object_name=object_name)
            return {"status": "ignored", "reason": "not in inbox"}

        # Check if document already exists
        gcs_path = f"gs://{bucket_name}/{object_name}"
        existing_query = select(Document).where(Document.gcs_path == gcs_path)
        existing = (await db.execute(existing_query)).scalar_one_or_none()

        if existing:
            logger.info("Document already exists", document_id=str(existing.id))
            return {"status": "exists", "document_id": str(existing.id)}

        # Create document record
        filename = object_name.split("/")[-1]
        document = Document(
            id=uuid.uuid4(),
            gcs_path=gcs_path,
            original_filename=filename,
            mime_type=content_type,
            file_size_bytes=int(size) if size else None,
            status=DocumentStatus.PENDING.value,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        logger.info(
            "Document record created",
            document_id=str(document.id),
            filename=filename,
        )

        # Queue background processing
        background_tasks.add_task(
            process_document_task,
            document_id=document.id,
        )

        return {
            "status": "accepted",
            "document_id": str(document.id),
            "message": "Document queued for processing",
        }

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Pub/Sub message", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message format",
        )
    except Exception as e:
        logger.error("Failed to handle Pub/Sub notification", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


async def process_document_task(document_id: uuid.UUID) -> None:
    """Background task to process a document."""
    processor = DocumentProcessor()
    try:
        await processor.process_document(document_id)
        logger.info("Document processing completed", document_id=str(document_id))
    except Exception as e:
        logger.error(
            "Document processing failed",
            document_id=str(document_id),
            error=str(e),
        )


@router.post("/pubsub/document-processed")
async def handle_document_processed(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Pub/Sub notification when document processing is complete.

    This can be used for downstream integrations (e.g., notifications, BigQuery).
    """
    try:
        body = await request.json()
        message_data = body.get("message", {}).get("data", "")

        if message_data:
            decoded_data = base64.b64decode(message_data).decode("utf-8")
            payload = json.loads(decoded_data)
        else:
            payload = body.get("message", {}).get("attributes", {})

        document_id = payload.get("document_id")
        status = payload.get("status")

        logger.info(
            "Document processed notification",
            document_id=document_id,
            status=status,
        )

        # Could trigger additional actions here:
        # - Send to BigQuery for analytics
        # - Send email notification
        # - Update external systems

        return {"status": "acknowledged"}

    except Exception as e:
        logger.error("Failed to handle processed notification", error=str(e))
        return {"status": "error", "message": str(e)}


@router.post("/manual-trigger/{document_id}")
async def manual_trigger_processing(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    force_claude: bool = False,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(require_auth),
) -> dict:
    """
    Manually trigger processing for a specific document.

    Useful for reprocessing or testing.
    """
    # Verify document exists
    query = select(Document).where(Document.id == document_id)
    document = (await db.execute(query)).scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Update status to pending
    document.status = DocumentStatus.PENDING.value
    document.processing_error = None
    await db.commit()

    # Queue processing
    background_tasks.add_task(
        process_document_task,
        document_id=document_id,
    )

    return {
        "status": "queued",
        "document_id": str(document_id),
        "message": "Document queued for processing",
    }
