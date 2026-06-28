# 04 · Demo runbook (≈10 minutes)

Pre-built scenes you *narrate and trigger* — no live coding. Mirrors the
"Demo flow — beat by beat" table in the session plan.

## Pre-stage (before you walk on)

- [ ] `docker compose up -d` — all services healthy (`docker compose ps`).
- [ ] `.env` has `OPENAI_API_KEY` + `CONFIDENT_API_KEY`; `DEEPEVAL_JUDGE_MODEL=gpt-4o-mini`.
- [ ] Confident AI open in a browser tab (Observatory + Test Runs).
- [ ] Web UI open: http://localhost:3000  ·  Obot open: http://localhost:8080.
- [ ] Terminals zoomed, dark theme, high contrast.
- [ ] Fallback screencast ready (alt-tab).

Two ways to drive the suite — use whichever reads better on stage:

- **Eval Studio UI** — http://localhost:3000/evals — pick a suite, toggle the
  regression, **Run**; results + live console + observability render in-page, with
  Confident AI deep-links. You can also **upload a custom golden dataset** here.
- **CLI** (inside the `api` container, no venv/MCP babysitting):
```powershell
./scripts/run_evals.ps1 layer1 --regression on   # Layer 1 end-to-end
./scripts/run_evals.ps1 layer2                    # Layer 2 component
./scripts/run_evals.ps1 shadow                    # shadow mode
```

> **Opener/closer:** the **web UI** (http://localhost:3000) is the most
> compelling way to show the agent — each agent lights up live and the token/
> cost meter ticks up as it runs.

---

## Beat 1 (0:00–1:30) — Run the golden eval · **Layer 1**
```powershell
./scripts/run_evals.ps1 layer1 --regression on
```
Narrate: goldens, the agent runs end-to-end on each, scored by
`TaskCompletion` (threshold 0.8). The table prints per-destination pass/fail +
a Confident AI link. **One case fails — Tokyo (~0.70): "no flights found".**

## Beat 2 (1:30–3:00) — Drill into the failure · **Layers 2 + 3**
Open the failing trace in Confident AI. Walk the **timeline/waterfall**:
`trip_planner → planner → supervisor → flight_agent → llm`. Point at the
**`ToolCorrectnessMetric`** on the flight LLM span: it called `get_flight_details`
instead of `search_flights` (**score 0.0**). `PlanAdherence` on the root is low
too. The trace tells the story end-to-end — *with span durations and token cost*.

## Beat 3 (3:00–4:30) — Confirm in isolation · **Layer 2 (Action)**
```powershell
./scripts/run_evals.ps1 layer2 --regression on
```
The **sweep** scores the flight decision per destination — every city is 1.0
except **Tokyo (0.0)**. The **isolated contrast** shows healthy `search_flights`
(1.0) vs buggy `get_flight_details` (0.0). Deterministic, no judge.
"Layer 1 said *that* it failed; Layer 2 says *why*."

## Beat 4 (4:30–6:00) — Shadow the fix before shipping · **Shadow mode**
```powershell
./scripts/run_evals.ps1 shadow
```
Run the candidate (bug fixed) against the live baseline on the same traffic —
output never served. `baseline 6/7 → candidate 7/7`, **Tokyo FIXED, 0 regressed
→ safe to promote.**

## Beat 5 (6:00–7:00) — Re-run + recovery · **Layer 1**
```powershell
./scripts/run_evals.ps1 layer1 --regression off
```
All green — Tokyo now ~0.95. "Ship the fix, watch the board recover."

## Beat 6 (7:00–8:30) — Eyes on *everything* · **Observability**
In Confident AI:
- **Observatory / Monitoring** — *aggregated* calls, tokens, **USD cost**, and
  latency across **all** runs (not just this session) — answers "track all the
  calls".
- **Trace timeline** — the Langfuse-style span waterfall on any trace.
- **Test Runs** — compare regression-on vs regression-off side by side.

The web UI's live meter is the *session* gauge; Confident AI is the *system of
record*.

## Beat 7 (8:30–9:30) — MCP gateway magic moment · **Layer 4**
With `USE_MCP_GATEWAY=true` (already on), run one trip from the web UI, then show
the **Obot** audit/usage view (http://localhost:8080): tool calls appear with
args, latency, and token **USD cost** — for servers you never instrumented, with
**zero agent code change**.

## Beat 8 (9:30–10:00) — Land the message
> "DeepEval covered the half I own. The gateway covered the half I don't.
> *That* is what 'eyes on your agents' looks like."

---

## Safety nets
- If Confident AI is flaky, the local console eval **tables** still show pass/fail.
- Layer 2 + shadow are **deterministic** (no judge) — they always reproduce, even
  offline-ish. Lead with them if the network is shaky.
- If a judge call rate-limits, re-run `layer1 --limit 5` (smaller, Tokyo kept).
- If Obot misbehaves, set `USE_MCP_GATEWAY=false` and narrate Layer 4 from slides.
- The web UI is a friendly opener/closer. (`app/streamlit_app.py` is a no-Node
  fallback if needed.)
