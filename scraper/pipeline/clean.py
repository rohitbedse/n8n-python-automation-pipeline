"""
Data Cleaning Utilities
=======================
Provides functions for cleaning and normalizing scraped data.
"""

import html
import re
from typing import Any, Optional, List, Set
from urllib.parse import urljoin, urlparse


def clean_text(value: Any) -> Optional[str]:
    """
    Clean and normalize text content.
    
    - Decodes HTML entities
    - Removes HTML tags
    - Normalizes whitespace
    - Returns None for empty/None input
    """
    if value is None:
        return None
    
    # Convert to string and decode HTML entities
    text = html.unescape(str(value))
    
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    
    # Remove escape characters (\n, \r, \t, etc.)
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ")
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    return text if text else None


def clean_text_safe(value: Any) -> str:
    """
    Clean and normalize text, returning '' instead of None for empty/missing input.
    Use in transform_record() when setting fields that must be strings.
    """
    result = clean_text(value)
    return result if result is not None else ""


def clean_html(value: Any) -> Optional[str]:
    """
    Clean HTML content - alias for clean_text for clarity.
    """
    return clean_text(value)


def strip_html_tags(value: Any) -> Optional[str]:
    """
    Strip HTML tags only, preserving whitespace more than clean_text.
    """
    if value is None:
        return None
    
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return text.strip() if text.strip() else None


def normalize_whitespace(value: Any) -> Optional[str]:
    """
    Normalize whitespace only (no HTML tag removal).
    """
    if value is None:
        return None
    
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def normalize_url(value: Any, base_url: str = "") -> Optional[str]:
    """
    Normalize and validate a URL.
    
    - Resolves relative URLs against base_url
    - Validates URL scheme
    - Returns None for invalid/empty URLs
    """
    if not value:
        return None
    
    url = str(value).strip()
    
    # Resolve relative URLs
    if base_url and not url.startswith(("http://", "https://")):
        url = urljoin(base_url, url)
    
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    
    if parsed.scheme not in ("http", "https"):
        return None
    
    return url


def normalize_date(value: Any) -> Optional[str]:
    """
    Normalize date to ISO format (YYYY-MM-DD).
    
    Handles various date formats and returns ISO date string.
    """
    if not value:
        return None
    
    from datetime import datetime
    
    raw = str(value).strip().replace("Z", "+00:00")
    
    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    
    # Try fromisoformat for ISO formats with timezone
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        pass
    
    return None


def deduplicate_list(values: Optional[List[Any]], key_func: Optional[callable] = None) -> List[str]:
    """
    Deduplicate a list of values while preserving order.
    
    Args:
        values: List of values to deduplicate
        key_func: Optional function to compute comparison key (default: casefold)
        
    Returns:
        Deduplicated list of cleaned strings
    """
    if not values:
        return []
    
    result = []
    seen: Set[str] = set()
    
    for value in values:
        cleaned = clean_text(value)
        if not cleaned:
            continue
        
        key = key_func(cleaned) if key_func else cleaned.casefold()
        if key not in seen:
            result.append(cleaned)
            seen.add(key)
    
    return result


def normalize_field(value: Any, field_type: str) -> Any:
    """
    Normalize a field value based on its expected type.
    
    Args:
        value: Raw value to normalize
        field_type: Type hint ('string', 'integer', 'float', 'boolean', 'list', 'date', 'url')
        
    Returns:
        Normalized value
    """
    if value is None:
        return None
    
    if field_type == "string":
        return clean_text(value)
    
    elif field_type == "integer":
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None
    
    elif field_type == "float":
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None
    
    elif field_type == "boolean":
        if isinstance(value, bool):
            return value
        str_val = str(value).strip().lower()
        if str_val in ("true", "1", "yes", "on"):
            return True
        if str_val in ("false", "0", "no", "off"):
            return False
        return None
    
    elif field_type == "list":
        if isinstance(value, list):
            return deduplicate_list(value)
        if isinstance(value, str):
            # Try to parse as comma-separated
            return deduplicate_list([v.strip() for v in value.split(",")])
        return []
    
    elif field_type == "date":
        return normalize_date(value)
    
    elif field_type == "url":
        return normalize_url(value)
    
    return value