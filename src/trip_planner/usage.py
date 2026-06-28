"""A tiny in-process token/cost accumulator.

DeepEval + Confident AI are the *real* place token cost is tracked across runs.
This local tracker exists so the demo chat UI can show a live "tokens & est.
cost" panel without a round-trip to the cloud - making the point tangible on
stage even offline.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    # MCP tool calls made, keyed by tool name (powers the Layer-4 breakdown).
    tool_calls: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def tool_call_count(self) -> int:
        return sum(self.tool_calls.values())


_lock = threading.Lock()
_usage = Usage()


def add(input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    with _lock:
        _usage.calls += 1
        _usage.input_tokens += int(input_tokens or 0)
        _usage.output_tokens += int(output_tokens or 0)
        _usage.cost_usd += float(cost_usd or 0.0)


def add_tool(name: str) -> None:
    with _lock:
        _usage.tool_calls[name] = _usage.tool_calls.get(name, 0) + 1


def snapshot() -> Usage:
    with _lock:
        return Usage(
            _usage.calls,
            _usage.input_tokens,
            _usage.output_tokens,
            _usage.cost_usd,
            dict(_usage.tool_calls),
        )


def reset() -> None:
    global _usage
    with _lock:
        _usage = Usage()
