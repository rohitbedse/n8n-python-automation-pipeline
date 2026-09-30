"""
Logging Utilities
=================
Provides structured logging setup and helper functions.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from ..config.settings import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT


def setup_logging(
    name: str = "scraper",
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    console: bool = True,
) -> logging.Logger:
    """
    Set up structured logging.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for file logging
        console: Whether to log to console
        
    Returns:
        Configured logger
    """
    if level is None:
        level = LOG_LEVEL
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def log_step(logger: logging.Logger, step_name: str, message: str = "", level: int = logging.INFO) -> None:
    """Log a pipeline step with consistent formatting."""
    prefix = f"[{step_name}]"
    if message:
        logger.log(level, f"{prefix} {message}")
    else:
        logger.log(level, prefix)


def log_summary(logger: logging.Logger, summary: dict) -> None:
    """Log a pipeline run summary."""
    logger.info("=" * 60)
    logger.info("PIPELINE RUN SUMMARY")
    logger.info("=" * 60)
    
    for key, value in summary.items():
        if isinstance(value, dict):
            logger.info(f"  {key}:")
            for k, v in value.items():
                logger.info(f"    {k}: {v}")
        elif isinstance(value, list):
            logger.info(f"  {key}: {len(value)} items")
        else:
            logger.info(f"  {key}: {value}")
    
    logger.info("=" * 60)


class PipelineLogger:
    """Context manager for pipeline run logging."""
    
    def __init__(self, site: str, run_logs_dir: Path):
        self.site = site
        self.run_logs_dir = Path(run_logs_dir)
        self.logger = None
        self.log_file = None
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.log_file = self.run_logs_dir / f"{self.site}_{timestamp}.log"
        
        self.logger = setup_logging(
            name=f"scraper.{self.site}",
            log_file=self.log_file,
            console=True,
        )
        
        self.logger.info(f"Starting {self.site} scraper run at {self.start_time.isoformat()}")
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(f"Scraper failed after {duration:.1f}s: {exc_val}", exc_info=True)
        else:
            self.logger.info(f"Scraper completed successfully in {duration:.1f}s")
        
        return False  # Don't suppress exceptions