"""
File Writing Utilities
======================
Provides atomic file writing, failed records handling, and JSON loading.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import tempfile


def write_json_atomic(
    data: Any,
    file_path: Path,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """
    Write JSON data atomically using a temporary file.
    
    Args:
        data: Data to write
        file_path: Target file path
        indent: JSON indentation
        ensure_ascii: Whether to escape non-ASCII characters
        
    Returns:
        True if successful
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            json.dump(data, tmp_file, ensure_ascii=ensure_ascii, indent=indent)
            tmp_path = Path(tmp_file.name)
        
        # Atomic replace
        tmp_path.replace(file_path)
        return True
        
    except Exception as e:
        # Clean up temp file if it exists
        if 'tmp_path' in locals() and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def write_failed_records(
    failed_records: List[Dict[str, Any]],
    file_path: Path,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """
    Write failed records to a JSON file with metadata.
    
    Args:
        failed_records: List of failed records with error info
        file_path: Target file path
        indent: JSON indentation
        ensure_ascii: Whether to escape non-ASCII characters
        
    Returns:
        True if successful
    """
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_failed": len(failed_records),
        "failed_records": failed_records,
    }
    
    return write_json_atomic(output, file_path, indent, ensure_ascii)


def load_json_file(file_path: Path) -> Optional[Any]:
    """
    Load JSON data from a file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Parsed JSON data or None if file doesn't exist or is invalid
    """
    try:
        if not Path(file_path).exists():
            return None
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    except (json.JSONDecodeError, OSError):
        return None


def load_existing_records(file_path: Path, record_key: str = None) -> List[Dict[str, Any]]:
    """
    Load existing records from a JSON file.
    
    Handles both array format and object-with-courses format.
    
    Args:
        file_path: Path to JSON file
        record_key: If the JSON is an object, the key containing the records array
        
    Returns:
        List of records
    """
    data = load_json_file(file_path)
    
    if data is None:
        return []
    
    if isinstance(data, list):
        return data
    
    if isinstance(data, dict):
        if record_key and record_key in data:
            return data[record_key] if isinstance(data[record_key], list) else []
        # Try common keys
        for key in ["courses", "data", "records", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        # If it's a single record object, wrap in list
        if all(isinstance(v, (str, int, float, bool, type(None), list, dict)) for v in data.values()):
            return [data]
    
    return []


def backup_file(file_path: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Create a timestamped backup of a file.
    
    Args:
        file_path: File to backup
        backup_dir: Directory for backups (default: same dir as file)
        
    Returns:
        Path to backup file or None if failed
    """
    if not file_path.exists():
        return None
    
    if backup_dir is None:
        backup_dir = file_path.parent / "backups"
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    backup_path = backup_dir / backup_name
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception:
        return None


def read_json_lines(file_path: Path) -> List[Dict[str, Any]]:
    """
    Read JSON Lines format file (one JSON object per line).
    
    Args:
        file_path: Path to JSONL file
        
    Returns:
        List of parsed objects
    """
    records = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON on line {line_num}: {e}")
    except OSError:
        pass
    
    return records


def write_json_lines(records: List[Dict[str, Any]], file_path: Path) -> bool:
    """
    Write records in JSON Lines format.
    
    Args:
        records: List of records to write
        file_path: Target file path
        
    Returns:
        True if successful
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            for record in records:
                tmp_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            tmp_path = Path(tmp_file.name)
        
        tmp_path.replace(file_path)
        return True
        
    except Exception as e:
        if 'tmp_path' in locals() and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise