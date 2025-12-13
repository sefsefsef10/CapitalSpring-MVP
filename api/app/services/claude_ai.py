"""Claude AI service for complex document extraction (API or mock)."""

import json
from typing import Any, Optional, Tuple

import structlog

from app.config import settings
from app.models.document import DocumentType, ProcessorType

logger = structlog.get_logger(__name__)

# Try to import Anthropic, use mock if not available
try:
    from anthropic import Anthropic
    from tenacity import retry, stop_after_attempt, wait_exponential
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic SDK not available, using mock service")


# Extraction schemas for different document types
EXTRACTION_SCHEMAS = {
    DocumentType.MONTHLY_FINANCIALS: {
        "period_end_date": "Date (YYYY-MM-DD)",
        "period_type": "monthly|quarterly|annual",
        "revenue": "Number (currency amount)",
        "revenue_growth_yoy": "Number (percentage)",
        "gross_profit": "Number (currency amount)",
        "gross_margin": "Number (percentage)",
        "ebitda": "Number (currency amount)",
        "ebitda_margin": "Number (percentage)",
        "net_income": "Number (currency amount)",
        "total_assets": "Number (currency amount)",
        "total_liabilities": "Number (currency amount)",
        "total_equity": "Number (currency amount)",
        "cash_and_equivalents": "Number (currency amount)",
        "total_debt": "Number (currency amount)",
    },
    DocumentType.COVENANT_COMPLIANCE: {
        "reporting_period": "Date (YYYY-MM-DD)",
        "leverage_ratio": "Number (decimal ratio like 3.5)",
        "leverage_covenant": "Number (max allowed ratio)",
        "leverage_compliant": "Boolean",
        "interest_coverage_ratio": "Number (decimal ratio)",
        "coverage_covenant": "Number (min required ratio)",
        "coverage_compliant": "Boolean",
        "fixed_charge_coverage": "Number (decimal ratio)",
        "fcc_covenant": "Number (min required ratio)",
        "fcc_compliant": "Boolean",
        "minimum_liquidity": "Number (currency amount)",
        "liquidity_covenant": "Number (min required amount)",
        "liquidity_compliant": "Boolean",
        "overall_compliance": "Boolean",
        "cure_required": "Boolean",
        "cure_amount": "Number (currency amount) or null",
    },
    DocumentType.BORROWING_BASE: {
        "certificate_date": "Date (YYYY-MM-DD)",
        "gross_accounts_receivable": "Number (currency amount)",
        "ineligible_ar": "Number (currency amount)",
        "eligible_ar": "Number (currency amount)",
        "ar_advance_rate": "Number (percentage like 85)",
        "ar_availability": "Number (currency amount)",
        "gross_inventory": "Number (currency amount)",
        "ineligible_inventory": "Number (currency amount)",
        "eligible_inventory": "Number (currency amount)",
        "inventory_advance_rate": "Number (percentage like 50)",
        "inventory_availability": "Number (currency amount)",
        "total_availability": "Number (currency amount)",
        "outstanding_loans": "Number (currency amount)",
        "outstanding_lcs": "Number (currency amount)",
        "excess_availability": "Number (currency amount)",
    },
    DocumentType.CAPITAL_CALL: {
        "notice_date": "Date (YYYY-MM-DD)",
        "due_date": "Date (YYYY-MM-DD)",
        "call_number": "Integer",
        "call_amount": "Number (currency amount)",
        "call_purpose": "String description",
        "cumulative_called": "Number (currency amount)",
        "remaining_commitment": "Number (currency amount)",
    },
}


