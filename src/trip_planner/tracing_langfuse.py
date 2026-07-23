"""Langfuse tracing (Layer 3 trace timeline) — open-source alternative to Confident AI.

The agents are LangGraph/LangChain, so the cleanest, lowest-touch way to get full
nested traces (orchestrator -> agent -> LLM span -> MCP tool span, with token/cost)
is Langfuse's LangChain callback handler. We attach it at the graph invocation
points; LangChain propagates it to every nested runnable automatically.

This is entirely independent of DeepEval: DeepEval still runs the Layer 1/2 metrics
locally. If Langfuse isn't configured or is unreachable, everything degrades to a
silent no-op so the agent never breaks.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .config import get_settings


@lru_cache(maxsize=1)
def get_langfuse_handler() -> Any | None:
    """Return a cached Langfuse LangChain CallbackHandler, or None if disabled.

    Config comes from the environment (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY /
    LANGFUSE_HOST); we mirror the settings into env so the SDK singleton picks them
    up regardless of import order.
    """
    s = get_settings()
    if not s.langfuse_enabled:
        return None
    try:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", s.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", s.langfuse_secret_key)
        os.environ.setdefault("LANGFUSE_HOST", s.langfuse_host)
        # Langfuse v3 exposes the LangChain integration here.
        from langfuse.langchain import CallbackHandler  # type: ignore

        return CallbackHandler()
    except Exception:
        # Missing package, bad keys, or unreachable host: tracing is best-effort.
        return None


def langfuse_config(run_name: str | None = None, **metadata: Any) -> dict:
    """Build a RunnableConfig fragment that wires Langfuse into a graph call.

    Returns ``{}`` when tracing is off, so callers can splat it unconditionally:
        await graph.ainvoke(state, config=langfuse_config("trip_planning"))
    """
    handler = get_langfuse_handler()
    if handler is None:
        return {}
    cfg: dict[str, Any] = {"callbacks": [handler]}
    if run_name:
        cfg["run_name"] = run_name
    md = {"langfuse_tags": ["trip-planner"], **metadata}
    cfg["metadata"] = md
    return cfg


def flush() -> None:
    """Best-effort flush of buffered events (useful for short-lived processes)."""
    handler = get_langfuse_handler()
    if handler is None:
        return
    try:
        from langfuse import get_client  # type: ignore

        get_client().flush()
    except Exception:
        pass
