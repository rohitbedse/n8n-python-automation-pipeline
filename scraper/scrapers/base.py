"""
Base Scraper Class
==================
Abstract base class for all site scrapers with common functionality.
"""

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..pipeline import (
    create_session,
    fetch_json_with_retry,
    fetch_html_with_retry,
    validate_record,
    validate_required_fields,
    deduplicate_records,
    classify_records,
    write_json_atomic,
    write_failed_records,
    load_existing_records,
    generate_record_key,
    RateLimiter,
    RateLimitConfig,
    setup_logging,
    get_logger,
)
from ..config.settings import SITES_CONFIG, PIPELINE_CONFIG, RETRYABLE_STATUS_CODES


@dataclass
class ScraperConfig:
    """Configuration for a scraper."""
    site: str
    name: str
    base_url: str
    output_file: Path
    failed_file: Path
    delay_between_requests: float
    timeout: int
    max_retries: int
    user_agent: str
    referer: Optional[str] = None
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrapingResult:
    """Result of a scraping run."""
    site: str
    run_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    success: bool
    records_scraped: int = 0
    records_new: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    records_failed: int = 0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class BaseScraper(ABC):
    """Abstract base class for site scrapers."""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.site = config.site
        self.logger = setup_logging(f"scraper.{self.site}")
        self.rate_limiter = RateLimiter(RateLimitConfig(
            requests_per_second=1.0 / config.delay_between_requests,
            burst_limit=3,
        ))
        self.session = create_session(
            user_agent=config.user_agent,
            referer=config.referer,
            timeout=config.timeout,
        )
        self.run_id = f"{self.site}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time = datetime.now()
        
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrape data from the site.
        
        Returns:
            List of raw scraped records
        """
        pass
    
    @abstractmethod
    def transform_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a raw record to the standardized schema.
        
        Args:
            raw_record: Raw data from the site
            
        Returns:
            Transformed record matching the schema
        """
        pass
    
    def get_key_fields(self) -> List[str]:
        """Get the fields used for deduplication key generation."""
        return PIPELINE_CONFIG["duplicate_check_fields"].get(self.site, ["id"])
    
    def get_required_fields(self) -> List[str]:
        """Get required fields for validation."""
        return PIPELINE_CONFIG["required_fields"].get(self.site, ["id"])
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        self.rate_limiter.acquire()
    
    def _fetch_json(self, url: str, method: str = "GET", **kwargs) -> Any:
        """Fetch JSON with retry and rate limiting."""
        self._rate_limit()
        result = fetch_json_with_retry(
            self.session,
            method,
            url,
            max_retries=self.config.max_retries,
            timeout=self.config.timeout,
            **kwargs,
        )
        if not result.success:
            raise RuntimeError(f"Failed to fetch {url}: {result.error}")
        return result.data
    
    def _fetch_html(self, url: str, **kwargs) -> str:
        """Fetch HTML with retry and rate limiting."""
        self._rate_limit()
        result = fetch_html_with_retry(
            self.session,
            url,
            max_retries=self.config.max_retries,
            timeout=self.config.timeout,
            **kwargs,
        )
        if not result.success:
            raise RuntimeError(f"Failed to fetch {url}: {result.error}")
        return result.data
    
    def _validate_and_clean(self, record: Dict[str, Any]) -> tuple:
        """
        Validate a record against schema and required fields.
        
        Returns:
            (validated_record, error_reason) — record is None if validation fails
        """
        # Check required fields
        required_fields = self.get_required_fields()
        req_result = validate_required_fields(record, required_fields)
        if not req_result.is_valid:
            reasons = req_result.get_error_messages()
            return None, f"Missing required fields: {'; '.join(reasons)}"
        
        # Validate against schema
        schema_result = validate_record(record, self.site)
        if not schema_result.is_valid:
            reasons = schema_result.get_error_messages()
            return None, f"Schema validation failed: {'; '.join(reasons)}"
        
        return record, None
    
    @staticmethod
    def _strip_internal_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
        """Remove internal pipeline metadata fields before writing to output."""
        internal_keys = {
            "_scraped_run_id", "_scraped_at",
            "_classification", "_changes", "_changed_fields",
        }
        return {k: v for k, v in record.items() if k not in internal_keys}
    
    def run(self) -> ScrapingResult:
        """
        Run the complete scraping pipeline.
        
        Returns:
            ScrapingResult with statistics
        """
        self.logger.info(f"Starting {self.config.name} scraper (run_id: {self.run_id})")
        
        try:
            # Step 1: Scrape raw data
            self.logger.info("Scraping data from source...")
            raw_records = self.scrape()
            self.logger.info(f"Scraped {len(raw_records)} raw records")
            if not raw_records:
                raise RuntimeError(
                    "Scraper returned no records; existing output was not modified"
                )
            
            # Step 2: Transform records
            self.logger.info("Transforming records...")
            transformed_records = []
            failed_records = []
            
            for i, raw_record in enumerate(raw_records):
                try:
                    transformed = self.transform_record(raw_record)
                    transformed["_scraped_run_id"] = self.run_id
                    transformed["_scraped_at"] = datetime.now().isoformat()
                    transformed_records.append(transformed)
                except Exception as e:
                    failed_records.append({
                        "raw_record": raw_record,
                        "reason": f"Transform error: {e}",
                        "stage": "transform",
                        "index": i,
                    })
                    self.logger.warning(f"Failed to transform record {i}: {e}")
            
            self.logger.info(f"Transformed {len(transformed_records)} records, {len(failed_records)} failed")
            
            # Step 3: Validate records
            self.logger.info("Validating records...")
            valid_records = []
            
            for record in transformed_records:
                validated, error_reason = self._validate_and_clean(record)
                if validated:
                    valid_records.append(validated)
                else:
                    failed_records.append({
                        "record": record,
                        "reason": error_reason,
                        "stage": "validation",
                    })
            
            self.logger.info(f"Validated {len(valid_records)} records, "
                           f"{len(failed_records)} total failed so far")
            
            # Step 4: Deduplicate
            self.logger.info("Deduplicating records...")
            key_fields = self.get_key_fields()
            deduplicated = deduplicate_records(valid_records, key_fields)
            self.logger.info(f"After deduplication: {len(deduplicated)} records")
            
            # Step 5: Load existing records and classify changes
            self.logger.info("Loading existing records and classifying changes...")
            existing_records = load_existing_records(self.config.output_file)
            
            # Exclude internal pipeline metadata from change detection
            exclude_fields = {"_scraped_run_id", "_scraped_at", "_classification", "_changes", "_changed_fields"}
            
            classification = classify_records(
                deduplicated,
                existing_records,
                key_fields,
                exclude_fields=exclude_fields,
            )
            
            # Step 6: Merge records (using the already-computed classification)
            merged_records = []
            merged_records.extend(classification["unchanged"])
            merged_records.extend(classification["new"])
            merged_records.extend(classification["updated"])
            
            # Step 7: Strip internal metadata before writing
            clean_records = [self._strip_internal_metadata(r) for r in merged_records]
            
            # Step 8: Write output
            self.logger.info(f"Writing {len(clean_records)} records to {self.config.output_file}")
            write_json_atomic(clean_records, self.config.output_file)
            
            # Step 9: Write failed records
            if failed_records:
                self.logger.info(f"Writing {len(failed_records)} failed records to {self.config.failed_file}")
                write_failed_records(failed_records, self.config.failed_file)
            
            # Calculate statistics
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            failed_transform = len([f for f in failed_records if f.get("stage") == "transform"])
            failed_validation = len([f for f in failed_records if f.get("stage") == "validation"])
            
            result = ScrapingResult(
                site=self.site,
                run_id=self.run_id,
                start_time=self.start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                success=True,
                records_scraped=len(raw_records),
                records_new=len(classification["new"]),
                records_updated=len(classification["updated"]),
                records_unchanged=len(classification["unchanged"]),
                records_failed=len(failed_records),
                details={
                    "raw_records": len(raw_records),
                    "transformed_records": len(transformed_records),
                    "valid_records": len(valid_records),
                    "deduplicated_records": len(deduplicated),
                    "existing_records": len(existing_records),
                    "merged_records": len(clean_records),
                    "failed_transform": failed_transform,
                    "failed_validation": failed_validation,
                    "updated_field_changes": {
                        r.get(self.get_key_fields()[0], "?"): r.get("_changed_fields", [])
                        for r in classification["updated"]
                    },
                }
            )
            
            self.logger.info(
                f"Scraping completed: {result.records_new} new, "
                f"{result.records_updated} updated, {result.records_unchanged} unchanged, "
                f"{result.records_failed} failed"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {e}", exc_info=True)
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            return ScrapingResult(
                site=self.site,
                run_id=self.run_id,
                start_time=self.start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                success=False,
                error=str(e),
            )


def create_scraper(site: str) -> BaseScraper:
    """Factory function to create a scraper instance."""
    site_config = SITES_CONFIG.get(site)
    if not site_config:
        raise ValueError(f"Unknown site: {site}")
    
    config = ScraperConfig(
        site=site,
        name=site_config["name"],
        base_url=site_config["base_url"],
        output_file=Path(site_config["output_file"]),
        failed_file=Path(site_config["failed_file"]),
        delay_between_requests=site_config["delay_between_requests"],
        timeout=site_config["timeout"],
        max_retries=site_config["max_retries"],
        user_agent=site_config["user_agent"],
        referer=site_config.get("referer"),
        extra_config=site_config,
    )
    
    if site == "mindler":
        from .mindler_api import MindlerAPIScraper
        return MindlerAPIScraper(config)
    elif site == "swayam":
        from .swayam_graphql import SwayamGraphQLScraper
        return SwayamGraphQLScraper(config)
    else:
        raise ValueError(f"No scraper implementation for site: {site}")