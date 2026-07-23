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

    from _harness import (by_input, confident_link, fmt_score, hr, info, mean,
                          pctl, plan_adherence, plan_quality, record_table,
                          run_e2e, select_goldens, write_report)
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

    result, latencies, states = run_e2e(goldens, metrics, print_results=False,
                                        identifier="layer1-e2e")
    if result is None:
        info("Evaluation did not produce results.")
        return

    flat = by_input(result.test_results)
    show_step = any(type(m).__name__ == "StepEfficiencyMetric" for m in metrics)

    columns = ["Destination", "Task Completion", "Plan Quality", "Plan Adherence"]
    if show_step:
        columns.append("Step Efficiency")
    columns += ["Latency (s)", "Status"]

    rows, passed = [], 0
    task_scores, pq_scores, pa_scores, lat_ok = [], [], [], []
    for i, g in enumerate(goldens):
        m = flat.get(g.input, {})
        task = m.get("Task Completion")
        step = m.get("Step Efficiency")
        present = [x for x in (task, step if show_step else None) if x is not None]
        ok = bool(present) and all(x.success for x in present)
        passed += int(ok)
        dest = (getattr(g, "additional_metadata", None) or {}).get("destination", "?")
        lat = latencies[i] if i < len(latencies) else None
        st = states[i] if i < len(states) else None
        pq = plan_quality(st)
        pa = plan_adherence(st)

        task_scores.append(task.score if task and task.score is not None else None)
        pq_scores.append(pq)
        pa_scores.append(pa)
        lat_ok.append(lat)

        row = {
            "Destination": dest,
            "Task Completion": fmt_score(task),
            "Plan Quality": f"{pq:.2f}" if pq is not None else "-",
            "Plan Adherence": f"{pa:.2f}" if pa is not None else "-",
            "Status": "PASS" if ok else "FAIL",
            "Latency (s)": f"{lat:.1f}" if lat is not None else "-",
        }
        if show_step:
            row["Step Efficiency"] = fmt_score(step)
        rows.append(row)

    total = len(goldens)
    stats = {
        "passed": passed,
        "total": total,
        "success_rate": round(passed / total, 4) if total else None,
        "task_completion_avg": mean(task_scores),
        "plan_quality_avg": mean(pq_scores),
        "plan_adherence_avg": mean(pa_scores),
        "latency_avg_s": mean(lat_ok),
        "latency_p95_s": pctl(lat_ok, 0.95),
    }

    tables: list = []
    title = f"Layer 1 results  -  {passed}/{total} passed"
    record_table(tables, title, rows, columns)

    # A compact KPI roll-up so the framework metrics are legible in the console too.
    def _pct(x):
        return f"{x * 100:.0f}%" if x is not None else "-"

    def _sc(x):
        return f"{x:.2f}" if x is not None else "-"

    record_table(
        tables,
        "Aggregate KPIs (this run)",
        [
            {"KPI": "Task Success Rate", "Value": _pct(stats["success_rate"]), "Layer": "1 - E2E"},
            {"KPI": "Task Completion (avg score)", "Value": _sc(stats["task_completion_avg"]), "Layer": "1 - E2E"},
            {"KPI": "Task Completion Latency (avg)",
             "Value": f"{stats['latency_avg_s']:.1f}s" if stats["latency_avg_s"] is not None else "-",
             "Layer": "1 - E2E"},
            {"KPI": "Plan Quality (avg)", "Value": _sc(stats["plan_quality_avg"]), "Layer": "2 - Reasoning"},
            {"KPI": "Plan Adherence (avg)", "Value": _sc(stats["plan_adherence_avg"]), "Layer": "2 - Reasoning"},
        ],
        ["KPI", "Value", "Layer"],
    )
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
            stats=stats,
            confident_link=getattr(result, "confident_link", None),
        )


if __name__ == "__main__":
    main()
