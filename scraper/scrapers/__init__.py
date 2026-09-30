"""
Site-Specific Scraper Modules
=============================
Base classes and site-specific implementations for career data scraping.
"""

from .base import BaseScraper, ScraperConfig, create_scraper
from .mindler import MindlerScraper
from .swayam import SwayamScraper
from .careers360 import Careers360Scraper

__all__ = [
    "BaseScraper",
    "ScraperConfig",
    "create_scraper",
    "MindlerScraper",
    "SwayamScraper",
    "Careers360Scraper",
]