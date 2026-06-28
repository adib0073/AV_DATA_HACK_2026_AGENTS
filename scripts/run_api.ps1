# Launch the FastAPI backend (serves the Next.js UI via SSE).
# Usage (from repo root):  ./scripts/run_api.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-Not (Test-Path $python)) { $python = "python" }

& $python -m uvicorn server.app:app --reload --port 8000 --app-dir $root
