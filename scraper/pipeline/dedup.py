"""
Deduplication and Record Comparison Utilities
==============================================
Provides functions for deduplicating records and comparing
records to detect changes (NEW, UPDATED, UNCHANGED).
"""

from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass
from datetime import date
import hashlib
import json


@dataclass
class RecordChange:
    """Represents a change between two record versions."""
    field: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added', 'removed', 'modified'
    
    def __str__(self) -> str:
        if self.change_type == "added":
            return f"+ {self.field}: {self.new_value}"
        elif self.change_type == "removed":
            return f"- {self.field}: {self.old_value}"
        else:
            return f"~ {self.field}: {self.old_value} -> {self.new_value}"


def generate_record_key(record: Dict[str, Any], key_fields: List[str]) -> str:
    """
    Generate a unique key for a record based on specified fields.
    
    Args:
        record: The record dictionary
        key_fields: List of field names to use for key generation
        
    Returns:
        String key for deduplication
    """
    key_parts = []
    for field in key_fields:
        value = record.get(field)
        if value is not None:
            key_parts.append(str(value))
        else:
            key_parts.append("__NULL__")
    
    return "|".join(key_parts)


def generate_content_hash(record: Dict[str, Any], exclude_fields: Optional[Set[str]] = None) -> str:
    """
    Generate a content hash for a record, excluding specified fields.
    
    Args:
        record: The record dictionary
        exclude_fields: Set of field names to exclude from hash
        
    Returns:
        SHA256 hash of record content
    """
    if exclude_fields is None:
        exclude_fields = {"last_verified_date", "scraped_date", "run_id", "_metadata", "_scraped_run_id", "_scraped_at", "_classification", "_changes", "_changed_fields"}
    
    # Create a copy without excluded fields
    filtered = {k: v for k, v in record.items() if k not in exclude_fields}
    
    # Sort keys for consistent hashing
    content = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def deduplicate_records(
    records: List[Dict[str, Any]], 
    key_fields: List[str],
    prefer_newest: bool = True
) -> List[Dict[str, Any]]:
    """
    Deduplicate records based on key fields.
    
    Args:
        records: List of records to deduplicate
        key_fields: Fields to use for deduplication key
        prefer_newest: If True, keep the last occurrence (newest); else keep first
        
    Returns:
        Deduplicated list of records
    """
    seen: Dict[str, Dict[str, Any]] = {}
    
    for record in records:
        key = generate_record_key(record, key_fields)
        
        if key not in seen:
            seen[key] = record
        elif prefer_newest:
            # Keep the newer record (last one wins)
            seen[key] = record
        # If not prefer_newest, keep the first (existing) record
    
    return list(seen.values())


def compare_records(
    old_record: Dict[str, Any], 
    new_record: Dict[str, Any],
    exclude_fields: Optional[Set[str]] = None,
    ignore_fields: Optional[Set[str]] = None
) -> List[RecordChange]:
    """
    Compare two records and return list of changes.
    
    Args:
        old_record: Previous version of the record
        new_record: New version of the record
        exclude_fields: Fields to exclude from comparison
        ignore_fields: Additional fields to ignore
        
    Returns:
        List of RecordChange objects
    """
    if exclude_fields is None:
        exclude_fields = {"last_verified_date", "scraped_date", "run_id", "_metadata", "_scraped_run_id", "_scraped_at", "_classification", "_changes", "_changed_fields"}
    
    if ignore_fields:
        exclude_fields = exclude_fields.union(ignore_fields)
    
    changes = []
    all_keys = set(old_record.keys()) | set(new_record.keys())
    
    for key in sorted(all_keys):
        if key in exclude_fields:
            continue
        
        old_val = old_record.get(key)
        new_val = new_record.get(key)
        
        if old_val == new_val:
            continue
        
        if key not in old_record:
            changes.append(RecordChange(key, None, new_val, "added"))
        elif key not in new_record:
            changes.append(RecordChange(key, old_val, None, "removed"))
        else:
            changes.append(RecordChange(key, old_val, new_val, "modified"))
    
    return changes


def classify_records(
    new_records: List[Dict[str, Any]],
    existing_records: List[Dict[str, Any]],
    key_fields: List[str],
    exclude_fields: Optional[Set[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Classify records as NEW, UPDATED, or UNCHANGED.
    
    Args:
        new_records: Newly scraped records
        existing_records: Previously saved records
        key_fields: Fields to use for matching records
        exclude_fields: Fields to exclude from change detection
        
    Returns:
        Dictionary with 'new', 'updated', 'unchanged' keys containing records
    """
    # Build lookup for existing records
    existing_by_key = {}
    for record in existing_records:
        key = generate_record_key(record, key_fields)
        existing_by_key[key] = record
    
    new_list = []
    updated_list = []
    unchanged_list = []
    
    for record in new_records:
        key = generate_record_key(record, key_fields)
        
        if key not in existing_by_key:
            # New record
            record["_classification"] = "NEW"
            new_list.append(record)
        else:
            existing = existing_by_key[key]
            changes = compare_records(existing, record, exclude_fields)
            
            if changes:
                record["_classification"] = "UPDATED"
                record["_changes"] = [str(c) for c in changes]
                record["_changed_fields"] = [c.field for c in changes]
                updated_list.append(record)
            else:
                record["_classification"] = "UNCHANGED"
                unchanged_list.append(record)
    
    return {
        "new": new_list,
        "updated": updated_list,
        "unchanged": unchanged_list,
    }


def merge_records(
    new_records: List[Dict[str, Any]],
    existing_records: List[Dict[str, Any]],
    key_fields: List[str],
) -> List[Dict[str, Any]]:
    """
    Merge new records with existing records, preserving existing data
    for unchanged records and updating changed ones.
    
    Args:
        new_records: Newly scraped records
        existing_records: Previously saved records
        key_fields: Fields to use for matching
        
    Returns:
        Merged list of records
    """
    classification = classify_records(new_records, existing_records, key_fields)
    
    # Start with unchanged existing records
    merged = classification["unchanged"].copy()
    
    # Add new records
    merged.extend(classification["new"])
    
    # Add updated records (new versions)
    merged.extend(classification["updated"])
    
    return merged


def get_record_stats(
    new_records: List[Dict[str, Any]],
    existing_records: List[Dict[str, Any]],
    key_fields: List[str],
) -> Dict[str, int]:
    """
    Get statistics about record changes.
    
    Returns:
        Dictionary with counts
    """
    classification = classify_records(new_records, existing_records, key_fields)
    
    return {
        "total_new": len(classification["new"]),
        "total_updated": len(classification["updated"]),
        "total_unchanged": len(classification["unchanged"]),
        "total_existing": len(existing_records),
        "total_after_merge": len(existing_records) + len(classification["new"]) + len(classification["updated"]),
    }