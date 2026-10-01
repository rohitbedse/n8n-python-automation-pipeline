# 🎓 Career Data Aggregation Pipeline

A modular, fault-tolerant Python pipeline that scrapes **2,000+ career and education records** from two Indian education platforms — **SWAYAM** and **Mindler** — with automated scheduling via **n8n** running in Docker.

Built for reliability: every run validates data against schemas, deduplicates records, classifies changes as NEW / UPDATED / UNCHANGED, and saves failed records separately with the reason for failure — so bad data never silently enters the main output.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            WINDOWS HOST                                  │
│                                                                          │
│  ┌───────────────┐         ┌──────────────────────────────────────────┐  │
│  │  n8n (Docker)  │──HTTP──▶│  trigger_server.py (Port 8765)          │  │
│  │  Schedule /    │         │  - Receives triggers from n8n           │  │
│  │  Manual Trigger│         │  - Prevents duplicate/concurrent runs   │  │
│  └───────────────┘         └──────────────┬───────────────────────────┘  │
│                                           │                              │
│                                           ▼                              │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    run_pipeline_new.py                              │  │
│  │  Orchestrates all scrapers sequentially with run logging           │  │
│  └───────┬────────────────────┬────────────────────┬──────────────────┘  │
│          │                    │                    │                      │
│          ▼                    ▼                    │                      │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐           │
│  │   Mindler     │   │   SWAYAM     │   │   (Future)        │           │
│  │   REST API    │   │   GraphQL    │   │   Careers360      │           │
│  │   44 records  │   │   2,226 recs │   │   HTML Scraping   │           │
│  └──────┬───────┘   └──────┬───────┘   └────────┬──────────┘           │
│         │                  │                     │                       │
│         └──────────────────┴─────────────────────┘                       │
│                            │                                             │
│              ┌─────────────▼──────────────┐                             │
│              │   Shared Pipeline Engine    │                             │
│              │  ┌──────┐ ┌──────────────┐ │                             │
│              │  │Fetch │ │  Validate    │ │                             │
│              │  │+Retry│ │  vs Schema   │ │                             │
│              │  └──────┘ └──────────────┘ │                             │
│              │  ┌──────┐ ┌──────────────┐ │                             │
│              │  │Clean │ │  Deduplicate │ │                             │
│              │  │+HTML │ │  +Classify   │ │                             │
│              │  └──────┘ └──────────────┘ │                             │
│              │  ┌──────────────────────┐  │                             │
│              │  │  Atomic Write + Log  │  │                             │
│              │  └──────────────────────┘  │                             │
│              └─────────────┬──────────────┘                             │
│                            │                                             │
│                            ▼                                             │
│              ┌─────────────────────────────┐                            │
│              │         output/              │                            │
│              │  mindler_career_library.json  │                            │
│              │  swayam_courses.json          │                            │
│              │  *_failed_records.json        │                            │
│              └─────────────────────────────┘                            │
│              ┌─────────────────────────────┐                            │
│              │        run_logs/             │                            │
│              │  <run_id>.json (per run)     │                            │
│              │  run_history.json (all runs) │                            │
│              └─────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Data Collection
| Source | Method | Records | Data |
|--------|--------|---------|------|
| **Mindler** | REST API | 44 career domains | Career paths, entrance exams, colleges, eligibility, pros/cons |
| **SWAYAM** | GraphQL API | 2,226 courses | Course details, instructors, syllabi, enrollment info, ratings |

> **Note**: Careers360 scraper is planned but not yet implemented. Current production scrapers: Mindler (REST API) and SWAYAM (GraphQL API).

### Reliability & Error Handling
- **Retry with exponential backoff** — configurable base/max delay with jitter to avoid thundering herd
- **HTTP error handling** — 429 (rate limit), 500/502/503/504 (server errors) trigger retries; 404, 403 fail fast without crashing the run
- **Rate limiting** — token-bucket rate limiter per scraper; configurable delay between requests (0.3s–1.0s)
- **Atomic writes** — output files are written to a temp file first, then atomically renamed, preventing data corruption on crash

### Data Quality
- **HTML tag removal** — strips `<b>`, `<p>`, etc. from scraped text
- **Escape character normalization** — `\n`, `\r`, `\t` collapsed to spaces
- **Schema validation** — every record validated against a `FieldSchema` definition (type checks, required fields, URL format, date format)
- **Failed records isolation** — records that fail validation are saved to `*_failed_records.json` with the specific reason (e.g., `"Missing required fields: course_url: Required field is missing or empty"`)
- **Deduplication** — configurable key fields per site; duplicates removed before writing

### Idempotent Pipeline
Running the pipeline again does **not** create duplicates. Each run:
1. Loads the existing output file
2. Compares every scraped record against existing records
3. Classifies each as **NEW**, **UPDATED**, or **UNCHANGED**
4. For **UPDATED** records, identifies which specific fields changed
5. Merges the result — only changed data is updated

