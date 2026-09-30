"""
Careers360 Scraper
==================
Scrapes career and education data from Careers360 website.

Careers360 serves college listing pages as server-rendered HTML.
We scrape each category page, paginate through results, and extract
college/institution cards with fields like name, URL, location,
rating, fees, and entrance exams.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .base import BaseScraper, ScraperConfig
from ..pipeline.clean import clean_text, clean_text_safe, normalize_url, normalize_date
from ..config.settings import SITES_CONFIG


class Careers360Scraper(BaseScraper):
    """Scraper for Careers360 website."""
    
    def __init__(self, config: ScraperConfig):
        super().__init__(config)
        self.base_url = config.base_url
        # Category URLs for college listings
        self.category_urls = {
            "engineering": "/university/engineering-colleges",
            "medical": "/university/medical-colleges",
            "management": "/university/management-colleges",
            "law": "/university/law-colleges",
            "design": "/university/design-colleges",
            "arts": "/university/arts-colleges",
            "science": "/university/science-colleges",
            "commerce": "/university/commerce-colleges",
            "hotel-management": "/university/hotel-management-colleges",
            "pharmacy": "/university/pharmacy-colleges",
            "architecture": "/university/architecture-colleges",
            "agriculture": "/university/agriculture-colleges",
        }
        # Max pages per category to avoid excessive crawling
        self.max_pages_per_category = config.extra_config.get("max_pages_per_category", 5)
        
    def scrape(self) -> List[Dict[str, Any]]:
        """Scrape college/course data from Careers360."""
        all_records = []
        
        for category, path in self.category_urls.items():
            url = urljoin(self.base_url, path)
            try:
                self.logger.info(f"Scraping category: {category}")
                records = self._scrape_category(category, url)
                all_records.extend(records)
                self.logger.info(f"Found {len(records)} records for {category}")
            except Exception as e:
                self.logger.error(f"Failed to scrape category {category}: {e}")
                # Continue with next category — don't crash the whole run
                continue
        
        return all_records
    
    def _scrape_category(self, category: str, url: str) -> List[Dict[str, Any]]:
        """Scrape a single category page with pagination."""
        records = []
        page = 1
        
        while page <= self.max_pages_per_category:
            page_url = f"{url}?page={page}" if page > 1 else url
            
            try:
                html = self._fetch_html(page_url)
                soup = BeautifulSoup(html, "html.parser")
                
                # Find college cards — try multiple selector strategies
                college_cards = self._find_college_cards(soup)
                
                if not college_cards:
                    self.logger.debug(f"No college cards found on page {page} for {category}")
                    break
                
                page_records = 0
                for card in college_cards:
                    try:
                        record = self._parse_college_card(card, category)
                        if record:
                            records.append(record)
                            page_records += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to parse college card: {e}")
                        continue
                
                self.logger.debug(f"Page {page}: found {page_records} records")
                
                # Check for next page — look for pagination link
                has_next = self._has_next_page(soup)
                if not has_next or page_records == 0:
                    break
                    
                page += 1
                
            except Exception as e:
                self.logger.error(f"Error scraping page {page} for {category}: {e}")
                break
        
        return records
    
    def _find_college_cards(self, soup: BeautifulSoup) -> list:
        """Find college card elements using multiple selector strategies."""
        # Try selectors from most specific to most general
        selectors = [
            "[data-college-id]",            # Data attribute
            ".college-card",                # Common class
            ".tupple",                      # Careers360-specific
            ".listing-card",                # Listing card
            "article.card",                 # Semantic article
            ".search-result .card",         # Search result cards
        ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                return cards
        
        # Fallback: look for any element with structured content
        cards = soup.select("article, .item")
        return cards if cards else []
    
    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there is a next page in pagination."""
        next_selectors = [
            "a.next",
            "a[rel='next']",
            ".pagination .next:not(.disabled)",
            ".pagination li:last-child a[href]",
        ]
        for selector in next_selectors:
            elem = soup.select_one(selector)
            if elem:
                return True
        return False
    
    def _parse_college_card(self, card: BeautifulSoup, category: str) -> Optional[Dict[str, Any]]:
        """Parse a college card element into a raw record."""
        # Extract name and link
        name_elem = (
            card.select_one("h3 a, h2 a, .college-name a, .name a, .title a, a[href*='/college/']") or
            card.select_one("h3, h2, .college-name, .name, .title")
        )
        
        if not name_elem:
            return None
            
        name = clean_text(name_elem.get_text())
        if not name:
            return None
            
        # Get URL
        link_elem = name_elem if name_elem.name == "a" else name_elem.select_one("a")
        url = ""
        if link_elem and link_elem.get("href"):
            url = normalize_url(link_elem["href"], self.base_url) or ""
        
        # Generate ID from URL or name
        record_id = ""
        if url:
            # Extract slug from URL path
            path_parts = url.rstrip("/").split("/")
            record_id = path_parts[-1].split("?")[0] if path_parts else ""
        if not record_id:
            record_id = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())[:80]
        
        # Extract location
        location_elem = card.select_one(
            ".location, .city, .address, [class*='location'], .college-location"
        )
        location = clean_text_safe(location_elem.get_text()) if location_elem else ""
        
        # Extract rating
        rating_elem = card.select_one(
            ".rating, .stars, [class*='rating'], .college-rating"
        )
        rating = clean_text_safe(rating_elem.get_text()) if rating_elem else ""
        
        # Extract fees
        fees_elem = card.select_one(
            ".fees, .fee, [class*='fee'], .college-fee"
        )
        fees = clean_text_safe(fees_elem.get_text()) if fees_elem else ""
        
        # Extract description/snippet
        desc_elem = card.select_one(
            ".description, .snippet, .summary, p"
        )
        description = clean_text_safe(desc_elem.get_text()) if desc_elem else ""
        
        # Extract exams/entrance info
        exam_elems = card.select(".exam, .entrance, [class*='exam']")
        exams = [clean_text(e.get_text()) for e in exam_elems if clean_text(e.get_text())]
        
        record = {
            "id": record_id,
            "title": name,
            "url": url,
            "category": category,
            "description": description,
            "location": location,
            "rating": rating,
            "fees": fees,
            "exams": exams,
            "source": "careers360",
        }
        
        return record
    
    def transform_record(self, raw_record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform raw record to standardized schema."""
        # Ensure all required fields are present as strings
        required_fields = self.get_required_fields()
        for field in required_fields:
            if field not in raw_record or raw_record[field] is None:
                raw_record[field] = ""
        
        # Clean all string fields
        for key, value in raw_record.items():
            if isinstance(value, str):
                raw_record[key] = clean_text_safe(value)
            elif isinstance(value, list):
                raw_record[key] = [
                    clean_text_safe(v) for v in value
                    if clean_text(v)  # filter out items that are empty after cleaning
                ]
        
        # Add scraping metadata
        raw_record["source"] = "careers360"
        raw_record["scraped_date"] = time.strftime("%Y-%m-%d")
        
        return raw_record