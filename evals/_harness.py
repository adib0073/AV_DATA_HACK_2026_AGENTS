"""Shared machinery for the Layer 1 / Layer 2 / shadow eval scripts.

Centralizes the bits that are easy to get wrong:

* A single, reused event loop. The MCP client caches an ``asyncio.Lock`` bound to
  the first loop it runs on, so every coroutine in a run must share one loop.
* DeepEval's ``evals_iterator`` is driven **synchronously** (``run_async=False``).
  Running our async agent inside a manual loop while DeepEval also spins up its
  own async executor corrupts context vars *and* fires judge calls 20-wide, which
  trips OpenAI rate limits. Sequential is slower but rock-solid for a live demo.
* Result capture: ``evals_iterator`` is a generator that ``return``s an
  ``EvaluationResult`` on ``StopIteration`` - we grab it to render our own tables.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

import trip_planner.config  # noqa: E402,F401  (normalizes env, e.g. OPENAI_BASE_URL)
from goldens import get_goldens  # noqa: E402

REGRESSION_DESTINATION = "Tokyo"  # the seeded-bug trigger


# ---------------------------------------------------------------------------
# One shared event loop for the whole script run.
# ---------------------------------------------------------------------------
_LOOP: asyncio.AbstractEventLoop | None = None


def get_loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


def run(coro) -> Any:
    return get_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Golden selection
# ---------------------------------------------------------------------------
def _destination(golden) -> str:
    meta = getattr(golden, "additional_metadata", None) or {}
    return meta.get("destination", "")


def select_goldens(limit: int | None = None, ensure: Iterable[str] = (REGRESSION_DESTINATION,)):
    """Return goldens, optionally capped to ``limit`` but always including the
    destinations in ``ensure`` (so the regression case is never dropped)."""
    goldens = get_goldens()
    if limit is None or limit >= len(goldens):
        return goldens

    ensure = {e.lower() for e in ensure}
    picked = goldens[:limit]
    picked_dests = {_destination(g).lower() for g in picked}
    for g in goldens:
        d = _destination(g).lower()
        if d in ensure and d not in picked_dests:
            picked.append(g)
            picked_dests.add(d)
    return picked


# ---------------------------------------------------------------------------
# Layer-1 end-to-end run (full agent per golden, trace-scored)
# ---------------------------------------------------------------------------
def run_e2e(goldens, metrics, *, print_results: bool = False, identifier: str | None = None,
            progress: bool = True):
    """Run the full agent on each golden via evals_iterator; return the captured
    DeepEval ``EvaluationResult`` (``.test_results`` + Confident AI link).

    Each golden runs the *whole* agent (~7 LLM calls) plus the judge, sequentially,
    so a full board takes minutes. We stream a one-line progress update per golden
    (``progress=True``) so the live console shows it is working rather than frozen.
    """
    import time

    from deepeval.dataset import EvaluationDataset
    from deepeval.evaluate.configs import AsyncConfig, DisplayConfig, ErrorConfig
    from trip_planner.graph import plan_trip

    goldens = list(goldens)
    total = len(goldens)
    dataset = EvaluationDataset(goldens=goldens)
    loop = get_loop()
    result = None
    gen = dataset.evals_iterator(
        metrics=metrics,
        identifier=identifier,
        async_config=AsyncConfig(run_async=False),
        error_config=ErrorConfig(ignore_errors=True),
        display_config=DisplayConfig(
            print_results=print_results,
            show_indicator=print_results,
            inspect_after_run=False,
        ),
    )
    idx = 0
    started = time.time()
    try:
        while True:
            golden = next(gen)
            idx += 1
            dest = _destination(golden) or (golden.input[:32] + "...")
            if progress:
                info(f"  [{idx}/{total}] running + scoring  ->  {dest} ...")
            t0 = time.time()
            loop.run_until_complete(plan_trip(golden.input))
            if progress:
                elapsed = time.time() - t0
                avg = (time.time() - started) / idx
                eta = avg * (total - idx)
                info(f"  [{idx}/{total}] done in {elapsed:4.1f}s "
                     f"(elapsed {time.time() - started:4.0f}s, ~{eta:4.0f}s left)")
    except StopIteration as exc:
        result = exc.value
    return result


# ---------------------------------------------------------------------------
# Layer-2 component surface: the flight agent's tool *decision*, in isolation.
# ---------------------------------------------------------------------------
async def _flight_decision(destination: str, *, force_wrong_tool: bool,
                           origin: str = "Mumbai", travelers: int = 2) -> dict:
    from trip_planner.agents.base import run_specialist
    from trip_planner.prompts import FLIGHT_SYSTEM

    ctx = (
        f"Find flights from {origin} to {destination} for {travelers} traveler(s). "
        f"Search for available flights and pick the best option within budget."
    )
    res = await run_specialist(
        domain="flights",
        system=FLIGHT_SYSTEM,
        context=ctx,
        expected_tools=["search_flights"],
        force_wrong_tool=force_wrong_tool,
        summarize=False,
    )
    return {"tools_called": res["tool_calls"], "tool_args": res["tool_args"]}


def flight_decision(destination: str, *, force_wrong_tool: bool, **kw) -> dict:
    return run(_flight_decision(destination, force_wrong_tool=force_wrong_tool, **kw))


# ---------------------------------------------------------------------------
# Pretty printing (rich if available, else plain)
# ---------------------------------------------------------------------------
try:  # rich ships with deepeval
    from rich.console import Console
    from rich.table import Table

    _console = Console()
    _HAS_RICH = True
except Exception:  # pragma: no cover
    _console = None
    _HAS_RICH = False


def hr(title: str) -> None:
    line = "=" * 78
    if _HAS_RICH:
        _console.print(f"[bold cyan]{line}[/]\n[bold white]{title}[/]\n[bold cyan]{line}[/]")
    else:
        print(f"\n{line}\n{title}\n{line}")


def info(msg: str) -> None:
    if _HAS_RICH:
        _console.print(msg)
    else:
        print(msg)


def metrics_table(title: str, rows: list[dict], columns: list[str]) -> None:
    """rows: list of dicts keyed by column name. A 'status' column is colorized."""
    if _HAS_RICH:
        table = Table(title=title, header_style="bold magenta", expand=False)
        for c in columns:
            table.add_column(c)
        for r in rows:
            cells = []
            for c in columns:
                v = str(r.get(c, ""))
                if c.lower() in {"status", "result", "verdict"}:
                    color = "green" if v.upper() in {"PASS", "FIXED", "OK"} else (
                        "red" if v.upper() in {"FAIL", "BROKEN"} else "yellow")
                    v = f"[{color}]{v}[/]"
                cells.append(v)
            table.add_row(*cells)
        _console.print(table)
    else:
        print(f"\n{title}")
        print(" | ".join(columns))
        print("-" * 78)
        for r in rows:
            print(" | ".join(str(r.get(c, "")) for c in columns))


def by_input(test_results) -> dict[str, dict]:
    """Flatten DeepEval test results into {test-case input -> {metric name -> MetricData}}.

    A single golden produces several test results (the trace-level metrics, the
    root-agent-span reasoning metrics, and one per tool-decision span). The two
    root-level results share the golden's input, so merging by input gives us all
    the trace/reasoning metrics for that golden in one place.
    """
    out: dict[str, dict] = {}
    for tr in test_results or []:
        bucket = out.setdefault(tr.input, {})
        for m in tr.metrics_data or []:
            bucket[m.name] = m
    return out


def fmt_score(metric) -> str:
    if metric is None or metric.score is None:
        return "-"
    return f"{metric.score:.2f}"


def usage_dict() -> dict:
    """Snapshot of agent-side token usage accrued during this run."""
    from trip_planner import usage

    s = usage.snapshot()
    return {
        "calls": s.calls,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "total_tokens": s.total_tokens,
        "cost_usd": round(s.cost_usd, 6),
        "tool_calls": dict(s.tool_calls),
    }


def record_table(tables: list, title: str, rows: list[dict], columns: list[str]) -> None:
    """Print a table to the console *and* collect it for the JSON report."""
    metrics_table(title, rows, columns)
    tables.append({"title": title, "columns": columns, "rows": rows})


def write_report(path: str, *, suite: str, meta: dict, tables: list,
                 stats: dict, confident_link: str | None = None) -> None:
    import json

    payload = {
        "suite": suite,
        **meta,
        "tables": tables,
        "stats": stats,
        "confident_link": confident_link,
        "usage": usage_dict(),
    }
    pathlib.Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def confident_link(result) -> None:
    link = getattr(result, "confident_link", None) if result else None
    if link:
        info(f"\n[bold]Confident AI:[/] {link}" if _HAS_RICH else f"\nConfident AI: {link}")
    else:
        info("\n(Log in with CONFIDENT_API_KEY to get a shareable trace link.)")
