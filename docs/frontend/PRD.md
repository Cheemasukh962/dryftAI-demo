# PRD — Reorder Copilot, Front End

**For:** an agent/engineer building the UI standalone, to be plugged into the existing
Python backend afterwards.
**You do not need the backend to build this.** Real fixtures captured from live runs are
in this folder. Build against them; wiring up later is a swap, not a rewrite.

---

## 1. What this product is (read this first — it's the whole point)

A factory stocks ~20 parts. Every week a buyer decides **how many of each to order.**
Order too much → cash frozen in a warehouse. Order too little → the assembly line stops.

A supplier emails: *"PART-1003 is going from 3 weeks to 6 weeks."*

An ERP can't re-think the plan. **This product can.** It re-optimizes what to buy, prices
what the delay cost, and names the constraint that's actually hurting.

### The ONE insight the UI exists to convey

> **One part got late. Seventeen of the twenty parts had their orders rewritten.**

Why? **Because the cash is shared.** The weekly budget is capped at **$361,134**. To
survive the delay you must panic-buy 769 more units of PART-1003 (+$85,812) — but the
budget did not grow. So that money is taken *from other parts*: PART-1012 is cut by
two-thirds, PART-1000 is **cancelled entirely**.

```
cash spent BEFORE : $361,132
cash spent AFTER  : $361,134
weekly budget cap : $361,135   <-- THE SAME MONEY BOTH TIMES
```

**The real decision is not "how much PART-1003 do I buy." It is "whose order do I cancel
to pay for it?"** That is what a per-part reorder rule fundamentally cannot do, and it is
what the UI must make visceral.

If a viewer leaves the demo understanding only that sentence, the UI succeeded.

### Vocabulary
| Term | Plain meaning |
|---|---|
| **SKU / part** | A purchasable item, e.g. `PART-1003` |
| **Lead time** | Weeks between placing an order and receiving it |
| **MOQ** | Minimum order quantity — supplier won't sell fewer |
| **Safety stock** | Buffer inventory held against demand surprises |
| **Fill rate** | % of demand actually served (higher = fewer line stoppages) |
| **Binding constraint** | The limit actually costing you money (cash / space / safety stock) |
| **`(s,Q)` baseline** | The dumb reorder rule a real ERP runs. We beat it. |
| **OPTIMAL** | The solver *proved* no cheaper plan exists (within a stated tolerance) |

---

## 2. Tech stack (non-negotiable — matches the company's stack)

