"""
Test Pipeline for n8n Validation
=================================
Runs only the test script to verify n8n -> Python -> Local file workflow.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\n8n-project\scraper")
OUTPUT_DIR = PROJECT_ROOT / "output"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

TEST_STEPS = [
    {
        "name": "Test Script (n8n Integration Validation)",
        "script": "test.py",
        "source_dir": SCRIPTS_DIR,
        "output_file": OUTPUT_DIR / "test.json",
        "source_output": SCRIPTS_DIR / "test.json",  # test.py writes directly to output/
        "required": True,
        "timeout": 30,
    },
]


def log(level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def log_info(msg): log("INFO", msg)
def log_success(msg): log("SUCCESS", msg)
def log_warning(msg): log("WARN", msg)
def log_error(msg): log("ERROR", msg)


def get_python_exe(source_dir):
    venv_python = source_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return "python"


def run_step(step):
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
    
    if not source_dir.exists():
        msg = f"Source directory not found: {source_dir}"
        log_error(msg)
        return False, msg
    
    script_path = source_dir / script
    if not script_path.exists():
        msg = f"Script not found: {script_path}"
        log_error(msg)
        return False, msg
    
    python_exe = get_python_exe(source_dir)
    log_info(f"  Using Python: {python_exe}")
    
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
                for line in result.stdout.strip().split("\n"):
                    log_info(f"  {line}")
        else:
            msg = f"{name}: Failed with exit code {result.returncode}"
            log_error(msg)
            if result.stderr:
                log_error(f"  STDERR: {result.stderr}")
            return False, msg
        
    except subprocess.TimeoutExpired:
        msg = f"{name}: Timed out after {timeout}s"
        log_error(msg)
        return False, msg
    except Exception as e:
        msg = f"{name}: Exception: {e}"
        log_error(msg)
        return False, msg
    
    # Verify output (test.py writes directly to OUTPUT_DIR/test.json)
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            log_success(f"{name}: Output verified - {output_file}")
            log_info(f"  Content: {json.dumps(data, indent=2)[:200]}...")
            return True, "Completed"
        except Exception as e:
            log_error(f"{name}: Output verification failed: {e}")
            return False, f"Verification failed: {e}"
    else:
        log_error(f"{name}: Output file not found: {output_file}")
        return False, "Output file missing"


def main():
    parser = argparse.ArgumentParser(description="Test Pipeline for n8n Validation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run")
    args = parser.parse_args()
    
    log_info("=" * 60)
    log_info("TEST PIPELINE - n8n + Python Integration Validation")
    log_info("=" * 60)
    
    if args.dry_run:
        for step in TEST_STEPS:
            log_info(f"  Would run: {step['name']}")
        return 0
    
    overall_success = True
    for step in TEST_STEPS:
        success, message = run_step(step)
        if not success:
            overall_success = False
            break
    
    log_info("=" * 60)
    if overall_success:
        log_success("TEST PIPELINE PASSED - n8n + Python integration works!")
        return 0
    else:
        log_error("TEST PIPELINE FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())