### Observability
- **Structured logging** — timestamped, leveled log output (`INFO`, `WARNING`, `ERROR`)
- **Run summaries** — each run produces a JSON summary with record counts, duration, step-by-step results
- **Run history** — all summaries appended to `run_logs/run_history.json` (last 100 runs)
- **Human-readable reports** — text-formatted run summaries printed to console

---

## Project Structure

```
n8n-project/
├── docker-compose.yml              # n8n container config
├── Dockerfile
├── README.md
├── .env.example                    # Environment variable template
├── n8n/                            # n8n workflow definitions
│   ├── workflow_test_integration.json
│   └── workflow_local_python_pipeline.json
│
└── scraper/                        # Python scraping pipeline
    ├── __init__.py
    ├── config/
    │   ├── __init__.py
    │   └── settings.py             # All configurable values (URLs, delays, schemas)
    │
    ├── pipeline/                   # Shared utilities (site-agnostic)
    │   ├── __init__.py
    │   ├── http.py                 # Fetch with retry + exponential backoff
    │   ├── clean.py                # Strip HTML, normalize text, dates, URLs
    │   ├── validate.py             # Schema definitions + validation engine
    │   ├── dedup.py                # Deduplication + NEW/UPDATED/UNCHANGED classification
    │   ├── write.py                # Atomic JSON writes, failed records, backups
    │   ├── rate_limit.py           # Token-bucket rate limiter
    │   ├── logging_utils.py        # Structured logging setup
    │   └── run_logging.py          # Run summaries + history tracking
    │
    ├── scrapers/                   # Site-specific modules
    │   ├── __init__.py
    │   ├── base.py                 # Abstract base class + factory
    │   ├── mindler_api.py          # Mindler Career Library (REST API)
    │   ├── swayam_graphql.py       # SWAYAM Courses (GraphQL)
    │
    ├── run_pipeline_new.py         # Main pipeline runner (modular)
    ├── run_pipeline.py             # Legacy runner (subprocess-based)
    ├── trigger_server.py           # HTTP bridge for n8n → Python
    ├── requirements.txt
    │
    ├── output/                     # Scraped data (JSON)
    │   ├── mindler_career_library.json
    │   ├── swayam_courses.json
    │   └── *_failed_records.json
    │
    └── run_logs/                   # Timestamped run summaries
        ├── <run_id>.json
        └── run_history.json
```

---

## Design Decisions

### Why a base class pattern instead of plain functions?
Each scraper needs the same pipeline flow (scrape → transform → validate → dedup → classify → write) but different data extraction logic. The `BaseScraper` abstract class implements the 9-step pipeline once, while subclasses only implement `scrape()` and `transform_record()`. Adding a new site means writing ~100 lines, not ~350.

### Why atomic writes?
The pipeline runs unattended on a schedule. If it crashes mid-write (power failure, disk full, OOM), a half-written JSON file would corrupt the output. Writing to a temp file first and then using `Path.replace()` (an OS-level atomic rename) guarantees the output file is always valid.

### Why classify records instead of just overwriting?
Overwriting loses history. By comparing against the previous output, we can:
- Track what's new each run (useful for downstream notifications)
- See which fields changed on existing records
- Avoid pointlessly re-writing unchanged data
- Make the run summary meaningful ("12 new, 3 updated, 1943 unchanged" vs "1958 written")

### Why separate failed_records.json?
Bad data should never silently enter the main output, but it also shouldn't disappear. Saving failed records with their failure reason enables:
- Debugging scraper issues without re-running
- Tracking data quality trends across runs
- Fixing transform/validation bugs without losing the raw data

### Why token-bucket rate limiting instead of simple `time.sleep()`?
`time.sleep()` between requests is rigid — it doesn't allow legitimate bursts (e.g., fetching a domain list of 5 items quickly) while still maintaining a polite average rate. The token-bucket allows short bursts up to `burst_limit` while enforcing `requests_per_second` over time.

---

## Quick Start

### Prerequisites
- **Windows 10/11**
- **Python 3.9+**
- **Docker Desktop** (for n8n orchestration — optional for standalone use)

### 1. Install Dependencies

```powershell
cd C:\n8n-project\scraper
pip install -r requirements.txt
```

### 2. Run the Pipeline (Standalone)

```powershell
# Set Python path
$env:PYTHONPATH = "C:\n8n-project"

# Dry run — see what would execute
python run_pipeline_new.py --dry-run

# Run all scrapers
python run_pipeline_new.py

# Run specific sites only
python run_pipeline_new.py --sites mindler swayam

# With debug logging
python run_pipeline_new.py --log-level DEBUG
```

### 3. Run with n8n (Docker Orchestration)

```powershell
# Start n8n
cd C:\n8n-project
docker compose up -d

# Start the trigger server (keep running)
cd C:\n8n-project\scraper
python trigger_server.py
```

