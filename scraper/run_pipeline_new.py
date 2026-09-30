"""
Unified Pipeline Runner
=======================
Runs all site scrapers using the shared pipeline utilities.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from scraper.scrapers import create_scraper
from scraper.config.settings import SITES_CONFIG, PIPELINE_CONFIG
from scraper.pipeline.run_logging import RunLogger, generate_human_readable_summary
from scraper.pipeline.logging_utils import setup_logging


class PipelineRunner:
    """Runs the unified scraping pipeline for all configured sites."""
    
    def __init__(self, sites: List[str] = None, run_logs_dir: Path = None):
        self.sites = sites or list(SITES_CONFIG.keys())
        self.run_logs_dir = run_logs_dir or Path(SITES_CONFIG["mindler"]["output_file"]).parent.parent / "run_logs"
        self.logger = setup_logging("pipeline.runner")
        self.run_logger = RunLogger(self.run_logs_dir)
        
    def run_site(self, site: str) -> Dict[str, Any]:
        """Run scraper for a single site."""
        self.logger.info(f"{'='*60}")
        self.logger.info(f"STARTING SCRAPER: {site.upper()}")
        self.logger.info(f"{'='*60}")
        
        try:
            scraper = create_scraper(site)
            result = scraper.run()
            
            # Convert to dict for serialization
            result_dict = {
                "site": result.site,
                "run_id": result.run_id,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "duration_seconds": result.duration_seconds,
                "success": result.success,
                "records_scraped": result.records_scraped,
                "records_new": result.records_new,
                "records_updated": result.records_updated,
                "records_unchanged": result.records_unchanged,
                "records_failed": result.records_failed,
                "error": result.error,
                "details": result.details,
            }
            
            if result.success:
                self.logger.info(f"SUCCESS: {site} - {result.records_new} new, {result.records_updated} updated, {result.records_unchanged} unchanged, {result.records_failed} failed")
            else:
                self.logger.error(f"FAILED: {site} - {result.error}")
            
            return result_dict
            
        except Exception as e:
            self.logger.error(f"Exception running scraper for {site}: {e}", exc_info=True)
            return {
                "site": site,
                "success": False,
                "error": str(e),
            }
    
    def run_all(self) -> Dict[str, Any]:
        """Run scrapers for all configured sites."""
        pipeline_start = datetime.now()
        run_id = f"pipeline_{pipeline_start.strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(f"{'='*60}")
        self.logger.info(f"UNIFIED PIPELINE RUNNER - {run_id}")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Sites to scrape: {', '.join(self.sites)}")
        self.logger.info(f"Run logs directory: {self.run_logs_dir}")
        
        # Start run logging
        config_snapshot = {
            "sites": self.sites,
            "pipeline_config": PIPELINE_CONFIG,
            "sites_config": {k: {kk: vv for kk, vv in v.items() if kk not in ["output_file", "failed_file"]} for k, v in SITES_CONFIG.items()},
        }
        self.run_logger.start_run("pipeline", config_snapshot)
        
        results = []
        overall_success = True
        
        for site in self.sites:
            self.run_logger.start_step(f"scrape_{site}")
            
            result = self.run_site(site)
            results.append(result)
            
            if not result.get("success", False):
                overall_success = False
            
            self.run_logger.end_step(
                f"scrape_{site}",
                success=result.get("success", False),
                message=f"{result.get('records_new', 0)} new, {result.get('records_updated', 0)} updated, {result.get('records_unchanged', 0)} unchanged, {result.get('records_failed', 0)} failed",
                records_processed=result.get("records_scraped", 0),
                records_new=result.get("records_new", 0),
                records_updated=result.get("records_updated", 0),
                records_unchanged=result.get("records_unchanged", 0),
                records_failed=result.get("records_failed", 0),
                error=result.get("error"),
            )
            
            # Small delay between sites
            if site != self.sites[-1]:
                time.sleep(2)
        
        # Finish run logging
        pipeline_end = datetime.now()
        pipeline_duration = (pipeline_end - pipeline_start).total_seconds()
        
        run_summary = self.run_logger.finish_run({
            "pipeline_duration_seconds": pipeline_duration,
            "sites_run": self.sites,
            "overall_success": overall_success,
        })
        
        # Print human-readable summary
        print(generate_human_readable_summary(run_summary))
        
        # Also print individual site results
        self.logger.info(f"{'='*60}")
        self.logger.info("PIPELINE SUMMARY")
        self.logger.info(f"{'='*60}")
        for result in results:
            status = "OK" if result.get("success") else "FAIL"
            self.logger.info(f"  [{status}] {result['site'].upper()}: "
                           f"{result.get('records_new', 0)} new, "
                           f"{result.get('records_updated', 0)} updated, "
                           f"{result.get('records_unchanged', 0)} unchanged, "
                           f"{result.get('records_failed', 0)} failed")
            if result.get("error"):
                self.logger.info(f"       Error: {result['error']}")
        
        overall_status = "SUCCESS" if overall_success else "FAILED"
        self.logger.info(f"{'='*60}")
        self.logger.info(f"PIPELINE {overall_status} (Duration: {pipeline_duration:.1f}s)")
        self.logger.info(f"{'='*60}")
        
        return {
            "run_id": run_id,
            "overall_success": overall_success,
            "duration_seconds": pipeline_duration,
            "site_results": results,
        }


def main():
    parser = argparse.ArgumentParser(description="Unified Career Data Scraping Pipeline")
    parser.add_argument(
        "--sites",
        nargs="+",
        choices=list(SITES_CONFIG.keys()),
        default=list(SITES_CONFIG.keys()),
        help="Sites to scrape (default: all)",
    )
    parser.add_argument(
        "--run-logs-dir",
        type=Path,
        help="Directory for run logs (default: scraper/run_logs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level",
    )
    args = parser.parse_args()
    
    # Setup logging
    setup_logging("pipeline", level=args.log_level)
    
    if args.dry_run:
        print("DRY RUN - Sites that would be scraped:")
        for site in args.sites:
            config = SITES_CONFIG[site]
            print(f"  - {site}: {config['name']} ({config['base_url']})")
        return 0
    
    # Run pipeline
    runner = PipelineRunner(sites=args.sites, run_logs_dir=args.run_logs_dir)
    result = runner.run_all()
    
    return 0 if result["overall_success"] else 1


if __name__ == "__main__":
    sys.exit(main())