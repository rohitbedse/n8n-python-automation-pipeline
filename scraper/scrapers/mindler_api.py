"""
Mindler Career Library Scraper (API based)
"""

import json
from typing import Any, Dict, List, Optional

from .base import BaseScraper, ScraperConfig
from ..pipeline.clean import clean_text, clean_text_safe, normalize_url
from ..config.settings import SITES_CONFIG

class MindlerAPIScraper(BaseScraper):
    """Scraper for Mindler Career Library using official API endpoints."""

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.api_domain_list = config.extra_config.get("api_domain_list")
        self.api_domain_details = config.extra_config.get("api_domain_details")

    def scrape(self) -> List[Dict[str, Any]]:
        self.logger.info("Fetching career domain list...")
        domain_list_data = self._fetch_json(self.api_domain_list)
        if not domain_list_data or "data" not in domain_list_data:
            self.logger.error("Invalid domain list response")
            return []
        domains = domain_list_data["data"]
        self.logger.info(f"Found {len(domains)} career domains")
        all_records = []
        for i, domain in enumerate(domains):
            # API returns Elasticsearch-style docs: real fields live under "_source"
            source = domain.get("_source", {})
            if source.get("isDraft") == 1:
                continue
            domain_name = source.get("career_domain_name", "")
            tagline = source.get("tagline", "")
            if not domain_name or not tagline:
                continue
            self.logger.info(f"Fetching details for domain {i+1}/{len(domains)}: {domain_name}")
            try:
                # Real endpoint is a POST keyed by "tagline", not a GET with "careerDomainName"
                detail_data = self._fetch_json(
                    self.api_domain_details,
                    method="POST",
                    json={"tagline": tagline},
                )
            except RuntimeError as e:
                self.logger.warning(f"Failed to fetch details for {domain_name}: {e}")
                continue
            records = detail_data.get("data") if detail_data else None
            if not records:
                continue
            detail_source = records[0].get("_source", {})
            record = self._parse_domain_detail(domain_name, detail_source)
            if record:
                all_records.append(record)
        return all_records

    def _parse_domain_detail(self, domain_name: str, source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if source.get("isDraft") == 1:
            return None
        subcareers = source.get("career_details", [])
        cleaned_subcareers = []
        for sub in subcareers:
            if sub.get("isDraft") == 1:
                continue
            cleaned = {
                "id": str(sub.get("id", "")),
                "name": clean_text(sub.get("career_name", "")),
                "keywords": clean_text(sub.get("keywords", "")),
                "notes": clean_text(sub.get("notes", "")),
                "eligibility_status": str(sub.get("eligliblity_status", "")),
                "entrance_exams": sub.get("career_entrance", []),
                "colleges_india": sub.get("career_colleges", []),
                "colleges_abroad": sub.get("career_abroad_colleges", []),
                "career_paths": sub.get("careers_path", {}),
                "pros_cons": sub.get("pros_cons", []),
                "career_opportunities": sub.get("career_opportunities", []),
                "work_description": sub.get("career_job_description", []),
            }
            cleaned_subcareers.append(cleaned)
        record = {
            "subject_id": clean_text_safe(domain_name).lower().replace(" ", "_"),
            "subject_title": clean_text_safe(domain_name),
            "description": clean_text_safe(source.get("description", "")),
            "image": clean_text_safe(source.get("image", "")),
            "subcareers": cleaned_subcareers,
        }
        return record

    def transform_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in raw_record or raw_record[field] is None:
                raw_record[field] = ""
        for key, value in raw_record.items():
            if isinstance(value, str):
                raw_record[key] = clean_text_safe(value)
            elif isinstance(value, list):
                raw_record[key] = [v for v in value if v]
        raw_record["source"] = "mindler"
        return raw_record
