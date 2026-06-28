# Launch the four mock MCP servers, each in its own PowerShell window.
# Usage (from repo root):  ./scripts/run_mcp_servers.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$servers = @(
    @{ name = "flights";    file = "flights_server.py";    port = 8001 },
    @{ name = "hotels";     file = "hotels_server.py";     port = 8002 },
    @{ name = "activities"; file = "activities_server.py"; port = 8003 },
    @{ name = "booking";    file = "booking_server.py";    port = 8004 }
)

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-Not (Test-Path $python)) { $python = "python" }

foreach ($s in $servers) {
    $script = Join-Path $root "mcp_servers\$($s.file)"
    Write-Host "Starting $($s.name) on :$($s.port)"
    Start-Process -FilePath $python -ArgumentList $script -WorkingDirectory (Join-Path $root "mcp_servers")
}

Write-Host ""
Write-Host "All MCP servers launched (flights 8001, hotels 8002, activities 8003, booking 8004)."
Write-Host "Close the spawned windows to stop them."
