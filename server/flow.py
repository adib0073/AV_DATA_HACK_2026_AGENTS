"""Build a call-flow view (React Flow node/edge graph + per-call list) from one run.

This powers the Eval Studio "Flow & Traces" panel, which shows Layer 3
(in-code agent/tool spans) and Layer 4 (the Obot MCP gateway) in a single view.

The topology is fixed by the graph (`src/trip_planner/graph.py`) and the
tool->server map (`src/trip_planner/mcp_client.py`); we mirror it here and then
*highlight* whichever agents / servers / tools actually fired in a given run.
"""

from __future__ import annotations

# Mirror of mcp_client.TOOLS_BY_DOMAIN, plus display metadata. Kept local so the
# server can describe the topology without importing the agent stack.
DOMAINS = [
    {
        "domain": "flights",
        "agent": "flight",
        "agent_label": "Flight agent",
        "server_id": "FS",
        "server_label": "Flights MCP",
        "tools": ["search_flights", "get_flight_details"],
    },
    {
        "domain": "hotels",
        "agent": "hotel",
        "agent_label": "Hotel agent",
        "server_id": "HS",
        "server_label": "Hotels MCP",
        "tools": ["search_hotels", "get_hotel_details"],
    },
    {
        "domain": "activities",
        "agent": "itinerary",
        "agent_label": "Itinerary agent",
        "server_id": "AS",
        "server_label": "Activities MCP",
        "tools": ["search_activities", "get_destination_overview"],
    },
    {
        "domain": "booking",
        "agent": "booking",
        "agent_label": "Booking agent",
        "server_id": "BS",
        "server_label": "Booking MCP",
        "tools": ["book_flight", "book_hotel", "get_booking_status"],
    },
]

_TOOL_INFO: dict[str, dict] = {
    t: {**d, "tool": t} for d in DOMAINS for t in d["tools"]
}

_AGENT_NODE = {d["domain"]: f"AG_{d['agent']}" for d in DOMAINS}


def _tool_node(tool: str) -> str:
    return f"T_{tool}"


def server_for_tool(name: str) -> str:
    info = _TOOL_INFO.get(name)
    return info["server_label"] if info else "unknown"


def build_graph_view(tool_trace: list[dict], *, use_gateway: bool, ran: bool = True) -> dict:
    """Structured nodes/edges for the React Flow diagram.

    Columns: user · orchestrator · agents · [gateway] · MCP servers · tools.
    Whatever fired in this run is flagged so the UI can light up the live path.
    """
    fired_tools = {t.get("tool", "") for t in (tool_trace or [])} if ran else set()
    fired_servers = {_TOOL_INFO[t]["server_id"] for t in fired_tools if t in _TOOL_INFO}
    fired_domains = {_TOOL_INFO[t]["domain"] for t in fired_tools if t in _TOOL_INFO}
    any_fired = bool(fired_tools)

    server_col = 4 if use_gateway else 3
    tool_col = server_col + 1

    nodes: list[dict] = []
    edges: list[dict] = []

    def node(nid, label, kind, col, order, fired, sublabel=""):
        nodes.append({
            "id": nid, "label": label, "kind": kind, "col": col,
            "order": order, "fired": bool(fired), "sublabel": sublabel,
        })

    def edge(src, dst, fired):
        edges.append({"id": f"{src}->{dst}", "source": src, "target": dst, "fired": bool(fired)})

    # Column 0-1: user + orchestrator (Layer 3 traced spans)
    node("USER", "User request", "user", 0, 0, any_fired)
    node("ORC", "trip_planner", "orchestrator", 1, 0, any_fired, "root span")
    node("PLN", "Planner", "orchestrator", 1, 1, any_fired)
    node("SUP", "Supervisor", "orchestrator", 1, 2, any_fired, "router")
    edge("USER", "ORC", any_fired)
    edge("ORC", "PLN", any_fired)
    edge("PLN", "SUP", any_fired)

    # Column 2: specialist agents (Layer 3 LLM tool-decision spans)
    for i, d in enumerate(DOMAINS):
        an = _AGENT_NODE[d["domain"]]
        fired = d["domain"] in fired_domains
        node(an, d["agent_label"], "agent", 2, i, fired)
        edge("SUP", an, fired)

    # Optional gateway column (Layer 4)
    if use_gateway:
        node("GW", "Obot MCP Gateway", "gateway", 3, 0, any_fired, "audit · tokens · cost")
        for d in DOMAINS:
            edge(_AGENT_NODE[d["domain"]], "GW", d["domain"] in fired_domains)

    # MCP servers + tools (context layer)
    for i, d in enumerate(DOMAINS):
        sid = d["server_id"]
        s_fired = sid in fired_servers
        node(sid, d["server_label"], "server", server_col, i, s_fired)
        src = "GW" if use_gateway else _AGENT_NODE[d["domain"]]
        edge(src, sid, s_fired)
        for j, t in enumerate(d["tools"]):
            tid = _tool_node(t)
            t_fired = t in fired_tools
            count = sum(1 for x in (tool_trace or []) if x.get("tool") == t) if ran else 0
            node(tid, t, "tool", tool_col, i * 3 + j, t_fired,
                 f"×{count}" if count else "")
            edge(sid, tid, t_fired)

    return {"nodes": nodes, "edges": edges, "use_gateway": use_gateway, "ran": ran}


def describe_calls(tool_trace: list[dict]) -> list[dict]:
    """Flatten a run's tool_trace into per-call rows: which tool, on which MCP
    server, driven by which agent (the Layer-4 'calls through the gateway' view)."""
    calls: list[dict] = []
    for t in tool_trace or []:
        name = t.get("tool", "")
        info = _TOOL_INFO.get(name)
        args = t.get("args", {})
        calls.append({
            "tool": name,
            "server": info["server_label"] if info else "unknown",
            "agent": info["agent_label"] if info else "?",
            "args": args,
        })
    return calls


def build_flow(tool_trace: list[dict], *, use_gateway: bool, ran: bool = True) -> dict:
    return {
        "graph": build_graph_view(tool_trace, use_gateway=use_gateway, ran=ran),
        "calls": describe_calls(tool_trace),
        "use_gateway": use_gateway,
        "ran": ran,
    }
