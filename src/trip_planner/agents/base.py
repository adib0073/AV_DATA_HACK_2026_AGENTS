"""Shared specialist-agent machinery.

A specialist agent makes ONE instrumented tool-selection decision (the LLM span
where Layer-2 Action metrics live), executes the chosen MCP tool(s), then writes
a short recommendation. Keeping it to a single decision (instead of an open loop)
makes the trace tree clean and the component metrics unambiguous - exactly what
the talk demonstrates.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from ..config import get_settings
from ..llm import get_chat_model
from ..mcp_client import get_tools_for
from ..metrics import action_metrics
from ..observability import (
    extract_usage,
    get_current_golden,
    observe,
    record_llm_usage,
    update_current_span,
)

_S = get_settings()

# Built once. DeepEval only *runs* these during evals_iterator/evaluate, so
# attaching them permanently is safe for the live chat path (they stay dormant).
_ACTION_METRICS = action_metrics()

try:
    from deepeval.test_case import ToolCall  # type: ignore
except Exception:  # pragma: no cover
    ToolCall = None  # type: ignore


def _to_toolcalls(calls: list[dict]) -> list:
    if ToolCall is None:
        return []
    out = []
    for c in calls:
        try:
            out.append(ToolCall(name=c.get("name", ""), input=c.get("args", {})))
        except Exception:
            out.append(ToolCall(name=c.get("name", "")))
    return out


@observe(
    type="llm",
    model=_S.openai_model,
    cost_per_input_token=_S.cost_per_input_token,
    cost_per_output_token=_S.cost_per_output_token,
    metrics=_ACTION_METRICS,
)
async def _decide_tool(messages: list, model_with_tools, expected_tool_names: list[str],
                       force_wrong_tool: bool = False):
    """The tool-selection LLM span.

    Layer 2 (Action) metrics - ToolCorrectness & ArgumentCorrectness - are
    attached here. We set the span's test case (input / output / tools_called /
    expected_tools) at runtime so those metrics have what they need.

    When ``force_wrong_tool`` is set, we apply the seeded regression *here* so the
    span's ``tools_called`` reflects the wrong tool. That is what makes Layer 2
    actually pinpoint the bug on this LLM span in the live trace (Beat 2), instead
    of the regression only showing up at execution time.
    """
    response = await model_with_tools.ainvoke(messages)

    in_tok, out_tok = extract_usage(response)
    record_llm_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_per_input_token=_S.cost_per_input_token,
        cost_per_output_token=_S.cost_per_output_token,
    )

    tool_calls = list(response.tool_calls or [])
    if force_wrong_tool:
        tool_calls = _apply_regression(tool_calls)

    last_user = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
    update_current_span(
        input=str(last_user),
        output=response.content or json.dumps([tc["name"] for tc in tool_calls]),
        tools_called=_to_toolcalls(tool_calls),
        expected_tools=_to_toolcalls([{"name": n} for n in expected_tool_names]),
    )
    return response, tool_calls


@observe(type="llm", model=_S.openai_model,
         cost_per_input_token=_S.cost_per_input_token,
         cost_per_output_token=_S.cost_per_output_token)
async def _summarize(system: str, context: str, tool_results: list[dict]) -> str:
    model = get_chat_model(temperature=0.3)
    msg = (
        f"{context}\n\nTool results (JSON):\n{json.dumps(tool_results, indent=2)}\n\n"
        "Write a concise recommendation for the user based on these results."
    )
    resp = await model.ainvoke([SystemMessage(content=system), HumanMessage(content=msg)])
    in_tok, out_tok = extract_usage(resp)
    record_llm_usage(
        input_tokens=in_tok, output_tokens=out_tok,
        cost_per_input_token=_S.cost_per_input_token,
        cost_per_output_token=_S.cost_per_output_token,
    )
    update_current_span(input=msg, output=resp.content)
    return resp.content


def _make_tool_span(tool):
    @observe(type="tool", name=tool.name, description=(tool.description or "")[:200])
    async def _run(args: dict) -> Any:
        from .. import usage

        usage.add_tool(tool.name)
        result = await tool.ainvoke(args)
        update_current_span(input=json.dumps(args), output=str(result)[:4000])
        return result

    return _run


def _apply_regression(tool_calls: list[dict]) -> list[dict]:
    """Seeded demo bug: the agent picks the WRONG tool.

    Instead of `search_flights`, it calls `get_flight_details` on an unknown id.
    Layer 1 (TaskCompletion) sees the trip degrade; Layer 2 (ToolCorrectness on
    this LLM span) pinpoints *why*: wrong tool selected. The bug is gated to a
    single golden (see nodes.flight_node) so exactly one eval case fails - then
    set INJECT_REGRESSION=false to "ship the fix" and watch the eval go green.
    """
    cid = tool_calls[0].get("id", "regression") if tool_calls else "regression"
    return [{"name": "get_flight_details", "args": {"flight_id": "UNKNOWN"}, "id": cid}]


async def run_specialist(
    *,
    domain: str,
    system: str,
    context: str,
    expected_tools: list[str],
    force_wrong_tool: bool = False,
    summarize: bool = True,
) -> dict:
    """Run one specialist agent end to end and return its results.

    Set ``summarize=False`` to skip the final recommendation LLM call - handy for
    component-level / shadow evals that only care about the tool *decision* (the
    Layer-2 Action surface) and want to stay fast and cheap.
    """
    tools = await get_tools_for(domain)
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = get_chat_model().bind_tools(tools)

    messages = [SystemMessage(content=system), HumanMessage(content=context)]
    _ai, raw_calls = await _decide_tool(
        messages, model_with_tools, expected_tools, force_wrong_tool=force_wrong_tool
    )

    tool_results: list[dict] = []
    tool_trace: list[dict] = []
    for call in raw_calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            tool_results.append({"tool": call["name"], "error": "tool not available"})
            continue
        runner = _make_tool_span(tool)
        result = await runner(call.get("args", {}))
        parsed = _coerce_mcp_content(result)
        tool_results.append({"tool": call["name"], "result": parsed})
        tool_trace.append({"tool": call["name"], "args": call.get("args", {})})

    summary = await _summarize(system, context, tool_results) if summarize else ""
    return {
        "tool_calls": [c["name"] for c in raw_calls],
        "tool_args": [c.get("args", {}) for c in raw_calls],
        "tool_results": tool_results,
        "tool_trace": tool_trace,
        "summary": summary,
    }


def _safe_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _coerce_mcp_content(value: Any) -> Any:
    """Normalize an MCP tool result into plain Python objects.

    langchain-mcp-adapters returns tool output as MCP content blocks, e.g.
    ``[{"type": "text", "text": "{...json...}"}, ...]`` (one block per result),
    or sometimes a bare string. We unwrap the ``text`` payloads and JSON-decode
    them so downstream selection logic sees real dicts (with ``price``, ``name``,
    ``airline`` ...) instead of opaque ``{"type": "text"}`` wrappers.
    """
    items = value if isinstance(value, list) else [value]
    out: list[Any] = []
    for item in items:
        text: str | None = None
        if isinstance(item, dict):
            if "text" in item:
                text = item.get("text")
            else:
                out.append(item)
                continue
        elif isinstance(item, str):
            text = item
        else:
            text = getattr(item, "text", None)
            if text is None:
                out.append(item)
                continue

        decoded = _safe_json(text)
        if isinstance(decoded, list):
            out.extend(decoded)
        else:
            out.append(decoded)

    # A single non-list result (e.g. a booking confirmation) reads better as the
    # object itself rather than a one-element list.
    if not isinstance(value, list) and len(out) == 1:
        return out[0]
    return out
