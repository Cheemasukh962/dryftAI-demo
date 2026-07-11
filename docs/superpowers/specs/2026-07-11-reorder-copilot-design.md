# Reorder Copilot — Design & Build Spec

*A decision layer for manufacturing purchasing. The agent frames the problem, a solver answers it, the agent explains the answer.*

**Status:** approved design, ready for implementation planning.
**Author's context:** built as an interview project. Comfortable in Python, new to CP-SAT / Pydantic AI / Langfuse / Dagster / forecasting. Live demo in the interview. Under one week to build. LLM access via an OpenAI API key.

This document doubles as a **study guide** — every unfamiliar concept is explained in plain English, because the whole point is being able to defend every line in the interview.

---

## 1. The problem (why anyone cares)

A factory buys parts to build things. Every week a buyer decides, for each of ~40 parts: **how many do we order, from whom, and when.**

Getting it wrong is expensive both ways:
- **Order too much** → cash frozen in a warehouse, parts go obsolete, space runs out.
- **Order too little** → the line stops. A $200 seal idles a $2M assembly cell.

It's hard because nothing is certain: demand is a forecast, lead times slip, suppliers force minimum order quantities (you can't order exactly what you need), cash is capped per week, and space is finite. Every choice trades off against the others — more of part A to be safe means less budget for part B.

Today this lives in an ERP (SAP/Oracle) running reorder rules a consultant typed in years ago, plus a spreadsheet, plus the buyer's gut. When a supplier emails "we're three weeks late," the whole thing gets redone by hand, badly, under time pressure. **ERPs plan. They don't think.**

---

## 2. What we're building (the 60-second demo)

A buyer types a disruption in plain English. The system re-decides what to order and explains what it cost.

> **Buyer:** *"Supplier Kraus just emailed. HOUSING-4471 lead time goes from 2 weeks to 5, starting now."*
>
> **System:**
> - Revised plan: order 480 units this week instead of 276 next week.
> - Cost of the disruption: **$37,738** over the 12-week horizon.
> - **The weekly cash budget is the binding constraint.** An extra $1,000/week of budget recovers $11,646 of that.
> - Loosening warehouse space instead: recovers $540. Not your problem.
> - Accepting 10% lower safety stock: recovers $2,403.

The last three lines **are the product.** Any system can produce a number. Producing *the number, plus which limit is hurting you, plus what relaxing it would cost* is what a buyer actually acts on.

---

## 3. Scope decision (what we are and aren't doing)

**Chosen approach: "A" — the headless 60-second demo.** Everything that produces the output above, runnable from a terminal, no servers or database. If we finish early, "C" (a one-page web UI) is a stretch goal.

**In scope:** synthetic data, simple forecast, CP-SAT solver, Monte Carlo simulation, the dumb-baseline backtest, the constraint probes, the plan diff, and the Pydantic AI agent.

**Out of scope (non-goals — stating these is half the value):**
- No multi-echelon networks. One warehouse, one tier of suppliers.
- No auth, no multi-tenancy, no deployment. Runs locally.
- No database, no FastAPI, no Dagster for now (all were in the original spec; cut for the one-week timeline).
- No pretty UI. Terminal output; web UI only if far ahead.
- No LLM cleverness. The model selects tools and writes prose. It does **not** do arithmetic.
- ~40 SKUs. Forty parts we can explain beats ten thousand we can't. Drop to 20 if the solver struggles.
- No NeuralProphet. A simple seasonal-quantile forecast instead (see §6).

---

## 4. Architecture

One Python package, no servers, no database. Data is plain CSV files on disk. Everything runs as `python -m reorder <command>`. Fewer moving parts = fewer ways to fail during a live demo.

