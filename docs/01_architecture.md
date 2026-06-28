# 01 · Architecture

## The agentic system (what you own)

A **LangGraph `StateGraph`** orchestrates a planner, a supervisor router, and
four specialist agents. Each box below is an `@observe`-instrumented span, so the
trace tree mirrors this diagram one-to-one.

```
START
  │
  ▼
planner            (LLM) parse request → structured TripRequest + ordered plan
  │
  ▼
supervisor  ◀──────────────────────────────────┐  picks next plan step
  │  route()                                    │
  ├─ "flight"   → flight_agent   ── search_flights ──┐
  ├─ "hotel"    → hotel_agent    ── search_hotels  ──┤
  ├─ "itinerary"→ itinerary_agent── search_activities┤  (MCP tools)
  ├─ "booking"  → booking_agent  ── book_flight/hotel┤
  └─ "finalize" → finalize ─────────────────────────┘
                     │
                     ▼
                    END
```

### Why a supervisor + specialists (not one mega-agent)?
- **Scoped tools per agent** (`mcp_client.TOOLS_BY_DOMAIN`) prevent "tool bleed"
  — the hotel agent can't accidentally call `book_flight`.
- **Clean component boundaries** = clean component-level evals (Layer 2).
- It mirrors how real teams split capabilities across agents/MCP servers.

### The specialist decision (where Layer 2 lives)
Each specialist makes **one** instrumented decision:

```
run_specialist(domain, system, context, expected_tools)
  └─ _decide_tool(...)      @observe(type="llm", metrics=[ToolCorrectness, ArgumentCorrectness])
        ├─ model.bind_tools(scoped_tools).ainvoke(messages)
        ├─ record token usage  → update_llm_span(...)        (cost on the span)
        └─ update_current_span(tools_called=…, expected_tools=…)
  └─ _make_tool_span(tool)   @observe(type="tool")           (the MCP call)
  └─ _summarize(...)         @observe(type="llm")            (recommendation)
```

## The MCP layer (tools)

Four **FastMCP** servers, fully offline & deterministic (seeded from inputs):

| Server | Port | Tools |
|---|---|---|
| flights | 8001 | `search_flights`, `get_flight_details` |
| hotels | 8002 | `search_hotels`, `get_hotel_details` |
| activities | 8003 | `search_activities`, `get_destination_overview` |
| booking | 8004 | `book_flight`, `book_hotel`, `get_booking_status` |

The agent reaches them through `langchain-mcp-adapters`
(`MultiServerMCPClient`), either **directly** (`USE_MCP_GATEWAY=false`) or via the
**Obot gateway** (`USE_MCP_GATEWAY=true`) — same agent code either way.

> Why mock servers? There's no reliable, offline, free open-source flight/hotel
> MCP that works wifi-independently on a conference stage. Mock servers keep the
> demo deterministic and let us seed a known regression. Swapping in a real MCP
> later is just a config change in `MultiServerMCPClient`.

## The observability layer

- **In-code (Layer 3):** `@observe` decorators produce a hierarchical trace
  (`agent → llm → tool`). Locally it prints; with `deepeval login` it streams to
  Confident AI.
- **Codeless (Layer 4):** the Obot gateway emits a span for every MCP call it
  proxies, even for servers the agent never instrumented. Both correlate into one
  trace tree.

## Configuration surface (`src/trip_planner/config.py`)

| Env | Effect |
|---|---|
| `OPENAI_MODEL` | agent model (default `gpt-4o-mini`) |
| `DEEPEVAL_JUDGE_MODEL` | LLM-as-judge model for metrics (default `gpt-4o`) |
| `OPENAI_BASE_URL` | route LLM through an AI gateway (Obot/LiteLLM/…) |
| `PRICE_INPUT_PER_M` / `PRICE_OUTPUT_PER_M` | per-token cost for span cost calc |
| `USE_MCP_GATEWAY` | direct MCP vs Obot gateway |
| `INJECT_REGRESSION` | seed the Tokyo tool-selection bug |
