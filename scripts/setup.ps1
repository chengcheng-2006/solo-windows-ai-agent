# Solo Setup — Prepare Python environment and check prerequisites

$ErrorActionPreference = 'Stop'
$script:SoloRoot = Split-Path -Parent $PSScriptRoot

Write-Host "===== Solo Setup =====" -ForegroundColor Cyan
Write-Host ""

# Run doctor first
$doctor = Join-Path $PSScriptRoot "doctor.ps1"
if (Test-Path $doctor) {
    & $doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Prerequisites check failed. Please fix the issues above." -ForegroundColor Red
        exit 1
    }
}

# Create Python virtual environment
$venvPath = Join-Path $script:SoloRoot ".venv"
if (!(Test-Path $venvPath)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "Failed to create venv" }
} else {
    Write-Host "Python virtual environment already exists" -ForegroundColor Green
}

# Activate venv
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
}

# Install requirements (minimal demo deps)
Write-Host "Installing requirements..." -ForegroundColor Yellow
$reqFile = Join-Path $script:SoloRoot "requirements-demo.txt"
if (Test-Path $reqFile) {
    pip install -r $reqFile 2>&1 | Out-Null
}

# Create .env from example if not exists
$envFile = Join-Path $script:SoloRoot ".env"
$envExample = Join-Path $script:SoloRoot ".env.example"
if (!(Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created .env from .env.example. Edit it to add your API keys." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== Setup complete =====" -ForegroundColor Cyan
Write-Host "Next: Review .env file, then run: .\scripts\start_demo.ps1"
exit 0
