"""
Run Logging and Summary Utilities
==================================
Provides run summary generation, history tracking, and run logs management.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class StepResult:
    """Result of a single pipeline step."""
    name: str
    success: bool
    message: str
    duration_seconds: float
    records_processed: int = 0
    records_new: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    records_failed: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunSummary:
    """Complete summary of a pipeline run."""
    run_id: str
    site: str
    start_time: str
    end_time: str
    duration_seconds: float
    overall_success: bool
    steps: List[StepResult]
    total_records_processed: int = 0
    total_new: int = 0
    total_updated: int = 0
    total_unchanged: int = 0
    total_failed: int = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)


class RunLogger:
    """Manages run logs and summaries."""
    
    def __init__(self, run_logs_dir: Path):
        self.run_logs_dir = Path(run_logs_dir)
        self.run_logs_dir.mkdir(parents=True, exist_ok=True)
        self.current_run: Optional[RunSummary] = None
        self.current_step_start: Optional[datetime] = None
    
    def start_run(self, site: str, config_snapshot: Dict[str, Any] = None) -> str:
        """Start a new run and return run ID."""
        run_id = f"{site}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_run = RunSummary(
            run_id=run_id,
            site=site,
            start_time=datetime.now().isoformat(),
            end_time="",
            duration_seconds=0.0,
            overall_success=True,
            steps=[],
            config_snapshot=config_snapshot or {},
        )
        
        return run_id
    
    def start_step(self, step_name: str) -> None:
        """Mark the start of a step."""
        self.current_step_start = datetime.now()
    
    def end_step(
        self,
        step_name: str,
        success: bool,
        message: str,
        records_processed: int = 0,
        records_new: int = 0,
        records_updated: int = 0,
        records_unchanged: int = 0,
        records_failed: int = 0,
        error: str = None,
    ) -> StepResult:
        """Mark the end of a step and record results."""
        if not self.current_step_start:
            duration = 0.0
        else:
            duration = (datetime.now() - self.current_step_start).total_seconds()
        
        step_result = StepResult(
            name=step_name,
            success=success,
            message=message,
            duration_seconds=duration,
            records_processed=records_processed,
            records_new=records_new,
            records_updated=records_updated,
            records_unchanged=records_unchanged,
            records_failed=records_failed,
            error=error,
        )
        
        if self.current_run:
            self.current_run.steps.append(step_result)
            self.current_run.total_records_processed += records_processed
            self.current_run.total_new += records_new
            self.current_run.total_updated += records_updated
            self.current_run.total_unchanged += records_unchanged
            self.current_run.total_failed += records_failed
            
            if not success:
                self.current_run.overall_success = False
        
        self.current_step_start = None
        return step_result
    
    def finish_run(self, metadata: Dict[str, Any] = None) -> RunSummary:
        """Finish the current run and save summary."""
        if not self.current_run:
            raise RuntimeError("No active run")
        
        self.current_run.end_time = datetime.now().isoformat()
        start = datetime.fromisoformat(self.current_run.start_time)
        end = datetime.fromisoformat(self.current_run.end_time)
        self.current_run.duration_seconds = (end - start).total_seconds()
        
        if metadata:
            self.current_run.metadata.update(metadata)
        
        # Save run summary
        self._save_run_summary(self.current_run)
        
        # Save to history
        self._append_to_history(self.current_run)
        
        run_summary = self.current_run
        self.current_run = None
        
        return run_summary
    
    def _save_run_summary(self, run_summary: RunSummary) -> None:
        """Save individual run summary as JSON."""
        file_path = self.run_logs_dir / f"{run_summary.run_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(run_summary.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _append_to_history(self, run_summary: RunSummary) -> None:
        """Append run summary to history file."""
        history_file = self.run_logs_dir / "run_history.json"
        
        history = []
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, OSError):
                history = []
        
        history.append(run_summary.to_dict())
        
        # Keep last 100 runs
        if len(history) > 100:
            history = history[-100:]
        
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get run history."""
        history_file = self.run_logs_dir / "run_history.json"
        
        if not history_file.exists():
            return []
        
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            return history[-limit:]
        except (json.JSONDecodeError, OSError):
            return []
    
    def get_latest_run(self, site: str = None) -> Optional[Dict[str, Any]]:
        """Get the latest run, optionally filtered by site."""
        history = self.get_history(limit=100)
        
        if site:
            history = [h for h in history if h.get("site") == site]
        
        return history[-1] if history else None


def generate_human_readable_summary(run_summary: RunSummary) -> str:
    """Generate a human-readable text summary of a run."""
    lines = [
        "=" * 60,
        f"RUN SUMMARY: {run_summary.run_id}",
        "=" * 60,
        f"Site: {run_summary.site}",
        f"Start: {run_summary.start_time}",
        f"End: {run_summary.end_time}",
        f"Duration: {run_summary.duration_seconds:.1f}s",
        f"Overall: {'SUCCESS' if run_summary.overall_success else 'FAILED'}",
        "",
        "STEPS:",
        "-" * 60,
    ]
    
    for step in run_summary.steps:
        status = "OK" if step.success else "FAIL"
        lines.append(f"  [{status}] {step.name} ({step.duration_seconds:.1f}s)")
        lines.append(f"       {step.message}")
        if step.records_processed > 0:
            lines.append(f"       Records: {step.records_processed} total "
                        f"({step.records_new} new, {step.records_updated} updated, "
                        f"{step.records_unchanged} unchanged, {step.records_failed} failed)")
        if step.error:
            lines.append(f"       Error: {step.error}")
        lines.append("")
    
    lines.extend([
        "TOTALS:",
        "-" * 60,
        f"  Total Processed: {run_summary.total_records_processed}",
        f"  New: {run_summary.total_new}",
        f"  Updated: {run_summary.total_updated}",
        f"  Unchanged: {run_summary.total_unchanged}",
        f"  Failed: {run_summary.total_failed}",
        "=" * 60,
    ])
    
    return "\n".join(lines)


def load_run_summary(run_logs_dir: Path, run_id: str) -> Optional[RunSummary]:
    """Load a specific run summary from file."""
    file_path = Path(run_logs_dir) / f"{run_id}.json"
    
    if not file_path.exists():
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Convert back to RunSummary
        steps = [StepResult(**s) for s in data.get("steps", [])]
        data["steps"] = steps
        return RunSummary(**data)
    except Exception:
        return None