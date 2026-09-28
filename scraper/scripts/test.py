#!/usr/bin/env python3
"""
Test Script for n8n + Python Integration Validation
====================================================
Creates a simple JSON output file to verify the n8n -> Python -> Local file workflow works.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(r"C:\n8n-project\scraper\output")
OUTPUT_FILE = OUTPUT_DIR / "test.json"


def main():
    print("=" * 50)
    print("TEST SCRIPT: n8n + Python Integration")
    print("=" * 50)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    
    # Create test data
    test_data = {
        "test_run": True,
        "timestamp": datetime.now().isoformat(),
        "message": "Hello from n8n + Python local automation!",
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "working_directory": str(Path.cwd()),
        },
        "pipeline": "test",
        "status": "success",
    }
    
    # Write to temporary file first (atomic write)
    temp_file = OUTPUT_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        
        # Atomic replace
        temp_file.replace(OUTPUT_FILE)
        
        print(f"SUCCESS: Test file created at {OUTPUT_FILE}")
        print(f"Content: {json.dumps(test_data, indent=2)}")
        
        # Verify
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            verify_data = json.load(f)
        
        if verify_data == test_data:
            print("VERIFICATION: File content matches!")
            return 0
        else:
            print("ERROR: File content mismatch!")
            return 1
            
    except Exception as e:
        print(f"ERROR: {e}")
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())