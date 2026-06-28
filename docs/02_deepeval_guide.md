# 02 · DeepEval guide (Layers 1–3)

This is the "how to use DeepEval in this project" walkthrough, mapped to the
talk's layers. Everything here works **locally**; `deepeval login` only adds the
Confident AI cloud UI.

---

## Layer 3 first — tracing (the substrate)

Layers 1 & 2 score *traces*, so tracing comes first. We instrument code we own
with `@observe` (see `src/trip_planner/observability.py`, `agents/base.py`,
`agents/nodes.py`, `graph.py`).

```python
from deepeval.tracing import observe, update_current_span, update_llm_span

@observe(type="agent", name="trip_planner")     # the trace root
async def plan_trip(user_input): ...

@observe(type="llm", model="gpt-4o-mini",
         cost_per_input_token=..., cost_per_output_token=...,
         metrics=[ToolCorrectnessMetric(), ArgumentCorrectnessMetric()])
async def _decide_tool(...):
    resp = await model.ainvoke(messages)
    update_llm_span(input_token_count=in_tok, output_token_count=out_tok)  # → cost
    update_current_span(tools_called=..., expected_tools=...)              # → Layer 2
    return resp

@observe(type="tool", name="search_flights")
async def _run(args): ...
```

**Span types matter:** `type="llm"` renders model + token cost, `type="tool"`
renders the description, `type="agent"` renders available tools / handoffs in the
Confident AI UI.

**Token cost.** We set `cost_per_input_token` / `cost_per_output_token` on the
decorator (from `PRICE_*` env) and the counts via `update_llm_span`. Confident AI
multiplies them → USD on each LLM span, summed to the trace. For OpenAI/Anthropic/
Gemini, Confident AI can even look pricing up automatically if you omit it.

> Metrics attached to `@observe` **do not run** during normal execution (the
> chat). They only fire under `evals_iterator` / `evaluate`. That's why it's safe
> to leave `metrics=[...]` on the spans permanently.

---

## Running the eval suite

Everything runs **inside the `api` container** (so the MCP / Obot-gateway URLs
resolve and the OpenAI + Confident keys are already present). The wrapper:

```powershell
./scripts/run_evals.ps1 layer1                 # end-to-end golden eval (Layer 1)
./scripts/run_evals.ps1 layer1 --limit 5       # quick subset (Tokyo always kept)
./scripts/run_evals.ps1 layer1 --regression on # force the seeded bug
./scripts/run_evals.ps1 layer2                 # component-level eval (Layer 2)
./scripts/run_evals.ps1 shadow                 # candidate-vs-baseline shadow mode
./scripts/run_evals.ps1 all                    # layer2 + shadow + layer1
```

> Under the hood it's `docker compose exec -T api python evals/<script>.py`.
> Layer 1 is LLM-judged (slower); Layer 2 and shadow are deterministic (seconds).

---

## Layer 1 — end-to-end evaluation

`evals/layer1_e2e_eval.py`. Build a dataset of **goldens**, iterate, and let the
trace-based Execution metric score the whole run. We capture the
`EvaluationResult` and render a per-destination pass/fail table.

```python
from deepeval.dataset import EvaluationDataset
from deepeval.evaluate.configs import AsyncConfig, ErrorConfig
from trip_planner.metrics import e2e_metrics       # TaskCompletion (threshold 0.8)
from trip_planner.graph import plan_trip

dataset = EvaluationDataset(goldens=get_goldens())
gen = dataset.evals_iterator(
    metrics=e2e_metrics(),
    async_config=AsyncConfig(run_async=False),     # see Gotchas
    error_config=ErrorConfig(ignore_errors=True),
)
# drive the generator with the (async) agent; capture the returned result
```

- **`TaskCompletionMetric`** (threshold **0.8**) — LLM-judged, referenceless: did
  the outcome match the inferred task? → "did it work?" The threshold sits in the
  gap between completable trips (~0.9–1.0) and the broken Tokyo run (~0.70, which
  honestly reports "no flights found"), so **exactly one golden fails** with the
  regression on, and the whole board goes green with it off.
- **`StepEfficiencyMetric`** is **opt-in** (`e2e_metrics(include_step_efficiency=True)`).
  For this decide-then-summarize agent it scores low *and uniformly* across all
  destinations, so it doesn't discriminate the bug — useful to *discuss* "cost per
  step", not to gate the board.

Both read the **full trace** — no `expected_output` labels needed.

### Anatomy of an agent golden (`evals/goldens.py`)
Not just `(input, expected_output)`. Ours carry `input`, `expected_tools`
(reference), and `additional_metadata` (difficulty, destination). The Tokyo
golden is the seeded-regression trigger.

---

## Layer 2 — component-level evaluation

`evals/layer2_component_eval.py`. Two complementary views, both deterministic
(`ToolCorrectnessMetric`, no judge → no rate-limit risk, repeatable):

### (a) Dataset-driven sweep
Run the **flight agent's tool decision** in isolation for every golden
destination and score each. With the regression on, exactly Tokyo flips to
`get_flight_details` (score 0.0) while the rest call `search_flights` (1.0).
"Component testing at dataset scale."

