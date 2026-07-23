"""DeepEval metric factories, mapped to the talk's 4-layer framework.

We isolate metric construction here for two reasons:

1. Version tolerance - DeepEval's agentic metrics (Plan*, StepEfficiency) are
   newer; if an installed version lacks one, we skip it with a clear warning
   instead of crashing the whole demo.
2. Single source of truth - both the agent's @observe spans and the eval
   scripts pull their metrics from the same place.

    Layer 1 (end-to-end / Execution) : TaskCompletionMetric, StepEfficiencyMetric
    Layer 2 (Reasoning)              : PlanQualityMetric, PlanAdherenceMetric
    Layer 2 (Action)                 : ToolCorrectnessMetric, ArgumentCorrectnessMetric
"""

from __future__ import annotations

import warnings
from typing import Any

from .config import get_settings


def _judge() -> str:
    return get_settings().judge_model


def _try(name: str, **kwargs: Any):
    """Instantiate a deepeval metric by class name, tolerating absence."""
    try:
        import deepeval.metrics as M  # noqa: N812

        cls = getattr(M, name)
    except Exception:
        warnings.warn(
            f"DeepEval metric '{name}' is unavailable in this version - skipping it. "
            "Upgrade deepeval to enable the full framework."
        )
        return None
    try:
        return cls(**kwargs)
    except TypeError:
        # Some metrics don't accept `model` (e.g. purely deterministic ones).
        kwargs.pop("model", None)
        try:
            return cls(**kwargs)
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"Could not construct {name}: {exc}")
            return None


def e2e_metrics(include_step_efficiency: bool = False) -> list:
    """Layer 1 - attach to the whole trace via evals_iterator(metrics=...).

    TaskCompletion is the headline Execution metric. The threshold (0.8) sits in
    the gap between completable trips (~0.9-1.0, and ~0.95 for a fixed Tokyo) and
    the seeded-regression Tokyo run (~0.70, since it surfaces "no flights found").
    So exactly the broken case fails - and flipping the regression off turns the
    whole board green.

    StepEfficiency is opt-in: for this decide-then-summarize agent it scores low
    and uniformly across *all* destinations, so it doesn't discriminate the bug
    and would just redden the whole board. Enable it to discuss "cost per step".
    """
    metrics = [
        _try("TaskCompletionMetric", threshold=0.8, model=_judge()),
    ]
    if include_step_efficiency:
        metrics.append(_try("StepEfficiencyMetric", threshold=0.6, model=_judge()))
    return [m for m in metrics if m is not None]


def reasoning_metrics() -> list:
    """Layer 2 (Reasoning) - attach to the planner / root agent span.

    Off by default. The Eval Studio dashboard scores Plan Quality / Plan
    Adherence with a fast, deterministic rubric (see ``evals/_harness.py``),
    which is reliable for a live demo. Set ``USE_LLM_REASONING_METRICS=true`` to
    additionally attach DeepEval's LLM-as-judge Plan* metrics to the trace (they
    show up in Langfuse but add two judge calls per run and score a coarse plan
    conservatively). ``DEEPEVAL_VERBOSE_REASONING=1`` prints the judge's reason.
    """
    import os

    if os.getenv("USE_LLM_REASONING_METRICS", "").lower() not in {"1", "true", "yes"}:
        return []

    verbose = os.getenv("DEEPEVAL_VERBOSE_REASONING", "").lower() in {"1", "true", "yes"}
    metrics = [
        _try("PlanQualityMetric", threshold=0.7, model=_judge(), verbose_mode=verbose),
        _try("PlanAdherenceMetric", threshold=0.7, model=_judge(), verbose_mode=verbose),
    ]
    return [m for m in metrics if m is not None]


def action_metrics(include_argument_correctness: bool = False) -> list:
    """Layer 2 (Action) - attach to the LLM span that decides the tool call.

    ToolCorrectness is deterministic (no judge, no rate-limit risk) and is the
    star of the Action layer - it catches the seeded wrong-tool regression every
    time. ArgumentCorrectness is judge-based and, in deepeval 4.0.x, raises a
    template-interpolation error on agentic spans, so it is opt-in only.
    """
    metrics = [
        _try("ToolCorrectnessMetric", threshold=0.9),  # deterministic, no judge
    ]
    if include_argument_correctness:
        metrics.append(_try("ArgumentCorrectnessMetric", threshold=0.7, model=_judge()))
    return [m for m in metrics if m is not None]
