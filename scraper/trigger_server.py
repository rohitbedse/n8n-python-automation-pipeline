"""
Local HTTP Trigger Server for n8n -> Python Execution Bridge
-------------------------------------------------------------
This runs on the Windows HOST (not in Docker) and receives HTTP requests
from n8n (running in Docker) to trigger Python script execution.

Run this on Windows host: python trigger_server.py

n8n (in Docker) calls: http://host.docker.internal:8765/trigger
"""
import json
import os
import subprocess
import sys
import threading
import time
import hmac
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

def get_project_root() -> Path:
    """Auto-detect project root from environment or file location."""
    env_root = os.getenv("SCRAPER_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    
    # Fallback: detect from this file's location
    current_dir = Path(__file__).resolve().parent.parent
    return current_dir

PROJECT_ROOT = get_project_root()
PROJECT_DIR = PROJECT_ROOT / "scraper"
PIPELINE_SCRIPT = "run_pipeline_new.py"
VENV_PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
HOST = "0.0.0.0"
PORT = 8765

# Authentication - simple API key (set via SCRAPER_TRIGGER_API_KEY env var)
TRIGGER_API_KEY = os.getenv("SCRAPER_TRIGGER_API_KEY", "").strip()

# Track running processes to prevent duplicates
running_lock = threading.Lock()
is_running = False
last_run_time = 0
MIN_INTERVAL_SECONDS = 5  # Prevent rapid duplicate triggers


def get_python_exe():
    """Get the appropriate Python executable."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return "python"


def run_pipeline(script_name=None):
    """Run the Python pipeline script and return (success, output, error)."""
    global is_running, last_run_time
    
    script = script_name or PIPELINE_SCRIPT
    script_path = PROJECT_DIR / script
    
    if not script_path.exists():
        return False, "", f"Script not found: {script_path}"
    
    python_exe = get_python_exe()
    
    # Set PYTHONPATH to project root so 'scraper' module can be imported
    project_root = PROJECT_DIR.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    
    try:
        # Run with timeout (5 minutes max)
        result = subprocess.run(
            [python_exe, str(script_path)],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        success = result.returncode == 0
        output = result.stdout
        error = result.stderr
        return success, output, error
    except subprocess.TimeoutExpired:
        return False, "", "Pipeline timed out after 5 minutes"
    except Exception as e:
        return False, "", str(e)


class TriggerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default log messages
        pass
    
    def _check_auth(self) -> bool:
        """Check API key authentication. Returns True if authenticated or no key configured."""
        if not TRIGGER_API_KEY:
            return True  # No auth required if not configured
        
        # Check X-API-Key header
        api_key = self.headers.get('X-API-Key', '').strip()
        if not api_key:
            return False
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(api_key, TRIGGER_API_KEY)
    
    def _send_auth_error(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": "Unauthorized",
            "message": "Invalid or missing API key. Provide X-API-Key header."
        }).encode())
    
    def do_GET(self):
        # Check authentication
        if not self._check_auth():
            self._send_auth_error()
            return
            
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "running": is_running}).encode())
            return
        
        if path == "/trigger":
            self.handle_trigger(parsed.query)
            return
        
        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        # Check authentication
        if not self._check_auth():
            self._send_auth_error()
            return
            
        parsed = urlparse(self.path)
        if parsed.path == "/trigger":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
            self.handle_trigger(body)
            return
        
        self.send_response(404)
        self.end_headers()
    
    def handle_trigger(self, query_or_body):
        global is_running, last_run_time
        
        # Parse parameters
        try:
            if query_or_body.startswith("{"):
                params = json.loads(query_or_body)
            else:
                params = parse_qs(query_or_body)
                params = {k: v[0] if v else "" for k, v in params.items()}
        except Exception:
            params = {}
        
        script_name = params.get("script", PIPELINE_SCRIPT)
        force = params.get("force", "false").lower() == "true"
        
        # Prevent duplicate runs (unless forced)
        current_time = time.time()
        with running_lock:
            if is_running and not force:
                self.send_json(409, {
                    "success": False,
                    "error": "Pipeline already running",
                    "running": True
                })
                return
            
            if not force and (current_time - last_run_time) < MIN_INTERVAL_SECONDS:
                self.send_json(429, {
                    "success": False,
                    "error": f"Too frequent triggers. Wait {MIN_INTERVAL_SECONDS}s between runs",
                    "running": False
                })
                return
            
            is_running = True
            last_run_time = current_time
        
        # Run pipeline in background thread
        def run_async():
            global is_running
            try:
                success, output, error = run_pipeline(script_name)
                
                # Log result
                status = "SUCCESS" if success else "FAILED"
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Pipeline {status}")
                if output:
                    print(f"  STDOUT: {output[:500]}")
                if error:
                    print(f"  STDERR: {error[:500]}")
            finally:
                with running_lock:
                    is_running = False
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        
        self.send_json(200, {
            "success": True,
            "message": "Pipeline triggered",
            "script": script_name,
            "running": True
        })
    
    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except ConnectionAbortedError:
            pass  # Client disconnected, ignore
        except BrokenPipeError:
            pass  # Client disconnected, ignore


def main():
    print(f"Starting n8n Trigger Server on http://{HOST}:{PORT}")
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Pipeline script: {PIPELINE_SCRIPT}")
    print(f"Python executable: {get_python_exe()}")
    print(f"\nEndpoints:")
    print(f"  GET  http://localhost:{PORT}/health  - Health check")
    print(f"  POST http://localhost:{PORT}/trigger - Trigger pipeline")
    print(f"       Body: {{\"script\": \"run_pipeline_new.py\", \"force\": false}}")
    print(f"\nFrom n8n (Docker) use: http://host.docker.internal:{PORT}/trigger")
    print("\nPress Ctrl+C to stop\n")
    
    server = HTTPServer((HOST, PORT), TriggerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()