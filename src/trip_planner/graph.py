"""Assemble the LangGraph multi-agent graph and the traced entrypoint."""

from __future__ import annotations

import json
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .agents.base import _to_toolcalls
from .agents.nodes import (
    booking_node,
    finalize_node,
    flight_node,
    hotel_node,
    itinerary_node,
    planner_node,
    route,
    supervisor_node,
)
from .config import get_settings
from .metrics import reasoning_metrics
from .observability import observe, update_current_span, update_current_trace
from .state import TripState
from .tracing_langfuse import langfuse_config

_S = get_settings()
# Layer 2 (Reasoning) metrics live on the root span, which has the full trace.
_REASONING_METRICS = reasoning_metrics()


@lru_cache(maxsize=1)
def build_graph():
    builder = StateGraph(TripState)
    builder.add_node("planner", planner_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("flight", flight_node)
    builder.add_node("hotel", hotel_node)
    builder.add_node("itinerary", itinerary_node)
    builder.add_node("booking", booking_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route,
        {
            "flight": "flight",
            "hotel": "hotel",
            "itinerary": "itinerary",
            "booking": "booking",
            "finalize": "finalize",
        },
    )
    # Every worker reports back to the supervisor, which picks the next step.
    for worker in ("flight", "hotel", "itinerary", "booking"):
        builder.add_edge(worker, "supervisor")
    builder.add_edge("finalize", END)
    return builder.compile()


@observe(type="agent", name="trip_planner", metrics=_REASONING_METRICS)
async def plan_trip(user_input: str) -> dict:
    """Run the full trip-planning agent for one user request.

    This is the trace root (the end-to-end `LLMTestCase`). Layer-1 metrics
    (TaskCompletion, StepEfficiency) are attached here by the eval harness via
    `evals_iterator`; Layer-2 Reasoning metrics are attached on this span.
    """
    update_current_trace(name="Trip planning", input=user_input)

    graph = build_graph()
    result: TripState = await graph.ainvoke(
        {"user_input": user_input}, config=langfuse_config("trip_planning")
    )

    final = result.get("final_response", "")
    tool_trace = result.get("tool_trace", [])

    update_current_span(
        input=user_input,
        output=final,
        tools_called=_to_toolcalls(
            [{"name": t["tool"], "args": t.get("args", {})} for t in tool_trace]
        ),
        metadata={"plan": result.get("plan", []), "completed": result.get("completed", [])},
    )
    update_current_trace(
        output=final,
        tools_called=_to_toolcalls(
            [{"name": t["tool"], "args": t.get("args", {})} for t in tool_trace]
        ),
        metadata={"plan": result.get("plan", [])},
    )
    return {"final_response": final, "state": result}


def plan_trip_sync(user_input: str) -> dict:
    """Convenience sync wrapper for scripts."""
    import asyncio

    return asyncio.run(plan_trip(user_input))


# ---------------------------------------------------------------------------
# Streaming variant - emits one event per graph node so a UI can show each
# agent "lighting up" as it works (great for the live web demo).
# ---------------------------------------------------------------------------
NODE_LABELS = {
    "planner": "Planner",
    "supervisor": "Supervisor",
    "flight": "Flight agent",
    "hotel": "Hotel agent",
    "itinerary": "Itinerary agent",
    "booking": "Booking agent",
    "finalize": "Finalizing",
}


@observe(type="agent", name="trip_planner", metrics=_REASONING_METRICS)
async def _run_streaming(user_input: str, queue) -> None:
    """Run the graph with astream, pushing node updates onto `queue`.

    Still produces a full root trace span (so the 'open the trace' demo beat
    works from the web UI too).
    """
    from . import usage

    update_current_trace(name="Trip planning", input=user_input)
    graph = build_graph()

    final_state: dict = {"user_input": user_input}
    async for mode, chunk in graph.astream(
        {"user_input": user_input},
        stream_mode=["updates", "values"],
        config=langfuse_config("trip_planning"),
    ):
        if mode == "values":
            final_state = chunk
            continue
        # mode == "updates": {node_name: partial_state}
        for node, partial in (chunk or {}).items():
            await queue.put({
                "type": "node",
                "node": node,
                "label": NODE_LABELS.get(node, node),
                "data": _safe(partial),
                "usage": _usage_dict(usage.snapshot()),
            })

    final = final_state.get("final_response", "")
    tool_calls = _to_toolcalls(
        [{"name": t["tool"], "args": t.get("args", {})}
         for t in final_state.get("tool_trace", [])]
    )
    update_current_span(
        input=user_input, output=final, tools_called=tool_calls,
        metadata={"plan": final_state.get("plan", [])},
    )
    update_current_trace(output=final, tools_called=tool_calls)

    await queue.put({
        "type": "final",
        "response": final,
        "state": {
            "request": final_state.get("request"),
            "plan": final_state.get("plan"),
            "completed": final_state.get("completed"),
            "selected_flight": final_state.get("selected_flight"),
            "flight_options": final_state.get("flight_options"),
            "selected_hotel": final_state.get("selected_hotel"),
            "hotel_options": final_state.get("hotel_options"),
            "itinerary": final_state.get("itinerary"),
            "booking": final_state.get("booking"),
        },
        "usage": _usage_dict(usage.snapshot()),
    })


def _flatten_error(exc: BaseException) -> str:
    """Produce a human-readable message, unwrapping ExceptionGroups.

    asyncio/anyio TaskGroups raise ExceptionGroup, whose str() is the useless
    "unhandled errors in a TaskGroup (1 sub-exception)". Dig out the real cause
    (e.g. an httpx ConnectError to an MCP server) so the UI shows something
    actionable.
    """
    parts: list[str] = []
    seen: set[int] = set()

    def _walk(e: BaseException) -> None:
        if id(e) in seen:
            return
        seen.add(id(e))
        subs = getattr(e, "exceptions", None)  # ExceptionGroup / BaseExceptionGroup
        if subs:
            for sub in subs:
                _walk(sub)
            return
        msg = str(e).strip()
        label = f"{type(e).__name__}: {msg}" if msg else type(e).__name__
        parts.append(label)
        if e.__cause__ is not None:
            _walk(e.__cause__)

    _walk(exc)
    # De-dup while preserving order.
    uniq = list(dict.fromkeys(parts))
    return " | ".join(uniq) if uniq else str(exc)


async def plan_trip_events(user_input: str):
    """Async generator of UI events for one trip-planning request."""
    import asyncio
    import traceback

    queue: asyncio.Queue = asyncio.Queue()

    async def _producer():
        try:
            await _run_streaming(user_input, queue)
        except Exception as exc:  # surface errors as an event, don't hang the stream
            traceback.print_exc()  # full traceback to the server logs for debugging
            await queue.put({"type": "error", "message": _flatten_error(exc)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(_producer())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        await task


def _usage_dict(u) -> dict:
    return {
        "calls": u.calls,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "total_tokens": u.total_tokens,
        "cost_usd": round(u.cost_usd, 6),
    }


def _safe(obj):
    """Make a node delta JSON-serializable (defensive)."""
    import json

    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {k: str(v) for k, v in (obj or {}).items()}
