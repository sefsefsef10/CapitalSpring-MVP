"""Document AI service for document processing (GCP or mock)."""

import os
import re
from typing import Any, Optional, Tuple

import structlog

from app.config import settings
from app.models.document import DocumentType, ProcessorType

logger = structlog.get_logger(__name__)

# Try to import Document AI, use mock if not available
try:
    from google.cloud import documentai_v1 as documentai
    from google.api_core.client_options import ClientOptions
    from google.oauth2 import service_account
    DOCAI_AVAILABLE = True
except ImportError:
    DOCAI_AVAILABLE = False
    logger.warning("Google Document AI not available, using mock service")


# Document type to processor mapping
PROCESSOR_MAP = {
    DocumentType.MONTHLY_FINANCIALS: ("form", settings.document_ai_form_processor_id),
    DocumentType.QUARTERLY_FINANCIALS: ("form", settings.document_ai_form_processor_id),
    DocumentType.ANNUAL_FINANCIALS: ("form", settings.document_ai_form_processor_id),
    DocumentType.COVENANT_COMPLIANCE: ("form", settings.document_ai_form_processor_id),
    DocumentType.BORROWING_BASE: ("form", settings.document_ai_form_processor_id),
    DocumentType.AR_AGING: ("form", settings.document_ai_form_processor_id),
    DocumentType.CAPITAL_CALL: ("invoice", settings.document_ai_invoice_processor_id),
    DocumentType.DISTRIBUTION_NOTICE: ("invoice", settings.document_ai_invoice_processor_id),
    DocumentType.INVOICE: ("invoice", settings.document_ai_invoice_processor_id),
    DocumentType.INSURANCE_CERTIFICATE: ("invoice", settings.document_ai_invoice_processor_id),
    DocumentType.BANK_STATEMENT: ("form", settings.document_ai_form_processor_id),
}

# Filename patterns for document type detection
FILENAME_PATTERNS = {
    DocumentType.MONTHLY_FINANCIALS: [r"monthly.*financial", r"financials.*\d{4}[-_]\d{2}"],
    DocumentType.QUARTERLY_FINANCIALS: [r"quarterly.*financial", r"q[1-4].*financial"],
    DocumentType.ANNUAL_FINANCIALS: [r"annual.*financial", r"audited.*financial", r"fy\d{4}"],
    DocumentType.COVENANT_COMPLIANCE: [r"covenant", r"compliance.*cert"],
    DocumentType.BORROWING_BASE: [r"bbc", r"borrowing.*base", r"bb.*cert"],
    DocumentType.AR_AGING: [r"aging", r"ar.*schedule", r"receivables"],
    DocumentType.INVENTORY_REPORT: [r"inventory"],
    DocumentType.CAPITAL_CALL: [r"capital.*call", r"call.*notice", r"drawdown"],
    DocumentType.DISTRIBUTION_NOTICE: [r"distribution", r"dist.*notice"],
    DocumentType.NAV_STATEMENT: [r"nav", r"net.*asset"],
    DocumentType.INVOICE: [r"invoice", r"bill"],
    DocumentType.BANK_STATEMENT: [r"bank.*statement", r"account.*statement"],
    DocumentType.INSURANCE_CERTIFICATE: [r"insurance", r"coi", r"certificate.*insurance"],
}


