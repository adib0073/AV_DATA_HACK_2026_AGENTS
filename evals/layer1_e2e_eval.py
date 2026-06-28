"""Layer 1 - End-to-End evaluation over the golden dataset.

Runs the *whole* agent on every golden and scores each run's trace with the
Execution metrics:

  - TaskCompletionMetric  : did the agent accomplish the user's goal?
  - StepEfficiencyMetric  : did it do so without wasted / redundant steps?

The Layer-2 metrics attached to inner spans (ToolCorrectness on each tool
decision, PlanQuality / PlanAdherence on the root agent span) fire in the same
run, so the failing case also shows *where* it broke - but Layer 1's job is to
answer "did it pass?" across the dataset.

With INJECT_REGRESSION=true exactly one golden (Tokyo) fails; flip it off and the
whole board goes green.

Usage:
    python evals/layer1_e2e_eval.py                 # all goldens
    python evals/layer1_e2e_eval.py --limit 5       # quick subset (Tokyo kept)
    python evals/layer1_e2e_eval.py --regression on # force the seeded bug
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of goldens (the Tokyo trigger is always kept)")
    ap.add_argument("--regression", choices=["on", "off"], default=None,
                    help="override INJECT_REGRESSION for this run")
    ap.add_argument("--json-out", default=None, help="write a structured JSON report here")
    args = ap.parse_args()

    # Must happen before the agent graph (and its cached settings) is imported.
    if args.regression is not None:
        os.environ["INJECT_REGRESSION"] = "true" if args.regression == "on" else "false"

    from _harness import (by_input, confident_link, fmt_score, hr, info,
                          record_table, run_e2e, select_goldens, write_report)
    from trip_planner.config import get_settings
    from trip_planner.metrics import e2e_metrics

    s = get_settings()
    hr("LAYER 1 - END-TO-END EVALUATION (golden dataset)")
    info(f"agent={s.openai_model}   judge={s.judge_model}   "
         f"regression={'ON' if s.inject_regression else 'off'}   "
         f"gateway={'ON' if s.use_gateway else 'off'}")

    goldens = select_goldens(limit=args.limit)
    metrics = e2e_metrics()
    if not metrics:
        info("No Layer-1 metrics available in this deepeval version.")
        return
    info(f"goldens={len(goldens)}   metrics={[type(m).__name__ for m in metrics]}\n")

    result = run_e2e(goldens, metrics, print_results=False, identifier="layer1-e2e")
    if result is None:
        info("Evaluation did not produce results.")
        return

    flat = by_input(result.test_results)
    show_step = any(type(m).__name__ == "StepEfficiencyMetric" for m in metrics)
    columns = ["Destination", "Task Completion"]
    if show_step:
        columns.append("Step Efficiency")
    columns.append("Status")

    rows, passed = [], 0
    for g in goldens:
        m = flat.get(g.input, {})
        task = m.get("Task Completion")
        step = m.get("Step Efficiency")
        present = [x for x in (task, step if show_step else None) if x is not None]
        ok = bool(present) and all(x.success for x in present)
        passed += int(ok)
        dest = (getattr(g, "additional_metadata", None) or {}).get("destination", "?")
        row = {
            "Destination": dest,
            "Task Completion": fmt_score(task),
            "Status": "PASS" if ok else "FAIL",
        }
        if show_step:
            row["Step Efficiency"] = fmt_score(step)
        rows.append(row)

    tables: list = []
    title = f"Layer 1 results  -  {passed}/{len(goldens)} passed"
    record_table(tables, title, rows, columns)
    confident_link(result)
    info("\nLayer 1 tells you *that* a case failed. Open its trace (or run "
         "layer2_component_eval.py) to see *why*.")

    if args.json_out:
        write_report(
            args.json_out,
            suite="layer1",
            meta={
                "title": "Layer 1 - End-to-End golden eval",
                "model": s.openai_model, "judge": s.judge_model,
                "regression": s.inject_regression, "gateway": s.use_gateway,
            },
            tables=tables,
            stats={"passed": passed, "total": len(goldens)},
            confident_link=getattr(result, "confident_link", None),
        )


if __name__ == "__main__":
    main()
