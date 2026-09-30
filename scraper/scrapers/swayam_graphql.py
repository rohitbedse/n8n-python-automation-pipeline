"""
SWAYAM Courses Scraper (GraphQL based)

Talks to the real endpoint the explorer page (course-explorer.html) uses:
GET /modules/gql/query with a raw GraphQL string in `q` and a JSON-encoded
filter/pagination object in `esq`. Responses are prefixed with ")]}'"
(stripped by pipeline.http.fetch_json_with_retry). The site only exposes
two status buckets ("Upcoming" and "Ongoing"), so both are queried and
merged to approximate "all courses".
"""

import json
import time
from typing import Any, Dict, List, Optional

from .base import BaseScraper, ScraperConfig
from ..pipeline.clean import clean_text, clean_text_safe, normalize_url, normalize_date

STATUSES = ["Upcoming", "Ongoing"]
PAGE_SIZE = 100


class SwayamGraphQLScraper(BaseScraper):
    """Scraper for SWAYAM courses using the real /modules/gql/query endpoint."""

    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.api_url = config.extra_config.get("api_url")
        self.explorer_url = config.extra_config.get("explorer_url")

    @staticmethod
    def _build_request(status: str, after_cursor: Optional[str], offset: int) -> Dict[str, Any]:
        after_clause = f', after:"{after_cursor}"' if after_cursor else ""
        query = (
            '{courseList(args: {includeClosed: false, filterText: "", category: "", '
            f'status: "{status}", tags: "", duration: "", examDate: "", credits: "", '
            'ncCode: "", courseType: "", courseLanguage: "", ncrfLevel: "all", '
            'programAlignedTo: "all", industryOrSector: "all", domain: "all",   }, '
            f'first:{PAGE_SIZE}{after_clause}) {{edges {{node {{'
            "  id, title, url, explorerSummary,"
            "  explorerInstructorName, enrollment {enrolled}, "
            "  openForRegistration, showInExplorer,"
            "  startDate, endDate, examDate, enrollmentEndDate, estimatedWorkload, category {name, category, parentId},"
            "  tags {name}, featured, coursePictureUrl, credits, weeks, nodeCode, instructorInstitute, ncCode, "
            "semester, examRegistrationEndDate, ncrfLevel, programAlignedTo, industryOrSector, departments}}, "
            "pageInfo {endCursor, hasNextPage}}, "
            "  courseLanguages{courseLanguage},"
            "  examDates{date}}"
        )
        esq = {
            "includeClosed": False, "filterText": "", "category": "", "status": status,
            "tags": "", "duration": "", "examDate": "", "credits": "", "ncCode": "",
            "courseType": "", "courseLanguage": "", "ncrfLevel": "all",
            "programAlignedTo": "all", "industryOrSector": "all", "domain": "all",
            "first": PAGE_SIZE, "from": offset,
        }
        return {"q": query, "expanded_gcb_tags": "gcb-markdown", "esq": json.dumps(esq)}

    def scrape(self) -> List[Dict[str, Any]]:
        self.logger.info("Fetching courses from SWAYAM API...")
        all_courses = []
        seen_ids = set()

        for status in STATUSES:
            self.logger.info(f"Fetching status={status}...")
            after_cursor = None
            offset = 0
            has_next = True

            while has_next:
                self.logger.info(f"  Fetching {status} offset {offset}...")
                params = self._build_request(status, after_cursor, offset)
                try:
                    result = self._fetch_json(self.api_url, method="GET", params=params)
                except RuntimeError as e:
                    self.logger.error(f"Error fetching {status} offset {offset}: {e}")
                    break

                if not result or "data" not in result or not result["data"]:
                    self.logger.error(f"Invalid response from SWAYAM API: {result.get('errors') if result else result}")
                    break

                course_list = result["data"].get("courseList") or {}
                edges = course_list.get("edges", [])
                page_info = course_list.get("pageInfo", {})

                if not edges:
                    self.logger.info(f"No more courses found for status={status}")
                    break

                for edge in edges:
                    node = edge.get("node", {})
                    if node and node.get("id") not in seen_ids:
                        record = self._parse_course(node)
                        if record:
                            all_courses.append(record)
                            seen_ids.add(node.get("id"))

                has_next = page_info.get("hasNextPage", False)
                after_cursor = page_info.get("endCursor")
                offset += PAGE_SIZE

                if has_next:
                    time.sleep(self.config.delay_between_requests)

        self.logger.info(f"Total courses scraped: {len(all_courses)}")
        return all_courses

    def _parse_course(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        course_id = node.get("id", "")
        if not course_id:
            return None
        course_name = clean_text_safe(node.get("title", ""))
        if not course_name:
            return None
        course_url = normalize_url(node.get("url", "")) or ""
        categories = node.get("category") or []
        category_names = [c.get("name") for c in categories if isinstance(c, dict) and c.get("name")]
        tags = node.get("tags") or []
        tag_names = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
        enrollment = node.get("enrollment") or {}

        record = {
            "course_id": str(course_id),
            "course_name": course_name,
            "course_url": course_url,
            "national_coordinator": clean_text_safe(node.get("ncCode", "")),
            "institute": clean_text_safe(node.get("instructorInstitute", "")),
            "provider": clean_text_safe(node.get("instructorInstitute", "")),
            "description": clean_text_safe(node.get("explorerSummary", "")),
            "course_type": clean_text_safe(node.get("nodeCode", "")),
            "category": clean_text_safe(", ".join(category_names)),
            "education_level": clean_text_safe(node.get("ncrfLevel", "")),
            "mode": "Online",
            "duration": f"{node.get('weeks')} weeks" if node.get("weeks") else "",
            "start_date": normalize_date(node.get("startDate")),
            "end_date": normalize_date(node.get("endDate")),
            "status": "Open" if node.get("openForRegistration") else "Closed",
            "skills": tag_names,
            "prerequisites": "",
            "eligibility": "",
            "instructors": [clean_text_safe(node.get("explorerInstructorName", ""))] if node.get("explorerInstructorName") else [],
            "certificate": bool(node.get("credits")),
            "certification_type": "",
            "learning_outcomes": [],
            "syllabus": [],
            "assessment": "",
            "language": "",
            "fees": "",
            "free_or_paid": "",
            "enrollment_information": "",
            "rating": None,
            "enrollment_count": enrollment.get("enrolled") if isinstance(enrollment, dict) else None,
            "career_relevance": clean_text_safe(node.get("industryOrSector", "")),
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
                raw_record[key] = [clean_text_safe(v) for v in value if clean_text(v)]
            elif key in ("rating", "enrollment_count") and value is not None:
                try:
                    raw_record[key] = float(value) if key == "rating" else int(value)
                except (ValueError, TypeError):
                    raw_record[key] = None
        if raw_record.get("course_url") is None:
            raw_record["course_url"] = ""
        raw_record["source"] = "SWAYAM"
        raw_record["last_verified_date"] = time.strftime("%Y-%m-%d")
        return raw_record
