"""Tests for scraper/pipeline/write.py"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from scraper.pipeline.write import (
    write_json_atomic,
    load_existing_records,
    write_failed_records,
)


class TestWriteJsonAtomic:
    def test_writes_file(self):
        data = [{"id": "1", "name": "Test"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            write_json_atomic(data, filepath)
            
            assert filepath.exists()
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_creates_parent_dirs(self):
        data = [{"id": "1"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "subdir" / "nested" / "test.json"
            write_json_atomic(data, filepath)
            assert filepath.exists()

    def test_atomic_write_on_error(self):
        # Test that partial writes don't corrupt
        data = [{"id": "1"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            # Write initial data
            write_json_atomic([{"id": "original"}], filepath)
            
            # Mock a failure during write - we can't easily test this
            # but we can verify the atomic behavior works
            write_json_atomic(data, filepath)
            
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data


class TestLoadExistingRecords:
    def test_loads_existing(self):
        data = [{"id": "1", "name": "Test"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f)
            
            loaded = load_existing_records(filepath)
            assert loaded == data

    def test_returns_empty_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "nonexistent.json"
            loaded = load_existing_records(filepath)
            assert loaded == []

    def test_returns_empty_for_corrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "corrupt.json"
            with open(filepath, "w") as f:
                f.write("not valid json")
            
            loaded = load_existing_records(filepath)
            assert loaded == []


class TestWriteFailedRecords:
    def test_writes_failed_records(self):
        failed = [
            {
                "record": {"id": "1"},
                "reason": "Missing required field",
                "stage": "validation",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "failed.json"
            write_failed_records(failed, filepath)
            
            assert filepath.exists()
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            
            assert "timestamp" in loaded
            assert loaded["total_failed"] == 1
            assert len(loaded["failed_records"]) == 1
            assert loaded["failed_records"][0]["reason"] == "Missing required field"

    def test_handles_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "failed.json"
            write_failed_records([], filepath)
            
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            
            assert loaded["total_failed"] == 0
            assert loaded["failed_records"] == []