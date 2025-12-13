"""Document processor service - main orchestration."""

import time
import uuid
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session_maker
from app.models.document import Document, DocumentStatus, DocumentType, ProcessorType
from app.models.exception import Exception as DocumentException, ExceptionCategory, ExceptionPriority
from app.models.audit import AuditLog, AuditAction
from app.services.storage import StorageService
from app.services.document_ai import DocumentAIService
from app.services.claude_ai import ClaudeService
from app.services.validation import ValidationService

logger = structlog.get_logger(__name__)


class DocumentProcessor:
    """Main document processing orchestrator."""

    def __init__(self):
        """Initialize processor with required services."""
        self.storage = StorageService()
        self.document_ai = DocumentAIService()
        self.claude = ClaudeService()
        self.validation = ValidationService()
        self.confidence_threshold = settings.processing_confidence_threshold

    async def process_document(
        self,
        document_id: uuid.UUID,
        force_claude: bool = False,
    ) -> None:
        """
        Process a document through the full pipeline.

        Args:
            document_id: UUID of the document to process
            force_claude: Skip Document AI and use Claude directly
        """
        start_time = time.time()

        async with async_session_maker() as db:
            # Fetch document
            query = select(Document).where(Document.id == document_id)
            result = await db.execute(query)
            document = result.scalar_one_or_none()

            if not document:
                logger.error("Document not found", document_id=str(document_id))
                return

            logger.info(
                "Starting document processing",
                document_id=str(document_id),
                filename=document.original_filename,
            )

            try:
                # Update status to processing
                document.status = DocumentStatus.PROCESSING.value
                await db.commit()

                # Log processing started
                await self._log_audit(
                    db,
                    document_id,
                    AuditAction.DOCUMENT_PROCESSING_STARTED,
                    {"filename": document.original_filename},
                )

                # Download file from GCS
                content = await self.storage.download_file(document.gcs_path)

                # Process document
                if force_claude:
                    # Use Claude directly
                    extracted_data, confidence, field_confidences, processor_type = (
                        await self._process_with_claude(content, document)
                    )
                else:
                    # Try Document AI first
                    extracted_data, confidence, field_confidences, processor_type = (
                        await self._process_with_document_ai(content, document)
                    )

                    # Fall back to Claude if confidence is low
                    if confidence < self.confidence_threshold:
                        logger.info(
                            "Low confidence, falling back to Claude",
                            document_id=str(document_id),
                            confidence=confidence,
                        )

                        await self._log_audit(
                            db,
                            document_id,
                            AuditAction.EXTRACTION_FALLBACK,
                            {"original_confidence": confidence, "processor": processor_type.value},
                        )

                        claude_data, claude_conf, claude_field_conf, _ = (
                            await self._process_with_claude(content, document)
                        )

                        # Use Claude results if better
                        if claude_conf > confidence:
                            extracted_data = claude_data
                            confidence = claude_conf
                            field_confidences = claude_field_conf
                            processor_type = ProcessorType.CLAUDE

                # Detect document type if not set
                if not document.doc_type or document.doc_type == DocumentType.UNKNOWN.value:
                    doc_type = await self._detect_document_type(
                        content, document.original_filename
                    )
                    document.doc_type = doc_type.value
                else:
                    doc_type = DocumentType(document.doc_type)

                # Validate extracted data
                validation_result = self.validation.validate(extracted_data, doc_type)

                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)

                # Update document
                document.extracted_data = extracted_data
                document.confidence = confidence
                document.field_confidences = field_confidences
                document.processor_used = processor_type.value
                document.processing_time_ms = processing_time_ms
                document.processed_at = datetime.utcnow()

                # Determine final status based on validation
                if not validation_result.is_valid:
                    document.status = DocumentStatus.NEEDS_REVIEW.value
                    document.requires_review = True

                    # Create exceptions for validation errors
                    for error in validation_result.errors:
                        exception = DocumentException(
                            document_id=document_id,
                            category=error.category.value,
                            reason=error.message,
                            field_name=error.field,
                            expected_value=error.expected,
                            actual_value=error.actual,
                            priority=error.priority.value,
                        )
                        db.add(exception)

                    logger.info(
                        "Document needs review",
                        document_id=str(document_id),
                        error_count=len(validation_result.errors),
                    )
                elif confidence < self.confidence_threshold:
                    document.status = DocumentStatus.NEEDS_REVIEW.value
                    document.requires_review = True

                    # Create low confidence exception
                    exception = DocumentException(
                        document_id=document_id,
                        category=ExceptionCategory.LOW_CONFIDENCE.value,
                        reason=f"Overall extraction confidence ({confidence:.2%}) below threshold ({self.confidence_threshold:.2%})",
                        priority=ExceptionPriority.MEDIUM.value,
                    )
                    db.add(exception)

                    logger.info(
                        "Document has low confidence",
                        document_id=str(document_id),
                        confidence=confidence,
                    )
                else:
                    document.status = DocumentStatus.PROCESSED.value
                    document.requires_review = False

                    # Move file to complete folder
                    new_path = await self.storage.move_file(
                        document.gcs_path,
                        settings.gcs_complete_prefix,
                    )
                    document.gcs_path = new_path

                await db.commit()

                # Log completion
                await self._log_audit(
                    db,
                    document_id,
                    AuditAction.DOCUMENT_PROCESSED,
                    {
                        "status": document.status,
                        "confidence": confidence,
                        "processor": processor_type.value,
                        "processing_time_ms": processing_time_ms,
                        "validation_errors": len(validation_result.errors),
                    },
                )

                logger.info(
                    "Document processing complete",
                    document_id=str(document_id),
                    status=document.status,
                    confidence=confidence,
                    processing_time_ms=processing_time_ms,
                )

            except Exception as e:
                logger.error(
                    "Document processing failed",
                    document_id=str(document_id),
                    error=str(e),
                )

                # Update document with error
                document.status = DocumentStatus.FAILED.value
                document.processing_error = str(e)
                document.processing_time_ms = int((time.time() - start_time) * 1000)

                # Move to failed folder
                try:
                    new_path = await self.storage.move_file(
                        document.gcs_path,
                        settings.gcs_failed_prefix,
                    )
                    document.gcs_path = new_path
                except Exception:
                    pass

                await db.commit()

                # Create processing failure exception
                exception = DocumentException(
                    document_id=document_id,
                    category=ExceptionCategory.PROCESSING_FAILURE.value,
                    reason=f"Processing failed: {str(e)}",
                    priority=ExceptionPriority.CRITICAL.value,
                )
                db.add(exception)
                await db.commit()

                # Log failure
                await self._log_audit(
                    db,
                    document_id,
                    AuditAction.DOCUMENT_FAILED,
                    {"error": str(e)},
                )

    async def _process_with_document_ai(
        self,
        content: bytes,
        document: Document,
    ) -> tuple:
        """Process document using Document AI."""
        doc_type = DocumentType(document.doc_type) if document.doc_type else None

        return await self.document_ai.process_document(
            content=content,
            mime_type=document.mime_type or "application/pdf",
            filename=document.original_filename,
            doc_type=doc_type,
        )

    async def _process_with_claude(
        self,
        content: bytes,
        document: Document,
    ) -> tuple:
        """Process document using Claude (requires text extraction first)."""
        # For Claude, we need text content
        # First try to get text from Document AI OCR
        doc_type = DocumentType(document.doc_type) if document.doc_type else None

        # Use Document AI for OCR to get text
        ocr_result = await self.document_ai.process_document(
            content=content,
            mime_type=document.mime_type or "application/pdf",
            filename=document.original_filename,
            doc_type=None,  # Force OCR
        )

        text_content = ocr_result[0].get("text", "")

        if not text_content:
            # If no text, return empty result
            return {}, 0.0, {}, ProcessorType.CLAUDE

        # Use Claude for extraction
        return await self.claude.extract_document_data(
            text_content=text_content,
            doc_type=doc_type,
            filename=document.original_filename,
        )

    async def _detect_document_type(
        self,
        content: bytes,
        filename: str,
    ) -> DocumentType:
        """Detect document type using filename patterns or Claude."""
        # Try filename patterns first
        detected = self.document_ai._detect_document_type(filename)
        if detected:
            return detected

        # Fall back to Claude for detection
        # Get text content first
        ocr_result = await self.document_ai.process_document(
            content=content,
            mime_type="application/pdf",
            filename=filename,
            doc_type=None,
        )

        text_content = ocr_result[0].get("text", "")
        if text_content:
            return await self.claude.detect_document_type(text_content, filename)

        return DocumentType.UNKNOWN

    async def _log_audit(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
        action: AuditAction,
        details: dict,
    ) -> None:
        """Log an audit entry."""
        audit_log = AuditLog(
            document_id=document_id,
            action=action.value,
            actor="system",
            actor_type="system",
            details=details,
        )
        db.add(audit_log)
        await db.commit()
