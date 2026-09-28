"""
Unified Pipeline Runner for n8n Automation
===========================================
Runs Mindler and SWAYAM scrapers sequentially with proper error handling.
Output files are saved to C:\n8n-project\scraper\output\
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================
PROJECT_ROOT = Path(r"C:\n8n-project\scraper")
OUTPUT_DIR = PROJECT_ROOT / "output"

# Source script locations (original locations)
MINDLER_DIR = Path(r"D:\Automation\Mindler")
SWAYAM_DIR = Path(r"D:\Automation\Swayam\Swayam-Web-Scraping")

# Output files (in our unified output directory)
OUTPUT_FILES = {
    "mindler": OUTPUT_DIR / "mindler_career_library.json",
    "swayam": OUTPUT_DIR / "swayam_courses.json",
    "swayam_enriched": OUTPUT_DIR / "swayam_courses_enriched.json",
}

# Pipeline steps configuration
PIPELINE_STEPS = [
    {
        "name": "Mindler Career Library Scraper",
        "script": "main.py",
        "source_dir": MINDLER_DIR,
        "output_file": OUTPUT_FILES["mindler"],
        "source_output": MINDLER_DIR / "mindler_career_library.json",
        "required": True,
        "timeout": 300,  # 5 minutes
    },
    {
        "name": "SWAYAM Course Scraper",
        "script": "scraper.py",
        "source_dir": SWAYAM_DIR,
        "output_file": OUTPUT_FILES["swayam"],
        "source_output": SWAYAM_DIR / "swayam_courses.json",
        "required": True,
        "timeout": 600,  # 10 minutes
    },
    {
        "name": "SWAYAM Course Enricher (Playwright)",
        "script": "enrich.py",
        "source_dir": SWAYAM_DIR,
        "output_file": OUTPUT_FILES["swayam_enriched"],
        "source_output": SWAYAM_DIR / "swayam_courses_enriched.json",
        "required": False,  # Optional - requires Playwright
        "timeout": 1800,  # 30 minutes
    },
]

# ============================================================
# UTILITIES
# ============================================================
def log(level, message):
    """Structured logging with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def log_info(msg): log("INFO", msg)
def log_success(msg): log("SUCCESS", msg)
def log_warning(msg): log("WARN", msg)
def log_error(msg): log("ERROR", msg)


def get_python_exe(source_dir):
    """Get Python executable, preferring virtual environment."""
    venv_python = source_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return "python"


def copy_output_file(source_output, target_output, step_name):
    """Copy output file from source location to unified output directory."""
    try:
        if source_output.exists():
            target_output.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(source_output, target_output)
            log_success(f"{step_name}: Copied output to {target_output}")
            return True
        else:
            log_warning(f"{step_name}: Source output not found at {source_output}")
            return False
    except Exception as e:
        log_error(f"{step_name}: Failed to copy output: {e}")
        return False


def verify_output_file(output_file, step_name):
    """Verify output file exists and is valid JSON."""
    try:
        if not output_file.exists():
            log_error(f"{step_name}: Output file missing: {output_file}")
            return False
        
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and "courses" in data:
            count = len(data["courses"])
        elif isinstance(data, dict) and "total_courses" in data:
            count = data["total_courses"]
        else:
            count = "unknown"
        
        log_success(f"{step_name}: Output verified - {count} items in {output_file}")
        return True
    except json.JSONDecodeError as e:
        log_error(f"{step_name}: Invalid JSON in output: {e}")
        return False
    except Exception as e:
        log_error(f"{step_name}: Verification failed: {e}")
        return False


