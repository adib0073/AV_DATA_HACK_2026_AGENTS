"""Mock Flights MCP server (FastMCP, streamable-http on :8001).

Tools: search_flights, get_flight_details. Fully offline & deterministic.
Run:  python mcp_servers/flights_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from _common import city_code, load_json, mcp_host, seeded_rng

mcp = FastMCP("Flights", host=mcp_host(), port=8001)

AIRLINES = load_json("airlines.json", [{"name": "MockAir", "rating": 4.0}])


def _make_flights(origin: str, destination: str, date: str | None, travelers: int):
    rng = seeded_rng("flights", origin, destination, date)
    oc, dc = city_code(origin), city_code(destination)
    base = 80 + rng.randint(0, 60) + len(destination) * 7
    flights = []
    for i in range(5):
        airline = rng.choice(AIRLINES)
        stops = rng.choice([0, 0, 1])
        price = round((base + i * 35 + stops * 25) * (0.9 + rng.random() * 0.5), 2)
        dep_h = rng.randint(5, 21)
        dur = 2 + stops + rng.randint(1, 9)
        flights.append({
            "flight_id": f"{oc}{dc}{100 + i}",
            "airline": airline["name"],
            "rating": airline["rating"],
            "origin": origin,
            "destination": destination,
            "date": date,
            "depart": f"{dep_h:02d}:00",
            "duration_hours": dur,
            "stops": stops,
            "seats_left": rng.randint(2, 40),
            "price": price * max(1, travelers),
            "price_per_traveler": price,
            "currency": "USD",
        })
    return sorted(flights, key=lambda f: f["price"])


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    date: str | None = None,
    travelers: int = 1,
    max_price: float | None = None,
) -> list:
    """Search available flights between two cities.

    Args:
        origin: Departure city (e.g. "Mumbai").
        destination: Arrival city (e.g. "Bali").
        date: Departure date YYYY-MM-DD (optional).
        travelers: Number of travelers.
        max_price: Optional max total price filter (USD).
    """
    flights = _make_flights(origin or "Origin", destination, date, max(1, travelers))
    if max_price:
        flights = [f for f in flights if f["price"] <= max_price] or flights
    return flights


@mcp.tool()
def get_flight_details(flight_id: str) -> dict:
    """Get fare rules and details for a specific flight id."""
    rng = seeded_rng("flight_details", flight_id)
    if not flight_id or flight_id.upper() == "UNKNOWN":
        return {"flight_id": flight_id, "error": "No flight found for that id."}
    return {
        "flight_id": flight_id,
        "baggage": f"{rng.choice([15, 20, 23, 30])} kg checked",
        "cabin": rng.choice(["Economy", "Premium Economy"]),
        "refundable": rng.choice([True, False]),
        "change_fee": rng.choice([0, 25, 50]),
        "on_time_performance": f"{rng.randint(70, 95)}%",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