```
reorder-copilot/
├── pyproject.toml          # project definition + dependencies
├── src/reorder/
│   ├── models.py           # entities (§5) as Pydantic classes
│   ├── datagen.py          # synthetic factory: 40 SKUs, suppliers, 2yrs demand
│   ├── forecast.py         # seasonal quantile forecast → p10/p50/p90 per SKU per week
│   ├── solver.py           # the CP-SAT model — the heart
│   ├── simulate.py         # NumPy Monte Carlo, 1,000 futures
│   ├── baseline.py         # the (s,Q) ERP-style policy + backtest vs the solver
│   ├── probes.py           # the 3 constraint-relaxation counterfactuals
│   ├── diff.py             # before/after plan comparison
│   ├── agent.py            # Pydantic AI agent + its typed tools
│   └── cli.py              # commands: generate, solve, backtest, demo
├── tests/
├── data/                   # generated CSVs live here
└── README.md
```

### Data flow, end to end
1. **Once, up front:** `datagen.py` invents a plausible factory — 40 parts with costs, MOQs, lead times; a few suppliers; two years of weekly demand with seasonality and noise. Synthetic, and the README says so.
2. **`forecast.py`** reads demand history, produces p10/p50/p90 per part for the next 12 weeks.
3. **`solver.py`** builds the CP-SAT model, solves the *baseline* plan, and **refuses to report anything unless status is `OPTIMAL`.**
4. **The disruption arrives** (from the agent, or directly via CLI): "HOUSING-4471 lead time 2→5." That's a changed parameter; the solver re-solves.
5. **`probes.py`** re-solves 3 more times with each constraint relaxed; **`simulate.py`** rolls the new plan through 1,000 sampled futures; **`diff.py`** compares old vs new plan.
6. **`agent.py`** is the only place an LLM appears: English sentence → parameter change (step 4), and numeric results → the explanation (§2 output).

### Two contracts that hold everywhere
- **All money is integer cents.** CP-SAT can't do floats. `$2.50` is stored as `250`.
- **Every `Plan` carries its solver status.** A `FEASIBLE`-vs-`FEASIBLE` comparison is structurally impossible, not just discouraged (see §7.2).

---

## 5. Entities

```
Part            sku, unit_cost, holding_cost, order_cost, moq,
                lead_time, volume, opening_inventory
Supplier        id, name, reliability, parts[]
DemandHistory   sku, week, units
Forecast        sku, week, p10, p50, p90        # quantiles, not a point
Plan            orders[sku][week], inventory[sku][week], cost, status
Recommendation  orders, binding_constraints[], counterfactuals[]
```

Implemented as Pydantic classes in `models.py` so the same types flow through the solver, the simulator, and the agent's typed boundary.

---

## 6. The solver (the heart)

### What a solver is, plainly
You don't write an algorithm that computes the answer. You write down (a) the **choices** allowed, (b) the **rules** they must obey, (c) one **number to minimize** — and CP-SAT (free, from Google OR-Tools) searches intelligently for the choice-combination that breaks no rule and makes that number smallest. *"I described the problem and the rules; the solver found the best answer."*

Analogy: planning a week of groceries with $100, a fixed-size fridge, and seven dinners to cover. A solver mentally tries millions of shopping lists in seconds and returns the cheapest one that still feeds you and fits.

### The model (from the original spec, transcribed faithfully)

Decision variables, per part `i`, per week `t`:
```
q[i,t]      units ordered            (integer)
y[i,t]      did we order at all      (boolean, drives MOQ + fixed cost)
inv[i,t]    on-hand inventory        (integer >= 0)
back[i,t]   unmet demand             (integer >= 0)
short[i,t]  units below safety stock (integer >= 0)
```

Constraints:
```
inv[i,t] - back[i,t] = inv[i,t-1] - back[i,t-1] + q[i, t-L_i] - demand[i,t]
q[i,t] >= MOQ_i * y[i,t]                       # order nothing, or at least the MOQ
q[i,t] <= BIG   * y[i,t]                        # link q to y ("big-M")
short[i,t] >= safety_stock_i - inv[i,t]         # soft: measure the dip, don't forbid it
Σ_i unit_cost_i * q[i,t] <= budget[t]           # weekly cash cap
Σ_i volume_i   * inv[i,t] <= warehouse_cap      # space
```

Objective:
```
minimize  holding_cost·inv + order_cost·y + stockout_penalty·back + safety_penalty·short
```

**Lead time is an index shift:** an order placed at `t - L` arrives at `t`. Orders near the end of the horizon arrive after it and only cost money — which is why the solver naturally stops ordering near the end. That edge effect is real; the proper fix is a rolling horizon (see §8.5).