Then open **http://localhost:5678**, import a workflow, and trigger it. n8n calls `http://host.docker.internal:8765/trigger` which runs the Python pipeline on the Windows host.

### 4. Check Results

```powershell
# View output files
dir C:\n8n-project\scraper\output\

# View run logs
dir C:\n8n-project\scraper\run_logs\

# Check pipeline summary
type C:\n8n-project\scraper\output\pipeline_summary.json
```

---

## Configuration

All configuration lives in [`scraper/config/settings.py`](scraper/config/settings.py). Nothing is hardcoded in scraper modules.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_PROJECT_ROOT` | `C:\n8n-project\scraper` | Base path for all output/logs |
| `SCRAPER_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Per-Site Configuration

Each site has its own config block with:

```python
"mindler": {
    "base_url": "https://careerlibrary.mindler.com",
    "delay_between_requests": 0.3,   # seconds between requests
    "timeout": 15,                    # HTTP timeout
    "max_retries": 3,                 # retry attempts per request
}
```

### Schema & Validation

Required fields and deduplication keys are configured per site:

```python
"required_fields": {
    "mindler": ["subject_id", "subject_title"],
    "swayam":  ["course_id", "course_name", "course_url"],
},
"duplicate_check_fields": {
    "mindler": ["subject_id"],
    "swayam":  ["course_id", "course_url"],
}
```

---

## Pipeline Flow

Each scraper runs through this 9-step pipeline (implemented once in `BaseScraper.run()`):

```
Step 1  SCRAPE          Call site-specific scrape() method
           │
Step 2  TRANSFORM       Normalize each record via transform_record()
           │            ──▶ failures saved with reason
Step 3  VALIDATE        Check required fields + schema types
           │            ──▶ failures saved with reason
Step 4  DEDUPLICATE     Remove duplicates by key fields
           │
Step 5  CLASSIFY        Compare with existing output file
           │            ──▶ NEW / UPDATED / UNCHANGED
Step 6  MERGE           Combine unchanged + new + updated
           │
Step 7  STRIP META      Remove internal tracking fields
           │
Step 8  WRITE OUTPUT    Atomic write to output JSON
           │
Step 9  WRITE FAILED    Save failed records to separate file
```

---

## Sample Output

### Successful Record (SWAYAM)
```json
{
  "course_id": "Q291cnNlTGlzdDovbmQyX2FpYzIwX3NwNTM=",
  "course_name": "C/C++ - Bengali",
  "course_url": "https://onlinecourses.swayam2.ac.in/aic20_sp53/preview",
  "institute": "Indian Institute of Technology Bombay",
  "provider": "Indian Institute of Technology Bombay (AICTE)",
  "duration": "12 weeks",
  "mode": "Online",
  "status": "Upcoming",
  "instructors": ["Prof Kannan Moudgalya"],
  "source": "SWAYAM",
  "last_verified_date": "2026-09-28"
}
```

### Failed Record (with reason)
```json
{
  "timestamp": "2026-09-29T16:00:00",
  "total_failed": 1,
  "failed_records": [
    {
      "record": {"course_id": "", "course_name": "Test"},
      "reason": "Missing required fields: course_id: Required field is missing or empty",
      "stage": "validation"
    }
  ]
}
```

### Run Summary
```
============================================================
RUN SUMMARY: pipeline_20260929_160000
============================================================
Site: pipeline
Duration: 45.2s
Overall: SUCCESS

STEPS:
------------------------------------------------------------
  [OK] scrape_mindler (12.3s)
       44 new, 0 updated, 0 unchanged, 0 failed
  [OK] scrape_swayam (30.1s)
       12 new, 3 updated, 1943 unchanged, 0 failed

TOTALS:
------------------------------------------------------------
  Total Processed: 2002
  New: 56
  Updated: 3
  Unchanged: 1943
  Failed: 0
============================================================
```

---

## Adding a New Scraper

1. Add site config to `config/settings.py`
2. Add schema to `pipeline/validate.py`
3. Create `scrapers/your_site.py`:

```python
class YourSiteScraper(BaseScraper):
    def scrape(self) -> List[Dict[str, Any]]:
        # Fetch data from API/HTML
        return raw_records

    def transform_record(self, raw_record):
        # Normalize to your schema
        return transformed_record
```

4. Register in `scrapers/base.py` → `create_scraper()` factory
5. Run: `python run_pipeline_new.py --sites your_site`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.9+ |
| HTTP | `requests` with custom retry adapter |
| HTML Parsing | `BeautifulSoup4` |
| Browser Automation | `Playwright` (optional, for enrichment) |
| Orchestration | n8n (Docker) |
| Data Format | JSON (atomic writes) |
| Scheduling | n8n Schedule Trigger / Windows Task Scheduler |

---

## License

This project is for educational and personal use.