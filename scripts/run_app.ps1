# Launch the Streamlit trip-planner UI.
# Usage (from repo root):  ./scripts/run_app.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-Not (Test-Path $python)) { $python = "python" }

& $python -m streamlit run (Join-Path $root "app\streamlit_app.py")
