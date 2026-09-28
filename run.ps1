# Fintech project full-stack launcher
# Run this file from PowerShell inside the project directory:
#   .\run.ps1
$ErrorActionPreference = "Stop"

Write-Host "`n[1/4] Checking Python..." -ForegroundColor Cyan
python --version

Write-Host "[2/4] Creating/using Python virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "[3/4] Installing and building React frontend..." -ForegroundColor Cyan
Push-Location frontend
npm install
npm run build
Pop-Location

Write-Host "[4/4] Starting FastAPI + React on one server..." -ForegroundColor Cyan
Write-Host "Open: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Swagger: http://127.0.0.1:8000/docs" -ForegroundColor Green
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
