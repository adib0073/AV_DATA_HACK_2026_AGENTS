# Run the DeepEval eval suite *inside* the api container, where the MCP/gateway
# URLs (flights:8001, obot:8080, ...) resolve. The agent + judge use the same
# OPENAI_API_KEY / CONFIDENT_API_KEY the container already has.
#
# Usage (from repo root):
#   ./scripts/run_evals.ps1 layer1                 # end-to-end golden eval
#   ./scripts/run_evals.ps1 layer1 --limit 5       # quick subset (Tokyo kept)
#   ./scripts/run_evals.ps1 layer1 --regression on # force the seeded bug
#   ./scripts/run_evals.ps1 layer2                 # component-level eval
#   ./scripts/run_evals.ps1 shadow                 # candidate-vs-baseline shadow
#   ./scripts/run_evals.ps1 all                    # layer2 + shadow + layer1

# NOTE: not "Stop" - DeepEval prints progress/results to stderr, and with Stop
# PowerShell would treat that as a terminating error mid-run.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $suite = if ($args.Count -ge 1) { $args[0] } else { "all" }
    $rest = if ($args.Count -ge 2) { $args[1..($args.Count - 1)] } else { @() }

    $map = @{
        "layer1" = "evals/layer1_e2e_eval.py"
        "layer2" = "evals/layer2_component_eval.py"
        "shadow" = "evals/shadow_eval.py"
    }

    function Run-Eval([string]$script, [string[]]$extra) {
        Write-Host ""
        & docker compose exec -T api python $script @extra
    }

    switch ($suite) {
        "all" {
            Run-Eval $map["layer2"] $rest
            Run-Eval $map["shadow"] $rest
            Run-Eval $map["layer1"] $rest
        }
        default {
            if (-not $map.ContainsKey($suite)) {
                Write-Error "Unknown suite '$suite'. Use: layer1 | layer2 | shadow | all"
                exit 1
            }
            Run-Eval $map[$suite] $rest
        }
    }
}
finally {
    Pop-Location
}