- **React + TypeScript**
- **Vite**
- **Chakra UI v3** (component library; do not hand-roll a design system)
- **TanStack Router** + **TanStack Query** (Query is how you'll swap fixtures → real API)
- Charts: **Recharts** (or visx). Keep it simple.

**Critical:** put every data fetch behind a **TanStack Query hook** in `src/api/`. During
this phase those hooks resolve fixture JSON. Plugging in the real backend later must be a
one-file change per hook. **Do not scatter `fetch()` calls through components.**

---

## 3. Fixtures (real data, captured from live solver runs)

In this folder:

| File | What it is |
|---|---|
| `fixture-disruption.json` | **The main payload.** Full analysis of PART-1003 going 3→6 weeks |
| `fixture-parts.json` | The 20 parts (cost, lead time, MOQ, stock, weeks of cover) |
| `fixture-backtest.json` | The evidence: solver vs the ERP rule |
| `fixture-demand-PART-1003.json` | 104 weeks of demand history (for a sparkline) |

**These are real numbers. Do not invent different ones** — the demo's credibility rests on
them.

---

## 4. The data contract (TypeScript)

This is what the backend will return. Type your fixtures with exactly these.

```ts
// ---------- GET /api/parts ----------
export interface Part {
  sku: string;                    // "PART-1003"
  unit_cost_dollars: number;      // 111.59
  lead_time_weeks: number;        // 3
  moq: number;                    // 200
  opening_inventory: number;      // 635
  avg_weekly_demand: number;      // 203
  weeks_of_cover: number;         // 3.1  <- stock ÷ weekly demand. THE tension metric.
}

// ---------- GET /api/parts/:sku/demand ----------
export interface DemandPoint { week: number; units: number; }

// ---------- POST /api/disrupt  { sku, new_lead_time_weeks } ----------
export interface Probe {
  name: string;                   // "budget +$10k/wk" | "safety -50%" | "warehouse +10000u"
  recovered_dollars: number;      // 332398.31  <- point estimate
  provable_low_dollars: number;   // 322458  <- rigorous lower bound
  provable_high_dollars: number;  // 354893  <- rigorous upper bound
}

export interface OrderChange {
  sku: string;
  before: number;                 // units ordered in week 0, before the disruption
  after: number;                  // units ordered in week 0, after
  delta: number;                  // after - before (negative = cut)
  cash_delta_dollars: number;     // -60412.80  <- money freed up / consumed
}

export interface DisruptionResult {
  sku: string;
  old_lead_time_weeks: number;
  new_lead_time_weeks: number;
  solver_status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE";
  weeks: number;                              // planning horizon (12)

  disruption_cost_dollars: number | null;     // 808203.14 — null if not provable!
  disruption_cost_range_dollars: [number, number] | null;  // [799241.23, 816618.61]

  binding_constraint: {
    name: string;                 // "budget +$10k/wk"
    proven: boolean;              // <-- IF FALSE, DO NOT CLAIM A WINNER IN THE UI
    recovered_dollars: number;
  };
  probes: Probe[];                // sorted, biggest recovery first

  simulation: {
    runs: number;                 // 1000
    fill_rate_p50: number;        // 0.812
    fill_rate_p10: number;        // 0.804  <- the bad-case
    peak_cash_p50_dollars: number;
  };

  weekly_budget_dollars: number;              // 361134.83
  cash_spent_week0_before_dollars: number;    // 361132.10
  cash_spent_week0_after_dollars: number;     // 361134.20
  parts_affected: number;                     // 17
  total_parts: number;                        // 20
  order_changes_week0: OrderChange[];         // sorted by |delta| desc
  focus_part_schedule: { before: number[]; after: number[] };  // 12 weeks each
}

// ---------- GET /api/backtest ----------
export interface BacktestResult {
  test_weeks: number;
  weekly_budget_dollars: number;
  solver: { cost_dollars: number; fill_rate: number };
  baseline_sq: { cost_dollars: number; fill_rate: number };
  dollars_saved: number;      // 691070.88
  fill_rate_delta: number;    // 0.065
}

// ---------- POST /api/agent  { text: string } ----------
// The AI path. Same numbers, but reached from an English sentence.
export interface AgentResult {
  explanation: string;            // the LLM's prose, written for a buyer
  recommendation: DisruptionResult;
  trace_url?: string;             // deep link to the Langfuse trace
}
```

### Two rules the UI MUST honor (this is the product's integrity)

1. **`disruption_cost_dollars` can be `null`.** The backend refuses to report a cost it
   cannot prove. When null, show *"The solver could not prove a reliable cost for this
   run"* — **never** show `$0` or a spinner forever, and never invent a number.
2. **`binding_constraint.proven` can be `false`.** That means the solver's own slack is
   wider than the gap between the probes. When false, show the probes but display
   *"Cannot name a bottleneck at this tolerance"* — **do not** put a winner badge on
   anything. *(This is a real bug we found and fixed; the UI must not undo it.)*

Always render `disruption_cost_range_dollars` next to the cost. "It cost $808,203 (provably
between $799,241 and $816,619)" is the product's credibility in one line.

---

## 5. Screens

Single-page app, 4 sections, top to bottom. **One route is fine**; use TanStack Router so
adding routes later is trivial.

### Section 1 — The Factory (the setup)
A table of the 20 parts from `fixture-parts.json`. Columns: SKU, unit cost, lead time,
MOQ, on hand, avg weekly demand, **weeks of cover**.

- **`weeks_of_cover` is the star.** Color it: **red < 2.5, amber < 4, green otherwise.**
- PART-1003 has 3.1 weeks of cover and a 3-week lead time. **Make that razor-thin margin
  visible** — it's why the disruption hurts. Consider a small sparkline of demand history
  (`fixture-demand-PART-1003.json`) in the expanded row.

### Section 2 — The Disruption (the interaction)
The user picks a SKU and a new lead time, then hits **Re-plan**.

- Provide **both** input modes:
  - **Structured:** a SKU dropdown + a lead-time number input. (Wire this to `/api/disrupt`.)
  - **Natural language:** a text box, pre-filled with
    *"Kraus emailed — PART-1003 is going from 3 weeks to 6 weeks."* (Wire this to `/api/agent`.)
- Show a loading state: **the real solve takes 10–30 seconds.** Do not let it look frozen.
  Show what's happening: *"Re-optimizing 20 parts… running 5 optimizations and 1,000
  simulations."* This wait is a feature — show the work.

### Section 3 — The Answer (the hero — spend your design budget here)

Three stacked blocks:

**3a. The headline**
> **This delay costs $808,203** — provably between $799,241 and $816,619.
> Badge: `SOLVER STATUS: OPTIMAL`

**3b. THE REALLOCATION — this is the money shot.** Build this carefully.

Visualize `order_changes_week0`. A **diverging horizontal bar chart**, sorted by
`|cash_delta_dollars|`:
- PART-1003 bar goes **right** (+$85,812) — color it as the *cause* (e.g. amber/accent).
- PART-1012 (−$60,412), PART-1000 (−$25,908) go **left** — these are the *victims*.
- Label the axis in **dollars**, not units. The story is about money.

Directly under it, pin the punchline as three big numbers:
```
cash before: $361,132     cash after: $361,134     BUDGET CAP: $361,135
```
with a caption: **"One part got late. 17 of 20 parts had their orders rewritten — because
the budget didn't grow. Paying for PART-1003 means cancelling someone else."**