def run_step(step):
    """Run a single pipeline step."""
    name = step["name"]
    script = step["script"]
    source_dir = step["source_dir"]
    output_file = step["output_file"]
    source_output = step["source_output"]
    required = step["required"]
    timeout = step["timeout"]
    
    log_info(f"=== Starting: {name} ===")
    log_info(f"  Script: {script}")
    log_info(f"  Working dir: {source_dir}")
    log_info(f"  Expected output: {source_output}")
    
    # Verify source directory exists
    if not source_dir.exists():
        msg = f"Source directory not found: {source_dir}"
        log_error(msg)
        if required:
            return False, msg
        log_warning(f"Skipping optional step: {name}")
        return True, "Skipped (source not found)"
    
    # Verify script exists
    script_path = source_dir / script
    if not script_path.exists():
        msg = f"Script not found: {script_path}"
        log_error(msg)
        if required:
            return False, msg
        log_warning(f"Skipping optional step: {name}")
        return True, "Skipped (script not found)"
    
    # Get Python executable
    python_exe = get_python_exe(source_dir)
    log_info(f"  Using Python: {python_exe}")
    
    # Run the script
    try:
        start_time = time.time()
        result = subprocess.run(
            [python_exe, script],
            cwd=str(source_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            log_success(f"{name}: Completed in {elapsed:.1f}s")
            if result.stdout:
                # Log last few lines of stdout
                lines = result.stdout.strip().split("\n")
                for line in lines[-5:]:
                    log_info(f"  {line}")
        else:
            msg = f"{name}: Failed with exit code {result.returncode}"
            log_error(msg)
            if result.stderr:
                log_error(f"  STDERR: {result.stderr[-1000:]}")
            if result.stdout:
                log_info(f"  STDOUT: {result.stdout[-1000:]}")
            if required:
                return False, msg
            log_warning(f"Optional step failed, continuing: {name}")
            return True, "Optional step failed"
        
    except subprocess.TimeoutExpired:
        msg = f"{name}: Timed out after {timeout}s"
        log_error(msg)
        if required:
            return False, msg
        log_warning(f"Optional step timed out, continuing: {name}")
        return True, "Optional step timed out"
    except Exception as e:
        msg = f"{name}: Exception: {e}"
        log_error(msg)
        if required:
            return False, msg
        log_warning(f"Optional step exception, continuing: {name}")
        return True, "Optional step exception"
    
    # Copy output to unified directory
    copy_output_file(source_output, output_file, name)
    
    # Verify output
    if output_file.exists():
        verify_output_file(output_file, name)
    else:
        log_warning(f"{name}: No output file generated at {output_file}")
    
    return True, "Completed"


def write_summary(results):
    """Write pipeline execution summary."""
    summary = {
        "timestamp": datetime.now().isoformat(),
        "steps": results,
        "overall_success": all(r["success"] for r in results if r.get("required", True)),
    }
    
    summary_file = OUTPUT_DIR / "pipeline_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    log_info(f"Pipeline summary written to: {summary_file}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Unified Pipeline Runner for n8n")
    parser.add_argument("--steps", nargs="+", help="Specific steps to run (by name)")
    parser.add_argument("--skip", nargs="+", help="Steps to skip (by name)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    args = parser.parse_args()
    
    log_info("=" * 60)
    log_info("UNIFIED PIPELINE RUNNER")
    log_info("=" * 60)
    log_info(f"Project root: {PROJECT_ROOT}")
    log_info(f"Output directory: {OUTPUT_DIR}")
    
    # Filter steps
    steps_to_run = []
    for step in PIPELINE_STEPS:
        name = step["name"]
        if args.steps and name not in args.steps:
            continue
        if args.skip and name in args.skip:
            log_info(f"Skipping: {name}")
            continue
        steps_to_run.append(step)
    
    if args.dry_run:
        log_info("DRY RUN - Steps that would be executed:")
        for step in steps_to_run:
            req = "REQUIRED" if step["required"] else "OPTIONAL"
            log_info(f"  - {step['name']} [{req}]")
        return 0
    
    # Run steps
    results = []
    overall_success = True
    
    for step in steps_to_run:
        success, message = run_step(step)
        results.append({
            "name": step["name"],
            "success": success,
            "message": message,
            "required": step["required"],
            "output_file": str(step["output_file"]),
        })
        
        if not success and step["required"]:
            overall_success = False
            log_error(f"Required step failed: {step['name']}. Stopping pipeline.")
            break
        
        # Small delay between steps
        time.sleep(1)
    
    # Write summary
    summary = write_summary(results)
    
    log_info("=" * 60)
    log_info("PIPELINE SUMMARY")
    log_info("=" * 60)
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        req = "" if r["required"] else " (optional)"
        log_info(f"  [{status}] {r['name']}{req}: {r['message']}")
    
    if overall_success:
        log_success("PIPELINE COMPLETED SUCCESSFULLY")
        return 0
    else:
        log_error("PIPELINE FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())