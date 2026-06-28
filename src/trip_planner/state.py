"""Typed state for the trip-planner graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

TravelType = Literal["explorer", "leisure", "relaxing", "adventure", "business", "family"]


class BudgetBreakdown(BaseModel):
    total: float | None = None
    flights: float | None = None
    hotels: float | None = None
    local_transport: float | None = None
    misc: float | None = None
    currency: str = "USD"


class TripRequest(BaseModel):
    """Structured form of the user's request, produced by the planner."""

    destination: str = ""
    origin: str | None = None
    start_date: str | None = None          # ISO YYYY-MM-DD
    end_date: str | None = None
    duration_days: int | None = None
    travelers: int = 1
    travel_type: TravelType = "leisure"
    budget: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    notes: str | None = None


class TripState(TypedDict, total=False):
    """Shared state threaded through the LangGraph supervisor + workers."""

    user_input: str
    request: dict                       # serialized TripRequest
    plan: list[str]                     # supervisor's ordered plan (for Plan* metrics)
    completed: Annotated[list[str], operator.add]  # steps actually executed

    flight_options: list[dict]
    selected_flight: dict | None
    hotel_options: list[dict]
    selected_hotel: dict | None
    itinerary: dict | None
    booking: dict | None

    # Router decision: which worker runs next (or "finish").
    next: str
    # Aggregated tool-call record (name + args) for trace/eval inspection.
    tool_trace: Annotated[list[dict], operator.add]
    final_response: str
    error: str | None