class ClaudeService:
    """Service for Claude AI document extraction (API or mock)."""

    def __init__(self):
        """Initialize the Claude client."""
        # Use real Claude if: SDK available AND API key is set
        # Claude doesn't require use_gcp flag since it's not a GCP service
        use_real = ANTHROPIC_AVAILABLE and settings.anthropic_api_key
        self.use_mock = not use_real

        if self.use_mock:
            logger.info("Using mock Claude service")
            self.client = None
        else:
            logger.info("Using real Claude API")
            self.client = Anthropic(api_key=settings.anthropic_api_key)

        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    async def extract_document_data(
        self,
        text_content: str,
        doc_type: Optional[DocumentType] = None,
        filename: Optional[str] = None,
    ) -> Tuple[dict, float, dict, ProcessorType]:
        """
        Extract structured data from document text using Claude or mock.

        Args:
            text_content: Extracted text from the document
            doc_type: Document type if known
            filename: Original filename for context

        Returns:
            Tuple of (extracted_data, confidence, field_confidences, processor_type)
        """
        if self.use_mock:
            return self._mock_extract(text_content, doc_type, filename)

        # Build the extraction prompt
        schema = self._get_schema(doc_type)
        prompt = self._build_extraction_prompt(text_content, schema, doc_type, filename)

        logger.info(
            "Sending document to Claude for extraction",
            doc_type=doc_type.value if doc_type else "unknown",
            text_length=len(text_content),
        )

        # Call Claude API with retry logic
        response = await self._call_with_retry(prompt)

        # Parse the response
        response_text = response.content[0].text
        extracted_data, field_confidences = self._parse_response(response_text)

        # Calculate overall confidence based on how many fields were extracted
        expected_fields = len(schema) if schema else 10
        filled_fields = sum(1 for v in extracted_data.values() if v is not None)
        confidence = min(filled_fields / expected_fields, 1.0)

        logger.info(
            "Claude extraction complete",
            fields_extracted=len(extracted_data),
            confidence=confidence,
        )

        return extracted_data, confidence, field_confidences, ProcessorType.CLAUDE

    async def detect_document_type(
        self,
        text_content: str,
        filename: Optional[str] = None,
    ) -> DocumentType:
        """
        Use Claude to detect the document type.

        Args:
            text_content: Document text content
            filename: Original filename

        Returns:
            Detected DocumentType
        """
        if self.use_mock:
            # In mock mode, return a default document type
            logger.info("Mock document type detection", filename=filename)
            return DocumentType.OTHER

        prompt = f"""Analyze this document and determine its type.

Document filename: {filename or "Unknown"}

Document content (first 3000 characters):
{text_content[:3000]}

Based on the content, classify this document as ONE of these types:
- monthly_financials: Monthly financial statements
- quarterly_financials: Quarterly financial statements
- annual_financials: Annual or audited financial statements
- covenant_compliance: Covenant compliance certificate
- borrowing_base: Borrowing base certificate
- ar_aging: Accounts receivable aging schedule
- capital_call: Capital call notice
- distribution_notice: Distribution notice
- nav_statement: NAV statement
- invoice: Invoice or bill
- bank_statement: Bank statement
- insurance_certificate: Insurance certificate
- other: None of the above

Respond with ONLY the document type (e.g., "monthly_financials" or "covenant_compliance").
Do not include any explanation or additional text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        type_str = response.content[0].text.strip().lower()

        # Map to DocumentType enum
        type_mapping = {
            "monthly_financials": DocumentType.MONTHLY_FINANCIALS,
            "quarterly_financials": DocumentType.QUARTERLY_FINANCIALS,
            "annual_financials": DocumentType.ANNUAL_FINANCIALS,
            "covenant_compliance": DocumentType.COVENANT_COMPLIANCE,
            "borrowing_base": DocumentType.BORROWING_BASE,
            "ar_aging": DocumentType.AR_AGING,
            "capital_call": DocumentType.CAPITAL_CALL,
            "distribution_notice": DocumentType.DISTRIBUTION_NOTICE,
            "nav_statement": DocumentType.NAV_STATEMENT,
            "invoice": DocumentType.INVOICE,
            "bank_statement": DocumentType.BANK_STATEMENT,
            "insurance_certificate": DocumentType.INSURANCE_CERTIFICATE,
        }

        doc_type = type_mapping.get(type_str, DocumentType.OTHER)
        logger.info("Document type detected by Claude", detected_type=doc_type.value)

        return doc_type

    def _get_schema(self, doc_type: Optional[DocumentType]) -> dict:
        """Get extraction schema for document type."""
        if doc_type and doc_type in EXTRACTION_SCHEMAS:
            return EXTRACTION_SCHEMAS[doc_type]

        # Generic schema for unknown types
        return {
            "document_date": "Date (YYYY-MM-DD)",
            "document_title": "String",
            "company_name": "String",
            "key_figures": "Object with key financial figures",
            "summary": "Brief summary of the document",
        }

    def _build_extraction_prompt(
        self,
        text_content: str,
        schema: dict,
        doc_type: Optional[DocumentType],
        filename: Optional[str],
    ) -> str:
        """Build the extraction prompt for Claude."""
        schema_str = json.dumps(schema, indent=2)

        prompt = f"""You are a financial document data extraction expert. Extract structured data from the following document.

