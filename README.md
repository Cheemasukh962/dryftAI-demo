# Reorder Copilot

**A buyer types a supply disruption in plain English. The system re-decides what to
order, prices what the delay cost, and names the constraint that's actually hurting.**

> All data in this repo is **synthetic**. See [Generalization](#12-generalization) for how
> the same engine runs on real data.

---

### Contents
1. [The problem](#1-the-problem)
2. [The solution in three words](#2-the-solution-in-three-words)
3. [Quickstart — run it in 30 seconds](#3-quickstart--run-it-in-30-seconds)
4. [Architecture](#4-architecture)
5. [The pipeline, step by step](#5-the-pipeline-step-by-step)
6. [Every file and its one job](#6-every-file-and-its-one-job)
7. [The evidence — does it beat an ERP?](#7-the-evidence--does-it-beat-an-erp)
8. [What `demo` prints](#8-what-demo-prints)
9. [What broke, and how we found it](#9-what-broke-and-how-we-found-it)
10. [Design decisions worth defending](#10-design-decisions-worth-defending)
11. [Tests](#11-tests)
12. [Generalization](#12-generalization)

---

## 1. The problem

A factory buys parts to build things. Every week a buyer decides, for ~40 parts:
**how many of each do we order, and when?**

Getting it wrong is expensive in *both* directions, and the two errors pull against
each other — so you can't simply be cautious:

| | |
|---|---|
| **Order too much** | Cash freezes in a warehouse. Parts go obsolete. Space runs out. |
| **Order too little** | The line stops. A $200 seal idles a $2M assembly cell. |

It's hard because nothing is certain. Demand is a forecast, not a fact. Lead times slip.
Suppliers impose minimum order quantities, so you can't order exactly what you need.
Cash is capped per week. Warehouse space is finite. And all of it interacts — ordering
more of part A to be safe means less budget for part B.

Today this lives in an ERP running reorder rules a consultant typed in years ago, plus a
spreadsheet, plus the buyer's gut. When a supplier emails *"we're three weeks late,"* the
whole thing gets redone by hand, badly, under time pressure.

**ERPs plan. They don't think.**

## 2. The solution in three words

**Frame → Solve → Explain.**

- **Frame** — the AI reads the buyer's sentence and turns it into a precise math problem.
- **Solve** — a CP-SAT optimizer finds the cheapest schedule that breaks no rule, and *proves* it.
- **Explain** — the AI turns the solver's numbers back into English a buyer can act on.

The language model sits **only at the two ends of the line.** It never does arithmetic and
never picks a quantity. If it hallucinates a part number, Pydantic rejects it at the
boundary (`ModelRetry`) instead of letting it become a purchase order.

> **In a chatbot, a hallucination is a weird sentence. In a purchasing system, it's a
> wrong purchase order.** That typed boundary is the point of the whole architecture.

## 3. Quickstart — run it in 30 seconds

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

reorder generate --n-parts 20        # invent a synthetic factory + 2 years of demand
reorder solve                        # 12-week plan; expect status=OPTIMAL
reorder backtest                     # THE EVIDENCE: solver vs the rule an ERP runs
reorder demo --sku PART-1003 --lead-time 6 --relative-gap 0.005   # a disruption, end to end

pytest                               # 42 tests; free, offline, no API key needed
```

`--n-parts 20` is the **fast demo path**: it proves optimality in ~1.5s per solve and the
whole demo runs in under 30 seconds. The default 40 parts also works (`reorder generate`),
but each solve takes ~15s and needs a looser gap to prove optimality.

**Only the AI agent needs an API key.** Everything above runs without one:

```powershell
copy .env.example .env               # add your OPENAI_API_KEY
python -c "from reorder.agent import run_disruption; print(run_disruption('PART-1003 lead time goes to 6 weeks').model_dump_json(indent=2))"
```

## 4. Architecture

```
   "Kraus is 3 weeks late on PART-1003"        <- a human sentence
                  |
       [ LLM: pick a tool + arguments ]         agent.py   ── translates IN
                  |
       ┌──────────▼───────────────────────────────────────┐
       │              CP-SAT  SOLVER                      │  solver.py
       │  every number in the answer is decided HERE      │  <- the heart
       └──────────┬───────────────────────────────────────┘
                  |
    ┌─────────────┼─────────────┬──────────────┐
    ▼             ▼             ▼              ▼
 probes.py    simulate.py    diff.py      baseline.py
 which limit  1000 random    what moved   beats the ERP
 is binding?  futures        in the plan  rule? (proof)
    └─────────────┴─────────────┴──────────────┘
                  |
       [ LLM: write the explanation ]           agent.py   ── translates OUT
                  |
   "Order 1,240 units now. The delay cost $810k.
    Cash is your binding constraint: +$1k/wk recovers $36k."
```

The AI works the **two ends** of the line. It never works the middle, where the math happens.

## 5. The pipeline, step by step

| # | Step | File | What it does |
|---|---|---|---|
| 1 | **Invent the factory** | `datagen.py` | 40 parts (costs, MOQs, lead times) + 2 years of weekly demand = seasonal wave × noise |
| 2 | **Forecast a *range*** | `forecast.py` | p10 / p50 / p90 per part per week — not a single number |
| 3 | **Build the Problem** | `models.py`, `problem_builder.py` | Package parts + forecast + limits into one typed object; money as integer cents |
| 4 | **Solve it** | **`solver.py`** | Declare the choices, the rules, one number to minimize → CP-SAT proves the cheapest plan |
| 5 | **A disruption arrives** | `scenario.py` | "Lead time 3 → 6." Re-solve, price the damage, report a *rigorous bound* |
| 6 | **Which limit is binding?** | `probes.py` | Re-solve 3× with each limit loosened; biggest recovery = the real bottleneck |
| 7 | **Stress-test & prove** | `simulate.py`, `baseline.py`, `diff.py` | 1,000 sampled futures; backtest vs the ERP rule; show what moved |
| 8 | **Explain in English** | `agent.py` | The agent narrates the solver's answer — inventing nothing |

## 6. Every file and its one job

| File | Its one job |
|---|---|
| `models.py` | The typed vocabulary: `Part`, `Problem`, `Plan` + the integer-cents rule |
| **`solver.py`** | **CP-SAT optimizer — the decision engine. Everything else feeds it or reads it.** |
| `datagen.py` | Generate the synthetic factory (parts + demand history) |
| `forecast.py` | History → a p10/p50/p90 demand range |
| `problem_builder.py` | Assemble parts + forecast + limits into a solvable `Problem` |
| `baseline.py` | The `(s,Q)` ERP policy + the rolling backtest that beats it |
| `scenario.py` | Apply a disruption; price it (guarded by `OPTIMAL`, reports a bound) |
| `probes.py` | Re-solve with each limit relaxed to find the binding one |
| `simulate.py` | Roll the plan through 1,000 sampled demand futures |
| `diff.py` | What changed between the old plan and the new one |
| `agent.py` | The Pydantic AI agent — English in, explanation out |
| `cli.py` | The commands: `generate` · `solve` · `backtest` · `demo` |

## 7. The evidence — does it beat an ERP?

Anyone can print a number. The real question: does the optimizer beat what factories
actually run — a classic `(s,Q)` rule, *"when stock drops below `s`, order a batch of `Q`"*?

We replay held-out demand through both policies, under the **same binding weekly cash
budget**, scored by the **same** cost function:

| Policy | Realized cost | Fill rate |
|---|---|---|
| `(s,Q)` reorder rule (what an ERP does) | $982,855 | 67.3% |
| **CP-SAT solver (rolling horizon)** | **$548,812** | **80.8%** |

**Saves ~$434,000 and serves 13.5 points more demand — cheaper *and* better service.**

### The honest caveat, stated up front

**With slack cash, the optimizer only *ties* `(s,Q)`.** A well-tuned reorder rule is
already near-optimal when nothing is scarce. The solver's advantage appears precisely when
the shared cash budget **binds** and it must ration across parts — something a per-part
rule fundamentally cannot do. That's the regime the backtest measures, and it's the premise
of the entire problem: **cash is capped per week.**

## 8. What `demo` prints

```
DISRUPTION: PART-1003 lead time 3 -> 6 weeks

COST OF THE DISRUPTION: $810,284.08
  rigorous bound: $800,847.43 .. $817,709.13  (both solves OPTIMAL)

WHICH LIMIT IS BINDING?  (cost recovered if we relax it)
  budget +$1000/wk     recovers $   36,057.38  <-- binding constraint
  safety -10%          recovers $    9,139.45
  warehouse +1000u     recovers $        0.00

STRESS TEST (1000 sampled demand futures):
  fill rate  median=81.1%   bad case (p10)=80.4%
```

That middle block **is the product.** Any system can produce a number. Producing *the
number, plus which constraint is hurting you, plus what relaxing it is worth* is the thing
a buyer will actually act on. Note this runs with **no LLM involved** — proof that the
intelligence lives in the solver, not the language model.

## 9. What broke, and how we found it

The backtest initially showed the solver **losing badly** to the dumb rule. Rather than
tune numbers until it looked good, each failure was traced to a root cause.

**Bug 1 — the solver was hallucinating inventory.**
Orders placed but not yet delivered were folded into *week-0 stock*, so the solver was told
it had **887 units** when the warehouse really held **172**. It under-ordered and the line
starved. *Fix:* a proper **pipeline** input, so in-transit orders arrive in the week they
actually arrive. Cost fell $707k → $326k; fill rose 74% → 88.5%.

**Bug 2 — safety stock ignored lead time.**
The buffer was sized from a single week of forecast spread: an **11-unit** cushion on a part
with a **4-week** lead time. The risk window is the whole lead time. *Fix:* scale the buffer
by `sqrt(lead_time + 1)`, which is what inventory theory actually says.

**Bug 3 — "cash is the binding constraint" was false.**
The demo ran with a *slack* budget, so relaxing the budget recovered **$0**. The headline
claim in the design doc was not true of the running code. *Fix:* make the weekly cash cap
actually bind — the premise of the problem. Budget now correctly ranks as the top constraint.

**Bug 4 — "OPTIMAL" still hides slack.**
Proving exact optimality has a long tail, so we stop at a small MIP gap. But then each plan
carries a little uncertainty, and subtracting two point costs **buries solver noise inside
the headline number**. *Fix:* `disruption_cost_bounds()` reports the rigorous interval
`[after.bound - before.cost, after.cost - before.bound]`, so you can say: *"the delay cost
$810k, and I can prove it's between $801k and $818k."*

## 10. Design decisions worth defending

**CP-SAT has no shadow prices, so we buy them.**
A linear program hands you the marginal value of relaxing each constraint for free. An
*integer* program has no duals — and you can't order 4.7 units. So we re-solve three times,
each with one limit loosened, and whichever recovers the most money is the binding
constraint. Costs 3× the solve time. Worth it.

**Never compare two unproven solves.**
CP-SAT returns `OPTIMAL` (proven) or `FEASIBLE` (good, but out of time before proving it).
Two `FEASIBLE` answers can differ for reasons unrelated to the disruption, so a delta built
from them is partly solver noise. `disruption_cost()` **raises** rather than report one.
Silently comparing two `FEASIBLE` solutions is the easiest way to ship a system that
confidently lies.

**Money is integer cents.** CP-SAT is integer-only. `$2.50` is stored as `250`. No float
ever enters the model.

**Safety stock is soft; a stockout is much harder.**
A hard `inventory >= safety_stock` constraint makes the model *infeasible* the moment
anything slips — useless. Instead we *measure* the dip and price it, with a stockout penalty
~15× larger. A buyer needs to know **how badly** the plan degrades, not to be told there's
no plan.

**The forecast is a range, not a point.**
Safety stock is a function of forecast *error*, so a point estimate literally cannot express
what the optimizer needs. Errors are **pooled across weeks**, because two years of history
gives only ~2 samples of any single calendar week — far too few to read a percentile from
directly.

## 11. Tests

```powershell
pytest        # 42 passed, 12 skipped — free, offline, no API key required
```

The agent is tested **without spending a cent**:
- A scripted `FunctionModel` drives the **real solver** end to end.
- A `TestModel` feeds deliberately garbage arguments, and we **assert the run fails** —
  proving the typed boundary *rejects* hallucinated input rather than passing it through.
- A 12-scenario eval suite checks a valid `Recommendation` comes back for every phrasing.

The evals that hit the real LLM (checking it pulls the right SKU out of a messy human
sentence) are **opt-in**, so CI never spends money:

```powershell
$env:REORDER_LIVE_EVAL=1; pytest tests/test_agent_evals.py
```

## 11b. Observability — tracing the agent with Langfuse

The solver is deterministic: it either proves `OPTIMAL` or it doesn't. **The agent is the
only unpredictable part of the system** — it can pick the wrong tool, misread a SKU, or
need two attempts to get it right, and *none of that shows up in a return value*.

Tracing is how you see what it actually did. Every agent run is recorded as a tree —
which tool was called, with what arguments, what came back, how long it took, how many
tokens it burned — and shipped to **Langfuse**, where you can click through it.

**No new dependency.** Pydantic AI emits OpenTelemetry spans, and Langfuse ingests
OpenTelemetry, so `observability.py` just points the OTel exporter at Langfuse and turns
Pydantic AI's instrumentation on.

**Entirely optional.** With no Langfuse keys set, `configure_tracing()` is a no-op and the
app behaves exactly as before — the test suite stays free, offline, and fast.

```powershell
# in .env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Then any agent run traces automatically. To prove the pipe works **without a Langfuse
account**, this script stands up a local OTLP receiver and asserts real spans arrive:

```powershell
python scripts/verify_langfuse_tracing.py
```
```
OTLP requests received: 2
  POST /v1/traces  17038 bytes  content-type=application/x-protobuf  auth=Basic ***
  span content contains b'agent run': True
  span content contains b'analyze_lead_time_change': True
PASS: real spans exported to the OTLP /v1/traces endpoint with Basic auth.
```

## 12. Generalization

This engine also runs on real HPC job traces from the Parallel Workloads Archive.
Right-sizing a job's memory request and setting a part's safety stock are the same problem:
allocate a constrained resource from noisy historical telemetry, where over-provisioning
wastes money and under-provisioning halts the line. I run a university compute cluster; the
SDSC-SP2 trace has 73,000 jobs of people getting this wrong.

**Same solver, different nouns.**

---

*Design spec and the full implementation plan live in [`docs/`](docs/).*
