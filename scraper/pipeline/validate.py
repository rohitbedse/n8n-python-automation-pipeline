"""
Schema Validation Utilities
===========================
Provides validation functions for scraped records against defined schemas.
"""

from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ValidationError:
    """Represents a single validation error."""
    field: str
    message: str
    value: Any = None
    code: str = "VALIDATION_ERROR"


@dataclass
class ValidationResult:
    """Result of validating a record."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, field: str, message: str, value: Any = None, code: str = "VALIDATION_ERROR") -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field, message, value, code))
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)
    
    def get_error_messages(self) -> List[str]:
        """Get list of error messages."""
        return [f"{e.field}: {e.message}" for e in self.errors]


# Type validators
def _validate_string(value: Any, field: str, result: ValidationResult, required: bool = False) -> None:
    if value is None or value == "":
        if required:
            result.add_error(field, "Required field is missing or empty", value, "REQUIRED_FIELD_MISSING")
    elif not isinstance(value, str):
        result.add_error(field, f"Expected string, got {type(value).__name__}", value, "TYPE_MISMATCH")


def _validate_integer(value: Any, field: str, result: ValidationResult, required: bool = False, min_val: int = None, max_val: int = None) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            result.add_error(field, f"Expected integer, got {type(value).__name__}", value, "TYPE_MISMATCH")
            return
    if min_val is not None and value < min_val:
        result.add_error(field, f"Value {value} is less than minimum {min_val}", value, "VALUE_TOO_SMALL")
    if max_val is not None and value > max_val:
        result.add_error(field, f"Value {value} exceeds maximum {max_val}", value, "VALUE_TOO_LARGE")


def _validate_float(value: Any, field: str, result: ValidationResult, required: bool = False) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, (int, float)):
        try:
            float(value)
        except (ValueError, TypeError):
            result.add_error(field, f"Expected number, got {type(value).__name__}", value, "TYPE_MISMATCH")


def _validate_boolean(value: Any, field: str, result: ValidationResult, required: bool = False) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, bool):
        result.add_error(field, f"Expected boolean, got {type(value).__name__}", value, "TYPE_MISMATCH")


def _validate_list(value: Any, field: str, result: ValidationResult, required: bool = False, item_validator: Callable = None) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, list):
        result.add_error(field, f"Expected list, got {type(value).__name__}", value, "TYPE_MISMATCH")
        return
    if item_validator:
        for i, item in enumerate(value):
            item_validator(item, f"{field}[{i}]", result)


def _validate_date(value: Any, field: str, result: ValidationResult, required: bool = False) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, str):
        result.add_error(field, f"Expected date string, got {type(value).__name__}", value, "TYPE_MISMATCH")
        return
    # Validate ISO date format
    try:
        date.fromisoformat(value)
    except ValueError:
        result.add_error(field, f"Invalid date format (expected YYYY-MM-DD): {value}", value, "INVALID_DATE_FORMAT")


def _validate_url(value: Any, field: str, result: ValidationResult, required: bool = False) -> None:
    if value is None:
        if required:
            result.add_error(field, "Required field is missing", value, "REQUIRED_FIELD_MISSING")
        return
    if not isinstance(value, str):
        result.add_error(field, f"Expected URL string, got {type(value).__name__}", value, "TYPE_MISMATCH")
        return
    if not value.startswith(("http://", "https://")):
        result.add_error(field, f"Invalid URL format: {value}", value, "INVALID_URL_FORMAT")


# Field type to validator mapping
FIELD_VALIDATORS = {
    "string": _validate_string,
    "integer": _validate_integer,
    "float": _validate_float,
    "boolean": _validate_boolean,
    "list": _validate_list,
    "date": _validate_date,
    "url": _validate_url,
}


@dataclass
class FieldSchema:
    """Schema definition for a single field."""
    name: str
    type: str  # One of FIELD_VALIDATORS keys
    required: bool = False
    description: str = ""
    min_val: Optional[int] = None
    max_val: Optional[int] = None
    item_validator: Optional[Callable] = None


class SchemaValidator:
    """Validates records against a defined schema."""
    
    def __init__(self, fields: List[FieldSchema], strict: bool = False):
        self.fields = {f.name: f for f in fields}
        self.strict = strict
    
    def validate(self, record: Dict[str, Any]) -> ValidationResult:
        """Validate a record against the schema."""
        result = ValidationResult(is_valid=True)
        
        # Check required fields
        for field_schema in self.fields.values():
            value = record.get(field_schema.name)
            validator = FIELD_VALIDATORS.get(field_schema.type)
            
            if validator:
                if field_schema.type == "integer":
                    validator(value, field_schema.name, result, field_schema.required, 
                            field_schema.min_val, field_schema.max_val)
                elif field_schema.type == "list":
                    validator(value, field_schema.name, result, field_schema.required,
                            field_schema.item_validator)
                else:
                    validator(value, field_schema.name, result, field_schema.required)
            elif self.strict:
                result.add_warning(f"No validator for field type: {field_schema.type}")
        
        # Check for unexpected fields in strict mode
        if self.strict:
            allowed_fields = set(self.fields.keys())
            for key in record.keys():
                if key not in allowed_fields:
                    result.add_warning(f"Unexpected field: {key}")
        
        return result


# Pre-defined schemas for each site
MINDLER_SCHEMA = SchemaValidator([
    FieldSchema("subject_id", "string", required=True, description="Unique subject identifier"),
    FieldSchema("subject_title", "string", required=True, description="Subject display title"),
    FieldSchema("description", "string", required=False),
    FieldSchema("image", "string", required=False),
    FieldSchema("subcareers", "list", required=False),
], strict=False)

SWAYAM_SCHEMA = SchemaValidator([
    FieldSchema("course_id", "string", required=True, description="Unique course identifier"),
    FieldSchema("course_name", "string", required=True, description="Course title"),
    FieldSchema("course_url", "url", required=True, description="Course URL"),
    FieldSchema("national_coordinator", "string", required=False),
    FieldSchema("institute", "string", required=False),
    FieldSchema("provider", "string", required=False),
    FieldSchema("description", "string", required=False),
    FieldSchema("course_type", "string", required=False),
    FieldSchema("category", "string", required=False),
    FieldSchema("education_level", "string", required=False),
    FieldSchema("mode", "string", required=False),
    FieldSchema("duration", "string", required=False),
    FieldSchema("start_date", "date", required=False),
    FieldSchema("end_date", "date", required=False),
    FieldSchema("status", "string", required=False),
    FieldSchema("skills", "list", required=False),
    FieldSchema("prerequisites", "string", required=False),
    FieldSchema("eligibility", "string", required=False),
    FieldSchema("instructors", "list", required=False),
    FieldSchema("certificate", "boolean", required=False),
    FieldSchema("certification_type", "string", required=False),
    FieldSchema("learning_outcomes", "list", required=False),
    FieldSchema("syllabus", "list", required=False),
    FieldSchema("assessment", "string", required=False),
    FieldSchema("language", "string", required=False),
    FieldSchema("fees", "string", required=False),
    FieldSchema("free_or_paid", "string", required=False),
    FieldSchema("enrollment_information", "string", required=False),
    FieldSchema("rating", "float", required=False),
    FieldSchema("enrollment_count", "integer", required=False),
    FieldSchema("career_relevance", "string", required=False),
    FieldSchema("source", "string", required=False),
    FieldSchema("last_verified_date", "date", required=False),
], strict=False)

CAREERS360_SCHEMA = SchemaValidator([
    FieldSchema("id", "string", required=True, description="Unique record identifier"),
    FieldSchema("title", "string", required=True, description="Record title"),
    FieldSchema("url", "url", required=True, description="Source URL"),
    FieldSchema("description", "string", required=False),
    FieldSchema("category", "string", required=False),
    FieldSchema("location", "string", required=False),
    FieldSchema("rating", "string", required=False),
    FieldSchema("fees", "string", required=False),
    FieldSchema("exams", "list", required=False),
    FieldSchema("source", "string", required=False),
    FieldSchema("scraped_date", "date", required=False),
], strict=False)


def validate_record(record: Dict[str, Any], site: str) -> ValidationResult:
    """
    Validate a record against the appropriate site schema.
    
    Args:
        record: Record to validate
        site: Site identifier ('mindler', 'swayam', 'careers360')
        
    Returns:
        ValidationResult
    """
    schemas = {
        "mindler": MINDLER_SCHEMA,
        "swayam": SWAYAM_SCHEMA,
        "careers360": CAREERS360_SCHEMA,
    }
    
    schema = schemas.get(site.lower())
    if not schema:
        result = ValidationResult(is_valid=True)
        result.add_warning(f"No schema defined for site: {site}")
        return result
    
    return schema.validate(record)


def validate_required_fields(record: Dict[str, Any], required_fields: List[str]) -> ValidationResult:
    """
    Simple validation checking only required fields are present and non-empty.
    """
    result = ValidationResult(is_valid=True)
    
    for field in required_fields:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(field, "Required field is missing or empty", value, "REQUIRED_FIELD_MISSING")
        elif isinstance(value, list) and len(value) == 0:
            result.add_error(field, "Required list field is empty", value, "REQUIRED_FIELD_EMPTY")
    
    return result