Document filename: {filename or "Unknown"}
Document type: {doc_type.value if doc_type else "Unknown"}

EXTRACTION SCHEMA (extract these fields):
{schema_str}

DOCUMENT CONTENT:
{text_content}

INSTRUCTIONS:
1. Extract data matching the schema above
2. Return ONLY valid JSON with the extracted values
3. Use null for fields that cannot be found
4. For numbers, return numeric values (not strings)
5. For dates, use YYYY-MM-DD format
6. For percentages, return the number (e.g., 85 for 85%)
7. For currency amounts, return the number without currency symbols
8. Be precise - only extract values you are confident about

Respond with ONLY the JSON object, no explanation or markdown:"""

        return prompt

    def _parse_response(self, response_text: str) -> Tuple[dict, dict]:
        """Parse Claude's JSON response."""
        # Clean up the response
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            data = json.loads(text)

            # Generate confidence scores (Claude doesn't provide these, so estimate)
            confidences = {}
            for key, value in data.items():
                if value is not None:
                    confidences[key] = 0.85  # Default confidence for Claude extractions
                else:
                    confidences[key] = 0.0

            return data, confidences

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Claude response as JSON", error=str(e))

            # Try to extract any key-value pairs
            return {"raw_response": text}, {"raw_response": 0.5}

    def _mock_extract(
        self,
        text_content: str,
        doc_type: Optional[DocumentType],
        filename: Optional[str],
    ) -> Tuple[dict, float, dict, ProcessorType]:
        """Generate mock extraction results for local development."""
        import random
        from datetime import datetime, timedelta

        logger.info("Using mock Claude extraction", filename=filename, doc_type=doc_type)

        # Generate mock data based on document type
        if doc_type == DocumentType.MONTHLY_FINANCIALS:
            extracted = {
                "period_end_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "period_type": "monthly",
                "revenue": random.randint(500000, 5000000),
                "revenue_growth_yoy": round(random.uniform(-5, 25), 1),
                "gross_profit": random.randint(200000, 2000000),
                "gross_margin": round(random.uniform(25, 45), 1),
                "ebitda": random.randint(100000, 1000000),
                "ebitda_margin": round(random.uniform(10, 25), 1),
                "net_income": random.randint(50000, 500000),
                "total_assets": random.randint(1000000, 10000000),
                "total_liabilities": random.randint(500000, 5000000),
                "total_equity": random.randint(500000, 5000000),
                "cash_and_equivalents": random.randint(100000, 1000000),
                "total_debt": random.randint(200000, 2000000),
            }
        elif doc_type == DocumentType.COVENANT_COMPLIANCE:
            leverage = round(random.uniform(2.0, 5.0), 2)
            leverage_cov = 4.5
            coverage = round(random.uniform(1.5, 3.0), 2)
            coverage_cov = 1.75
            extracted = {
                "reporting_period": datetime.now().strftime("%Y-%m-%d"),
                "leverage_ratio": leverage,
                "leverage_covenant": leverage_cov,
                "leverage_compliant": leverage <= leverage_cov,
                "interest_coverage_ratio": coverage,
                "coverage_covenant": coverage_cov,
                "coverage_compliant": coverage >= coverage_cov,
                "fixed_charge_coverage": round(random.uniform(1.0, 2.5), 2),
                "fcc_covenant": 1.25,
                "fcc_compliant": True,
                "minimum_liquidity": random.randint(1000000, 5000000),
                "liquidity_covenant": 1000000,
                "liquidity_compliant": True,
                "overall_compliance": random.choice([True, True, True, False]),
                "cure_required": False,
                "cure_amount": None,
            }
        elif doc_type == DocumentType.BORROWING_BASE:
            gross_ar = random.randint(1000000, 5000000)
            inelig_ar = int(gross_ar * random.uniform(0.1, 0.25))
            elig_ar = gross_ar - inelig_ar
            ar_rate = 0.85
            gross_inv = random.randint(500000, 2000000)
            inelig_inv = int(gross_inv * random.uniform(0.15, 0.3))
            elig_inv = gross_inv - inelig_inv
            inv_rate = 0.50
            extracted = {
                "certificate_date": datetime.now().strftime("%Y-%m-%d"),
                "gross_accounts_receivable": gross_ar,
                "ineligible_ar": inelig_ar,
                "eligible_ar": elig_ar,
                "ar_advance_rate": int(ar_rate * 100),
                "ar_availability": int(elig_ar * ar_rate),
                "gross_inventory": gross_inv,
                "ineligible_inventory": inelig_inv,
                "eligible_inventory": elig_inv,
                "inventory_advance_rate": int(inv_rate * 100),
                "inventory_availability": int(elig_inv * inv_rate),
                "total_availability": int(elig_ar * ar_rate + elig_inv * inv_rate),
                "outstanding_loans": random.randint(500000, 2000000),
                "outstanding_lcs": random.randint(0, 200000),
                "excess_availability": random.randint(100000, 500000),
            }
        elif doc_type == DocumentType.CAPITAL_CALL:
            extracted = {
                "notice_date": datetime.now().strftime("%Y-%m-%d"),
                "due_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                "call_number": random.randint(1, 10),
                "call_amount": random.randint(100000, 1000000),
                "call_purpose": "Portfolio investment",
                "cumulative_called": random.randint(1000000, 10000000),
                "remaining_commitment": random.randint(500000, 5000000),
            }
        else:
            # Generic extraction for unknown types
            extracted = {
                "document_date": datetime.now().strftime("%Y-%m-%d"),
                "document_title": filename or "Unknown Document",
                "company_name": "Sample Company Inc.",
                "key_figures": {"value_1": random.randint(10000, 100000)},
                "summary": f"Mock extraction from {filename or 'document'}",
            }

        # Generate confidence scores
        base_confidence = random.uniform(0.82, 0.95)
        field_confidences = {
            field: round(random.uniform(base_confidence - 0.05, min(base_confidence + 0.05, 1.0)), 3)
            for field in extracted.keys()
        }

        return extracted, round(base_confidence, 3), field_confidences, ProcessorType.CLAUDE

    async def _call_with_retry(self, prompt: str):
        """Call Claude API with retry logic."""
        if ANTHROPIC_AVAILABLE:
            from tenacity import retry, stop_after_attempt, wait_exponential

            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
            )
            def _make_request():
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )

            return _make_request()
        else:
            raise RuntimeError("Anthropic SDK not available")

    async def validate_extraction(
        self,
        extracted_data: dict,
        original_text: str,
        doc_type: DocumentType,
    ) -> Tuple[bool, list[str]]:
        """
        Use Claude to validate extracted data against the original document.

        Args:
            extracted_data: Previously extracted data
            original_text: Original document text
            doc_type: Document type

        Returns:
            Tuple of (is_valid, list of validation issues)
        """
        if self.use_mock:
            # In mock mode, assume validation passes
            logger.info("Mock validation - assuming valid")
            return True, []

        prompt = f"""Review this extracted data against the original document and identify any errors.

DOCUMENT TYPE: {doc_type.value}

EXTRACTED DATA:
{json.dumps(extracted_data, indent=2)}

ORIGINAL DOCUMENT (first 4000 chars):
{original_text[:4000]}

Check for:
1. Incorrect values that don't match the document
2. Missing critical fields
3. Data type errors (wrong format)
4. Logical inconsistencies (e.g., totals don't add up)

Respond with JSON:
{{"is_valid": true/false, "issues": ["issue 1", "issue 2", ...]}}

Only include issues you are confident about. Respond with ONLY JSON:"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            result = json.loads(response.content[0].text.strip())
            return result.get("is_valid", True), result.get("issues", [])
        except json.JSONDecodeError:
            logger.warning("Failed to parse validation response")
            return True, []
