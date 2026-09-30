"""
SWAYAM Courses Scraper
======================
Scrapes course data from SWAYAM GraphQL API.
"""

import json
import time
from typing import Any, Dict, List, Optional

from .base import BaseScraper, ScraperConfig
from ..pipeline.clean import clean_text, clean_text_safe, normalize_url, normalize_date
from ..config.settings import SITES_CONFIG


class SwayamScraper(BaseScraper):
    """Scraper for SWAYAM courses."""
    
    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.api_url = config.extra_config.get("api_url")
        self.explorer_url = config.extra_config.get("explorer_url")
        
        # GraphQL query for course list
        self.course_list_query = """
        query getCourses($filters: CourseFiltersInput, $pagination: PaginationInput) {
            courses(filters: $filters, pagination: $pagination) {
                totalCount
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        name
                        courseUrl
                        nationalCoordinator
                        institute
                        provider
                        description
                        courseType
                        category
                        educationLevel
                        mode
                        duration
                        startDate
                        endDate
                        status
                        skills
                        prerequisites
                        eligibility
                        instructors
                        certificate
                        certificationType
                        learningOutcomes
                        syllabus
                        assessment
                        language
                        fees
                        freeOrPaid
                        enrollmentInformation
                        rating
                        enrollmentCount
                        careerRelevance
                    }
                }
            }
        }
        """
    
    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape courses from SWAYAM GraphQL API."""
        self.logger.info("Fetching courses from SWAYAM API...")
        
        all_courses = []
        page = 1
        page_size = 100
        has_next = True
        
        while has_next:
            self.logger.info(f"Fetching page {page}...")
            
            variables = {
                "filters": {},
                "pagination": {
                    "page": page,
                    "limit": page_size,
                }
            }
            
            try:
                payload = {
                    "query": self.course_list_query,
                    "variables": variables,
                }
                
                result = self._fetch_json(self.api_url, method="POST", json=payload)
                
                if not result or "data" not in result:
                    self.logger.error("Invalid response from SWAYAM API")
                    break
                
                courses_data = result["data"].get("courses", {})
                edges = courses_data.get("edges", [])
                page_info = courses_data.get("pageInfo", {})
                
                if not edges:
                    self.logger.info("No more courses found")
                    break
                
                for edge in edges:
                    node = edge.get("node", {})
                    if node:
                        record = self._parse_course(node)
                        if record:
                            all_courses.append(record)
                
                has_next = page_info.get("hasNextPage", False)
                page += 1
                
                # Respect rate limiting
                if has_next:
                    time.sleep(self.config.delay_between_requests)
                    
            except Exception as e:
                self.logger.error(f"Error fetching page {page}: {e}")
                break
        
        self.logger.info(f"Total courses scraped: {len(all_courses)}")
        return all_courses
    
    def _parse_course(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a course node from GraphQL response."""
        course_id = node.get("id", "")
        if not course_id:
            return None
            
        course_name = clean_text_safe(node.get("name", ""))
        if not course_name:
            return None
            
        course_url = normalize_url(node.get("courseUrl", "")) or ""
        
        record = {
            "course_id": str(course_id),
            "course_name": course_name,
            "course_url": course_url,
            "national_coordinator": clean_text_safe(node.get("nationalCoordinator", "")),
            "institute": clean_text_safe(node.get("institute", "")),
            "provider": clean_text_safe(node.get("provider", "")),
            "description": clean_text_safe(node.get("description", "")),
            "course_type": clean_text_safe(node.get("courseType", "")),
            "category": clean_text_safe(node.get("category", "")),
            "education_level": clean_text_safe(node.get("educationLevel", "")),
            "mode": clean_text_safe(node.get("mode", "")),
            "duration": clean_text_safe(node.get("duration", "")),
            "start_date": normalize_date(node.get("startDate")),
            "end_date": normalize_date(node.get("endDate")),
            "status": clean_text_safe(node.get("status", "")),
            "skills": node.get("skills", []) if node.get("skills") else [],
            "prerequisites": clean_text_safe(node.get("prerequisites", "")),
            "eligibility": clean_text_safe(node.get("eligibility", "")),
            "instructors": node.get("instructors", []) if node.get("instructors") else [],
            "certificate": node.get("certificate"),
            "certification_type": clean_text_safe(node.get("certificationType", "")),
            "learning_outcomes": node.get("learningOutcomes", []) if node.get("learningOutcomes") else [],
            "syllabus": node.get("syllabus", []) if node.get("syllabus") else [],
            "assessment": clean_text_safe(node.get("assessment", "")),
            "language": clean_text_safe(node.get("language", "")),
            "fees": clean_text_safe(node.get("fees", "")),
            "free_or_paid": clean_text_safe(node.get("freeOrPaid", "")),
            "enrollment_information": clean_text_safe(node.get("enrollmentInformation", "")),
            "rating": node.get("rating"),
            "enrollment_count": node.get("enrollmentCount"),
            "career_relevance": clean_text_safe(node.get("careerRelevance", "")),
        }
        
        return record
    
    def transform_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw record to standardized schema."""
        # Ensure required fields are present
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in raw_record or raw_record[field] is None:
                raw_record[field] = ""
        
        # Clean and normalize
        for key, value in raw_record.items():
            if isinstance(value, str):
                raw_record[key] = clean_text_safe(value)
            elif isinstance(value, list):
                raw_record[key] = [clean_text_safe(v) for v in value if clean_text(v)]
            elif key in ("rating", "enrollment_count") and value is not None:
                try:
                    raw_record[key] = float(value) if key == "rating" else int(value)
                except (ValueError, TypeError):
                    raw_record[key] = None
        
        # Ensure course_url is a string (normalize_url can return None)
        if raw_record.get("course_url") is None:
            raw_record["course_url"] = ""
        
        # Add source and verification date
        raw_record["source"] = "SWAYAM"
        raw_record["last_verified_date"] = time.strftime("%Y-%m-%d")
        
        return raw_record