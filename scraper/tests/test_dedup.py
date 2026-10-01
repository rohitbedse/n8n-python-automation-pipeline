"""Tests for scraper/pipeline/dedup.py"""
import pytest
from scraper.pipeline.dedup import (
    generate_record_key,
    generate_content_hash,
    deduplicate_records,
    compare_records,
    RecordChange,
    classify_records,
    merge_records,
    get_record_stats,
)


class TestGenerateRecordKey:
    def test_basic_key_generation(self):
        record = {"subject_id": "123", "subject_title": "Test"}
        key = generate_record_key(record, ["subject_id"])
        assert key == "123"

    def test_multiple_key_fields(self):
        record = {"course_id": "abc", "course_url": "http://example.com"}
        key = generate_record_key(record, ["course_id", "course_url"])
        assert key == "abc|http://example.com"

    def test_none_values(self):
        record = {"subject_id": None, "subject_title": "Test"}
        key = generate_record_key(record, ["subject_id"])
        assert key == "__NULL__"


class TestGenerateContentHash:
    def test_hash_excludes_fields(self):
        record = {
            "course_id": "123",
            "course_name": "Test",
            "last_verified_date": "2024-01-01",
            "scraped_date": "2024-01-01",
        }
        hash1 = generate_content_hash(record)
        record["last_verified_date"] = "2025-01-01"
        hash2 = generate_content_hash(record)
        assert hash1 == hash2  # Should be same because date fields excluded

    def test_hash_changes_with_content(self):
        record1 = {"course_id": "123", "course_name": "Test"}
        record2 = {"course_id": "123", "course_name": "Different"}
        assert generate_content_hash(record1) != generate_content_hash(record2)


class TestDeduplicateRecords:
    def test_removes_duplicates(self):
        records = [
            {"subject_id": "1", "subject_title": "A"},
            {"subject_id": "1", "subject_title": "B"},  # duplicate key
            {"subject_id": "2", "subject_title": "C"},
        ]
        result = deduplicate_records(records, ["subject_id"])
        assert len(result) == 2
        assert result[0]["subject_id"] == "1"
        assert result[1]["subject_id"] == "2"

    def test_prefer_newest(self):
        records = [
            {"subject_id": "1", "subject_title": "OLD"},
            {"subject_id": "1", "subject_title": "NEW"},
        ]
        result = deduplicate_records(records, ["subject_id"], prefer_newest=True)
        assert len(result) == 1
        assert result[0]["subject_title"] == "NEW"

    def test_prefer_first(self):
        records = [
            {"subject_id": "1", "subject_title": "FIRST"},
            {"subject_id": "1", "subject_title": "SECOND"},
        ]
        result = deduplicate_records(records, ["subject_id"], prefer_newest=False)
        assert len(result) == 1
        assert result[0]["subject_title"] == "FIRST"


class TestCompareRecords:
    def test_no_changes(self):
        old = {"course_id": "1", "course_name": "Test"}
        new = {"course_id": "1", "course_name": "Test"}
        changes = compare_records(old, new)
        assert len(changes) == 0

    def test_added_field(self):
        old = {"course_id": "1"}
        new = {"course_id": "1", "course_name": "Test"}
        changes = compare_records(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "added"
        assert changes[0].field == "course_name"

    def test_removed_field(self):
        old = {"course_id": "1", "course_name": "Test"}
        new = {"course_id": "1"}
        changes = compare_records(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "removed"

    def test_modified_field(self):
        old = {"course_id": "1", "course_name": "Old"}
        new = {"course_id": "1", "course_name": "New"}
        changes = compare_records(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "modified"
        assert changes[0].old_value == "Old"
        assert changes[0].new_value == "New"

    def test_excludes_internal_fields(self):
        old = {"course_id": "1", "_scraped_run_id": "old_run"}
        new = {"course_id": "1", "_scraped_run_id": "new_run"}
        changes = compare_records(old, new)
        assert len(changes) == 0  # Should ignore _scraped_run_id


class TestClassifyRecords:
    def test_new_record(self):
        new_records = [{"subject_id": "1", "subject_title": "New"}]
        existing_records = []
        result = classify_records(new_records, existing_records, ["subject_id"])
        assert len(result["new"]) == 1
        assert len(result["updated"]) == 0
        assert len(result["unchanged"]) == 0

    def test_unchanged_record(self):
        new_records = [{"subject_id": "1", "subject_title": "Same"}]
        existing_records = [{"subject_id": "1", "subject_title": "Same"}]
        result = classify_records(new_records, existing_records, ["subject_id"])
        assert len(result["new"]) == 0
        assert len(result["updated"]) == 0
        assert len(result["unchanged"]) == 1

    def test_updated_record(self):
        new_records = [{"subject_id": "1", "subject_title": "Updated"}]
        existing_records = [{"subject_id": "1", "subject_title": "Original"}]
        result = classify_records(new_records, existing_records, ["subject_id"])
        assert len(result["new"]) == 0
        assert len(result["updated"]) == 1
        assert len(result["unchanged"]) == 0

    def test_mixed_classification(self):
        new_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Updated"},
            {"subject_id": "3", "subject_title": "New"},
        ]
        existing_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Original"},
        ]
        result = classify_records(new_records, existing_records, ["subject_id"])
        assert len(result["new"]) == 1
        assert len(result["updated"]) == 1
        assert len(result["unchanged"]) == 1

    def test_ignores_internal_metadata(self):
        new_records = [{"subject_id": "1", "subject_title": "Test", "_scraped_run_id": "run2"}]
        existing_records = [{"subject_id": "1", "subject_title": "Test", "_scraped_run_id": "run1"}]
        result = classify_records(new_records, existing_records, ["subject_id"])
        assert len(result["unchanged"]) == 1  # Should be unchanged despite different run_id
        assert len(result["updated"]) == 0


class TestMergeRecords:
    def test_merge_preserves_all(self):
        new_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Updated"},
            {"subject_id": "3", "subject_title": "New"},
        ]
        existing_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Original"},
        ]
        merged = merge_records(new_records, existing_records, ["subject_id"])
        assert len(merged) == 3
        ids = {r["subject_id"] for r in merged}
        assert ids == {"1", "2", "3"}


class TestGetRecordStats:
    def test_stats_correct(self):
        new_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Updated"},
            {"subject_id": "3", "subject_title": "New"},
        ]
        existing_records = [
            {"subject_id": "1", "subject_title": "Same"},
            {"subject_id": "2", "subject_title": "Original"},
        ]
        stats = get_record_stats(new_records, existing_records, ["subject_id"])
        assert stats["total_new"] == 1
        assert stats["total_updated"] == 1
        assert stats["total_unchanged"] == 1
        assert stats["total_existing"] == 2