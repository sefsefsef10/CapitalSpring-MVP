"""Validation service for document data validation."""

import re
from datetime import datetime, timedelta
from typing import Any, Optional

import structlog
from pydantic import BaseModel

from app.models.document import DocumentType
from app.models.exception import ExceptionCategory, ExceptionPriority

logger = structlog.get_logger(__name__)


class ValidationError(BaseModel):
    """Validation error details."""
    field: str
    category: ExceptionCategory
    priority: ExceptionPriority
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of validation."""
    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]


# Validation rules configuration
VALIDATION_RULES = {
    DocumentType.MONTHLY_FINANCIALS: {
        "required_fields": [
            "period_end_date",
            "revenue",
        ],
        "rules": [
            {
                "field": "revenue",
                "type": "positive_number",
                "priority": ExceptionPriority.HIGH,
            },
            {
                "field": "ebitda",
                "type": "number",
                "priority": ExceptionPriority.MEDIUM,
            },
            {
                "field": "gross_margin",
                "type": "percentage",
                "min": 0,
                "max": 100,
                "priority": ExceptionPriority.MEDIUM,
            },
            {
                "field": "ebitda_margin",
                "type": "percentage",
                "min": -100,
                "max": 100,
                "priority": ExceptionPriority.LOW,
            },
            {
                "field": "period_end_date",
                "type": "date",
                "max_age_days": 180,
                "priority": ExceptionPriority.MEDIUM,
            },
        ],
        "cross_field_rules": [
            {
                "condition": "gross_profit <= revenue",
                "message": "Gross profit cannot exceed revenue",
                "priority": ExceptionPriority.HIGH,
            },
        ],
    },
    DocumentType.COVENANT_COMPLIANCE: {
        "required_fields": [
            "reporting_period",
            "overall_compliance",
        ],
        "rules": [
            {
                "field": "leverage_ratio",
                "type": "positive_number",
                "priority": ExceptionPriority.HIGH,
            },
            {
                "field": "interest_coverage_ratio",
                "type": "positive_number",
                "priority": ExceptionPriority.HIGH,
            },
            {
                "field": "reporting_period",
                "type": "date",
                "max_age_days": 120,
                "priority": ExceptionPriority.MEDIUM,
            },
        ],
        "cross_field_rules": [
            {
                "condition": "leverage_ratio <= leverage_covenant or not leverage_compliant",
                "message": "Leverage compliance flag doesn't match ratio vs covenant",
                "priority": ExceptionPriority.HIGH,
            },
        ],
    },
    DocumentType.BORROWING_BASE: {
        "required_fields": [
            "certificate_date",
            "eligible_ar",
            "total_availability",
        ],
        "rules": [
            {
                "field": "eligible_ar",
                "type": "non_negative",
                "priority": ExceptionPriority.HIGH,
            },
            {
                "field": "eligible_inventory",
                "type": "non_negative",
                "priority": ExceptionPriority.MEDIUM,
            },
            {
                "field": "ar_advance_rate",
                "type": "percentage",
                "min": 0,
                "max": 95,
                "priority": ExceptionPriority.MEDIUM,
            },
            {
                "field": "inventory_advance_rate",
                "type": "percentage",
                "min": 0,
                "max": 70,
                "priority": ExceptionPriority.MEDIUM,
            },
        ],
        "cross_field_rules": [
            {
                "condition": "eligible_ar <= gross_accounts_receivable",
                "message": "Eligible AR cannot exceed gross AR",
                "priority": ExceptionPriority.HIGH,
            },
            {
                "condition": "total_availability >= 0",
                "message": "Total availability cannot be negative",
                "priority": ExceptionPriority.CRITICAL,
            },
        ],
    },
    DocumentType.CAPITAL_CALL: {
        "required_fields": [
            "notice_date",
            "due_date",
            "call_amount",
        ],
        "rules": [
            {
                "field": "call_amount",
                "type": "positive_number",
                "priority": ExceptionPriority.HIGH,
            },
        ],
        "cross_field_rules": [
            {
                "condition": "due_date > notice_date",
                "message": "Due date must be after notice date",
                "priority": ExceptionPriority.HIGH,
            },
        ],
    },
}


class ValidationService:
    """Service for validating extracted document data."""

    def validate(
        self,
        data: dict,
        doc_type: Optional[DocumentType],
    ) -> ValidationResult:
        """
        Validate extracted data against rules for the document type.

        Args:
            data: Extracted data to validate
            doc_type: Document type for rule selection

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        if not doc_type or doc_type not in VALIDATION_RULES:
            # Use generic validation for unknown types
            errors.extend(self._validate_generic(data))
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
            )

        rules = VALIDATION_RULES[doc_type]

        # Check required fields
        for field in rules.get("required_fields", []):
            if field not in data or data[field] is None:
                errors.append(
                    ValidationError(
                        field=field,
                        category=ExceptionCategory.MISSING_FIELD,
                        priority=ExceptionPriority.HIGH,
                        message=f"Required field '{field}' is missing",
                    )
                )

        # Apply field rules
        for rule in rules.get("rules", []):
            result = self._apply_rule(data, rule)
            if result:
                if rule.get("priority") in [ExceptionPriority.LOW]:
                    warnings.append(result)
                else:
                    errors.append(result)

        # Apply cross-field rules
        for rule in rules.get("cross_field_rules", []):
            result = self._apply_cross_field_rule(data, rule)
            if result:
                errors.append(result)

        logger.info(
            "Validation complete",
            doc_type=doc_type.value if doc_type else "unknown",
            error_count=len(errors),
            warning_count=len(warnings),
        )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _apply_rule(self, data: dict, rule: dict) -> Optional[ValidationError]:
        """Apply a single validation rule."""
        field = rule["field"]
        value = data.get(field)

        # Skip if field is not present (handled by required check)
        if value is None:
            return None

        rule_type = rule.get("type")
        priority = rule.get("priority", ExceptionPriority.MEDIUM)

        try:
            if rule_type == "positive_number":
                if not isinstance(value, (int, float)) or value <= 0:
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.VALIDATION_ERROR,
                        priority=priority,
                        message=f"Field '{field}' must be a positive number",
                        expected="positive number",
                        actual=str(value),
                    )

            elif rule_type == "non_negative":
                if not isinstance(value, (int, float)) or value < 0:
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.VALIDATION_ERROR,
                        priority=priority,
                        message=f"Field '{field}' cannot be negative",
                        expected="non-negative number",
                        actual=str(value),
                    )

            elif rule_type == "number":
                if not isinstance(value, (int, float)):
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.INVALID_FORMAT,
                        priority=priority,
                        message=f"Field '{field}' must be a number",
                        expected="number",
                        actual=str(type(value).__name__),
                    )

            elif rule_type == "percentage":
                if not isinstance(value, (int, float)):
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.INVALID_FORMAT,
                        priority=priority,
                        message=f"Field '{field}' must be a percentage",
                        expected="percentage",
                        actual=str(value),
                    )
                min_val = rule.get("min", 0)
                max_val = rule.get("max", 100)
                if value < min_val or value > max_val:
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.VALIDATION_ERROR,
                        priority=priority,
                        message=f"Field '{field}' must be between {min_val}% and {max_val}%",
                        expected=f"{min_val}-{max_val}",
                        actual=str(value),
                    )

            elif rule_type == "date":
                parsed_date = self._parse_date(value)
                if not parsed_date:
                    return ValidationError(
                        field=field,
                        category=ExceptionCategory.INVALID_FORMAT,
                        priority=priority,
                        message=f"Field '{field}' is not a valid date",
                        expected="date (YYYY-MM-DD)",
                        actual=str(value),
                    )

                max_age_days = rule.get("max_age_days")
                if max_age_days:
                    age = (datetime.now() - parsed_date).days
                    if age > max_age_days:
                        return ValidationError(
                            field=field,
                            category=ExceptionCategory.VALIDATION_ERROR,
                            priority=priority,
                            message=f"Field '{field}' is older than {max_age_days} days",
                            expected=f"within {max_age_days} days",
                            actual=f"{age} days old",
                        )

        except Exception as e:
            logger.warning(f"Error applying rule for {field}", error=str(e))
            return None

        return None

    def _apply_cross_field_rule(self, data: dict, rule: dict) -> Optional[ValidationError]:
        """Apply a cross-field validation rule."""
        condition = rule.get("condition", "")
        message = rule.get("message", "Cross-field validation failed")
        priority = rule.get("priority", ExceptionPriority.MEDIUM)

        try:
            # Create a safe evaluation context with the data
            eval_context = {k: v for k, v in data.items() if v is not None}

            # Add helper functions
            eval_context["abs"] = abs
            eval_context["min"] = min
            eval_context["max"] = max

            # Evaluate the condition
            result = eval(condition, {"__builtins__": {}}, eval_context)

            if not result:
                return ValidationError(
                    field="_cross_field",
                    category=ExceptionCategory.CROSS_FIELD,
                    priority=priority,
                    message=message,
                )

        except Exception as e:
            # If evaluation fails (e.g., missing fields), skip this rule
            logger.debug(f"Cross-field rule skipped: {condition}", error=str(e))

        return None

    def _validate_generic(self, data: dict) -> list[ValidationError]:
        """Apply generic validation for unknown document types."""
        errors = []

        # Check for completely empty data
        if not data or all(v is None for v in data.values()):
            errors.append(
                ValidationError(
                    field="_all",
                    category=ExceptionCategory.EXTRACTION_ERROR,
                    priority=ExceptionPriority.CRITICAL,
                    message="No data could be extracted from the document",
                )
            )

        return errors

    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Try to parse a value as a date."""
        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            return None

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        return None