Also show the focus part's 12-week schedule (`focus_part_schedule`) as a before/after
grouped bar chart — the "buy 1,067 now instead of 298" moment.

**3c. The binding constraint**
Render `probes[]` as bars showing `recovered_dollars`, **with the provable range as an
error bar** (`provable_low` → `provable_high`). This is unusual and it's the point: *we
show our error bars.*

- If `binding_constraint.proven === true` → badge the winner **`BINDING — PROVEN`**, and add
  a caption explaining *why* it's proven: *"Its worst case ($322,458) still beats the
  runner-up's best case ($79,231)."*
- If `false` → **no badge.** Show *"Cannot name a bottleneck at this tolerance."*

Then the simulation: fill rate **median 81.2%**, bad case (p10) **80.4%**, from 1,000
sampled futures. A simple distribution/gauge. Emphasize p10 — *"even in a bad week."*

### Section 4 — The Evidence (why anyone should believe this)
From `fixture-backtest.json`. Two bars, side by side:

| | Cost | Fill rate |
|---|---|---|
| `(s,Q)` rule — what an ERP runs | $2,021,032 | 77.9% |
| **This solver** | **$1,329,961** | **84.4%** |

Headline: **"Saves $691,071 and serves 6.5 points more demand — cheaper *and* better
service, not a trade-off."**

Include the honest caveat as body text (it makes the claim more credible, not less):
> *With slack cash, the optimizer only ties the simple rule. Its advantage appears when the
> cash budget binds and it must ration across parts — which a per-part rule cannot do.*

If `AgentResult.trace_url` exists, show a **"View the agent's trace"** link.

---

## 6. Design direction

- **Industrial / operations console**, not a consumer SaaS landing page. Think control
  room: dense, precise, trustworthy. Cool steel neutrals; **one** warm accent (copper/amber)
  reserved for the *decision* (the solver's output, the binding constraint).
- Semantic color is **separate** from the accent: green = good/recovered, red = cut/at-risk.
- **Tabular numerals everywhere** (`font-variant-numeric: tabular-nums`). Money must align.
- Money: always `$1,234,567` with thousands separators. Never raw floats.
- Dark **and** light mode (Chakra handles this — don't fight it).
- Responsive: charts scroll horizontally in their own container; the page body never scrolls
  sideways.
- Empty/loading/error states for every panel. The 30-second solve **will** be seen.

---

## 7. Non-goals (do not build these)

- No auth, no multi-tenancy, no user accounts.
- No editing the parts data. It's read-only.
- No "add a new part" flow.
- No mobile-first design (desktop demo; just don't let it break on a tablet).
- No animation flourishes. This is a serious operations tool.
- **Do not reimplement any math in TypeScript.** Every number comes from the API. If you
  find yourself computing a cost in the frontend, stop — that's the backend's job, and
  duplicating it is how the demo starts lying.

---

## 8. Acceptance criteria

- [ ] `npm install && npm run dev` works from a clean clone.
- [ ] All four sections render from the fixture JSON with **zero** invented numbers.
- [ ] Every fetch lives in a TanStack Query hook under `src/api/`, so swapping fixtures for
      HTTP is a one-file change per hook.
- [ ] `disruption_cost_dollars: null` renders the honest "not provable" message (test it by
      editing the fixture).
- [ ] `binding_constraint.proven: false` renders **no** winner badge (test it by editing the
      fixture).
- [ ] The provable range is visible next to the cost AND as error bars on the probes.
- [ ] The reallocation chart makes it obvious that PART-1003's gain is other parts' loss,
      under a fixed budget.
- [ ] Light and dark mode both legible.
- [ ] A 20-second loading state exists and explains what's happening.

**The demo is a success if a viewer who has never seen this can watch it once and say:
"Ah — the money is fixed, so helping one part means starving another. And the tool tells me
cash is the thing to go fix."**

---

## 9. How this plugs into the backend later (context, not your job)

The backend today is a Python package + CLI (`reorder generate|solve|backtest|demo`) and a
Pydantic AI agent. It has **no HTTP layer yet.** A thin FastAPI wrapper will be added
exposing exactly the endpoints in §4:

| Endpoint | Backend function it wraps |
|---|---|
| `GET /api/parts` | reads `data/parts.csv` |
| `GET /api/parts/:sku/demand` | reads `data/demand_history.csv` |
| `POST /api/disrupt` | `scenario.with_lead_time` → `solver.solve_reorder` → `probes.probe_constraints` → `simulate.simulate` → `diff.diff_plans` |
| `GET /api/backtest` | `baseline.backtest` |
| `POST /api/agent` | `agent.run_disruption` (needs `OPENAI_API_KEY`) |

Because the fixtures were generated *from those exact functions*, the shapes already match.

**Solve latency is real: 10–30 seconds** for `/api/disrupt` (it runs 5 optimizations plus
1,000 simulations). Design for it. `/api/agent` adds ~2 LLM round trips on top.
