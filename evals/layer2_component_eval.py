"""Layer 2 - Component-level evaluation (the Action surface), in isolation.

Layer 1 tells you *that* the Tokyo case failed. Layer 2 tells you *why*, and it
does it without re-running the whole agent. We test one component - the flight
agent's tool *decision* - directly:

  ToolCorrectnessMetric : deterministic. Did it call `search_flights`? (no judge)

Two views:

  A. Dataset-driven sweep - run the flight decision for every golden destination
     and score each. With INJECT_REGRESSION=true, exactly Tokyo breaks; the rest
     are green. This is "component testing at dataset scale".

  B. Isolated contrast - a healthy decision vs the buggy decision the seeded
     regression produces, scored side by side. Fast, deterministic, repeatable -
     the punchy "here is the bug" moment.

Usage:
    python evals/layer2_component_eval.py
    python evals/layer2_component_eval.py --limit 6
    python evals/layer2_component_eval.py --regression on
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of destinations swept (Tokyo always kept)")
    ap.add_argument("--regression", choices=["on", "off"], default=None,
                    help="override INJECT_REGRESSION for this run")
    ap.add_argument("--json-out", default=None, help="write a structured JSON report here")
    args = ap.parse_args()

    if args.regression is not None:
        os.environ["INJECT_REGRESSION"] = "true" if args.regression == "on" else "false"

    from deepeval.metrics import ToolCorrectnessMetric
    from deepeval.test_case import LLMTestCase, ToolCall

    from _harness import (flight_decision, hr, info, mean, record_table,
                          select_goldens, write_report)
    from trip_planner.config import get_settings

    s = get_settings()
    EXPECTED = "search_flights"

    def score(called: list[str], call_args: list[dict] | None = None) -> tuple[float, bool]:
        metric = ToolCorrectnessMetric(threshold=0.9)
        tc = LLMTestCase(
            input="Find the best flights for the trip.",
            actual_output="(flight agent tool decision)",
            tools_called=[ToolCall(name=n, input=(call_args[i] if call_args and i < len(call_args) else {}))
                          for i, n in enumerate(called)] or [ToolCall(name="<none>")],
            expected_tools=[ToolCall(name=EXPECTED)],
        )
        metric.measure(tc)
        return metric.score, metric.score >= metric.threshold

    # ---- View A: dataset-driven component sweep -------------------------------
    hr("LAYER 2 - COMPONENT SWEEP (flight tool decision per destination)")
    info(f"agent={s.openai_model}   regression={'ON' if s.inject_regression else 'off'}   "
         f"gateway={'ON' if s.use_gateway else 'off'}   (ToolCorrectness is deterministic - no judge)\n")

    tables: list = []
    goldens = select_goldens(limit=args.limit)
    rows, passed, total = [], 0, 0
    tool_scores: list[float] = []
    for g in goldens:
        dest = (getattr(g, "additional_metadata", None) or {}).get("destination", "")
        if not dest or dest.lower() == "unspecified":
            continue  # ambiguous goldens aren't about flight-tool selection
        force = s.inject_regression and "tokyo" in dest.lower()
        decision = flight_decision(dest, force_wrong_tool=force)
        called = decision["tools_called"]
        sc, ok = score(called, decision["tool_args"])
        passed += int(ok)
        total += 1
        tool_scores.append(sc)
        rows.append({
            "Destination": dest,
            "Tool called": ", ".join(called) or "<none>",
            "Score": f"{sc:.2f}",
            "Status": "PASS" if ok else "FAIL",
        })

    record_table(
        tables,
        f"Flight-agent component  -  {passed}/{total} correct",
        rows,
        ["Destination", "Tool called", "Score", "Status"],
    )

    # ---- View B: isolated healthy-vs-buggy contrast --------------------------
    hr("LAYER 2 - ISOLATED CONTRAST (healthy vs seeded-regression decision)")
    healthy_score, healthy_ok = score(["search_flights"], [{"origin": "Mumbai", "destination": "Tokyo"}])
    buggy_score, buggy_ok = score(["get_flight_details"], [{"flight_id": "UNKNOWN"}])
    record_table(
        tables,
        "Same input, two implementations",
        [
            {"Implementation": "Healthy flight agent", "Tool called": "search_flights",
             "Score": f"{healthy_score:.2f}", "Verdict": "PASS" if healthy_ok else "FAIL"},
            {"Implementation": "Buggy flight agent", "Tool called": "get_flight_details",
             "Score": f"{buggy_score:.2f}", "Verdict": "FAIL" if not buggy_ok else "PASS"},
        ],
        ["Implementation", "Tool called", "Score", "Verdict"],
    )
    info("\nTakeaway: Layer 1 said *that* Tokyo failed; Layer 2 says *why* - the flight\n"
         "agent selected `get_flight_details` instead of `search_flights`.")

    if args.json_out:
        write_report(
            args.json_out,
            suite="layer2",
            meta={
                "title": "Layer 2 - Component-level eval",
                "model": s.openai_model, "judge": s.judge_model,
                "regression": s.inject_regression, "gateway": s.use_gateway,
            },
            tables=tables,
            stats={
                "passed": passed,
                "total": total,
                "success_rate": round(passed / total, 4) if total else None,
                "tool_correctness_avg": mean(tool_scores),
            },
        )


if __name__ == "__main__":
    main()
