# n8n + Python Local Automation Workflow

## Overview
This project sets up **n8n running in Docker** on Windows to orchestrate **Python scrapers running natively on Windows**. The Python scripts execute in your local Python environment and save output files to your local Windows filesystem.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WINDOWS HOST                              │
│  ┌──────────────────┐    ┌──────────────────────────────────┐  │
│  │  trigger_server.py│◄───│  n8n (Docker)                    │  │
│  │  (Port 8765)      │    │  - Manual/Schedule Trigger       │  │
│  └────────┬──────────┘    │  - HTTP Request → trigger_server │  │
│           │               │  - Poll for completion           │  │
│           ▼               │  - Verify output files           │  │
│  ┌──────────────────┐    └──────────────────────────────────┘  │
│  │  Python Scripts  │                                         │
│  │  - run_pipeline.py                                    │  │
│  │  - Mindler/main.py                                    │  │
│  │  - Swayam/scraper.py                                  │  │
│  │  - Swayam/enrich.py                                   │  │
│  └────────┬──────────┘                                         │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │  Output Files    │                                           │
│  │  C:\n8n-project\scraper\output\                             │  │
│  │  - mindler_career_library.json                              │  │
│  │  - swayam_courses.json                                      │  │
│  │  - swayam_courses_enriched.json                             │  │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Windows 10/11**
2. **Docker Desktop** installed and running
3. **Python 3.9+** installed on Windows (not in Docker)
4. **Git** (optional, for cloning)

## Quick Start

### 1. Install Docker Desktop
```powershell
# Download from https://www.docker.com/products/docker-desktop/
# Or install via winget:
winget install Docker.DockerDesktop
```

### 2. Verify Python Environment
```powershell
python --version
# Should show Python 3.9+

# Verify your existing scraper environments work:
cd D:\Automation\Mindler
python main.py --help

cd D:\Automation\Swayam\Swayam-Web-Scraping
python scraper.py --help
```

### 3. Set Up Project Structure
```powershell
# The structure is already created at C:\n8n-project\
# Verify:
dir C:\n8n-project\
```

### 4. Install Python Dependencies (in your existing environments)
```powershell
# Mindler
cd D:\Automation\Mindler
pip install -r requirements.txt
playwright install chromium

# SWAYAM
cd D:\Automation\Swayam\Swayam-Web-Scraping
pip install -r requirements.txt
# For enrich.py:
pip install playwright
playwright install chromium
```

### 5. Start n8n (Docker)
```powershell
cd C:\n8n-project
docker compose up -d
```

Wait 10-15 seconds for n8n to start, then open: **http://localhost:5678**
- Username: `admin`
- Password: `changeme123` (change in docker-compose.yml)

### 6. Start Trigger Server (Windows Host)
Open a **new PowerShell window** (keep it running):
```powershell
cd C:\n8n-project\scraper
python trigger_server.py
```
You should see:
```
Starting n8n Trigger Server on http://0.0.0.0:8765
Project directory: C:\n8n-project\scraper
Pipeline script: run_pipeline.py
Python executable: python

Endpoints:
  GET  http://localhost:8765/health  - Health check
  POST http://localhost:8765/trigger - Trigger pipeline
       Body: {"script": "run_pipeline.py", "force": false}

From n8n (Docker) use: http://host.docker.internal:8765/trigger

Press Ctrl+C to stop
```

### 7. Import Workflow in n8n
1. Open n8n at http://localhost:5678
2. Go to **Workflows** → **Import**
3. Select `C:\n8n-project\n8n\workflow_test_integration.json`
4. Click **Save**

### 8. Run Test Workflow
1. Open the imported workflow "Test n8n + Python Integration"
2. Click **Execute Workflow** (or **Test Workflow**)
3. Watch the execution - it should show **SUCCESS** with test output

### 9. Verify Output File
```powershell
type C:\n8n-project\scraper\output\test.json
```
Should show JSON with `"test_run": true` and timestamp.

