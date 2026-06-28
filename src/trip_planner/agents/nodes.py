"""Graph nodes: planner, supervisor router, and the four specialist workers."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_chat_model
from ..observability import (
    extract_usage,
    observe,
    record_llm_usage,
    update_current_span,
)
from ..config import get_settings
from ..prompts import (
    BOOKING_SYSTEM,
    FLIGHT_SYSTEM,
    HOTEL_SYSTEM,
    ITINERARY_SYSTEM,
    PLANNER_SYSTEM,
)
from ..state import TripRequest, TripState
from .base import run_specialist

_S = get_settings()

# The seeded regression is gated to this destination so exactly ONE golden
# fails when INJECT_REGRESSION=true (clean "one case failed" demo moment).
REGRESSION_TRIGGER = "tokyo"

# plan step -> worker node name
STEP_TO_NODE = {
    "search_flights": "flight",
    "search_hotels": "hotel",
    "build_itinerary": "itinerary",
    "book": "booking",
}
# worker node -> the "completed" marker it writes
NODE_TO_STEP = {v: k for k, v in STEP_TO_NODE.items()}


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return {}


# ----------------------------------------------------------------------------
# Planner (Reasoning component - "the brain")
# ----------------------------------------------------------------------------
@observe(type="agent", name="planner", available_tools=[])
async def planner_node(state: TripState) -> dict:
    model = get_chat_model(temperature=0.0)
    user_input = state["user_input"]
    resp = await model.ainvoke(
        [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=user_input)]
    )
    in_tok, out_tok = extract_usage(resp)
    record_llm_usage(
        input_tokens=in_tok, output_tokens=out_tok,
        cost_per_input_token=_S.cost_per_input_token,
        cost_per_output_token=_S.cost_per_output_token,
    )

    data = _extract_json(resp.content)
    try:
        request = TripRequest(**(data.get("request") or {}))
    except Exception:
        request = TripRequest(destination=data.get("request", {}).get("destination", ""))
    plan = [s for s in (data.get("plan") or []) if s in STEP_TO_NODE]
    if not plan:
        plan = ["search_flights", "search_hotels", "build_itinerary"]

    update_current_span(
        input=user_input,
        output=json.dumps({"request": request.model_dump(), "plan": plan}),
        metadata={"plan": plan},
    )
    return {"request": request.model_dump(), "plan": plan, "completed": []}


# ----------------------------------------------------------------------------
# Supervisor (router)
# ----------------------------------------------------------------------------
def supervisor_node(state: TripState) -> dict:
    plan = state.get("plan", [])
    completed = set(state.get("completed", []))
    for step in plan:
        if step not in completed:
            return {"next": STEP_TO_NODE[step]}
    return {"next": "finalize"}


def route(state: TripState) -> str:
    return state.get("next", "finalize")


# ----------------------------------------------------------------------------
# Specialist workers
# ----------------------------------------------------------------------------
def _request(state: TripState) -> TripRequest:
    return TripRequest(**state.get("request", {}))


def _first_list(tool_results: list[dict]) -> list[dict]:
    for tr in tool_results:
        res = tr.get("result")
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and isinstance(res.get("results"), list):
            return res["results"]
    return []


def _cheapest(options: list[dict], budget: float | None) -> dict | None:
    if not options:
        return None
    priced = [o for o in options if isinstance(o.get("price"), (int, float))]
    pool = priced or options
    if budget:
        within = [o for o in priced if o["price"] <= budget]
        if within:
            pool = within
    return min(pool, key=lambda o: o.get("price", 1e12))


@observe(type="agent", name="flight_agent", available_tools=["search_flights", "get_flight_details"])
async def flight_node(state: TripState) -> dict:
    req = _request(state)
    ctx = (
        f"Find flights from {req.origin or 'the traveler origin'} to {req.destination} "
        f"for {req.travelers} traveler(s). Dates: {req.start_date} to {req.end_date} "
        f"(duration {req.duration_days} days). Travel type: {req.travel_type}. "
        f"Flight budget: {req.budget.flights or req.budget.total} {req.budget.currency}."
    )
    force_bug = _S.inject_regression and REGRESSION_TRIGGER in (req.destination or "").lower()
    result = await run_specialist(
        domain="flights", system=FLIGHT_SYSTEM, context=ctx,
        expected_tools=["search_flights"], force_wrong_tool=force_bug,
    )
    options = _first_list(result["tool_results"])
    selected = _cheapest(options, req.budget.flights or req.budget.total)
    update_current_span(input=ctx, output=result["summary"])
    return {
        "flight_options": options,
        "selected_flight": selected,
        "completed": ["search_flights"],
        "tool_trace": result["tool_trace"],
    }


@observe(type="agent", name="hotel_agent", available_tools=["search_hotels", "get_hotel_details"])
async def hotel_node(state: TripState) -> dict:
    req = _request(state)
    ctx = (
        f"Find hotels in {req.destination} for {req.travelers} guest(s), "
        f"{req.duration_days or ''} nights, travel type {req.travel_type}. "
        f"Hotel budget: {req.budget.hotels or req.budget.total} {req.budget.currency}."
    )
    result = await run_specialist(
        domain="hotels", system=HOTEL_SYSTEM, context=ctx,
        expected_tools=["search_hotels"],
    )
    options = _first_list(result["tool_results"])
    selected = _cheapest(options, req.budget.hotels or req.budget.total)
    update_current_span(input=ctx, output=result["summary"])
    return {
        "hotel_options": options,
        "selected_hotel": selected,
        "completed": ["search_hotels"],
        "tool_trace": result["tool_trace"],
    }


@observe(type="agent", name="itinerary_agent", available_tools=["search_activities", "get_destination_overview"])
async def itinerary_node(state: TripState) -> dict:
    req = _request(state)
    ctx = (
        f"Build a {req.duration_days or 3}-day itinerary for {req.destination}, "
        f"travel type {req.travel_type}, {req.travelers} traveler(s). "
        f"Selected hotel: {(state.get('selected_hotel') or {}).get('name', 'n/a')}."
    )
    result = await run_specialist(
        domain="activities", system=ITINERARY_SYSTEM, context=ctx,
        expected_tools=["search_activities"],
    )
    itinerary = {
        "summary": result["summary"],
        "activities": _first_list(result["tool_results"]),
    }
    update_current_span(input=ctx, output=result["summary"])
    return {
        "itinerary": itinerary,
        "completed": ["build_itinerary"],
        "tool_trace": result["tool_trace"],
    }


@observe(type="agent", name="booking_agent", available_tools=["book_flight", "book_hotel", "get_booking_status"])
async def booking_node(state: TripState) -> dict:
    req = _request(state)
    flight = state.get("selected_flight") or {}
    hotel = state.get("selected_hotel") or {}
    ctx = (
        f"Book the trip to {req.destination}. "
        f"Selected flight: {json.dumps(flight)}. Selected hotel: {json.dumps(hotel)}. "
        "Call book_flight first, then book_hotel."
    )
    result = await run_specialist(
        domain="booking", system=BOOKING_SYSTEM, context=ctx,
        expected_tools=["book_flight", "book_hotel"],
    )
    update_current_span(input=ctx, output=result["summary"])
    return {
        "booking": {"summary": result["summary"], "details": result["tool_results"]},
        "completed": ["book"],
        "tool_trace": result["tool_trace"],
    }


# ----------------------------------------------------------------------------
# Finalize
# ----------------------------------------------------------------------------
@observe(type="agent", name="finalize")
async def finalize_node(state: TripState) -> dict:
    req = _request(state)
    completed = set(state.get("completed", []))
    parts: list[str] = [f"Trip plan for {req.destination} ({req.travel_type})"]
    if state.get("selected_flight"):
        f = state["selected_flight"]
        parts.append(f"- Flight: {f.get('airline', '')} {f.get('flight_id', '')} "
                     f"@ {f.get('price', '?')} {req.budget.currency}")
    elif "search_flights" in completed:
        # Flights were attempted but none could be selected (e.g. the agent used
        # the wrong tool and got no results). Surface it honestly - this trip is
        # not actually plannable without flights, which is what TaskCompletion
        # should (and does) penalize.
        parts.append("- Flight: NONE FOUND - no flights were retrieved, so this "
                     "trip cannot be completed as requested.")
    if state.get("selected_hotel"):
        h = state["selected_hotel"]
        parts.append(f"- Hotel: {h.get('name', '')} @ {h.get('price', '?')} "
                     f"{req.budget.currency}/night")
    elif "search_hotels" in completed:
        parts.append("- Hotel: NONE FOUND - no hotels were retrieved for this trip.")
    if state.get("itinerary"):
        parts.append("- Itinerary:\n" + str(state["itinerary"].get("summary", "")))
    if state.get("booking"):
        parts.append("- Booking:\n" + str(state["booking"].get("summary", "")))
    if "book" not in set(state.get("completed", [])):
        parts.append("\nReply 'book it' to confirm and I'll make the reservations.")
    final = "\n".join(parts)
    update_current_span(input=state["user_input"], output=final)
    return {"final_response": final}
