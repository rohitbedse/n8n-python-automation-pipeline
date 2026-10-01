"""
Configuration settings for the scraping pipeline.
All configurable values should be defined here.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

# Base paths - auto-detect project root or use environment variable
def get_project_root() -> Path:
    """Auto-detect project root from environment or file location."""
    env_root = os.getenv("SCRAPER_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    
    # Fallback: detect from this file's location (scraper/config/settings.py -> project root)
    current_dir = Path(__file__).resolve().parent.parent.parent
    return current_dir

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "scraper" / "output"
RUN_LOGS_DIR = PROJECT_ROOT / "scraper" / "run_logs"

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Site configurations
SITES_CONFIG = {
    "mindler": {
        "name": "Mindler Career Library",
        "base_url": "https://careerlibrary.mindler.com",
        "api_domain_list": "https://careerlibrary.mindler.com/api/careerlibrary/v1/careerDomainNameList",
        "api_domain_details": "https://careerlibrary.mindler.com/api/careerlibrary/v1/careerDomainDetails",
        "output_file": OUTPUT_DIR / "mindler_career_library.json",
        "failed_file": OUTPUT_DIR / "mindler_failed_records.json",
        "delay_between_requests": 0.3,
        "timeout": 15,
        "max_retries": 3,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "referer": "https://www.mindler.com/",
    },
    "swayam": {
        "name": "SWAYAM Courses",
        "base_url": "https://swayam.gov.in",
        "api_url": "https://swayam.gov.in/modules/gql/query",
        "explorer_url": "https://swayam.gov.in/explorer",
        "output_file": OUTPUT_DIR / "swayam_courses.json",
        "failed_file": OUTPUT_DIR / "swayam_failed_records.json",
        "delay_between_requests": 0.5,
        "warmup_wait_seconds": 4,
        "timeout": 30,
        "max_retries": 3,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    },
}

# Pipeline settings
PIPELINE_CONFIG = {
    "max_concurrent_scrapers": 1,
    "request_timeout": 30,
    "default_max_retries": 3,
    "retry_backoff_base": 2,  # seconds
    "retry_backoff_max": 60,  # seconds
    "duplicate_check_fields": {
        "mindler": ["subject_id"],
        "swayam": ["course_id", "course_url"],
    },
    "required_fields": {
        "mindler": ["subject_id", "subject_title"],
        "swayam": ["course_id", "course_name", "course_url"],
    },
}

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# HTTP status codes that are non-retryable errors
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}

# Logging
LOG_LEVEL = os.getenv("SCRAPER_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Schema validation
ENABLE_SCHEMA_VALIDATION = True
STRICT_VALIDATION = False  # If True, validation errors raise exceptions