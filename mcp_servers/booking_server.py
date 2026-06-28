"""Mock Booking MCP server (FastMCP, streamable-http on :8004).

Tools: book_flight, book_hotel, get_booking_status.
Bookings are kept in-process memory (reset on restart).
Run:  python mcp_servers/booking_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from _common import mcp_host, seeded_rng

mcp = FastMCP("Booking", host=mcp_host(), port=8004)

_BOOKINGS: dict[str, dict] = {}


def _ref(kind: str, ident: str) -> str:
    rng = seeded_rng("ref", kind, ident, len(_BOOKINGS))
    return f"{kind[:2].upper()}-{rng.randint(100000, 999999)}"


@mcp.tool()
def book_flight(flight_id: str, passenger_name: str = "Guest", travelers: int = 1) -> dict:
    """Reserve a flight. Returns a confirmation reference.

    Args:
        flight_id: The flight id to book (from search_flights).
        passenger_name: Lead passenger name.
        travelers: Number of seats to reserve.
    """
    if not flight_id:
        return {"status": "error", "message": "flight_id is required"}
    ref = _ref("flight", flight_id)
    record = {
        "reference": ref, "type": "flight", "flight_id": flight_id,
        "passenger_name": passenger_name, "travelers": travelers,
        "status": "CONFIRMED",
    }
    _BOOKINGS[ref] = record
    return record


@mcp.tool()
def book_hotel(hotel_id: str, guest_name: str = "Guest", nights: int = 1, guests: int = 1) -> dict:
    """Reserve a hotel. Returns a confirmation reference.

    Args:
        hotel_id: The hotel id to book (from search_hotels).
        guest_name: Lead guest name.
        nights: Number of nights.
        guests: Number of guests.
    """
    if not hotel_id:
        return {"status": "error", "message": "hotel_id is required"}
    ref = _ref("hotel", hotel_id)
    record = {
        "reference": ref, "type": "hotel", "hotel_id": hotel_id,
        "guest_name": guest_name, "nights": nights, "guests": guests,
        "status": "CONFIRMED",
    }
    _BOOKINGS[ref] = record
    return record


@mcp.tool()
def get_booking_status(reference: str) -> dict:
    """Look up a booking by its confirmation reference."""
    return _BOOKINGS.get(reference, {"reference": reference, "status": "NOT_FOUND"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
