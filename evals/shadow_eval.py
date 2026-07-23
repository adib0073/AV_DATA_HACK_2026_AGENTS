"""Shadow-mode A/B evaluation - is the candidate build *significantly* better?

Shadow mode = mirror the traffic the live system sees onto a *candidate* build,
score it, and compare against the current baseline - but never serve the
candidate's output to users. It's how you earn confidence to promote a change
*before* it reaches production.

The two "versions" here are two flight-agent builds, replayed on the golden
traffic:

  * Version B (baseline)  - the currently-deployed build; carries the Tokyo
                            wrong-tool regression.
  * Version A (candidate) - the proposed fix; bug removed.

The suite produces two things:

  1. Paired diff (deterministic, grounded)
     Both versions run on every golden destination once; ToolCorrectness scores
     each. Per destination we show what the candidate FIXED and prove it
     REGRESSED nothing.

  2. A/B significance test (the promote / hold decision)
     We treat the goldens as a sample of production traffic and simulate a
     shadow window of `--trials` mirrored requests per arm (each request is
     drawn from the golden traffic; a small `--noise` flake rate mimics
     real-world variance). Successes per arm feed a two-proportion z-test:
        - lift = p_A - p_B, with a 95% confidence interval
        - two-sided p-value
        - verdict: is A significantly better than B at alpha = 0.05?
     Raise --trials to watch sample size drive statistical power.

Usage:
    python evals/shadow_eval.py
    python evals/shadow_eval.py --trials 500 --noise 0.03 --seed 7
    python evals/shadow_eval.py --limit 8
"""

from __future__ import annotations

import argparse
import math
import random


