"""Tests for scraper/pipeline/validate.py"""
import pytest
from scraper.pipeline.validate import (
    FieldSchema,
    SchemaValidator,
    validate_record,
    validate_required_fields,
    ValidationResult,
    ValidationError,
)


class TestFieldSchema:
    def test_creation(self):
        schema = FieldSchema("name", "string", required=True)
        assert schema.name == "name"
        assert schema.type == "string"
        assert schema.required is True

    def test_optional_field(self):
        schema = FieldSchema("optional_field", "string", required=False)
        assert schema.required is False

    def test_extra_params(self):
        schema = FieldSchema("age", "integer", required=True, min_val=0, max_val=150)
        assert schema.min_val == 0
        assert schema.max_val == 150


class TestSchemaValidator:
    def test_valid_record(self):
        fields = [
            FieldSchema("name", "string", required=True),
            FieldSchema("age", "integer", required=True),
        ]
        validator = SchemaValidator(fields)
        
        record = {"name": "John", "age": 30}
        result = validator.validate(record)
        assert result.is_valid

    def test_missing_required_field(self):
        fields = [
            FieldSchema("name", "string", required=True),
            FieldSchema("age", "integer", required=True),
        ]
        validator = SchemaValidator(fields)
        
        record = {"name": "John"}  # missing age
        result = validator.validate(record)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].field == "age"

    def test_type_mismatch(self):
        fields = [FieldSchema("age", "integer", required=True)]
        validator = SchemaValidator(fields)
        
        record = {"age": "thirty"}  # string instead of int
        result = validator.validate(record)
        assert not result.is_valid
        assert result.errors[0].code == "TYPE_MISMATCH"

    def test_url_validation(self):
        fields = [FieldSchema("url", "url", required=True)]
        validator = SchemaValidator(fields)
        
        record = {"url": "not-a-url"}
        result = validator.validate(record)
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_URL_FORMAT"
        
        record = {"url": "https://example.com"}
        result = validator.validate(record)
        assert result.is_valid

    def test_date_validation(self):
        fields = [FieldSchema("date", "date", required=True)]
        validator = SchemaValidator(fields)
        
        record = {"date": "not-a-date"}
        result = validator.validate(record)
        assert not result.is_valid
        assert result.errors[0].code == "INVALID_DATE_FORMAT"
        
        record = {"date": "2024-01-15"}
        result = validator.validate(record)
        assert result.is_valid


class TestValidateRequiredFields:
    def test_all_present(self):
        record = {"subject_id": "1", "subject_title": "Test"}
        required = ["subject_id", "subject_title"]
        result = validate_required_fields(record, required)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_field(self):
        record = {"subject_id": "1"}
        required = ["subject_id", "subject_title"]
        result = validate_required_fields(record, required)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "subject_title" in result.get_error_messages()[0]

    def test_empty_field(self):
        record = {"subject_id": "1", "subject_title": ""}
        required = ["subject_id", "subject_title"]
        result = validate_required_fields(record, required)
        assert not result.is_valid

    def test_none_value(self):
        record = {"subject_id": "1", "subject_title": None}
        required = ["subject_id", "subject_title"]
        result = validate_required_fields(record, required)
        assert not result.is_valid


class TestValidateRecord:
    def test_valid_record(self):
        record = {
            "course_id": "123",
            "course_name": "Test Course",
            "course_url": "https://example.com",
        }
        result = validate_record(record, "swayam")
        assert result.is_valid

    def test_invalid_record_missing_required(self):
        record = {
            "course_id": "123",
            # missing course_name and course_url
        }
        result = validate_record(record, "swayam")
        assert not result.is_valid

    def test_invalid_url_format(self):
        record = {
            "course_id": "123",
            "course_name": "Test",
            "course_url": "not-a-valid-url",
        }
        result = validate_record(record, "swayam")
        assert not result.is_valid