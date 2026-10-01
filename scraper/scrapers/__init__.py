"""
Site-Specific Scraper Modules
=============================
Base classes and site-specific implementations for career data scraping.
"""

from .base import BaseScraper, ScraperConfig, create_scraper
from .mindler_api import MindlerAPIScraper
from .swayam_graphql import SwayamGraphQLScraper

__all__ = [
    "BaseScraper",
    "ScraperConfig",
    "create_scraper",
    "MindlerAPIScraper",
    "SwayamGraphQLScraper",
]