class DocumentAIService:
    """Service for Document AI processing (GCP or mock)."""

    def __init__(self):
        """Initialize the Document AI client."""
        # Use real Document AI if: flag is set AND library available AND credentials exist AND processor configured
        has_credentials = settings.google_application_credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        has_processor = settings.document_ai_form_processor_id or settings.document_ai_ocr_processor_id
        use_real = settings.use_gcp and DOCAI_AVAILABLE and has_credentials and has_processor
        self.use_mock = not use_real

        if self.use_mock:
            logger.info("Using mock Document AI service")
            self.client = None
        else:
            client_options = ClientOptions(
                api_endpoint=f"{settings.document_ai_location}-documentai.googleapis.com"
            )
            # Load credentials from service account file if specified
            creds_path = settings.google_application_credentials
            if creds_path and os.path.exists(creds_path):
                credentials = service_account.Credentials.from_service_account_file(creds_path)
                self.client = documentai.DocumentProcessorServiceClient(
                    client_options=client_options,
                    credentials=credentials
                )
                logger.info("Using Document AI with service account", path=creds_path)
            else:
                self.client = documentai.DocumentProcessorServiceClient(
                    client_options=client_options
                )
                logger.info("Using Document AI with default credentials")

        self.project_id = settings.gcp_project_id
        self.location = settings.document_ai_location

    async def process_document(
        self,
        content: bytes,
        mime_type: str,
        filename: Optional[str] = None,
        doc_type: Optional[DocumentType] = None,
    ) -> Tuple[dict, float, dict, ProcessorType]:
        """
        Process a document using Document AI or mock.

        Args:
            content: Document content as bytes
            mime_type: MIME type of the document
            filename: Original filename for type detection
            doc_type: Optional pre-determined document type

        Returns:
            Tuple of (extracted_data, overall_confidence, field_confidences, processor_type)
        """
        # Detect document type if not provided
        if not doc_type:
            doc_type = self._detect_document_type(filename)

        if self.use_mock:
            return self._mock_process(content, filename, doc_type)

        # Select appropriate processor
        processor_info = PROCESSOR_MAP.get(doc_type)
        if processor_info:
            processor_type_str, processor_id = processor_info
        else:
            # Default to form parser
            processor_type_str = "form"
            processor_id = settings.document_ai_form_processor_id

        # If no processor configured, fall back to OCR
        if not processor_id:
            processor_id = settings.document_ai_ocr_processor_id
            processor_type_str = "ocr"

        logger.info(
            "Processing document with Document AI",
            processor_type=processor_type_str,
            processor_id=processor_id,
            doc_type=doc_type.value if doc_type else "unknown",
        )

        # Build processor name
        processor_name = (
            f"projects/{self.project_id}/locations/{self.location}/processors/{processor_id}"
        )

        # Create the request
        raw_document = documentai.RawDocument(
            content=content,
            mime_type=mime_type,
        )

        request = documentai.ProcessRequest(
            name=processor_name,
            raw_document=raw_document,
        )

        # Process the document
        result = self.client.process_document(request=request)
        document = result.document

        # Extract data based on processor type
        if processor_type_str == "invoice":
            extracted_data, field_confidences = self._extract_invoice_data(document)
            processor_type = ProcessorType.DOCUMENT_AI_INVOICE
        elif processor_type_str == "form":
            extracted_data, field_confidences = self._extract_form_data(document)
            processor_type = ProcessorType.DOCUMENT_AI_FORM
        else:
            extracted_data, field_confidences = self._extract_ocr_data(document)
            processor_type = ProcessorType.DOCUMENT_AI_OCR

        # Calculate overall confidence
        if field_confidences:
            overall_confidence = sum(field_confidences.values()) / len(field_confidences)
        else:
            overall_confidence = 0.0

        logger.info(
            "Document AI processing complete",
            fields_extracted=len(extracted_data),
            overall_confidence=overall_confidence,
        )

        return extracted_data, overall_confidence, field_confidences, processor_type

    def _detect_document_type(self, filename: Optional[str]) -> Optional[DocumentType]:
        """Detect document type from filename patterns."""
        if not filename:
            return None

        filename_lower = filename.lower()

        for doc_type, patterns in FILENAME_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    logger.debug(
                        "Document type detected from filename",
                        filename=filename,
                        doc_type=doc_type.value,
                    )
                    return doc_type

        return None

    def _extract_invoice_data(self, document: documentai.Document) -> Tuple[dict, dict]:
        """Extract data from invoice processor result."""
        extracted = {}
        confidences = {}

        for entity in document.entities:
            field_name = self._normalize_field_name(entity.type_)
            value = entity.mention_text

            # Handle nested properties
            if entity.properties:
                nested = {}
                for prop in entity.properties:
                    prop_name = self._normalize_field_name(prop.type_)
                    nested[prop_name] = prop.mention_text
                    if prop.confidence:
                        confidences[f"{field_name}.{prop_name}"] = prop.confidence
                extracted[field_name] = nested
            else:
                extracted[field_name] = self._parse_value(value, entity.type_)
                if entity.confidence:
                    confidences[field_name] = entity.confidence

        return extracted, confidences

    def _extract_form_data(self, document: documentai.Document) -> Tuple[dict, dict]:
        """Extract data from form parser result."""
        extracted = {}
        confidences = {}

        # Extract from entities
        for entity in document.entities:
            field_name = self._normalize_field_name(entity.type_)
            value = entity.mention_text
            extracted[field_name] = self._parse_value(value, entity.type_)
            if entity.confidence:
                confidences[field_name] = entity.confidence

        # Extract from form fields (key-value pairs)
        for page in document.pages:
            for field in page.form_fields:
                if field.field_name and field.field_value:
                    field_name = self._normalize_field_name(
                        self._get_text(field.field_name, document.text)
                    )
                    value = self._get_text(field.field_value, document.text)
                    extracted[field_name] = self._parse_value(value, field_name)

                    confidence = (
                        field.field_name.confidence + field.field_value.confidence
                    ) / 2
                    confidences[field_name] = confidence

        # Extract from tables
        tables = self._extract_tables(document)
        if tables:
            extracted["_tables"] = tables

        return extracted, confidences

    def _extract_ocr_data(self, document: documentai.Document) -> Tuple[dict, dict]:
        """Extract data from OCR processor result."""
        extracted = {
            "text": document.text,
            "pages": len(document.pages),
        }
        confidences = {}

        # Extract any detected entities
        for entity in document.entities:
            field_name = self._normalize_field_name(entity.type_)
            extracted[field_name] = entity.mention_text
            if entity.confidence:
                confidences[field_name] = entity.confidence

        return extracted, confidences

    def _extract_tables(self, document: documentai.Document) -> list[dict]:
        """Extract tables from document."""
        tables = []

        for page in document.pages:
            for table in page.tables:
                table_data = {
                    "headers": [],
                    "rows": [],
                }

                # Extract header row
                if table.header_rows:
                    for cell in table.header_rows[0].cells:
                        cell_text = self._get_text(cell.layout, document.text)
                        table_data["headers"].append(cell_text.strip())

                # Extract body rows
                for row in table.body_rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = self._get_text(cell.layout, document.text)
                        row_data.append(cell_text.strip())
                    table_data["rows"].append(row_data)

                tables.append(table_data)

        return tables

    def _get_text(self, layout: documentai.Document.Page.Layout, full_text: str) -> str:
        """Get text from a layout element."""
        text = ""
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index) if segment.end_index else 0
            text += full_text[start:end]
        return text

    def _normalize_field_name(self, name: str) -> str:
        """Normalize field names to snake_case."""
        # Replace spaces and special chars with underscores
        name = re.sub(r"[^a-zA-Z0-9]", "_", name)
        # Convert to lowercase
        name = name.lower()
        # Remove consecutive underscores
        name = re.sub(r"_+", "_", name)
        # Remove leading/trailing underscores
        return name.strip("_")

    def _parse_value(self, value: str, field_type: str) -> Any:
        """Parse value based on field type hints."""
        if not value:
            return None

        value = value.strip()

        # Try to parse as number if it looks like one
        if re.match(r"^[\$\€\£]?[\d,]+\.?\d*%?$", value.replace(",", "")):
            # Remove currency symbols and commas
            clean_value = re.sub(r"[\$\€\£,%]", "", value)
            try:
                if "." in clean_value:
                    return float(clean_value)
                return int(clean_value)
            except ValueError:
                pass

        # Try to parse as date
        if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$", value):
            return value  # Keep as string, let the application parse

        return value

    def _mock_process(
        self,
        content: bytes,
        filename: Optional[str],
        doc_type: Optional[DocumentType],
    ) -> Tuple[dict, float, dict, ProcessorType]:
        """Generate mock document extraction results for local development."""
        import random
        from datetime import datetime, timedelta

        logger.info("Using mock document processing", filename=filename, doc_type=doc_type)

        # Generate mock data based on document type
        if doc_type == DocumentType.MONTHLY_FINANCIALS or doc_type == DocumentType.QUARTERLY_FINANCIALS:
            extracted = {
                "period_end_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "revenue": random.randint(500000, 5000000),
                "gross_profit": random.randint(200000, 2000000),
                "ebitda": random.randint(100000, 1000000),
                "net_income": random.randint(50000, 500000),
                "total_assets": random.randint(1000000, 10000000),
                "total_liabilities": random.randint(500000, 5000000),
                "cash_and_equivalents": random.randint(100000, 1000000),
            }
        elif doc_type == DocumentType.COVENANT_COMPLIANCE:
            extracted = {
                "reporting_period": datetime.now().strftime("%Y-%m-%d"),
                "leverage_ratio": round(random.uniform(2.0, 5.0), 2),
                "leverage_covenant": 4.5,
                "interest_coverage_ratio": round(random.uniform(1.5, 3.0), 2),
                "coverage_covenant": 1.75,
                "overall_compliance": random.choice([True, True, True, False]),
            }
        elif doc_type == DocumentType.BORROWING_BASE:
            extracted = {
                "certificate_date": datetime.now().strftime("%Y-%m-%d"),
                "gross_accounts_receivable": random.randint(1000000, 5000000),
                "eligible_ar": random.randint(800000, 4000000),
                "ar_advance_rate": 0.85,
                "gross_inventory": random.randint(500000, 2000000),
                "eligible_inventory": random.randint(400000, 1600000),
                "inventory_advance_rate": 0.50,
                "total_availability": random.randint(500000, 2000000),
            }
        elif doc_type == DocumentType.CAPITAL_CALL:
            extracted = {
                "notice_date": datetime.now().strftime("%Y-%m-%d"),
                "due_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                "call_amount": random.randint(100000, 1000000),
                "call_number": random.randint(1, 10),
            }
        elif doc_type == DocumentType.INVOICE:
            extracted = {
                "invoice_number": f"INV-{random.randint(10000, 99999)}",
                "invoice_date": datetime.now().strftime("%Y-%m-%d"),
                "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "vendor_name": "Sample Vendor Inc.",
                "total_amount": round(random.uniform(1000, 50000), 2),
            }
        else:
            # Generic extraction
            extracted = {
                "text": f"Mock extracted text from {filename}",
                "pages": 1,
            }

        # Generate confidence scores
        base_confidence = random.uniform(0.85, 0.98)
        field_confidences = {
            field: round(random.uniform(base_confidence - 0.1, base_confidence + 0.05), 3)
            for field in extracted.keys()
        }

        return extracted, round(base_confidence, 3), field_confidences, ProcessorType.DOCUMENT_AI_FORM
