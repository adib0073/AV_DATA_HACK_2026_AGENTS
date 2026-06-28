# Keeping Eyes on Your Agents — Trip Planner Demo

> Companion code for the session **"Keeping Eyes on Your Agents"** at
> **Analytics Vidhya Data Hack Summit 2026** — by **Aditya Bhattacharya**
> ([LinkedIn](https://www.linkedin.com/in/adi-phd/)).
>
> 📣 **Free to use (MIT).** If this helps you or you reuse it elsewhere, please
> credit **Aditya Bhattacharya** and link
> **https://www.linkedin.com/in/adi-phd/**. Questions? Reach out on LinkedIn.

A small-but-real **agentic travel planner** that you can *watch*. The app itself
is just the example; the point of the repo is to show a **multi-layered
evaluation + observability stack** wrapped around an agentic system:

| Layer | Question it answers | Tooling here |
|---|---|---|
| **1 — End-to-End Eval** | Did the agent succeed, efficiently? | DeepEval `TaskCompletionMetric`, `StepEfficiencyMetric` |
| **2 — Component Eval** | *Where* exactly did it fail? | DeepEval `PlanQuality`/`PlanAdherence`, `ToolCorrectness`/`ArgumentCorrectness` |
| **3 — Observability (in-code)** | Can I see what I *own*? | DeepEval `@observe` traces → Confident AI |
| **4 — Codeless Observability** | Can I see what I *don't own*? | **Obot** MCP gateway (+ AI gateway for token/cost) |

The agent is a **LangGraph multi-agent system** (planner → supervisor → flight /
hotel / itinerary / booking specialists) that calls **MCP servers** for its
tools.

---

## What the app does

Give it a destination, dates/duration, number of travelers, budget (total or
split across flights/hotels/transport/misc) and a travel type (explorer,
leisure, relaxing, adventure, business, family). The system:

1. **Planner** parses the request and produces an ordered plan.
2. **Supervisor** routes to specialist agents in turn.
3. **Flight / Hotel / Itinerary agents** call MCP tools to search options.
4. On confirmation, the **Booking agent** reserves the flight + hotel.

Every LLM call and tool call is traced; the whole thing can be scored against a
golden dataset.

---

## Architecture

```
                ┌──────────────────────────── Agent (you own) ───────────────────────────┐
   user ──▶ plan_trip  ──▶  planner ──▶ supervisor ──▶ ┌ flight_agent ┐                    │
   (@observe type=agent, trace root)                   │ hotel_agent  │ ── MCP tools ──┐    │
                                                       │ itinerary    │                │    │
                                                       └ booking_agent┘                │    │
                └────────────────────────────────────────────────────────────────────┼────┘
   Layers 1-3:  DeepEval @observe spans + metrics ─────────────────────────────────┐  │
                                                                                    ▼  ▼
                                            Confident AI (trace UI)        ┌──────────────────┐
                                                                           │   Obot Gateway   │  Layer 4
                                                                           │ (MCP + AI proxy) │  (codeless)
                                                                           └───┬───┬───┬───┬──┘
                                                                  flights  hotels  activities  booking
                                                                  :8001    :8002    :8003       :8004  (FastMCP)
```

See `docs/01_architecture.md` for the detailed version.

---

## What you need (API keys)

| Key | Required? | Why | Where to get it |
|---|---|---|---|
| `OPENAI_API_KEY` | **Yes** | the agents + the DeepEval judge call OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (a few dollars of credit is plenty for the demo) |
| `CONFIDENT_API_KEY` | Optional | streams traces to the Confident AI cloud UI (Layer 3). **Everything runs locally without it.** | [app.confident-ai.com](https://app.confident-ai.com) → create a **project**, copy the **Project API key** |

Put them in `.env` (copied from `.env.example`). **Never commit `.env`** — it is
already in `.gitignore`. The mock MCP servers and Obot need **no** keys of their own.

> Tip: use a *project-level* OpenAI key with access to `gpt-4o-mini` (the default
> agent **and** judge model — chosen to stay cheap and avoid Tier-1 rate limits).

---

## Quickstart (Docker — recommended)

The single best way to run everything. Brings up the whole stack with one command:
**4 mock MCP servers + agent API + Next.js UI + the Obot gateway**.

```bash
# 1. clone, then from the repo root:
cp .env.example .env            # (Windows PowerShell: copy .env.example .env)
# 2. open .env and paste your OPENAI_API_KEY  (CONFIDENT_API_KEY optional)
docker compose up --build
```

That's it. Open:

- **Web UI** → http://localhost:3000  (the chat planner)
- **Eval Studio** → http://localhost:3000/evals  (run evals + dashboards)
- **API** → http://localhost:8000  (MCP servers on 8001–8004)
- **Obot gateway (Layer 4)** → http://localhost:8080  (auth is off for the local demo)
- Stop with `docker compose down` (add `-v` to also wipe the saved eval history).

> The agent inside the `api` container reaches the MCP servers by their service
> names (`http://flights:8001/mcp`, …). The browser reaches the API at
> `http://localhost:8000` (baked in via `NEXT_PUBLIC_API_BASE` at build time).

**Layer 4 routing is opt-in.** By default (`USE_MCP_GATEWAY=false`) the agent calls
the MCP servers directly and Obot just runs alongside for you to explore. To route
every tool call *through* Obot (so the gateway audits them), register the four mock
servers in the Obot UI, set `USE_MCP_GATEWAY=true` and the `MCP_GATEWAY_*_URL`
values in `.env`, then `docker compose up -d api`. See
`docs/03_obot_gateway_guide.md`.

**Your eval history is saved.** Run history, uploaded goldens, and the MCP
tool-call tally persist in a Docker volume (`eval-data`), so they survive
`docker compose up`/restarts. Remove them with `docker compose down -v`.

Toggle the demo regression without rebuilding the app image:
```bash
# PowerShell:  $env:INJECT_REGRESSION="true"; docker compose up -d api
INJECT_REGRESSION=true docker compose up -d api    # re-create api with the seeded bug
```

---

## Quickstart (local, no Docker)

### 0. Prereqs
- Python 3.11+
- Node 18+ (for the web UI)
- An OpenAI API key
- (Optional, for Layer 4) Docker Desktop

### 1. Install

```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .          # optional: makes `import trip_planner` work everywhere
```

### 2. Configure

```powershell
copy .env.example .env
# edit .env and set OPENAI_API_KEY
```

### 3. Start the MCP servers (keep this running)

```powershell
python mcp_servers/run_all.py
# (or: .\scripts\run_mcp_servers.ps1  to get one window per server)
```

### 4. Run the web app (recommended)

A polished **Next.js** UI that streams each agent step live (SSE) with a token/
cost meter — backed by a small **FastAPI** server.

```powershell
# terminal 2 — backend API (:8000)
.\scripts\run_api.ps1
# or:  python -m uvicorn server.app:app --reload --port 8000

# terminal 3 — frontend (:3000)
cd web
npm install
npm run dev
```

Open http://localhost:3000. See `web/README.md` for details.

### Alternatives

```powershell
# one-shot CLI run
python scripts/run_agent.py "Plan a 5-day relaxing trip to Bali for 2 from Mumbai, budget $2500."

# lightweight Streamlit fallback UI
python -m streamlit run app/streamlit_app.py
```

### 5. (Optional) Stream traces to Confident AI

```powershell
deepeval login        # paste your Confident AI key
```

---

## Running the evaluations (the heart of the talk)

### From the UI — **Eval Studio** (http://localhost:3000/evals)
A dedicated page to run the whole suite and *see* it, without touching a terminal:

- **Run any suite** (Layer 1 / Layer 2 / Shadow), set a limit, toggle the seeded
  regression, and **Run** — the live console streams per-golden progress (with an
  ETA, since Layer 1 is LLM-judged) and the results render as structured tables.
- **Call flow & traces** — a **dynamic React-Flow diagram** of the real call path:
  `orchestrator → planner → supervisor → specialist agents → Obot gateway → MCP
  servers → tools`. Hit **Capture live trace** to run one trip and watch the nodes
  and edges that actually fired **light up** (Layer 3 spans + Layer 4 gateway in one
  view), with the per-tool call list and token/cost for that run.
- **Observability dashboard** — the headline numbers from Confident AI + Obot in
  one place: runs · LLM calls · **MCP calls** · tokens · est. cost · avg run time,
  a **Layer-1 pass-rate trend** (red = regression on, green = off), and an **MCP
  tool-call breakdown by server/tool** (the Obot/Layer-4 view). Deep links to
  Confident AI and Obot are one click away for the full waterfall / raw audit.
- **Upload your own golden dataset** (`.json` or `.csv`); it's used by every run
  until you reset to the built-in set.
- Everything here is **retained** across restarts (saved to the `eval-data` volume).

### From the CLI

The suite also runs **inside the `api` container** (so MCP/gateway URLs resolve and
the keys are present). One wrapper drives all of it:

```powershell
./scripts/run_evals.ps1 layer1                 # Layer 1 — end-to-end golden eval
./scripts/run_evals.ps1 layer1 --regression on # force the seeded bug
./scripts/run_evals.ps1 layer1 --limit 5       # quick subset (Tokyo always kept)
./scripts/run_evals.ps1 layer2                 # Layer 2 — component-level (deterministic)
./scripts/run_evals.ps1 shadow                 # shadow mode — candidate vs baseline
./scripts/run_evals.ps1 all                    # layer2 + shadow + layer1
```

- **Layer 1** scores each golden's full trace with `TaskCompletionMetric`
  (threshold 0.8) and prints a per-destination pass/fail table + a Confident AI
  link. With the regression on, **exactly Tokyo fails** ("no flights found").
- **Layer 2** runs the flight tool-decision both as a *dataset sweep* and as an
  *isolated healthy-vs-buggy contrast* — deterministic `ToolCorrectness`, no judge.
- **Shadow mode** replays the goldens through the buggy baseline and the fixed
  candidate, proving the fix repairs Tokyo and regresses nothing → *safe to ship*.

**Demo move:** `layer1 --regression on` → Tokyo fails. Drill into the trace
(Confident AI), confirm with `layer2`, shadow the fix with `shadow`, then
`layer1 --regression off` ("ship the fix") → all green.

> **Aggregated calls & a Langfuse-style trace timeline?** Yes — Confident AI's
> **Observatory** aggregates calls / tokens / USD / latency across *all* runs, and
> any trace opens as a **span waterfall** with per-span duration and cost. The
> in-app meter is the live *session* gauge; Confident AI is the system of record.
> See `docs/02_deepeval_guide.md` → "Observability".

Full beat-by-beat script: `docs/04_demo_runbook.md`.

---

## Layer 4 — Obot as MCP gateway *and* AI gateway

```powershell
docker compose -f config/obot/docker-compose.yml up -d
# open http://localhost:8080, grab the bootstrap token from `docker logs obot`
```

Register the four mock servers as **remote MCP servers** in Obot (using
`http://host.docker.internal:800X/mcp` URLs), copy the gateway connection URLs
back into `.env`, and set `USE_MCP_GATEWAY=true`. Now every tool call is
captured by the gateway — **no change to the agent code**.

**Can Obot / DeepEval be an AI gateway that shows token use + cost? → Yes.**
The short answer:

- **Obot** ships an **LLM proxy** that tracks realized **USD spend** per model /
  per user (input + output + cached + thinking tokens). Point the agent's
  `OPENAI_BASE_URL` at it → codeless token + cost tracking. This is a true
  network *gateway*.
- **DeepEval + Confident AI** track **token usage and cost per LLM span** and
  roll it up per trace — but via *in-code instrumentation* (`@observe`), not as a
  network proxy. It's an *eval/observability* layer, not a gateway.

Details, trade-offs, and the comparison table: `docs/03_obot_gateway_guide.md`.

---

## Repo layout

```
src/trip_planner/        the agent (LangGraph + MCP + DeepEval instrumentation)
  config.py              env-driven settings (model, pricing, gateway, regression)
  llm.py                 ChatOpenAI factory (gateway-aware base_url)
  observability.py       Layer 3 — @observe wrappers + usage recording
  metrics.py             DeepEval metric factories mapped to the 4 layers
  mcp_client.py          MultiServerMCPClient → scoped tools per agent
  state.py, prompts.py   typed graph state + system prompts
  agents/                base specialist runner + graph nodes
  graph.py               graph assembly + traced `plan_trip` entrypoint
mcp_servers/             4 mock FastMCP servers (flights/hotels/activities/booking)
server/app.py            FastAPI backend (SSE streaming of the agent run)
server/evals_api.py      Eval Studio API — run suites, goldens, observability, flow
server/flow.py           builds the call-flow graph (Layer 3 + Layer 4) for the UI
web/                     Next.js + Tailwind UI (chat planner + Eval Studio)
  components/EvalStudio.tsx   Eval Studio page (runs, dashboard, goldens)
  components/FlowDiagram.tsx  dynamic React-Flow call-flow diagram
app/streamlit_app.py     lightweight Streamlit fallback UI
evals/                   golden dataset + Layer 1 / Layer 2 / shadow eval scripts
config/obot/             standalone Obot gateway docker-compose (alt to the main one)
docker-compose.yml       full stack (MCP x4 + api + web + Obot gateway)
Dockerfile, web/Dockerfile   container images
docs/                    architecture, DeepEval guide, Obot guide, demo runbook
scripts/                 PowerShell + Python launchers
```

---

## Docs

- `docs/01_architecture.md` — how a request flows through the system
- `docs/02_deepeval_guide.md` — Layers 1–3 with DeepEval, step by step
- `docs/03_obot_gateway_guide.md` — Layer 4 + the AI-gateway / cost question
- `docs/04_demo_runbook.md` — the 10-minute live demo, beat by beat

## Author & citation

Created by **Aditya Bhattacharya** for the *"Keeping Eyes on Your Agents"* session
at the **Analytics Vidhya Data Hack Summit 2026**.

- LinkedIn: **https://www.linkedin.com/in/adi-phd/**

If you use, adapt, or build on this repo — in a talk, blog, course, or product —
please **credit Aditya Bhattacharya** and link the LinkedIn profile above. For
questions or collaboration, reach out on LinkedIn.

```
Aditya Bhattacharya, "Keeping Eyes on Your Agents — Trip Planner Demo",
Analytics Vidhya Data Hack Summit 2026. https://www.linkedin.com/in/adi-phd/
```

## License

MIT — free for personal and commercial use, see [`LICENSE`](LICENSE). The MIT
license requires retaining the copyright notice (Aditya Bhattacharya); attribution
as above is appreciated.
