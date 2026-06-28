"""Travel-planner chatbot UI (Streamlit).

The agentic system (LangGraph + MCP) is the "example app"; the real subject of
the talk is the evaluation + observability around it. This UI gives a tangible
front end and a live token/cost panel.

Run:  streamlit run app/streamlit_app.py
(Make sure the MCP servers are running first: python mcp_servers/run_all.py)
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

import streamlit as st

# --- make `trip_planner` importable from src/ ---
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trip_planner import usage  # noqa: E402
from trip_planner.config import get_settings  # noqa: E402
from trip_planner.graph import plan_trip  # noqa: E402

st.set_page_config(page_title="Trip Planner Agent", page_icon="🧭", layout="wide")

settings = get_settings()


def _run(user_input: str) -> dict:
    return asyncio.run(plan_trip(user_input))


# ----------------------------- Sidebar --------------------------------------
with st.sidebar:
    st.title("🧭 Trip Planner")
    st.caption("Agentic demo · *Keeping Eyes on Your Agents*")

    st.subheader("Configuration")
    st.write(f"**Model:** `{settings.openai_model}`")
    st.write(f"**MCP mode:** {'Obot Gateway (Layer 4)' if settings.use_gateway else 'Direct'}")
    st.write(f"**AI gateway:** {'on' if settings.openai_base_url else 'off (direct OpenAI)'}")
    if settings.inject_regression:
        st.error("⚠ Seeded regression is ON (flight agent picks wrong tool)")
    else:
        st.success("✓ Regression off (fixed)")

    st.divider()
    st.subheader("💸 Token & cost (this session)")
    u = usage.snapshot()
    c1, c2 = st.columns(2)
    c1.metric("LLM calls", u.calls)
    c2.metric("Est. cost (USD)", f"${u.cost_usd:.4f}")
    c3, c4 = st.columns(2)
    c3.metric("Input tokens", f"{u.input_tokens:,}")
    c4.metric("Output tokens", f"{u.output_tokens:,}")
    if st.button("Reset usage"):
        usage.reset()
        st.rerun()

    st.divider()
    st.caption(
        "Token cost shown here is the local mirror of what DeepEval records on "
        "each LLM span (and what an AI gateway like Obot tracks in USD)."
    )


# ----------------------------- Main chat ------------------------------------
st.title("Plan your trip ✈️🏨🗺️")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi! Tell me about your trip — destination, dates or duration, "
                "number of travelers, budget, and the kind of trip you want "
                "(explorer, leisure, relaxing, adventure…).\n\n"
                "*Example:* \"Plan a 5-day relaxing trip to Bali for 2 from Mumbai "
                "in October, budget $2500 total.\""
            ),
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("details"):
            _render = msg["details"]
            with st.expander("Trip details"):
                st.json(_render)

prompt = st.chat_input("Describe your trip…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agents are planning your trip…"):
            try:
                result = _run(prompt)
                final = result["final_response"]
                state = result["state"]
            except Exception as exc:  # surface errors instead of a blank screen
                final = f"Something went wrong: `{exc}`\n\nIs the MCP server stack running?"
                state = {}
        st.markdown(final)
        details = {
            "selected_flight": state.get("selected_flight"),
            "selected_hotel": state.get("selected_hotel"),
            "itinerary": state.get("itinerary"),
            "booking": state.get("booking"),
            "plan": state.get("plan"),
        }
        with st.expander("Trip details"):
            st.json(details)

    st.session_state.messages.append(
        {"role": "assistant", "content": final, "details": details}
    )
    st.rerun()