### 10. Run Full Pipeline
1. Import `C:\n8n-project\n8n\workflow_local_python_pipeline.json`
2. Execute workflow
3. Check output files:
```powershell
dir C:\n8n-project\scraper\output\
```

## Detailed Configuration

### Docker Compose (C:\n8n-project\docker-compose.yml)
```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n-automation
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=changeme123
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://localhost:5678/
      - GENERIC_TIMEZONE=Asia/Kolkata
      - TZ=Asia/Kolkata
    volumes:
      - n8n_data:/home/node/.n8n
      - ./scraper:/data/scraper
    restart: unless-stopped

volumes:
  n8n_data:
```

**Key Points:**
- `./scraper:/data/scraper` - Mounts Windows `C:\n8n-project\scraper` to `/data/scraper` in container
- n8n can READ/WRITE to `/data/scraper/output` via Function node (Node.js fs module)
- n8n CANNOT directly execute Windows `.bat`/`.ps1` files (runs in Linux container)

### Path Mapping

| Windows Path | Docker (n8n) Path | Purpose |
|--------------|-------------------|---------|
| `C:\n8n-project\scraper` | `/data/scraper` | Project root in container |
| `C:\n8n-project\scraper\output` | `/data/scraper/output` | Output files (read by n8n) |
| `C:\n8n-project\scraper\scripts` | `/data/scraper/scripts` | Test scripts |

### Trigger Server (trigger_server.py)
Runs on **Windows host** (not in Docker). Receives HTTP requests from n8n.

**Endpoints:**
- `GET /health` - Returns `{"status": "ok", "running": false}`
- `POST /trigger` - Triggers pipeline
  - Body: `{"script": "run_pipeline.py", "force": false}`

**From n8n (Docker):** Use `http://host.docker.internal:8765/trigger`

### Pipeline Scripts

#### run_pipeline.py (Main Pipeline)
Runs all scrapers sequentially:
1. **Mindler** - `D:\Automation\Mindler\main.py` → outputs to `output/mindler_career_library.json`
2. **SWAYAM Scraper** - `D:\Automation\Swayam\Swayam-Web-Scraping\scraper.py` → outputs to `output/swayam_courses.json`
3. **SWAYAM Enricher** - `D:\Automation\Swayam\Swayam-Web-Scraping\enrich.py` → outputs to `output/swayam_courses_enriched.json` (optional)

**Features:**
- Uses virtual environments if present (`.venv`)
- Copies output files to unified `C:\n8n-project\scraper\output\`
- Validates JSON output
- Writes `pipeline_summary.json` with execution results
- Proper error handling with continue-on-failure for optional steps

#### run_test_pipeline.py (Test Pipeline)
Runs only `scripts/test.py` to verify integration.

#### test.py (Test Script)
Creates `output/test.json` with simple test data.

### n8n Workflow Nodes

| Node | Type | Purpose |
|------|------|---------|
| Manual Trigger | `manualTrigger` | Start workflow manually |
| Check Trigger Server Health | `httpRequest` | Verify trigger_server.py is running |
| Trigger Python Pipeline | `httpRequest` | POST to `/trigger` to start pipeline |
| Wait | `wait` | Pause between polls |
| Poll Pipeline Completion | `httpRequest` | GET `/health` to check `running: false` |
| Verify Output Files | `function` | Node.js fs to check `/data/scraper/output/` |
| All Outputs Valid? | `if` | Branch on validation result |
| Workflow Success/Failure | `function` | Final status output |

## Scheduling & Automation

### Option 1: n8n Schedule Trigger
Replace **Manual Trigger** with **Schedule Trigger** node:
- Every day at 2 AM: `0 2 * * *`
- Every hour: `0 * * * *`
- Every Monday 9 AM: `0 9 * * 1`

### Option 2: Windows Task Scheduler
Trigger via PowerShell:
```powershell
# Save as trigger_pipeline.ps1
Invoke-RestMethod -Uri "http://localhost:8765/trigger" -Method POST -Body '{"script":"run_pipeline.py"}' -ContentType "application/json"
```
Create scheduled task running this script.

### Option 3: File Watcher (Code Changes)
Use a file watcher script that calls trigger_server.py when Python files change.

## Error Handling

### Pipeline Errors
- **Required step fails** → Pipeline stops, n8n marks workflow failed
- **Optional step fails** → Pipeline continues, warning logged
- **Timeout** → Step marked failed (5 min for Mindler, 10 min for SWAYAM, 30 min for Enricher)

### n8n Workflow Errors
- **Trigger server down** → "Server Unhealthy" error
- **Trigger fails** → "Trigger Failed" error
- **Pipeline times out** → Increase wait time or check trigger_server.py logs
- **Output validation fails** → Check file permissions, disk space

### Duplicate Prevention
- `trigger_server.py` has `MIN_INTERVAL_SECONDS = 5` between triggers
- `running` lock prevents concurrent executions
- Use `force: true` in trigger body to override

## Troubleshooting

### n8n Not Accessible
```powershell
# Check container status
docker compose ps

