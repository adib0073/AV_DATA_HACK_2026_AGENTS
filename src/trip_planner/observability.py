"""Layer 3 - in-code observability via DeepEval's @observe tracing.

This module is a thin, dependency-tolerant wrapper around `deepeval.tracing`.
The whole point of the talk is that instrumenting code you own takes ~3 lines,
so we centralize those imports here and expose small helpers the agents reuse.
"""

from __future__ import annotations

from typing import Any

# DeepEval tracing primitives. Imported here so the rest of the codebase has a
# single, stable surface to call - and so a missing install fails loudly once.
from deepeval.tracing import (  # type: ignore
    observe,
    update_current_span,
    update_current_trace,
    update_llm_span,
)

try:
    from deepeval.dataset import get_current_golden  # type: ignore
except Exception:  # pragma: no cover - older deepeval
    def get_current_golden():  # type: ignore
        return None


__all__ = [
    "observe",
    "update_current_span",
    "update_current_trace",
    "update_llm_span",
    "get_current_golden",
    "record_llm_usage",
]


def record_llm_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_per_input_token: float,
    cost_per_output_token: float,
) -> None:
    """Attach token counts to the current LLM span.

    Confident AI multiplies these by the per-token cost (set on the @observe
    decorator) to render USD cost on the LLM span and roll it up to the trace.
    Safe to call even if there is no active span.
    """
    if input_tokens is None and output_tokens is None:
        return
    try:
        update_llm_span(
            input_token_count=float(input_tokens or 0),
            output_token_count=float(output_tokens or 0),
        )
    except Exception:
        # Never let instrumentation break the agent.
        pass

    # Mirror into the local accumulator for the live UI cost panel.
    try:
        from . import usage

        cost = (input_tokens or 0) * cost_per_input_token + (
            output_tokens or 0
        ) * cost_per_output_token
        usage.add(input_tokens or 0, output_tokens or 0, cost)
    except Exception:
        pass


def extract_usage(message: Any) -> tuple[int | None, int | None]:
    """Pull (input_tokens, output_tokens) out of a LangChain AIMessage."""
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage.get("input_tokens"), usage.get("output_tokens")
    # Fallback: response_metadata.token_usage (OpenAI style)
    meta = getattr(message, "response_metadata", {}) or {}
    tu = meta.get("token_usage") or meta.get("usage") or {}
    if tu:
        return tu.get("prompt_tokens"), tu.get("completion_tokens")
    return None, None
