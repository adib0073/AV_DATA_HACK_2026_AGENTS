"""Eval Studio API - run the eval suite, manage goldens, surface observability.

Evals are executed as **subprocesses** (`python evals/<script>.py --json-out ...`)
rather than in-process. That keeps DeepEval's synchronous `evals_iterator` and the
agent's cached MCP event loop completely isolated from the FastAPI event loop, and
it reuses the exact same scripts the CLI/demo uses. We stream the subprocess
stdout to the browser as SSE, then emit the structured JSON report it wrote.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import tempfile
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "evals") not in sys.path:
    sys.path.insert(0, str(ROOT / "evals"))

router = APIRouter(prefix="/api/evals", tags=["evals"])

SCRIPTS = {
    "layer1": "layer1_e2e_eval.py",
    "layer2": "layer2_component_eval.py",
    "shadow": "shadow_eval.py",
}

SUITES = [
    {
        "id": "layer1",
        "name": "Layer 1 · End-to-End",
        "desc": "Runs the whole agent on each golden, scored by TaskCompletion. "
                "LLM-judged, so slower. With regression on, only Tokyo fails.",
        "judged": True,
        "supports_regression": True,
    },
    {
        "id": "layer2",
        "name": "Layer 2 · Component",
        "desc": "Scores the flight tool-decision per destination + an isolated "
                "healthy-vs-buggy contrast. Deterministic (no judge) - seconds.",
        "judged": False,
        "supports_regression": True,
    },
    {
        "id": "shadow",
        "name": "Shadow mode",
        "desc": "Replays goldens through the buggy baseline and the fixed candidate "
                "and compares - proves the fix is safe to ship. Deterministic.",
        "judged": False,
        "supports_regression": False,
    },
]

_MAX_HISTORY = 50

# Only one eval run at a time (they share OpenAI rate budget + MCP servers).
_run_lock = asyncio.Lock()


def _data_dir() -> pathlib.Path:
    import goldens as G

    return G.data_dir()


def _history_file() -> pathlib.Path:
    return _data_dir() / "_run_history.json"


def _tally_file() -> pathlib.Path:
    return _data_dir() / "_tool_tally.json"


# ---------------------------------------------------------------------------
# Goldens
# ---------------------------------------------------------------------------
class GoldensPayload(BaseModel):
    goldens: list[dict]


@router.get("/info")
def info() -> dict:
    from trip_planner.config import get_settings
    import goldens as G

    s = get_settings()
    return {
        "suites": SUITES,
        "model": s.openai_model,
        "judge_model": s.judge_model,
        "use_gateway": s.use_gateway,
        "inject_regression": s.inject_regression,
        "goldens_count": len(G.get_golden_dicts()),
        "goldens_custom": G.is_custom(),
    }


@router.get("/goldens")
def list_goldens() -> dict:
    import goldens as G

    return {"goldens": G.get_golden_dicts(), "custom": G.is_custom()}


@router.post("/goldens")
def upload_goldens(payload: GoldensPayload) -> dict:
    import goldens as G

    if not payload.goldens:
        raise HTTPException(status_code=400, detail="No goldens provided.")
    count = G.save_custom(payload.goldens)
    if count == 0:
        raise HTTPException(status_code=400, detail="No valid goldens (each needs an 'input').")
    return {"ok": True, "count": count, "custom": True}


@router.post("/goldens/reset")
def reset_goldens() -> dict:
    import goldens as G

    G.reset_custom()
    return {"ok": True, "count": len(G.get_golden_dicts()), "custom": False}


# ---------------------------------------------------------------------------
# Run history / observability
# ---------------------------------------------------------------------------
def _load_history() -> list[dict]:
    f = _history_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _append_history(result: dict, duration_s: float | None = None) -> None:
    hist = _load_history()
    usage = result.get("usage", {}) or {}
    hist.append({
        "ts": time.time(),
        "suite": result.get("suite"),
        "title": result.get("title"),
        "stats": result.get("stats", {}),
        "usage": usage,
        "duration_s": round(duration_s, 1) if duration_s else None,
        "confident_link": result.get("confident_link"),
        "regression": result.get("regression"),
    })
    hist = hist[-_MAX_HISTORY:]
    _history_file().write_text(json.dumps(hist, indent=2), encoding="utf-8")
    bump_tool_tally(usage.get("tool_calls") or {})


def _load_tally() -> dict[str, int]:
    f = _tally_file()
    if f.exists():
        try:
            return {k: int(v) for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
        except Exception:
            return {}
    return {}


def bump_tool_tally(tool_calls: dict[str, int]) -> None:
    """Accumulate MCP tool-call counts across all runs (the Layer-4 breakdown)."""
    if not tool_calls:
        return
    tally = _load_tally()
    for name, n in tool_calls.items():
        tally[name] = tally.get(name, 0) + int(n or 0)
    _tally_file().write_text(json.dumps(tally, indent=2), encoding="utf-8")


def _tally_by_server() -> dict:
    """Group the persistent tool tally by MCP server, for the dashboard."""
    from server.flow import server_for_tool

    tally = _load_tally()
    by_server: dict[str, int] = {}
    tools: list[dict] = []
    for name, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        srv = server_for_tool(name)
        by_server[srv] = by_server.get(srv, 0) + n
        tools.append({"tool": name, "server": srv, "count": n})
    return {
        "total": sum(tally.values()),
        "by_server": [{"server": s, "count": c} for s, c in
                      sorted(by_server.items(), key=lambda kv: -kv[1])],
        "by_tool": tools,
    }


def _langfuse_url() -> str | None:
    """Browser link to the Langfuse trace list (Layer 3 trace timeline)."""
    try:
        from trip_planner.config import get_settings

        return get_settings().langfuse_traces_url
    except Exception:
        return None


def _confident_project_link(hist: list[dict]) -> str | None:
    for h in reversed(hist):
        link = h.get("confident_link")
        if link and "/project/" in link:
            base = link.split("/test-runs/")[0]
            return f"{base}/observatory"
    return None


@router.get("/observability")
def observability() -> dict:
    hist = _load_history()
    agg = {"runs": len(hist), "calls": 0, "input_tokens": 0,
           "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0,
           "tool_calls": 0, "avg_duration_s": 0.0}
    durations: list[float] = []
    for h in hist:
        u = h.get("usage", {})
        agg["calls"] += int(u.get("calls", 0) or 0)
        agg["input_tokens"] += int(u.get("input_tokens", 0) or 0)
        agg["output_tokens"] += int(u.get("output_tokens", 0) or 0)
        agg["total_tokens"] += int(u.get("total_tokens", 0) or 0)
        agg["cost_usd"] += float(u.get("cost_usd", 0.0) or 0.0)
        agg["tool_calls"] += sum((u.get("tool_calls") or {}).values())
        if h.get("duration_s"):
            durations.append(float(h["duration_s"]))
    agg["cost_usd"] = round(agg["cost_usd"], 6)
    agg["avg_duration_s"] = round(sum(durations) / len(durations), 1) if durations else 0.0

    # Layer-1 pass-rate series (mirrors Confident AI "Test Runs"): oldest -> newest.
    pass_series = [
        {
            "ts": h["ts"],
            "regression": h.get("regression"),
            "passed": h["stats"].get("passed", 0),
            "total": h["stats"].get("total", 0),
            "rate": round(h["stats"]["passed"] / h["stats"]["total"], 3)
            if h.get("stats", {}).get("total") else None,
        }
        for h in hist
        if h.get("suite") == "layer1" and h.get("stats", {}).get("total")
    ]

    # Framework KPIs (per the 4-layer slide): Task Success Rate + Task Completion
    # Latency (Layer 1), Plan Quality + Plan Adherence (Layer 2 reasoning). These
    # are aggregated per Layer-1 run so the dashboard refreshes on every eval.
    quality_series: list[dict] = []
    for h in hist:
        if h.get("suite") != "layer1":
            continue
        st = h.get("stats", {}) or {}
        if not st.get("total"):
            continue
        sr = st.get("success_rate")
        if sr is None and st.get("total"):
            sr = round(st.get("passed", 0) / st["total"], 4)
        quality_series.append({
            "ts": h["ts"],
            "regression": h.get("regression"),
            "success_rate": sr,
            "task_completion": st.get("task_completion_avg"),
            "plan_quality": st.get("plan_quality_avg"),
            "plan_adherence": st.get("plan_adherence_avg"),
            "latency_avg_s": st.get("latency_avg_s"),
        })
    quality_series = quality_series[-12:]

    def _kpi(key: str) -> dict | None:
        pts = [(p["ts"], p[key]) for p in quality_series if p.get(key) is not None]
        if not pts:
            return None
        return {
            "latest": pts[-1][1],
            "prev": pts[-2][1] if len(pts) >= 2 else None,
            "avg": round(sum(v for _, v in pts) / len(pts), 4),
            "n": len(pts),
        }

    kpis = {
        "success_rate": _kpi("success_rate"),
        "latency_avg_s": _kpi("latency_avg_s"),
        "task_completion": _kpi("task_completion"),
        "plan_quality": _kpi("plan_quality"),
        "plan_adherence": _kpi("plan_adherence"),
    }

    # Latest shadow A/B outcome (for the significance card).
    shadow_ab = None
    for h in reversed(hist):
        st = h.get("stats", {}) or {}
        if h.get("suite") == "shadow" and st.get("trials"):
            shadow_ab = {
                "ts": h["ts"],
                "a_rate": st.get("a_rate"), "b_rate": st.get("b_rate"),
                "lift": st.get("lift"), "p_value": st.get("p_value"),
                "significant": st.get("significant"),
                "ci_low": st.get("ci_low"), "ci_high": st.get("ci_high"),
                "trials": st.get("trials"),
                "fixed": st.get("fixed"), "regressed": st.get("regressed"),
            }
            break

    return {
        "aggregate": agg,
        "history": list(reversed(hist)),
        "pass_series": pass_series[-12:],
        "quality_series": quality_series,
        "kpis": kpis,
        "shadow_ab": shadow_ab,
        "mcp": _tally_by_server(),
        "confident_observatory": _confident_project_link(hist),
        "langfuse_url": _langfuse_url(),
        "obot_url": OBOT_URL,
        "use_gateway": get_settings_safe("use_gateway"),
    }


def get_settings_safe(attr: str):
    try:
        from trip_planner.config import get_settings

        return getattr(get_settings(), attr)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Flow & traces (Layer 3 + Layer 4 in one view)
# ---------------------------------------------------------------------------
class FlowRequest(BaseModel):
    input: str | None = None


_DEFAULT_FLOW_INPUT = (
    "Plan a 4-day leisure trip to Goa for 2 travelers in October with a total "
    "budget of $2500. Find flights from Mumbai and a beachfront hotel, build a "
    "day-by-day itinerary, and make the reservations."
)

OBOT_URL = os.environ.get("OBOT_PUBLIC_URL", "http://localhost:8080")


@router.get("/flow")
def flow_topology() -> dict:
    """The canonical orchestrator -> agents -> gateway -> MCP -> tools diagram,
    with no run attached (instant; 'typically how the flow looks')."""
    from server.flow import build_flow
    from trip_planner.config import get_settings

    s = get_settings()
    payload = build_flow([], use_gateway=s.use_gateway, ran=False)
    payload.update({
        "obot_url": OBOT_URL,
        "confident_observatory": _confident_project_link(_load_history()),
        "langfuse_url": _langfuse_url(),
        "input": None,
        "usage": None,
    })
    return payload


@router.post("/flow")
async def flow_capture(req: FlowRequest) -> dict:
    """Run ONE trip in-process, capture its real tool calls, and return a Mermaid
    diagram (Layer 3 spans + Layer 4 gateway) plus the per-call list."""
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="An eval/flow run is already in progress.")

    from server.flow import build_flow
    from trip_planner import usage
    from trip_planner.config import get_settings
    from trip_planner.graph import plan_trip

    s = get_settings()
    user_input = (req.input or _DEFAULT_FLOW_INPUT).strip()

    async with _run_lock:
        before = usage.snapshot()
        t0 = time.time()
        result = await plan_trip(user_input)
        duration_s = round(time.time() - t0, 1)
        after = usage.snapshot()

    state = result.get("state", {}) if isinstance(result, dict) else {}
    tool_trace = state.get("tool_trace", []) or []

    # Per-run tool-call delta -> feed the persistent Layer-4 tally.
    tool_delta = {
        name: after.tool_calls.get(name, 0) - before.tool_calls.get(name, 0)
        for name in after.tool_calls
    }
    tool_delta = {k: v for k, v in tool_delta.items() if v > 0}
    try:
        bump_tool_tally(tool_delta)
    except Exception:
        pass

    payload = build_flow(tool_trace, use_gateway=s.use_gateway, ran=True)
    payload.update({
        "input": user_input,
        "final_response": (result.get("final_response", "") if isinstance(result, dict) else ""),
        "plan": state.get("plan", []),
        "completed": state.get("completed", []),
        "duration_s": duration_s,
        "obot_url": OBOT_URL,
        "confident_observatory": _confident_project_link(_load_history()),
        "langfuse_url": _langfuse_url(),
        "usage": {
            "calls": after.calls - before.calls,
            "input_tokens": after.input_tokens - before.input_tokens,
            "output_tokens": after.output_tokens - before.output_tokens,
            "total_tokens": after.total_tokens - before.total_tokens,
            "cost_usd": round(after.cost_usd - before.cost_usd, 6),
            "tool_calls": tool_delta,
        },
    })
    return payload


# ---------------------------------------------------------------------------
# Run a suite (SSE)
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    suite: str
    limit: int | None = None
    regression: str | None = None  # "on" | "off" | None


@router.post("/run")
async def run_eval(req: RunRequest):
    script = SCRIPTS.get(req.suite)
    if not script:
        raise HTTPException(status_code=400, detail=f"Unknown suite '{req.suite}'.")
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="An eval run is already in progress.")

    json_out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    args = [sys.executable, "-u", f"evals/{script}", "--json-out", json_out]
    if req.limit:
        args += ["--limit", str(int(req.limit))]
    if req.suite in ("layer1", "layer2") and req.regression in ("on", "off"):
        args += ["--regression", req.regression]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["TERM"] = "dumb"  # plain (no ANSI) rich output in the streamed log

    async def gen():
        await _run_lock.acquire()
        try:
            run_t0 = time.time()
            yield {"event": "start", "data": json.dumps({"suite": req.suite, "args": args[3:]})}
            proc = await asyncio.create_subprocess_exec(
                *args, cwd=str(ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if line.strip():
                    yield {"event": "log", "data": json.dumps({"line": line})}
            code = await proc.wait()

            result = None
            try:
                result = json.loads(pathlib.Path(json_out).read_text(encoding="utf-8"))
            except Exception:
                pass
            if result is not None:
                try:
                    _append_history(result, duration_s=time.time() - run_t0)
                except Exception:
                    pass
                yield {"event": "result", "data": json.dumps(result)}
            else:
                yield {"event": "error",
                       "data": json.dumps({"message": f"Run exited ({code}) without a report."})}
            yield {"event": "done", "data": json.dumps({"code": code})}
        finally:
            _run_lock.release()
            try:
                os.unlink(json_out)
            except Exception:
                pass

    return EventSourceResponse(gen())
