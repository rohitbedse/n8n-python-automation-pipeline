<#
.SYNOPSIS
    Python Pipeline Runner for n8n (PowerShell)
.DESCRIPTION
    Runs the Python pipeline using the local Python environment.
    Called by n8n via HTTP trigger or Execute Command node.
.PARAMETER PipelineScript
    Name of the pipeline script to run (default: run_pipeline.py)
.PARAMETER ProjectDir
    Project directory (default: C:\n8n-project\scraper)
.PARAMETER UseVenv
    Whether to use virtual environment if available (default: $true)
#>

param(
    [string]$PipelineScript = "run_pipeline.py",
    [string]$ProjectDir = "C:\n8n-project\scraper",
    [bool]$UseVenv = $true
)

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "SUCCESS" { "Green" }
        default { "Cyan" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

Write-Log "Starting Python Pipeline Runner"
Write-Log "Project Directory: $ProjectDir"
Write-Log "Pipeline Script: $PipelineScript"

# Change to project directory
try {
    Set-Location -LiteralPath $ProjectDir -ErrorAction Stop
    Write-Log "Changed to directory: $(Get-Location)"
} catch {
    Write-Log "ERROR: Cannot change to project directory $ProjectDir" -Level "ERROR"
    Write-Log "ERROR: $($_.Exception.Message)" -Level "ERROR"
    exit 1
}

# Determine Python executable
$pythonExe = "python"
$venvPath = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if ($UseVenv -and (Test-Path -LiteralPath $venvPath)) {
    $pythonExe = $venvPath
    Write-Log "Using virtual environment: $venvPath"
} else {
    Write-Log "Using system Python: $pythonExe"
}

# Verify Python executable
try {
    $version = & $pythonExe --version 2>&1
    Write-Log "Python version: $version"
} catch {
    Write-Log "ERROR: Python not found at $pythonExe" -Level "ERROR"
    Write-Log "ERROR: $($_.Exception.Message)" -Level "ERROR"
    exit 1
}

# Check if pipeline script exists
$scriptPath = Join-Path $ProjectDir $PipelineScript
if (-not (Test-Path -LiteralPath $scriptPath)) {
    Write-Log "ERROR: Pipeline script not found: $scriptPath" -Level "ERROR"
    exit 1
}

# Run the pipeline
Write-Log "Executing: $pythonExe $PipelineScript"
try {
    $exitCode = 0
    & $pythonExe $scriptPath 2>&1 | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
} catch {
    Write-Log "ERROR: Exception during pipeline execution" -Level "ERROR"
    Write-Log "ERROR: $($_.Exception.Message)" -Level "ERROR"
    exit 1
}

if ($exitCode -eq 0) {
    Write-Log "SUCCESS: Pipeline completed successfully (exit code: $exitCode)" -Level "SUCCESS"
} else {
    Write-Log "FAILURE: Pipeline failed with exit code: $exitCode" -Level "ERROR"
}

exit $exitCode