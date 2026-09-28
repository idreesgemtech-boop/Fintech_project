# FinTech MVP — Full Stack

This package combines the existing FastAPI backend and React frontend into one project.

## Project structure

- `app/` — FastAPI backend, database, ledger, trading and provider services
- `frontend/` — React/Vite customer interface
- `run.ps1` — Windows one-command setup/build/run script
- `run.bat` — Windows double-click launcher

## Quick test on Windows

Prerequisites:
- Python 3.11+ recommended
- Node.js 18+ / npm

From this folder:

```powershell
.\run.ps1
```

Then open:

- http://127.0.0.1:8000 — customer frontend
- http://127.0.0.1:8000/docs — FastAPI Swagger API

The React frontend is built into `frontend/dist`, and FastAPI serves it from the same server. This means you can test the MVP as a single application.

## Alternative manual run

Terminal 1:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm install
npm run build
```

Refresh `http://127.0.0.1:8000`.

## Important

This is an assessment/demo MVP, not production financial infrastructure. Authentication, real KYC, custody, provider integrations, robust reconciliation, production-grade ledger controls, and regulatory compliance still need to be implemented before real financial use.
