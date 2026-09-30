"""
Shared Pipeline Utilities for Career Data Scraping
===================================================
Provides common utilities for fetching, validation, cleaning, 
deduplication, writing, and logging across all site scrapers.
"""

from .http import (
    create_session,
    fetch_with_retry,
    fetch_json_with_retry,
    fetch_html_with_retry,
    RETRYABLE_STATUS_CODES,
    NON_RETRYABLE_STATUS_CODES,
)
from .clean import (
    clean_text,
    clean_text_safe,
    clean_html,
    normalize_url,
    normalize_date,
    normalize_whitespace,
    deduplicate_list,
    strip_html_tags,
)
from .validate import (
    validate_record,
    validate_required_fields,
    ValidationError,
    ValidationResult,
)
from .dedup import (
    deduplicate_records,
    generate_record_key,
    compare_records,
    RecordChange,
)
from .write import (
    write_json_atomic,
    write_failed_records,
    load_json_file,
    load_existing_records,
)
from .logging_utils import (
    setup_logging,
    get_logger,
    log_step,
    log_summary,
)
from .rate_limit import RateLimiter, RateLimitConfig
from .dedup import classify_records, merge_records

__all__ = [
    # HTTP
    "create_session",
    "fetch_with_retry",
    "fetch_json_with_retry",
    "fetch_html_with_retry",
    "RETRYABLE_STATUS_CODES",
    "NON_RETRYABLE_STATUS_CODES",
    # Clean
    "clean_text",
    "clean_text_safe",
    "clean_html",
    "normalize_url",
    "normalize_date",
    "normalize_whitespace",
    "deduplicate_list",
    "strip_html_tags",
    # Validate
    "validate_record",
    "validate_required_fields",
    "ValidationError",
    "ValidationResult",
    # Dedup
    "deduplicate_records",
    "generate_record_key",
    "compare_records",
    "classify_records",
    "merge_records",
    "RecordChange",
    # Write
    "write_json_atomic",
    "write_failed_records",
    "load_json_file",
    "load_existing_records",
    # Logging
    "setup_logging",
    "get_logger",
    "log_step",
    "log_summary",
    # Rate Limit
    "RateLimiter",
    "RateLimitConfig",
]