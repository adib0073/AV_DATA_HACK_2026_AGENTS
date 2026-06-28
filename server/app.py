"""FastAPI backend for the Next.js trip-planner UI.

Exposes the agent over HTTP + Server-Sent Events so the frontend can show each
agent "lighting up" as it works, with a live token/cost meter.

Run:  python -m uvicorn server.app:app --reload --port 8000
(or:  .\scripts\run_api.ps1)
"""

from __future__ import annotations

import json
import pathlib
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trip_planner import usage  # noqa: E402
from trip_planner.config import get_settings  # noqa: E402
from trip_planner.graph import NODE_LABELS, plan_trip_events  # noqa: E402

from server.evals_api import router as evals_router  # noqa: E402

app = FastAPI(title="Trip Planner Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evals_router)


class PlanRequest(BaseModel):
    message: str


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def config() -> dict:
    s = get_settings()
    return {
        "model": s.openai_model,
        "judge_model": s.judge_model,
        "use_gateway": s.use_gateway,
        "ai_gateway": bool(s.openai_base_url),
        "inject_regression": s.inject_regression,
        "nodes": NODE_LABELS,
    }


@app.post("/api/usage/reset")
def reset_usage() -> dict:
    usage.reset()
    return {"ok": True}


@app.post("/api/plan/stream")
async def plan_stream(req: PlanRequest):
    """Stream the agent run as SSE events: node | final | error."""

    async def event_gen():
        # Tell the client what the pipeline looks like up front.
        yield {"event": "pipeline", "data": json.dumps(NODE_LABELS)}
        async for ev in plan_trip_events(req.message):
            yield {"event": ev.get("type", "message"), "data": json.dumps(ev)}

    return EventSourceResponse(event_gen())