### (b) Isolated contrast
A healthy `search_flights` decision vs the buggy `get_flight_details` decision,
scored side by side — the punchy "here is the bug" moment.

Both also fire **on the LLM span during the Layer 1 run**: `_decide_tool` carries
`metrics=action_metrics()`, and because we now apply the seeded regression
*inside* `_decide_tool`, the span's `tools_called` reflects the wrong tool — so
the failing **span** in the live trace (Beat 2) shows `ToolCorrectness = 0`.

> **`ArgumentCorrectnessMetric` is off by default.** In deepeval 4.0.x it raises a
> `MetricTemplateInterpolationError` on agentic spans. Re-enable with
> `action_metrics(include_argument_correctness=True)` once that's fixed upstream.

### Reasoning metrics
`reasoning_metrics()` provides `PlanQualityMetric` + `PlanAdherenceMetric`,
attached to the trace root in `graph.py`. Under the regression, Tokyo's
`PlanAdherence` drops too. "A perfect plan ignored is as broken as a bad plan
followed."

---

## Shadow mode (`evals/shadow_eval.py`)

Shadow mode = run a **candidate** build on the same traffic the live system
sees, score it, and compare — *without serving its output to users*. It's how you
earn confidence to promote a change before it reaches production.

Here we replay the golden destinations through two flight-agent implementations
and compare per destination:

- **baseline** — the currently-deployed build (carries the Tokyo bug)
- **candidate** — the proposed fix (bug removed)

```
Shadow comparison  -  baseline 6/7  →  candidate 7/7
Tokyo:  get_flight_details  →  search_flights   FIXED
Fixed: 1   Regressed: 0  → safe to promote.
```

In a real system the baseline is live prod traffic and the candidate a shadow
deployment; the goldens stand in for that traffic here.

---

## Observability — aggregated calls & trace timeline

> "In the app I only see *per-session* calls. Can I get *total aggregated* calls,
> and a Langfuse-style trace timeline?" — **Yes, both, in Confident AI.**

**Two different scopes, on purpose:**

| | Where | Scope |
|---|---|---|
| Live token/cost meter (`UsageMeter`) | the web app | this server process / session — a *live gauge* for the demo |
| Aggregated calls, tokens, USD, latency | Confident AI → **Observatory / Monitoring** | **all** traces, all time, every run (app + evals) |

Every `plan_trip` run — whether from the chat UI or an eval — posts a trace, so
the aggregates accumulate automatically. To see them:

1. **Aggregated totals & trends:** Confident AI → your project → **Observatory**
   (a.k.a. Monitoring). You get total LLM calls, input/output tokens, **USD cost**,
   p50/p95 latency, and error rate, charted over time and sliceable by model,
   metric, and metadata. That is the "all the calls, aggregated" view.
2. **Trace timeline (the Langfuse-style waterfall):** open any trace → the
   **span tree / timeline** shows each span (`trip_planner → planner →
   supervisor → flight_agent → llm → tool …`) with its **duration, token count,
   and cost**, laid out as a waterfall. This is produced *for free* by our
   `@observe` spans — no extra code.
3. **Per-run comparison:** the **Test Runs** tab compares eval runs (e.g.
   regression-on vs regression-off) so you can watch a fix move the pass rate and
   the cost.

The in-app meter is intentionally a *session* gauge (Confident AI is the system
of record for history); use `POST /api/usage/reset` / the UI button to zero it
between demo takes.

---

## The local loop

1. Run the agent → inspect the trace timeline.
2. Find the failing span (Layer 2 score).
3. Fix the prompt/code (or flip `INJECT_REGRESSION`).
4. Re-run the eval; compare runs in Confident AI.

---

## Gotchas baked into this repo

- **Empty `OPENAI_BASE_URL` breaks the judge.** docker compose passes it as `""`,
  and the OpenAI SDK (used by DeepEval's judge) treats `""` as the base URL →
  every judge call fails with *"Request URL is missing an 'http://' …"*.
  `config.py` deletes the empty value so the SDK falls back to api.openai.com.
- **Drive `evals_iterator` synchronously** (`AsyncConfig(run_async=False)`).
  Running our async agent inside a manual loop while DeepEval also spins up its
  own async executor corrupts context vars; and the default `max_concurrent=20`
  fires judge calls 20-wide → OpenAI rate limits. Sequential is slower but solid.
- **Judge = `gpt-4o-mini`** (`DEEPEVAL_JUDGE_MODEL`). A new OpenAI project is
  Tier 1; `gpt-4o` judge calls with large trace context blow the TPM limit during
  evals. Bump to `gpt-4o` if your account has higher limits.
- **One event loop for the whole eval run** (`evals/_harness.py`) so the cached
  MCP client/`asyncio.Lock` doesn't get bound to a closed loop.
- **Version tolerance** — `metrics.py` skips any metric your installed DeepEval
  version lacks (with a warning) instead of crashing.
- **`CONFIDENT_TRACE_VERBOSE=0`** in `.env` silences local trace logs during chat.
