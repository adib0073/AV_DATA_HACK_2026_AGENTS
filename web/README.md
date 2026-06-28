# Wander — Next.js trip-planner UI

A polished web frontend for the agentic trip planner. It streams the agent run
over **Server-Sent Events** so you can *watch each agent light up* as it works,
with a live token/cost meter — on-theme for "Keeping Eyes on Your Agents".

- **Next.js 14** (App Router) · **React 18** · **TypeScript** · **Tailwind CSS**
- Talks to the FastAPI backend at `server/app.py`

## Prerequisites

1. Backend running (from the repo root):
   ```powershell
   python mcp_servers/run_all.py          # terminal 1 — MCP tools
   .\scripts\run_api.ps1                   # terminal 2 — FastAPI (:8000)
   ```
2. Node 18+ / npm.

## Run

```bash
cd web
npm install
cp .env.local.example .env.local    # optional; defaults to http://localhost:8000
npm run dev                          # http://localhost:3000
```

## Build

```bash
npm run build && npm run start
```

## How it works

- `lib/api.ts` POSTs to `/api/plan/stream` and parses the SSE stream by hand
  (EventSource only supports GET).
- `components/Chat.tsx` orchestrates chat state, the live **Agent Activity**
  panel, and the **Tokens & cost** meter.
- Backend events: `pipeline` (stage labels) → many `node` events (one per graph
  node, with a running usage snapshot) → one `final` event (response + trip
  state) — or an `error` event.
