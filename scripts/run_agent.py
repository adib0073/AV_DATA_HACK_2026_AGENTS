"""Run the trip-planner agent once from the command line.

Usage:
    python scripts/run_agent.py "Plan a 5-day relaxing trip to Bali for 2..."
    python scripts/run_agent.py            # uses a default prompt

Requires the MCP servers to be running (python mcp_servers/run_all.py).
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trip_planner import usage  # noqa: E402
from trip_planner.graph import plan_trip  # noqa: E402

DEFAULT = "Plan a 5-day relaxing trip to Bali for 2 from Mumbai in October, budget $2500 total."


async def _run(prompt: str) -> None:
    result = await plan_trip(prompt)
    print("\n" + "=" * 70)
    print(result["final_response"])
    print("=" * 70)
    u = usage.snapshot()
    print(f"\nLLM calls: {u.calls} | tokens: {u.total_tokens:,} "
          f"(in {u.input_tokens:,} / out {u.output_tokens:,}) | "
          f"est. cost: ${u.cost_usd:.4f}")


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or DEFAULT
    print(f"User: {prompt}")
    asyncio.run(_run(prompt))


if __name__ == "__main__":
    main()
