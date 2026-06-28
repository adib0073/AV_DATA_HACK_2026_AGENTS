"""Mock Activities/Itinerary MCP server (FastMCP, streamable-http on :8003).

Tools: search_activities, get_destination_overview.
Run:  python mcp_servers/activities_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from _common import load_json, mcp_host, seeded_rng

mcp = FastMCP("Activities", host=mcp_host(), port=8003)

_ACT = load_json("activities.json", {"by_type": {}, "meals": []})
BY_TYPE = _ACT.get("by_type", {})
MEALS = _ACT.get("meals", [])


@mcp.tool()
def search_activities(destination: str, travel_type: str = "leisure", days: int = 3) -> list:
    """Return a day-by-day list of suggested activities for the destination.

    Args:
        destination: City to plan activities in.
        travel_type: explorer | leisure | relaxing | adventure | business | family.
        days: Number of days to plan.
    """
    rng = seeded_rng("activities", destination, travel_type)
    pool = list(BY_TYPE.get(travel_type, BY_TYPE.get("leisure", ["City tour"])))
    rng.shuffle(pool)
    plan = []
    for d in range(1, max(1, days) + 1):
        picks = [pool[(d - 1 + i) % len(pool)] for i in range(2)]
        plan.append({
            "day": d,
            "morning": f"{picks[0]} in {destination}",
            "afternoon": f"{picks[1]} in {destination}",
            "evening": rng.choice(MEALS) if MEALS else "Dinner",
            "est_cost": 20 + rng.randint(0, 80),
        })
    return plan


@mcp.tool()
def get_destination_overview(destination: str) -> dict:
    """Get a short overview (best season, currency, tips) for a destination."""
    rng = seeded_rng("overview", destination)
    return {
        "destination": destination,
        "best_season": rng.choice(["Spring", "Summer", "Autumn", "Winter", "Year-round"]),
        "avg_daily_budget_usd": 60 + rng.randint(0, 140),
        "safety": rng.choice(["High", "Moderate"]),
        "tips": [
            "Book popular attractions ahead.",
            "Carry some local currency for street vendors.",
            f"Best explored over {rng.randint(3, 6)} days.",
        ],
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
