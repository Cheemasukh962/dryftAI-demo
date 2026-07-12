# Reorder Copilot

**A buyer types a supply disruption in plain English. The system re-decides what to
order, prices what the delay cost, and names the constraint that's actually hurting.**

An ERP follows reorder rules a consultant typed in years ago. When a supplier emails
*"we're three weeks late,"* it can't re-think the plan — somebody redoes it by hand,
under pressure, badly. **ERPs plan. They don't think.**

> All data in this repo is **synthetic**. See [Generalization](#generalization) for
> how the same engine runs on real data.

---

## The architecture in one line

```
English sentence → [LLM picks a tool] → CP-SAT SOLVER decides → [LLM explains] → English
                                        ^^^^^^^^^^^^^^^^^^^^^^
                                        every number comes from here
```

The language model sits only at the **two ends** of the line. It translates in and
translates out. **It never does arithmetic and never picks a quantity.** If it
hallucinates a SKU, Pydantic rejects it at the boundary (`ModelRetry`) instead of
letting it become a wrong purchase order.

---

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

reorder generate                    # invent a synthetic 40-part factory, 2 years of demand
reorder solve                       # 12-week plan; expect status=OPTIMAL
reorder backtest                    # THE EVIDENCE: solver vs the rule an ERP runs
reorder demo --sku PART-1003 --lead-time 6    # a disruption, end to end, no LLM

pytest                              # 40+ tests; agent tests are free and offline
```

**For a fast, tight live demo**, use 20 parts — it proves optimality in ~1.5s/solve
and the whole demo runs in under 30 seconds:

```powershell
reorder generate --n-parts 20
reorder demo --sku PART-1003 --lead-time 6 --relative-gap 0.005
```

**To run the agent** (the only part that needs an API key):

```powershell
copy .env.example .env              # add your OPENAI_API_KEY
python -c "from reorder.agent import run_disruption; print(run_disruption('PART-1003 lead time goes to 6 weeks').model_dump_json(indent=2))"
```

---

## The evidence

Anyone can print a number. The question is whether the optimizer actually beats what
factories run today: a classic `(s,Q)` reorder rule — *"when stock drops below `s`,
order a batch of `Q`."*

We replay held-out demand through both policies, under the **same binding weekly cash
budget**, scored by the same cost function:

| Policy | Realized cost | Fill rate |
|---|---|---|
| `(s,Q)` reorder rule (what an ERP does) | $982,855 | 67.3% |
| **CP-SAT solver (rolling horizon)** | **$548,812** | **80.8%** |

**Saves ~$434k and serves 13.5 points more demand — cheaper *and* better service.**

### The honest caveat, stated up front
**With slack cash, the optimizer only ties `(s,Q)`.** A well-tuned reorder rule is
already near-optimal when nothing is scarce. The solver's advantage appears precisely
when the shared cash budget **binds** and it must ration across parts — which a
per-part rule fundamentally cannot do. That's the regime the backtest tests, and it's
the premise of the whole problem: cash is capped per week.

---

## What `demo` prints

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

That middle block is the product. Any system can produce a number. Producing *the
number, plus which constraint is hurting you, plus what relaxing it is worth* is what a
buyer can actually act on.

---

## Design decisions worth defending

**1. CP-SAT has no shadow prices, so we buy them.**
A linear program hands you the marginal value of relaxing each constraint for free.
An *integer* program has no duals — and you can't order 4.7 units. So we re-solve
three times, each with one limit loosened, and whichever recovers the most money is
the binding constraint. Costs 3× the solve time. Worth it.

**2. Never compare two unproven solves.**
CP-SAT returns `OPTIMAL` (proven) or `FEASIBLE` (good, but out of time before proving
it). Two `FEASIBLE` answers can differ for reasons unrelated to the disruption — so a
cost delta built from them is partly solver noise. `disruption_cost()` **raises**
rather than report one. Silently comparing two `FEASIBLE` solutions is the easiest way
to ship a system that confidently lies.

**3. "OPTIMAL" is optimal *to a tolerance*, and we publish the tolerance.**
Proving exact optimality on a fixed-charge integer program has a long tail — it reaches
0.05% in seconds, then stalls. So we stop at a **MIP gap tolerance** (standard
practice). But that means each plan still carries a little slack, so a naked delta
would hide it. `disruption_cost_bounds()` reports the **rigorous interval**
`[after.bound − before.cost, after.cost − before.bound]`. If the interval is wide
relative to the delta, tighten the gap and pay in solve time. Nothing is hidden.

**4. Money is integer cents.**
CP-SAT is integer-only. `$2.50` is stored as `250`. No float ever enters the model.

**5. Safety stock is soft; a stockout is much harder.**
A hard `inventory >= safety_stock` constraint makes the model *infeasible* the moment
anything slips — useless. Instead we *measure* the dip and price it, with a stockout
penalty ~15× larger. A buyer needs to know **how badly** the plan degrades, not to be
told there's no plan.

**6. Safety stock must cover the lead-time risk window.**
The buffer scales with `sqrt(lead_time + 1)`, not one week of forecast spread. An
11-unit buffer on a part with a 4-week lead time was never going to hold — this was a
real bug the backtest caught.

**7. The forecast is a range, not a point.**
`p10 / p50 / p90` per SKU per week. Safety stock is a function of forecast *error*, and
a point estimate literally cannot express the quantity the optimizer needs. Errors are
pooled across weeks, because two years of history gives only ~2 samples of any single
calendar week — far too few to read a percentile off directly.

---

## Layout

| File | Its one job |
|---|---|
| `models.py` | The typed vocabulary: `Part`, `Problem`, `Plan` + the integer-cents rule |
| `solver.py` | **CP-SAT optimizer — the decision engine** |
| `forecast.py` | History → a p10/p50/p90 demand range |
| `problem_builder.py` | Assemble parts + forecast + limits into a `Problem` |
| `baseline.py` | The `(s,Q)` ERP policy + the rolling backtest that beats it |
| `scenario.py` | Apply a disruption; price it (guarded by `OPTIMAL`) |
| `probes.py` | Re-solve with each limit relaxed to find the binding one |
| `simulate.py` | Roll the plan through 1,000 sampled demand futures |
| `diff.py` | What changed between the old plan and the new one |
| `agent.py` | The Pydantic AI agent: English in, explanation out |
| `cli.py` | `generate` · `solve` · `backtest` · `demo` |

Design spec and full implementation plan live in [`docs/`](docs/).

---

## Tests

```powershell
pytest                              # everything; free, offline, no API key needed
```

The agent is tested **without spending a cent**: a scripted `FunctionModel` drives the
real solver end-to-end, and a `TestModel` feeds deliberately garbage arguments to prove
the typed boundary **rejects** them rather than passing them through. A 12-scenario
eval suite checks a `Recommendation` validates for every phrasing.

The evals that hit the real LLM (checking it extracts the right SKU from a messy human
sentence) are **opt-in** so CI never spends money:

```powershell
$env:REORDER_LIVE_EVAL=1; pytest tests/test_agent_evals.py
```

---

## Generalization

This engine also runs on real HPC job traces from the Parallel Workloads Archive.
Right-sizing a job's memory request and setting a part's safety stock are the same
problem: allocate a constrained resource from noisy historical telemetry, where
over-provisioning wastes money and under-provisioning halts the line. I run a
university compute cluster; the SDSC-SP2 trace has 73,000 jobs of people getting this
wrong. **Same solver, different nouns.**