### The forecast (simplified from the spec)
Produce **p10 / p50 / p90** per SKU per week — quantiles, not a point estimate. This isn't a nicety: **safety stock is a function of forecast-error spread.** `p50` feeds the demand constraint; the `p10`–`p90` spread sets the safety-stock target.

Method (kept deliberately simple and explainable, ~40 lines): estimate a **seasonal level** per SKU per week for `p50` — a smooth week-of-year pattern times a recent-trend level — then set `p10`/`p90` from the **spread of historical forecast errors** for that SKU (residuals pooled across all weeks, so we have enough samples even with only two years of history). No neural net. Two years gives only ~2 observations of any single calendar week, which is far too few to read quantiles off directly — pooling the residuals is what makes the spread trustworthy, and that reasoning is itself a good interview answer.

### The simulation
Take the plan the solver produced, roll it forward 1,000 times sampling demand from the forecast quantiles and lead times from a supplier-reliability distribution. Report the **distribution** of fill-rate and cash-tied-up, not one number. The solver plans against `p50`; reality isn't `p50`; simulation is how you learn whether the plan survives variance.

---

## 7. Design decisions worth defending (interview gold)

### 7.1 CP-SAT has no shadow prices
Linear programs hand you, for free, the marginal value of relaxing each constraint (the "dual"). **Integer programs don't have duals**, and our variables are integers (you can't order 4.7 units). So CP-SAT won't tell you what the budget cap is costing you. We **buy** that information: re-solve with each constraint relaxed by ε and report the change in objective. Three probes — `+$1,000/wk budget`, `+1,000 units warehouse`, `-10% safety stock` — and the largest drop names the binding constraint. Costs 3× solve time; worth it. *Knowing why the free approach doesn't work here is a stronger signal than it just working.*

### 7.2 Never compare two FEASIBLE solutions
CP-SAT returns `OPTIMAL` (proven best) or `FEASIBLE` (valid, but ran out of time before proving nothing better exists). Two `FEASIBLE` answers can differ by an arbitrary amount for reasons unrelated to the change you made — so a "cost of disruption" computed from them is partly solver noise. **Rule: assert `status == OPTIMAL` before reporting any delta.** If the model's too big to prove optimality, report the optimality gap explicitly and call the delta a bound, not a number. (Hit this on the first run — the baseline came back `FEASIBLE` and the computed cost was partly noise.)

### 7.3 Money is integer cents
CP-SAT is integer-only. All costs scale to cents; no floats anywhere in the model. Obvious once known; a day lost if not.

### 7.4 Safety stock is soft, stockout is hard(er)
Two penalty tiers. Dipping below safety stock is bad (`safety_penalty`). Failing to meet demand is much worse (`stockout_penalty`, ~15× larger). A hard safety-stock constraint makes the model infeasible the moment anything goes wrong — useless. A real buyer wants to know *how badly* the plan degrades, not to be told there's no plan.

### 7.5 Plan long, act short (rolling horizon)
Solve over 12 weeks, execute only week 1, advance, re-forecast, re-solve. This is receding-horizon control and it fixes the end-of-horizon artifact in §6. It also creates a real problem: **the plan changes every week and buyers stop trusting it.** So `diff.py` isn't a convenience — it's what makes the system adoptable; the agent's job is to explain *why* the plan moved. *(This connects directly to predictive-control work — a controller does exactly this, fast, in a loop.)* Note: within the one-week build we implement the single re-solve and the diff; the full week-by-week rolling loop is optional polish.

---

## 8. The agent layer

**The agent is a translator, not a decision-maker.** Two jobs only: (1) turn the buyer's English into the parameter change the solver understands; (2) turn the solver's numeric output back into the §2 explanation. **It never does math and never picks a quantity.**

Built with **Pydantic AI** (uses the OpenAI key). A language model is text-in/text-out and will invent things if left alone. We hand it a small menu of real Python functions with strict shape-checking on input and output:

```python
get_part_context(sku)            -> PartContext
forecast_demand(sku, horizon)    -> QuantileForecast
solve_reorder(problem)           -> Plan
simulate(plan, n=1000)           -> ServiceLevelDistribution
probe_constraint(problem, which) -> CounterfactualResult
diff_plans(before, after)        -> PlanDiff
```

Output type is a validated `Recommendation`. **This typed boundary is the whole point of the architecture.** If the model hands the solver an infeasible or malformed problem, `ModelRetry` bounces it back with the reason attached and the model tries again. In a chatbot a hallucination is a weird sentence; in a purchasing system it's a wrong purchase order. Pydantic catches it at the boundary. *This is the answer to "how do you keep the LLM from doing something dumb?"*

**Langfuse (stretch, last):** records the agent's tool-call sequence like a flight recorder, viewable in a web page ("here's the trace"). Nice-to-have; skipped with zero essential loss if time is short.

---

## 9. How we know it works

In ascending order of what they prove:
1. **Optimality shown on every solve** — status and gap reported; no `FEASIBLE`-vs-`FEASIBLE` comparisons. No confident lying.
2. **Backtest against a dumb baseline** — replay six months of held-out demand through a classic `(s, Q)` reorder-point policy (order `Q` whenever inventory drops below `s`, what the ERP actually does) and through the solver. Report dollars saved and fill-rate. *Without this it's a demo; with it, it's evidence.*
3. **Agent evals** — a dataset of ~10–20 disruption scenarios asserting the agent selects the right tool sequence and returns a `Recommendation` that validates. Cheapest, highest-value thing here, and the clearest rebuttal to "have you shipped production code end-to-end?"

---

## 10. Build plan (under 7 days, explain-back at every checkpoint)

A live demo where you can't explain the code is worse than no demo. **Each step ends with the builder reading it back in plain English before moving on**, and each layer is a working demo by itself — if a later day explodes, an earlier working artifact still stands.

- **Days 1–2 — the engine.** Synthetic data → seasonal-quantile forecast → CP-SAT solver hitting `OPTIMAL` on 40 SKUs × 12 weeks → the `(s,Q)` baseline and a backtest showing the solver beats it. *Done when: one command prints a plan, a cost, and "beat the baseline by $X."* **This alone is a defensible project.**
- **Days 3–4 — disruption + explanations.** The lead-time change, the three constraint probes, the 1,000-run simulation, the before/after plan diff.
- **Day 5 — the agent.** Pydantic AI with the typed tools + `ModelRetry`, so typing the English disruption produces the §2 output. The ~10–20 scenario eval set (§9).
- **Days 6–7 — polish + rehearsal.** README (state up front it's synthetic data), a clean run-through, and the walkthrough practiced out loud. Langfuse and the web UI only if ahead.

**Solver first** — it's the unfamiliar piece and everything hangs off it.

---

## 11. Risks

| Risk | Response |
|---|---|
| Solver doesn't reach `OPTIMAL` at 40 SKUs | Tighten `BIG`, add symmetry breaking, or cut to 20 SKUs. Report the gap honestly either way. |
| It's all synthetic data | Say so in the README up front. Optional stretch: validate the same engine on real HPC job traces (§12). |
| Scope creep into a pretty UI | The plain terminal output is the deliverable; web UI is explicitly a stretch goal only. |
| One week becomes tight | Days 1–2 alone, backtested, is already a defensible artifact. Ship in layers. |
| Can't explain a piece under questioning | The explain-back checkpoint at each step is a hard gate, not a suggestion. |

---

## 12. The generalization paragraph (for the README)

> This engine also runs on real HPC job traces from the Parallel Workloads Archive. Right-sizing a job's memory request and setting a part's safety stock are the same problem: allocate a constrained resource from noisy historical telemetry, where over-provisioning wastes money and under-provisioning halts the line. I run a university compute cluster; the SDSC-SP2 trace has 73,000 jobs of people getting this wrong. Same solver, different nouns.

One paragraph: it proves the engine generalizes rather than being fitted to a demo, grounds the project in real data when nobody else has any, and explains — without bragging — why someone who administers a research cluster is qualified to reason about factory operations. (Stretch; include only if the core is solid.)