# Check logs
docker compose logs n8n

# Restart
docker compose restart n8n
```

### Trigger Server Not Responding
```powershell
# Check if running
netstat -an | findstr 8765

# Test manually
Invoke-RestMethod http://localhost:8765/health

# Check firewall (allow port 8765)
```

### "host.docker.internal" Not Resolving
- Docker Desktop → Settings → Resources → Network → "Enable host.docker.internal"
- Restart Docker Desktop
- Alternative: Use Windows host IP (run `ipconfig` to find)

### Python Scripts Fail
```powershell
# Test manually first
cd D:\Automation\Mindler
python main.py

cd D:\Automation\Swayam\Swayam-Web-Scraping
python scraper.py
```

### Output Files Not Appearing
```powershell
# Check trigger_server.py console for errors
# Check pipeline_summary.json
type C:\n8n-project\scraper\output\pipeline_summary.json

# Verify permissions
icacls C:\n8n-project\scraper\output
```

### Permission Issues (Windows)
```powershell
# Run PowerShell as Administrator
# Take ownership
takeown /f C:\n8n-project /r /d y
icacls C:\n8n-project /grant Everyone:F /t
```

## File Structure

```
C:\n8n-project\
├── docker-compose.yml
├── n8n\
│   ├── workflow_test_integration.json
│   └── workflow_local_python_pipeline.json
└── scraper\
    ├── run_pipeline.py          # Main pipeline orchestrator
    ├── run_test_pipeline.py     # Test pipeline
    ├── run_pipeline.bat         # Batch runner (alternative)
    ├── run_pipeline.ps1         # PowerShell runner (alternative)
    ├── trigger_server.py        # HTTP bridge (run on Windows host)
    ├── requirements.txt         # Combined requirements (optional)
    ├── scripts\
    │   └── test.py              # Test script
    └── output\
        ├── mindler_career_library.json
        ├── swayam_courses.json
        ├── swayam_courses_enriched.json
        ├── test.json
        └── pipeline_summary.json
```

## Maintenance

### Update n8n
```powershell
cd C:\n8n-project
docker compose pull
docker compose up -d
```

### Backup n8n Data
```powershell
# n8n data is in Docker volume 'n8n_data'
docker run --rm -v n8n-project_n8n_data:/data -v C:\backup:/backup alpine tar czf /backup/n8n_backup_$(date +%Y%m%d).tar.gz /data
```

### Update Python Dependencies
```powershell
# In each source directory
cd D:\Automation\Mindler
pip install -r requirements.txt --upgrade

cd D:\Automation\Swayam\Swayam-Web-Scraping
pip install -r requirements.txt --upgrade
```

## Security Notes

- Change default n8n password in `docker-compose.yml`
- Trigger server binds to `0.0.0.0:8765` - consider firewall rules
- For production, add authentication to trigger_server.py
- Keep Docker and Python updated

## Next Steps

1. ✅ Test workflow works
2. ✅ Full pipeline works
3. Add Schedule Trigger for daily runs
4. Add notifications (email, Slack, Teams) on success/failure
5. Add data validation/quality checks
6. Consider database storage instead of JSON files