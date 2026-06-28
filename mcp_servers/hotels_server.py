"""Mock Hotels MCP server (FastMCP, streamable-http on :8002).

Tools: search_hotels, get_hotel_details.
Run:  python mcp_servers/hotels_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from _common import city_code, load_json, mcp_host, seeded_rng

mcp = FastMCP("Hotels", host=mcp_host(), port=8002)

_HOTELS = load_json("hotels.json", {"brands": [], "amenities": []})
BRANDS = _HOTELS.get("brands", [])
AMENITIES = _HOTELS.get("amenities", [])


def _make_hotels(destination: str, travel_type: str, guests: int):
    rng = seeded_rng("hotels", destination, travel_type)
    code = city_code(destination)
    results = []
    for i, brand in enumerate(rng.sample(BRANDS, k=min(5, len(BRANDS)))):
        stars = brand["stars"]
        base = 40 + stars * 35 + len(destination) * 3
        price = round((base + i * 12) * (0.9 + rng.random() * 0.6), 2)
        match = 0.6 + (0.4 if brand["style"] == travel_type else rng.random() * 0.3)
        results.append({
            "hotel_id": f"{code}-H{200 + i}",
            "name": f"{brand['name']} {destination}",
            "style": brand["style"],
            "stars": stars,
            "rating": round(3.5 + rng.random() * 1.5, 1),
            "price": price,
            "currency": "USD",
            "per": "night",
            "guests": guests,
            "amenities": rng.sample(AMENITIES, k=min(4, len(AMENITIES))),
            "match_score": round(min(match, 0.99), 2),
            "neighborhood": rng.choice(["City Center", "Old Town", "Beachfront", "Business District", "Riverside"]),
        })
    return sorted(results, key=lambda h: (-h["match_score"], h["price"]))


@mcp.tool()
def search_hotels(
    destination: str,
    checkin: str | None = None,
    checkout: str | None = None,
    guests: int = 1,
    travel_type: str = "leisure",
    max_price_per_night: float | None = None,
) -> list:
    """Search hotels at a destination, ranked by fit to the travel type.

    Args:
        destination: City to stay in.
        checkin: Check-in date YYYY-MM-DD (optional).
        checkout: Check-out date YYYY-MM-DD (optional).
        guests: Number of guests.
        travel_type: explorer | leisure | relaxing | adventure | business | family.
        max_price_per_night: Optional per-night price cap (USD).
    """
    hotels = _make_hotels(destination, travel_type, max(1, guests))
    if max_price_per_night:
        hotels = [h for h in hotels if h["price"] <= max_price_per_night] or hotels
    return hotels


@mcp.tool()
def get_hotel_details(hotel_id: str) -> dict:
    """Get room types and policies for a specific hotel id."""
    rng = seeded_rng("hotel_details", hotel_id)
    if not hotel_id:
        return {"error": "hotel_id required"}
    return {
        "hotel_id": hotel_id,
        "rooms": [
            {"type": "Standard", "price": 40 + rng.randint(0, 40)},
            {"type": "Deluxe", "price": 90 + rng.randint(0, 60)},
            {"type": "Suite", "price": 180 + rng.randint(0, 120)},
        ],
        "free_cancellation": rng.choice([True, False]),
        "checkin_time": "14:00",
        "checkout_time": "11:00",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
