"""
Mindler Career Library Scraper
==============================
Scrapes career domain data from Mindler Career Library API.
"""

import json
from typing import Any, Dict, List, Optional

from .base import BaseScraper, ScraperConfig
from ..pipeline.clean import clean_text, clean_text_safe, normalize_url
from ..config.settings import SITES_CONFIG


class MindlerScraper(BaseScraper):
    """Scraper for Mindler Career Library."""
    
    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.api_domain_list = config.extra_config.get("api_domain_list")
        self.api_domain_details = config.extra_config.get("api_domain_details")
        
    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape career domains from Mindler API."""
        self.logger.info("Fetching career domain list...")
        
        # Fetch domain list
        domain_list_data = self._fetch_json(self.api_domain_list)
        
        if not domain_list_data or "data" not in domain_list_data:
            self.logger.error("Invalid domain list response")
            return []
        
        domains = domain_list_data["data"]
        self.logger.info(f"Found {len(domains)} career domains")
        
        # Fetch details for each domain
        all_records = []
        for i, domain in enumerate(domains):
            try:
                domain_name = domain.get("careerDomainName", "")
                if not domain_name:
                    continue
                    
                self.logger.info(f"Fetching details for domain {i+1}/{len(domains)}: {domain_name}")
                
                # Fetch domain details
                detail_url = f"{self.api_domain_details}?careerDomainName={domain_name}"
                detail_data = self._fetch_json(detail_url)
                
                if detail_data and "data" in detail_data:
                    record = self._parse_domain_detail(domain_name, detail_data["data"])
                    if record:
                        all_records.append(record)
                        
            except Exception as e:
                self.logger.warning(f"Failed to fetch details for domain {domain_name}: {e}")
                continue
        
        return all_records
    
    def _parse_domain_detail(self, domain_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse domain detail response."""
        # Handle the nested structure
        career_info = data.get("careerDomainInfo", {})
        subcareers = data.get("subCareers", [])
        
        # Clean subcareers
        cleaned_subcareers = []
        for sub in subcareers:
            cleaned = {
                "id": str(sub.get("id", "")),
                "name": clean_text(sub.get("name", "")),
                "keywords": clean_text(sub.get("keywords", "")),
                "notes": clean_text(sub.get("notes", "")),
                "eligibility_status": str(sub.get("eligibility_status", "")),
                "entrance_exams": sub.get("entrance_exams", []),
                "colleges_india": sub.get("colleges_india", []),
                "colleges_abroad": sub.get("colleges_abroad", []),
                "career_paths": sub.get("career_paths", []),
                "pros_cons": sub.get("pros_cons", {}),
                "career_opportunities": sub.get("career_opportunities", []),
                "work_description": sub.get("work_description", []),
            }
            cleaned_subcareers.append(cleaned)
        
        record = {
            "subject_id": clean_text_safe(domain_name).lower().replace(" ", "_"),
            "subject_title": clean_text_safe(domain_name),
            "description": clean_text_safe(career_info.get("description", "")),
            "image": clean_text_safe(career_info.get("image", "")),
            "subcareers": cleaned_subcareers,
        }
        
        return record
    
    def transform_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw record to standardized schema."""
        # Ensure required fields are present as non-empty strings
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in raw_record or raw_record[field] is None:
                raw_record[field] = ""
        
        # Clean string fields
        for key, value in raw_record.items():
            if isinstance(value, str):
                # Required fields use safe variant (never None)
                if key in required_fields:
                    raw_record[key] = clean_text_safe(value)
                else:
                    raw_record[key] = clean_text_safe(value)
            elif isinstance(value, list):
                raw_record[key] = [v for v in value if v]  # Remove empty items
        
        raw_record["source"] = "mindler"
        
        return raw_record