def _phi(z: float) -> float:
    """Standard-normal CDF via the error function (no scipy dependency)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_proportion_ztest(a_succ: int, a_n: int, b_succ: int, b_n: int,
                         alpha: float = 0.05) -> dict:
    """Two-sided two-proportion z-test for 'is A better than B?'.

    Uses the pooled SE for the test statistic and the unpooled SE for the
    confidence interval on the difference (standard practice).
    """
    p_a = a_succ / a_n if a_n else 0.0
    p_b = b_succ / b_n if b_n else 0.0
    diff = p_a - p_b

    pooled = (a_succ + b_succ) / (a_n + b_n) if (a_n + b_n) else 0.0
    se_pool = (math.sqrt(pooled * (1 - pooled) * (1 / a_n + 1 / b_n))
               if a_n and b_n and 0.0 < pooled < 1.0 else 0.0)
    z = diff / se_pool if se_pool > 0 else 0.0
    p_value = 2.0 * (1.0 - _phi(abs(z)))

    se_diff = (math.sqrt(p_a * (1 - p_a) / a_n + p_b * (1 - p_b) / b_n)
               if a_n and b_n else 0.0)
    z_crit = 1.959963985  # two-sided 95%
    ci_low = diff - z_crit * se_diff
    ci_high = diff + z_crit * se_diff

    return {
        "p_a": p_a, "p_b": p_b, "diff": diff,
        "z": z, "p_value": p_value,
        "ci_low": ci_low, "ci_high": ci_high,
        "alpha": alpha,
        "significant": bool(p_value < alpha and diff > 0),
    }


def _simulate(outcomes: dict[str, bool], dests: list[str], trials: int,
              noise: float, rng: random.Random) -> int:
    """Draw `trials` mirrored requests from the golden traffic and count
    successes for one version, flipping each outcome with prob `noise`."""
    succ = 0
    for _ in range(trials):
        ok = outcomes[rng.choice(dests)]
        if noise > 0 and rng.random() < noise:
            ok = not ok
        succ += int(ok)
    return succ


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of destinations (Tokyo always kept)")
    ap.add_argument("--trials", type=int, default=300,
                    help="mirrored requests per arm in the simulated shadow window")
    ap.add_argument("--noise", type=float, default=0.03,
                    help="per-request flake rate (real-world variance), 0..1")
    ap.add_argument("--seed", type=int, default=7, help="RNG seed (reproducible demo)")
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

    hr("SHADOW MODE - A/B test: Version A (candidate fix) vs Version B (baseline)")
    info(f"agent={s.openai_model}   gateway={'ON' if s.use_gateway else 'off'}   "
         f"trials/arm={args.trials}   noise={args.noise}   seed={args.seed}\n"
         "Version B simulates the deployed Tokyo wrong-tool bug; Version A removes it.\n")

    # ---- Step 1: paired, deterministic per-destination diff -------------------
    tables: list = []
    goldens = select_goldens(limit=args.limit)
    rows = []
    outcomes_a: dict[str, bool] = {}
    outcomes_b: dict[str, bool] = {}
    a_pass = b_pass = total = fixed = regressed = 0
    for g in goldens:
        dest = (getattr(g, "additional_metadata", None) or {}).get("destination", "")
        if not dest or dest.lower() == "unspecified":
            continue
        is_trigger = "tokyo" in dest.lower()

        cand = flight_decision(dest, force_wrong_tool=False)        # Version A (fix)
        base = flight_decision(dest, force_wrong_tool=is_trigger)   # Version B (deployed)
        a_ok = ok(cand["tools_called"])
        b_ok = ok(base["tools_called"])
        outcomes_a[dest] = a_ok
        outcomes_b[dest] = b_ok

        total += 1
        a_pass += int(a_ok)
        b_pass += int(b_ok)
        if a_ok and not b_ok:
            verdict, fixed = "FIXED", fixed + 1
        elif b_ok and not a_ok:
            verdict, regressed = "REGRESSED", regressed + 1
        else:
            verdict = "PASS" if a_ok else "FAIL"

        rows.append({
            "Destination": dest,
            "Version B (baseline)": ", ".join(base["tools_called"]) or "<none>",
            "Version A (candidate)": ", ".join(cand["tools_called"]) or "<none>",
            "Result": verdict,
        })

    record_table(
        tables,
        f"Paired diff  -  baseline {b_pass}/{total}  ->  candidate {a_pass}/{total}",
        rows,
        ["Destination", "Version B (baseline)", "Version A (candidate)", "Result"],
    )

    # ---- Step 2: A/B significance test over a simulated shadow window ---------
    dests = list(outcomes_a.keys())
    stat: dict = {}
    if dests and args.trials > 0:
        rng = random.Random(args.seed)
        a_succ = _simulate(outcomes_a, dests, args.trials, args.noise, rng)
        b_succ = _simulate(outcomes_b, dests, args.trials, args.noise, rng)
        stat = two_proportion_ztest(a_succ, args.trials, b_succ, args.trials)
        stat["a_succ"], stat["b_succ"], stat["trials"] = a_succ, b_succ, args.trials

        hr("SHADOW MODE - A/B SIGNIFICANCE (two-proportion z-test)")
        record_table(
            tables,
            f"Simulated shadow window  -  {args.trials} mirrored requests / arm "
            f"(noise {args.noise:.0%})",
            [
                {"Version": "A - candidate (fix)", "Requests": str(args.trials),
                 "Successes": str(a_succ), "Success rate": f"{stat['p_a'] * 100:.1f}%"},
                {"Version": "B - baseline (deployed)", "Requests": str(args.trials),
                 "Successes": str(b_succ), "Success rate": f"{stat['p_b'] * 100:.1f}%"},
            ],
            ["Version", "Requests", "Successes", "Success rate"],
        )
        record_table(
            tables,
            "Hypothesis test  -  H0: rate_A = rate_B   (alpha = 0.05)",
            [
                {"Statistic": "Lift (A - B)",
                 "Value": f"{stat['diff'] * 100:+.1f} pp"},
                {"Statistic": "95% CI on lift",
                 "Value": f"[{stat['ci_low'] * 100:+.1f}, {stat['ci_high'] * 100:+.1f}] pp"},
                {"Statistic": "z-statistic", "Value": f"{stat['z']:.2f}"},
                {"Statistic": "p-value (two-sided)", "Value": f"{stat['p_value']:.4f}"},
                {"Statistic": "Significant at 0.05?",
                 "Value": "YES" if stat["significant"] else "no"},
            ],
            ["Statistic", "Value"],
        )

    # ---- Verdict --------------------------------------------------------------
    lift_pp = (stat.get("diff", 0.0)) * 100
    if regressed:
        verdict = (f"Version A REGRESSED {regressed} case(s) vs baseline -> do NOT promote.")
    elif stat.get("significant"):
        verdict = (f"Version A beats B by {lift_pp:+.1f} pp "
                   f"(95% CI [{stat['ci_low'] * 100:+.1f}, {stat['ci_high'] * 100:+.1f}] pp), "
                   f"p={stat['p_value']:.4f} < 0.05 - statistically significant. Safe to promote.")
    elif stat.get("diff", 0.0) > 0:
        verdict = (f"Version A is ahead by {lift_pp:+.1f} pp but p={stat.get('p_value', 1):.3f} "
                   f">= 0.05 - not statistically significant yet. Collect more shadow "
                   f"traffic (raise --trials) before promoting.")
    else:
        verdict = "No advantage detected for Version A over Version B."

    info(f"\nFixed: {fixed}   Regressed: {regressed}")
    info(verdict)

    if args.json_out:
        write_report(
            args.json_out,
            suite="shadow",
            meta={
                "title": "Shadow mode - A/B: candidate vs baseline",
                "model": s.openai_model, "judge": s.judge_model,
                "gateway": s.use_gateway, "verdict": verdict,
            },
            tables=tables,
            stats={
                "version_a_pass": a_pass, "version_b_pass": b_pass,
                "candidate_pass": a_pass, "baseline_pass": b_pass,  # back-compat
                "total": total, "fixed": fixed, "regressed": regressed,
                "trials": stat.get("trials"), "noise": args.noise,
                "a_rate": round(stat.get("p_a", 0.0), 4),
                "b_rate": round(stat.get("p_b", 0.0), 4),
                "lift": round(stat.get("diff", 0.0), 4),
                "ci_low": round(stat.get("ci_low", 0.0), 4),
                "ci_high": round(stat.get("ci_high", 0.0), 4),
                "p_value": round(stat.get("p_value", 1.0), 4),
                "z": round(stat.get("z", 0.0), 3),
                "significant": bool(stat.get("significant", False)),
            },
        )


if __name__ == "__main__":
    main()
