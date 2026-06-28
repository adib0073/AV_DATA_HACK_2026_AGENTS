"""MCP tool loading via langchain-mcp-adapters.

Connects to the four mock MCP servers (or to the Obot gateway, depending on
config) and exposes LangChain-compatible tools to the agents. Tools are loaded
once and cached for the process lifetime.
"""

from __future__ import annotations

import asyncio

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import get_settings

# Which tool names belong to which specialist agent. Keeping this explicit makes
# the trace readable and lets each agent see only the tools it should use
# (preventing cross-capability "tool bleed").
TOOLS_BY_DOMAIN: dict[str, set[str]] = {
    "flights": {"search_flights", "get_flight_details"},
    "hotels": {"search_hotels", "get_hotel_details"},
    "activities": {"search_activities", "get_destination_overview"},
    "booking": {"book_flight", "book_hotel", "get_booking_status"},
}

_client: MultiServerMCPClient | None = None
_all_tools: list[BaseTool] | None = None
_lock = asyncio.Lock()


async def _ensure_loaded() -> list[BaseTool]:
    global _client, _all_tools
    async with _lock:
        if _all_tools is None:
            settings = get_settings()
            _client = MultiServerMCPClient(settings.mcp_connections())
            _all_tools = await _client.get_tools()
    return _all_tools


async def get_all_tools() -> list[BaseTool]:
    return await _ensure_loaded()


async def get_tools_for(domain: str) -> list[BaseTool]:
    """Return the subset of tools a given specialist agent is allowed to use."""
    wanted = TOOLS_BY_DOMAIN.get(domain, set())
    tools = await _ensure_loaded()
    scoped = [t for t in tools if t.name in wanted]
    if not scoped:
        # Fall back to all tools so a naming drift doesn't silently disable an
        # agent; the agent prompt still steers it to the right tool.
        return tools
    return scoped


async def reset() -> None:
    """Drop cached tools/client (useful when toggling gateway mode in a session)."""
    global _client, _all_tools
    async with _lock:
        _client = None
        _all_tools = None
