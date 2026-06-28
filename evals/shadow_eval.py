"""Shadow-mode evaluation - test a candidate build against the current one.

Shadow mode = run a *candidate* implementation on the same traffic the live
system sees, score it, and compare - but never serve its output to users. It's
how you gain confidence to promote a change *before* it reaches production.

Here we replay the golden destinations through two flight-agent implementations:

  * baseline   - the currently-deployed build (carries the Tokyo wrong-tool bug)
  * candidate  - the proposed fix (bug removed)

Both are scored with the deterministic ToolCorrectness metric and compared
per destination, so you can see exactly what the candidate FIXED and prove it
REGRESSED nothing. (In a real system the baseline would be live prod traffic and
the candidate a shadow deployment; the goldens stand in for that traffic here.)

Usage:
    python evals/shadow_eval.py
    python evals/shadow_eval.py --limit 8
"""

from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of destinations (Tokyo always kept)")
    ap.add_argument("--json-out", default=None, help="write a structured JSON report here")
    args = ap.parse_args()

    from deepeval.metrics import ToolCorrectnessMetric
    from deepeval.test_case import LLMTestCase, ToolCall

    from _harness import (flight_decision, hr, info, record_table, select_goldens,
                          write_report)
    from trip_planner.config import get_settings

    s = get_settings()
    EXPECTED = "search_flights"

    def ok(called: list[str]) -> bool:
        metric = ToolCorrectnessMetric(threshold=0.9)
        metric.measure(LLMTestCase(
            input="Find the best flights for the trip.",
            actual_output="(flight agent tool decision)",
            tools_called=[ToolCall(name=n) for n in called] or [ToolCall(name="<none>")],
            expected_tools=[ToolCall(name=EXPECTED)],
        ))
        return metric.score >= metric.threshold

    hr("SHADOW MODE - candidate (fix) vs baseline (current deployment)")
    info(f"agent={s.openai_model}   gateway={'ON' if s.use_gateway else 'off'}   "
         "baseline simulates the deployed Tokyo bug; candidate removes it\n")

    tables: list = []
    goldens = select_goldens(limit=args.limit)
    rows = []
    base_pass = cand_pass = total = fixed = regressed = 0
    for g in goldens:
        dest = (getattr(g, "additional_metadata", None) or {}).get("destination", "")
        if not dest or dest.lower() == "unspecified":
            continue
        is_trigger = "tokyo" in dest.lower()

        base = flight_decision(dest, force_wrong_tool=is_trigger)   # current deployment
        cand = flight_decision(dest, force_wrong_tool=False)        # proposed fix
        base_ok = ok(base["tools_called"])
        cand_ok = ok(cand["tools_called"])

        total += 1
        base_pass += int(base_ok)
        cand_pass += int(cand_ok)
        if not base_ok and cand_ok:
            verdict, fixed = "FIXED", fixed + 1
        elif base_ok and not cand_ok:
            verdict, regressed = "REGRESSED", regressed + 1
        else:
            verdict = "PASS" if base_ok else "FAIL"

        rows.append({
            "Destination": dest,
            "Baseline": ", ".join(base["tools_called"]) or "<none>",
            "Candidate": ", ".join(cand["tools_called"]) or "<none>",
            "Result": verdict,
        })

    record_table(
        tables,
        f"Shadow comparison  -  baseline {base_pass}/{total}  →  candidate {cand_pass}/{total}",
        rows,
        ["Destination", "Baseline", "Candidate", "Result"],
    )
    info(f"\nFixed: {fixed}   Regressed: {regressed}")
    if regressed == 0 and fixed > 0:
        verdict = "Candidate fixes the bug and regresses nothing → safe to promote."
    elif regressed:
        verdict = "Candidate REGRESSED at least one case → do NOT promote."
    else:
        verdict = "No behavioural difference detected between baseline and candidate."
    info(verdict)

    if args.json_out:
        write_report(
            args.json_out,
            suite="shadow",
            meta={
                "title": "Shadow mode - candidate vs baseline",
                "model": s.openai_model, "judge": s.judge_model,
                "gateway": s.use_gateway, "verdict": verdict,
            },
            tables=tables,
            stats={"baseline_pass": base_pass, "candidate_pass": cand_pass,
                   "total": total, "fixed": fixed, "regressed": regressed},
        )


if __name__ == "__main__":
    main()
