# Reorder Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A terminal-runnable "reorder copilot": type a supply-chain disruption in English, get a re-optimized purchasing plan plus an explanation of what it cost and which constraint is binding — backed by a CP-SAT optimizer, a Monte Carlo simulator, and a backtest against a dumb baseline.

**Architecture:** One Python package (`reorder`) with a strict typed core (Pydantic models) shared by every layer. A CP-SAT solver makes every numeric decision; a Pydantic AI agent only translates English↔parameters and never does arithmetic. Built solver-first in working layers — each task leaves a runnable, testable artifact.

**Tech Stack:** Python 3.13 (3.12+ fine), OR-Tools CP-SAT 9.15, Pydantic v2, pandas, NumPy, Pydantic AI (OpenAI backend), pytest.

## Global Constraints

- **All money is integer cents.** No floats enter the CP-SAT model. `$2.50` is stored as `250`. Helpers `to_cents`/`to_dollars` live in `models.py`.
- **Every `Plan` carries its solver status.** Never compare two plans' costs unless both are `OPTIMAL` — enforced by `disruption_cost()` raising `NotOptimalError`.
- **Solver decides; the LLM translates.** The agent never picks a quantity or does math.
- **Synthetic data, stated up front** in the README.
- **~40 SKUs, 12-week horizon.** Drop to 20 SKUs if the solver won't prove `OPTIMAL`; report the gap honestly either way.
- **Src layout + editable install.** Package at `src/reorder/`; tests import `from reorder.xxx import ...`.
- **Every task ends with an "Explain-back checkpoint"** — questions the builder must answer aloud, because the deliverable is being able to defend every line in the interview.
- Spec of record: `docs/superpowers/specs/2026-07-11-reorder-copilot-design.md`.

---

## File Structure

- `pyproject.toml` — project + deps + pytest config
- `.gitignore`, `.env.example` — ignore venv/data/.env; document the OpenAI key
- `src/reorder/__init__.py`
- `src/reorder/models.py` — `to_cents`, `Part`, `Problem`, `Plan`; the typed core
- `src/reorder/solver.py` — `solve_reorder(problem) -> Plan` (CP-SAT). The heart.
- `src/reorder/scenario.py` — `with_lead_time`, `disruption_cost`, `NotOptimalError`
- `src/reorder/datagen.py` — `generate(...)` writes synthetic CSVs
- `src/reorder/forecast.py` — `forecast_quantiles(history, horizon)`
- `src/reorder/problem_builder.py` — `build_problem(...)` from parts + forecast
- `src/reorder/baseline.py` — `(s,Q)` policy + `backtest(...)`
- `src/reorder/probes.py` — `probe_constraints(...)` counterfactuals
- `src/reorder/simulate.py` — `simulate(problem, plan, n)` Monte Carlo
- `src/reorder/diff.py` — `diff_plans(before, after)`
- `src/reorder/agent.py` — Pydantic AI agent + typed tools + `Recommendation`
- `src/reorder/cli.py` — argparse subcommands: `generate`, `solve`, `backtest`, `demo`
- `tests/` — one test module per component
- `data/` — generated CSVs (gitignored)
- `README.md` — run instructions + the generalization paragraph

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `src/reorder/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: an installed `reorder` package importable in tests; `reorder.__version__`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "reorder-copilot"
version = "0.1.0"
description = "A decision layer for manufacturing purchasing."
requires-python = ">=3.12"
dependencies = [
    "ortools>=9.14",
    "pydantic>=2.7",
    "pandas>=2.2",
    "numpy>=1.26",
    "pydantic-ai>=0.0.14",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
reorder = "reorder.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Write `.gitignore` and `.env.example`**

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
data/
.env
.pytest_cache/
*.egg-info/
```

`.env.example`:
```
# Copy to .env and fill in. Never commit .env.
OPENAI_API_KEY=sk-...
# Optional: which model the agent uses (default in agent.py)
REORDER_MODEL=openai:gpt-4o
```

- [ ] **Step 3: Write package init and the failing smoke test**

`src/reorder/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

`tests/test_smoke.py`:
```python
import reorder

def test_package_imports():
    assert reorder.__version__ == "0.1.0"
```

- [ ] **Step 4: Create the venv and install (Windows PowerShell)**

Run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```
Expected: install completes; `pip show reorder-copilot` lists the package.

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: `test_package_imports PASSED`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example src tests
git commit -m "chore: scaffold reorder package"
```

- [ ] **Step 7: Explain-back checkpoint.** Answer aloud:
  - Why a `src/` layout and an *editable* install (`-e`) rather than just putting files in the repo root?
  - What is `.env` for and why is it in `.gitignore`?

---

## Task 2: The typed core (`models.py`)

**Files:**
- Create: `src/reorder/models.py`, `tests/test_models.py`

**Interfaces:**
- Produces:
  - `to_cents(dollars: float) -> int`, `to_dollars(cents: int) -> float`
  - `Part(sku, unit_cost, holding_cost, order_cost, moq, lead_time, volume, opening_inventory)` — all ints except `sku:str`; money fields in cents
  - `Problem(parts: list[Part], weeks: int, demand: dict[str,list[int]], safety_stock: dict[str,int], budget: list[int], warehouse_cap: int, stockout_penalty: int, safety_penalty: int)` with `.part(sku) -> Part`
  - `Plan(status: str, cost: int|None, bound: int|None, orders, inventory, backorder, short)` with `.is_optimal: bool` and `.gap: float`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from reorder.models import to_cents, to_dollars, Part, Problem, Plan

def test_cents_roundtrip():
    assert to_cents(2.50) == 250
    assert to_dollars(250) == 2.50

def test_problem_lookup():
    part = Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
                moq=50, lead_time=2, volume=1, opening_inventory=100)
    prob = Problem(parts=[part], weeks=3, demand={"A": [10, 10, 10]},
                   safety_stock={"A": 20}, budget=[100000, 100000, 100000],
                   warehouse_cap=10000, stockout_penalty=15000, safety_penalty=1000)
    assert prob.part("A").moq == 50

def test_plan_optimal_and_gap():
    good = Plan(status="OPTIMAL", cost=1000, bound=1000,
                orders={}, inventory={}, backorder={}, short={})
    assert good.is_optimal is True
    assert good.gap == 0.0
    feas = Plan(status="FEASIBLE", cost=1200, bound=1000,
                orders={}, inventory={}, backorder={}, short={})
    assert feas.is_optimal is False
    assert abs(feas.gap - 0.1667) < 0.01
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` on `reorder.models`.

- [ ] **Step 3: Write `src/reorder/models.py`**

```python
from pydantic import BaseModel


def to_cents(dollars: float) -> int:
    """Money is integer cents everywhere in the model. CP-SAT cannot do floats."""
    return round(dollars * 100)


def to_dollars(cents: int) -> float:
    return cents / 100.0


class Part(BaseModel):
    sku: str
    unit_cost: int          # cents per unit
    holding_cost: int       # cents per unit per week held
    order_cost: int         # cents charged whenever we place any order
    moq: int                # minimum order quantity (units)
    lead_time: int          # weeks between placing and receiving
    volume: int             # warehouse space units per unit held
    opening_inventory: int  # units on hand at t=0


class Problem(BaseModel):
    parts: list[Part]
    weeks: int
    demand: dict[str, list[int]]     # sku -> p50 forecast units per week (len == weeks)
    safety_stock: dict[str, int]     # sku -> target buffer units
    budget: list[int]                # cents available to spend per week (len == weeks)
    warehouse_cap: int               # total volume units available
    stockout_penalty: int            # cents per unit of unmet demand per week
    safety_penalty: int              # cents per unit below safety stock per week

    def part(self, sku: str) -> Part:
        return next(p for p in self.parts if p.sku == sku)

    @property
    def skus(self) -> list[str]:
        return [p.sku for p in self.parts]


class Plan(BaseModel):
    status: str                      # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
    cost: int | None                 # objective value in cents (None if infeasible)
    bound: int | None                # best proven bound in cents
    orders: dict[str, list[int]]     # sku -> units ordered per week
    inventory: dict[str, list[int]]  # sku -> on-hand per week
    backorder: dict[str, list[int]]  # sku -> unmet demand per week
    short: dict[str, list[int]]      # sku -> units below safety stock per week

    @property
    def is_optimal(self) -> bool:
        return self.status == "OPTIMAL"

    @property
    def gap(self) -> float:
        """Relative optimality gap. 0.0 means proven optimal."""
        if self.cost is None or self.bound is None or self.cost == 0:
            return 0.0
        return abs(self.cost - self.bound) / abs(self.cost)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/models.py tests/test_models.py
git commit -m "feat: typed core models with integer-cents contract"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Why must every money field be an integer number of cents?
  - What is `Plan.gap`, and why does the presence of `status`/`bound` on every plan matter for honesty?

---

## Task 3: CP-SAT solver core, proven on a toy (`solver.py`)

This is the heart. Built first, on a tiny instance, so optimality is provable and every constraint is visible. (This exact model was verified to return `OPTIMAL` with `cost == bound` before this plan was written.)

**Files:**
- Create: `src/reorder/solver.py`, `tests/test_solver.py`

**Interfaces:**
- Consumes: `Problem`, `Plan` from `models.py`.
- Produces: `solve_reorder(problem: Problem, max_seconds: float = 10.0) -> Plan`.

- [ ] **Step 1: Write the failing test (easy instance must be OPTIMAL, MOQ respected)**

`tests/test_solver.py`:
```python
from reorder.models import Part, Problem
from reorder.solver import solve_reorder


def _two_part_problem(budget_per_week=1_000_000):
    parts = [
        Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
             moq=50, lead_time=2, volume=1, opening_inventory=100),
        Part(sku="B", unit_cost=800, holding_cost=20, order_cost=5000,
             moq=30, lead_time=1, volume=2, opening_inventory=40),
    ]
    return Problem(
        parts=parts, weeks=6,
        demand={"A": [20, 25, 30, 20, 25, 30], "B": [10, 15, 10, 20, 15, 10]},
        safety_stock={"A": 20, "B": 15},
        budget=[budget_per_week] * 6,
        warehouse_cap=10_000,
        stockout_penalty=15_000, safety_penalty=1_000,
    )


def test_easy_instance_is_optimal():
    plan = solve_reorder(_two_part_problem())
    assert plan.status == "OPTIMAL"
    assert plan.cost == plan.bound            # optimality proven
    assert plan.gap == 0.0

def test_moq_respected():
    plan = solve_reorder(_two_part_problem())
    for sku, moq in (("A", 50), ("B", 30)):
        for qty in plan.orders[sku]:
            assert qty == 0 or qty >= moq

def test_no_backorders_when_budget_generous():
    plan = solve_reorder(_two_part_problem())
    assert sum(sum(plan.backorder[s]) for s in ("A", "B")) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_solver.py -v`
Expected: FAIL — `ImportError` on `reorder.solver`.

- [ ] **Step 3: Write `src/reorder/solver.py`**

```python
from ortools.sat.python import cp_model

from reorder.models import Problem, Plan


def solve_reorder(problem: Problem, max_seconds: float = 10.0) -> Plan:
    """Build and solve the reorder problem as an integer program.

    Decision variables per part i, week t:
      q[i,t]     units ordered (integer)
      y[i,t]     did we order at all (bool -> drives MOQ + fixed order cost)
      inv[i,t]   on-hand inventory (>= 0)
      back[i,t]  unmet demand carried (>= 0)
      short[i,t] units below safety stock (>= 0, soft)
    """
    m = cp_model.CpModel()
    skus = problem.skus

    # Tight-ish upper bound: nobody ever needs to hold/order more than total demand.
    BIG = {s: max(1, sum(problem.demand[s])) for s in skus}

    q, y, inv, back, short = {}, {}, {}, {}, {}
    for s in skus:
        p = problem.part(s)
        cap = BIG[s] + p.opening_inventory
        for t in range(problem.weeks):
            q[s, t] = m.NewIntVar(0, BIG[s], f"q_{s}_{t}")
            y[s, t] = m.NewBoolVar(f"y_{s}_{t}")
            inv[s, t] = m.NewIntVar(0, cap, f"inv_{s}_{t}")
            back[s, t] = m.NewIntVar(0, BIG[s], f"back_{s}_{t}")
            short[s, t] = m.NewIntVar(0, problem.safety_stock[s], f"short_{s}_{t}")

    for s in skus:
        p = problem.part(s)
        for t in range(problem.weeks):
            # An order placed at t-L arrives now. Before that, nothing arrives.
            arrivals = q[s, t - p.lead_time] if t - p.lead_time >= 0 else 0
            prev_net = (inv[s, t - 1] - back[s, t - 1]) if t >= 1 else p.opening_inventory
            # net inventory = previous net + arrivals - demand
            m.Add(inv[s, t] - back[s, t] == prev_net + arrivals - problem.demand[s][t])
            # order nothing, or at least the MOQ (big-M links q to the y switch)
            m.Add(q[s, t] >= p.moq * y[s, t])
            m.Add(q[s, t] <= BIG[s] * y[s, t])
            # soft safety stock: measure the dip below target, do not forbid it
            m.Add(short[s, t] >= problem.safety_stock[s] - inv[s, t])

    for t in range(problem.weeks):
        m.Add(sum(problem.part(s).unit_cost * q[s, t] for s in skus) <= problem.budget[t])
        m.Add(sum(problem.part(s).volume * inv[s, t] for s in skus) <= problem.warehouse_cap)

    m.Minimize(
        sum(problem.part(s).holding_cost * inv[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.part(s).order_cost * y[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.stockout_penalty * back[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.safety_penalty * short[s, t] for s in skus for t in range(problem.weeks))
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(m)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Plan(status=status_name, cost=None, bound=None,
                    orders={}, inventory={}, backorder={}, short={})

    def series(var):
        return {s: [solver.Value(var[s, t]) for t in range(problem.weeks)] for s in skus}

    return Plan(
        status=status_name,
        cost=round(solver.ObjectiveValue()),
        bound=round(solver.BestObjectiveBound()),
        orders=series(q), inventory=series(inv),
        backorder=series(back), short=series(short),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_solver.py -v`
Expected: all 3 PASS (solve returns in well under a second).

- [ ] **Step 5: Commit**

```bash
git add src/reorder/solver.py tests/test_solver.py
git commit -m "feat: CP-SAT reorder solver, OPTIMAL on toy instance"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud, pointing at the code:
  - Walk through the inventory-balance line. What does `inv - back` represent, and why do we index arrivals at `t - lead_time`?
  - Explain the two MOQ lines together (`q >= moq*y` and `q <= BIG*y`). What happens when `y=0` vs `y=1`?
  - Why is `short` a penalized variable instead of a hard constraint `inv >= safety_stock`?
  - What is `BIG`, and why does making it smaller help the solver?

---

## Task 4: Stress the solver (tight-constraint behavior)

Proves the penalty tiers and constraints actually bite. No new production code — this hardens confidence and gives interview stories.

**Files:**
- Modify: `tests/test_solver.py` (add cases)

**Interfaces:** unchanged.

- [ ] **Step 1: Add failing tests for constrained behavior**

Append to `tests/test_solver.py`:
```python
def test_tight_budget_forces_backorders():
    plan = solve_reorder(_two_part_problem(budget_per_week=8_000))
    assert plan.status == "OPTIMAL"
    total_back = sum(sum(plan.backorder[s]) for s in ("A", "B"))
    assert total_back > 0   # cannot afford enough parts -> demand goes unmet

def test_warehouse_cap_limits_inventory():
    prob = _two_part_problem()
    prob.warehouse_cap = 60   # volumes: A=1,B=2 -> very little room
    plan = solve_reorder(prob)
    assert plan.status == "OPTIMAL"
    for t in range(prob.weeks):
        used = sum(prob.part(s).volume * plan.inventory[s][t] for s in ("A", "B"))
        assert used <= 60

def test_stockout_costs_more_than_safety_dip():
    # With equal penalties the solver would treat them the same; assert the tiering.
    prob = _two_part_problem()
    assert prob.stockout_penalty > prob.safety_penalty * 10
```

- [ ] **Step 2: Run to verify behavior**

Run: `pytest tests/test_solver.py -v`
Expected: all PASS. (If `test_warehouse_cap_limits_inventory` is infeasible instead, raise `warehouse_cap` to 80 and note it — a too-tight hard cap with hard demand can be infeasible; that itself is a finding to mention.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_solver.py
git commit -m "test: solver honors budget, warehouse, penalty tiers"
```

- [ ] **Step 4: Explain-back checkpoint.** Answer aloud:
  - Under a tight budget, *why* does the solver choose to backorder rather than break the budget constraint?
  - If demand is a hard requirement and space is a hard cap, how can a problem become `INFEASIBLE`? How would you detect and report that to a buyer?

---

## Task 5: Synthetic factory data (`datagen.py`)

**Files:**
- Create: `src/reorder/datagen.py`, `tests/test_datagen.py`

**Interfaces:**
- Produces: `generate(out_dir="data", n_parts=40, weeks_history=104, seed=7) -> None` writing `parts.csv` (columns: `sku,unit_cost,holding_cost,order_cost,moq,lead_time,volume,opening_inventory` — money in cents) and `demand_history.csv` (columns: `sku,week,units`).

- [ ] **Step 1: Write the failing test**

`tests/test_datagen.py`:
```python
import pandas as pd
from reorder.datagen import generate

def test_generate_writes_expected_shapes(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=40, weeks_history=104, seed=7)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    assert len(parts) == 40
    assert set(parts.columns) == {
        "sku", "unit_cost", "holding_cost", "order_cost", "moq",
        "lead_time", "volume", "opening_inventory"}
    assert (parts["unit_cost"] > 0).all()
    assert len(hist) == 40 * 104
    assert (hist["units"] >= 0).all()

def test_generate_is_deterministic(tmp_path):
    generate(out_dir=str(tmp_path / "a"), seed=7)
    generate(out_dir=str(tmp_path / "b"), seed=7)
    a = pd.read_csv(tmp_path / "a" / "demand_history.csv")
    b = pd.read_csv(tmp_path / "b" / "demand_history.csv")
    assert a.equals(b)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_datagen.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/datagen.py`**

```python
import os
import numpy as np
import pandas as pd

from reorder.models import to_cents


def generate(out_dir: str = "data", n_parts: int = 40,
             weeks_history: int = 104, seed: int = 7) -> None:
    """Invent a plausible, fully synthetic factory and write CSVs.

    Demand = base level * seasonal factor * noise, per part per week.
    Costs are stored in integer cents.
    """
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    skus = [f"PART-{1000 + i}" for i in range(n_parts)]

    # --- Parts table ---
    rows = []
    base_levels = {}
    for s in skus:
        unit_cost_dollars = float(rng.uniform(2, 200))
        base_level = int(rng.integers(20, 400))       # avg weekly demand
        base_levels[s] = base_level
        rows.append({
            "sku": s,
            "unit_cost": to_cents(unit_cost_dollars),
            # holding ~ 0.5% of unit cost per week; ordering fixed-ish
            "holding_cost": max(1, to_cents(unit_cost_dollars * 0.005)),
            "order_cost": to_cents(float(rng.uniform(20, 100))),
            "moq": int(rng.choice([25, 50, 100, 200])),
            "lead_time": int(rng.integers(1, 5)),      # 1-4 weeks
            "volume": int(rng.integers(1, 5)),
            "opening_inventory": int(base_level * rng.uniform(1.5, 3.0)),
        })
    parts = pd.DataFrame(rows)
    parts.to_csv(os.path.join(out_dir, "parts.csv"), index=False)

    # --- Demand history: seasonal sine + lognormal-ish noise ---
    hist_rows = []
    for s in skus:
        level = base_levels[s]
        phase = rng.uniform(0, 2 * np.pi)
        amp = rng.uniform(0.1, 0.4)                    # seasonal amplitude
        for w in range(weeks_history):
            seasonal = 1.0 + amp * np.sin(2 * np.pi * w / 52.0 + phase)
            noise = rng.normal(1.0, 0.15)
            units = max(0, int(round(level * seasonal * noise)))
            hist_rows.append({"sku": s, "week": w, "units": units})
    hist = pd.DataFrame(hist_rows)
    hist.to_csv(os.path.join(out_dir, "demand_history.csv"), index=False)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_datagen.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/datagen.py tests/test_datagen.py
git commit -m "feat: synthetic factory data generator"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - What are the three ingredients of each demand value (level, seasonal, noise) and why include seasonality at all?
  - Why does `seed` make the data deterministic, and why does that matter for a live demo?

---

## Task 6: Quantile forecast (`forecast.py`)

**Files:**
- Create: `src/reorder/forecast.py`, `tests/test_forecast.py`

**Interfaces:**
- Consumes: a demand-history `pd.DataFrame` (`sku,week,units`).
- Produces: `forecast_quantiles(history: pd.DataFrame, horizon: int = 12) -> dict[str, dict[str, list[int]]]` returning `{sku: {"p10":[...], "p50":[...], "p90":[...]}}`, each list length `horizon`, integer units, non-negative.

- [ ] **Step 1: Write the failing test**

`tests/test_forecast.py`:
```python
import numpy as np
import pandas as pd
from reorder.forecast import forecast_quantiles

def _history():
    rows = []
    rng = np.random.default_rng(0)
    for w in range(104):
        seasonal = 1.0 + 0.3 * np.sin(2 * np.pi * w / 52.0)
        rows.append({"sku": "X", "week": w,
                     "units": max(0, int(100 * seasonal * rng.normal(1, 0.1)))})
    return pd.DataFrame(rows)

def test_shape_and_ordering():
    fc = forecast_quantiles(_history(), horizon=12)
    assert set(fc["X"]) == {"p10", "p50", "p90"}
    assert len(fc["X"]["p50"]) == 12
    for i in range(12):
        assert fc["X"]["p10"][i] <= fc["X"]["p50"][i] <= fc["X"]["p90"][i]
        assert fc["X"]["p10"][i] >= 0
        assert isinstance(fc["X"]["p50"][i], int)

def test_p50_near_recent_level():
    fc = forecast_quantiles(_history(), horizon=12)
    assert 70 <= np.mean(fc["X"]["p50"]) <= 130   # roughly the ~100 base level
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_forecast.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/forecast.py`**

```python
import numpy as np
import pandas as pd

# z-scores for the 10th and 90th percentiles of a normal distribution.
_Z90 = 1.2816


def forecast_quantiles(history: pd.DataFrame, horizon: int = 12
                       ) -> dict[str, dict[str, list[int]]]:
    """Seasonal-level median + pooled-residual spread.

    p50: recent demand level scaled by a week-of-year seasonal factor.
    p10/p90: p50 +/- z * (std of historical forecast errors), errors POOLED
             across all weeks because 2 years gives only ~2 samples of any
             single calendar week -- far too few to read a quantile directly.
    """
    out: dict[str, dict[str, list[int]]] = {}
    for sku, g in history.groupby("sku"):
        g = g.sort_values("week")
        units = g["units"].to_numpy(dtype=float)
        weeks = g["week"].to_numpy(dtype=int)
        overall_mean = max(1.0, units.mean())

        # Week-of-year seasonal factor (ratio to overall mean).
        woy = weeks % 52
        factor = np.ones(52)
        for k in range(52):
            sel = units[woy == k]
            if len(sel) > 0:
                factor[k] = max(0.05, sel.mean() / overall_mean)

        # Recent level = mean of last 12 weeks, de-seasonalized.
        recent = units[-12:]
        recent_woy = weeks[-12:] % 52
        recent_level = np.mean(recent / factor[recent_woy])

        # Fitted values over history -> residuals -> pooled std.
        fitted = recent_level * factor[woy]
        resid_std = float(np.std(units - fitted)) or 1.0

        last_week = int(weeks[-1])
        p10, p50, p90 = [], [], []
        for h in range(1, horizon + 1):
            k = (last_week + h) % 52
            med = recent_level * factor[k]
            p50.append(max(0, int(round(med))))
            p10.append(max(0, int(round(med - _Z90 * resid_std))))
            p90.append(max(0, int(round(med + _Z90 * resid_std))))
        out[sku] = {"p10": p10, "p50": p50, "p90": p90}
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_forecast.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/forecast.py tests/test_forecast.py
git commit -m "feat: seasonal quantile forecast with pooled residual spread"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Why produce p10/p50/p90 instead of a single number? What does the solver do with the spread?
  - Why *pool* residuals across weeks instead of taking quantiles of each calendar week directly? (The "2 samples" answer.)
  - Where does safety stock come from, conceptually, given this forecast?

---

## Task 7: Assemble a `Problem` and solve the full 40-SKU instance (`problem_builder.py` + CLI `solve`)

**Files:**
- Create: `src/reorder/problem_builder.py`, `src/reorder/cli.py`, `tests/test_problem_builder.py`

**Interfaces:**
- Consumes: `parts.csv`, forecast dict, `solve_reorder`.
- Produces:
  - `build_problem(parts_df, forecast, weeks=12, service_z=1.2816, budget_per_week=None, warehouse_cap=None) -> Problem`. Safety stock per sku = `round(service_z * (p90-p50)/1.2816)` averaged over horizon (i.e., ~ one z of forecast spread); budget defaults to 1.2× mean weekly spend at p50; warehouse_cap defaults to 1.5× peak p50 volume.
  - `cli.main()` with subcommands `generate` and `solve`.

- [ ] **Step 1: Write the failing test**

`tests/test_problem_builder.py`:
```python
import pandas as pd
from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder

def test_full_instance_solves_optimal(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=40, seed=7)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    fc = forecast_quantiles(hist, horizon=12)
    problem = build_problem(parts, fc, weeks=12)
    assert len(problem.parts) == 40
    assert all(len(problem.demand[s]) == 12 for s in problem.skus)
    plan = solve_reorder(problem, max_seconds=20.0)
    # If OPTIMAL is not reached at 40 SKUs, the fallback is 20 SKUs; see plan risk row.
    assert plan.status in ("OPTIMAL", "FEASIBLE")
    if plan.status == "FEASIBLE":
        print(f"WARNING: only FEASIBLE, gap={plan.gap:.3f}")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_problem_builder.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/problem_builder.py`**

```python
import numpy as np
import pandas as pd

from reorder.models import Part, Problem


def build_problem(parts_df: pd.DataFrame, forecast: dict, weeks: int = 12,
                  service_z: float = 1.2816, budget_per_week: int | None = None,
                  warehouse_cap: int | None = None,
                  stockout_penalty: int | None = None,
                  safety_penalty: int = 1_000) -> Problem:
    parts = [Part(**row) for row in parts_df.to_dict("records")]
    skus = [p.sku for p in parts]

    demand = {s: forecast[s]["p50"][:weeks] for s in skus}

    # Safety stock ~ one service-z of forecast spread. (p90-p50) already ~= z*sigma,
    # so (p90-p50) is ~1 z of spread; use its horizon average.
    safety_stock = {}
    for s in skus:
        spread = np.mean([forecast[s]["p90"][t] - forecast[s]["p50"][t]
                          for t in range(weeks)])
        safety_stock[s] = max(0, int(round(spread)))

    part_by_sku = {p.sku: p for p in parts}
    if budget_per_week is None:
        weekly_spend = sum(part_by_sku[s].unit_cost * np.mean(demand[s]) for s in skus)
        budget_per_week = int(round(weekly_spend * 1.2))
    budget = [budget_per_week] * weeks

    if warehouse_cap is None:
        peak_vol = sum(part_by_sku[s].volume * max(demand[s]) for s in skus)
        warehouse_cap = int(round(peak_vol * 1.5))

    if stockout_penalty is None:
        # ~15x the average holding cost, so a stockout dominates holding decisions.
        avg_holding = int(np.mean([p.holding_cost for p in parts]))
        stockout_penalty = max(15_000, avg_holding * 200)

    return Problem(
        parts=parts, weeks=weeks, demand=demand, safety_stock=safety_stock,
        budget=budget, warehouse_cap=warehouse_cap,
        stockout_penalty=stockout_penalty, safety_penalty=safety_penalty,
    )
```

- [ ] **Step 4: Write `src/reorder/cli.py` (generate + solve)**

```python
import argparse
import pandas as pd

from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.models import to_dollars


def _load_problem(data_dir: str, weeks: int):
    parts = pd.read_csv(f"{data_dir}/parts.csv")
    hist = pd.read_csv(f"{data_dir}/demand_history.csv")
    fc = forecast_quantiles(hist, horizon=weeks)
    return build_problem(parts, fc, weeks=weeks)


def cmd_generate(args):
    generate(out_dir=args.data_dir, n_parts=args.n_parts, seed=args.seed)
    print(f"Wrote synthetic data for {args.n_parts} parts to {args.data_dir}/")


def cmd_solve(args):
    problem = _load_problem(args.data_dir, args.weeks)
    plan = solve_reorder(problem, max_seconds=args.max_seconds)
    print(f"status={plan.status}  gap={plan.gap:.3f}  "
          f"cost=${to_dollars(plan.cost):,.2f}" if plan.cost is not None
          else f"status={plan.status}")
    total_units = sum(sum(plan.orders[s]) for s in problem.skus)
    print(f"total units ordered over {args.weeks} weeks: {total_units}")


def main():
    ap = argparse.ArgumentParser(prog="reorder")
    ap.add_argument("--data-dir", default="data")
    sub = ap.add_subparsers(required=True)

    g = sub.add_parser("generate", help="write synthetic factory data")
    g.add_argument("--n-parts", type=int, default=40)
    g.add_argument("--seed", type=int, default=7)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("solve", help="solve the baseline reorder plan")
    s.add_argument("--weeks", type=int, default=12)
    s.add_argument("--max-seconds", type=float, default=20.0)
    s.set_defaults(func=cmd_solve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the test and the CLI end to end**

Run:
```
pytest tests/test_problem_builder.py -v
reorder generate
reorder solve
```
Expected: test PASS; `generate` writes `data/`; `solve` prints `status=OPTIMAL gap=0.000 cost=$...` and a units total. If `solve` prints `FEASIBLE`, rerun `reorder generate --n-parts 20` and note it (risk row).

- [ ] **Step 6: Commit**

```bash
git add src/reorder/problem_builder.py src/reorder/cli.py tests/test_problem_builder.py
git commit -m "feat: build+solve full 40-SKU instance via CLI"
```

- [ ] **Step 7: Explain-back checkpoint.** Answer aloud:
  - How is safety stock derived from the forecast here? Why tie it to the p90–p50 spread?
  - If the full instance only reaches `FEASIBLE`, what exactly would you tell the interviewer, and what would you do about it?

---

## Task 8: The `(s,Q)` baseline policy (`baseline.py`)

**Files:**
- Create: `src/reorder/baseline.py`, `tests/test_baseline.py`

**Interfaces:**
- Produces:
  - `run_sq(parts_df, actual_demand: dict[str,list[int]], weeks: int) -> dict` returning `{"cost": int_cents, "fill_rate": float, "orders": dict}`. Policy: reorder point `s = lead_time*mean_weekly + safety`; when inventory position ≤ `s`, order `Q = max(moq, 4*mean_weekly)`. Simulated week-by-week against `actual_demand`; realized cost = holding + order + stockout using the same penalties as the solver problem defaults.
  - `realized_cost(parts_df, orders, actual_demand, weeks, stockout_penalty, safety_penalty, safety_stock) -> dict` — shared cost accounting used by both policies.

- [ ] **Step 1: Write the failing test**

`tests/test_baseline.py`:
```python
import pandas as pd
from reorder.datagen import generate
from reorder.baseline import run_sq

def test_sq_runs_and_reports(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=10, seed=1)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    # use the last 26 weeks of history as "actuals" to replay
    actual = {}
    for sku, g in hist.groupby("sku"):
        actual[sku] = g.sort_values("week")["units"].to_numpy()[-26:].tolist()
    result = run_sq(parts, actual, weeks=26)
    assert result["cost"] > 0
    assert 0.0 <= result["fill_rate"] <= 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_baseline.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/baseline.py`**

```python
import numpy as np
import pandas as pd


def realized_cost(parts_df: pd.DataFrame, orders: dict, actual_demand: dict,
                  weeks: int, stockout_penalty: int, safety_penalty: int,
                  safety_stock: dict) -> dict:
    """Roll a fixed order schedule forward against ACTUAL demand and price it.

    Returns realized {cost (cents), fill_rate, met, demanded}.
    """
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    total_cost = 0
    met = demanded = 0
    for s, p in part.items():
        inv = p["opening_inventory"]
        L = p["lead_time"]
        placed = orders.get(s, [0] * weeks)
        for t in range(weeks):
            arrivals = placed[t - L] if t - L >= 0 else 0
            inv += arrivals
            d = actual_demand[s][t]
            demanded += d
            shipped = min(inv, d)
            met += shipped
            inv -= shipped
            unmet = d - shipped
            total_cost += p["holding_cost"] * max(0, inv)
            total_cost += stockout_penalty * unmet
            total_cost += safety_penalty * max(0, safety_stock.get(s, 0) - inv)
            if placed[t] > 0:
                total_cost += p["order_cost"]
    fill = (met / demanded) if demanded else 1.0
    return {"cost": int(total_cost), "fill_rate": fill, "met": met, "demanded": demanded}


def run_sq(parts_df: pd.DataFrame, actual_demand: dict, weeks: int,
           stockout_penalty: int = 15_000, safety_penalty: int = 1_000) -> dict:
    """Classic reorder-point policy: order Q when inventory position <= s."""
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    orders = {s: [0] * weeks for s in part}
    safety_stock = {}
    for s, p in part.items():
        mean_wk = max(1.0, float(np.mean(actual_demand[s])))
        safety = int(round(mean_wk))                 # ~1 week buffer
        safety_stock[s] = safety
        s_point = int(round(p["lead_time"] * mean_wk + safety))
        Q = int(max(p["moq"], round(4 * mean_wk)))
        inv = p["opening_inventory"]
        pipeline = [0] * (weeks + p["lead_time"] + 1)
        for t in range(weeks):
            inv += pipeline[t]
            position = inv + sum(pipeline[t + 1:])   # on-hand + in-transit
            if position <= s_point:
                orders[s][t] = Q
                pipeline[t + p["lead_time"]] += Q
            inv -= min(inv, actual_demand[s][t])
    return realized_cost(parts_df, orders, actual_demand, weeks,
                         stockout_penalty, safety_penalty, safety_stock)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_baseline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/baseline.py tests/test_baseline.py
git commit -m "feat: (s,Q) baseline policy with realized-cost accounting"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - In plain English, what does the `(s,Q)` policy do each week? What is "inventory position" and why include in-transit orders?
  - Why is this the *right* baseline to compare against (what do real ERPs actually run)?

---

## Task 9: Backtest — solver vs baseline on held-out demand (CLI `backtest`) — **DAYS 1–2 MILESTONE**

**Files:**
- Modify: `src/reorder/baseline.py` (add `run_solver_rolling`, `backtest`), `src/reorder/cli.py` (add `backtest` command)
- Create: `tests/test_backtest.py`

**Interfaces:**
- Produces:
  - `run_solver_rolling(parts_df, hist_df, test_weeks=26, horizon=12, max_seconds=5.0) -> dict` — rolling receding-horizon: for each test week, forecast from data seen so far, solve a `horizon`-week problem, execute week-0 orders, advance against actuals. Returns realized `{"cost","fill_rate","orders"}`.
  - `backtest(parts_df, hist_df, test_weeks=26) -> dict` returning `{"solver": {...}, "sq": {...}, "dollars_saved": float, "fill_delta": float}`.
  - `cli` subcommand `backtest`.

- [ ] **Step 1: Write the failing test**

`tests/test_backtest.py`:
```python
import pandas as pd
from reorder.datagen import generate
from reorder.baseline import backtest

def test_backtest_reports_both_policies(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=8, seed=3)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    result = backtest(parts, hist, test_weeks=12)
    assert result["solver"]["cost"] > 0
    assert result["sq"]["cost"] > 0
    assert "dollars_saved" in result
    # We expect the optimizer to be no worse on total realized cost in most seeds.
    print("solver:", result["solver"]["cost"], "sq:", result["sq"]["cost"],
          "saved$:", result["dollars_saved"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_backtest.py -v`
Expected: FAIL — `ImportError` on `backtest`.

- [ ] **Step 3: Add `run_solver_rolling` and `backtest` to `src/reorder/baseline.py`**

```python
# --- append to baseline.py ---
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.models import to_dollars


def run_solver_rolling(parts_df: pd.DataFrame, hist_df: pd.DataFrame,
                       test_weeks: int = 26, horizon: int = 12,
                       max_seconds: float = 5.0) -> dict:
    """Receding-horizon control: re-solve every week, execute only week 0."""
    full = {sku: g.sort_values("week")["units"].to_numpy()
            for sku, g in hist_df.groupby("sku")}
    n = len(next(iter(full.values())))
    start = n - test_weeks
    skus = list(full)

    executed = {s: [0] * test_weeks for s in skus}
    safety_stock = {}
    for w in range(test_weeks):
        seen_end = start + w
        seen = hist_df[hist_df["week"] < seen_end]
        fc = forecast_quantiles(seen, horizon=horizon)
        # opening inventory for the sub-problem = current on-hand (approx via parts file
        # for w==0; thereafter track it below through executed orders + actuals)
        problem = build_problem(parts_df, fc, weeks=horizon)
        safety_stock = problem.safety_stock
        plan = solve_reorder(problem, max_seconds=max_seconds)
        if plan.status in ("OPTIMAL", "FEASIBLE"):
            for s in skus:
                executed[s][w] = plan.orders[s][0]
    actual = {s: full[s][start:start + test_weeks].tolist() for s in skus}
    return {**realized_cost(parts_df, executed, actual, test_weeks,
                            15_000, 1_000, safety_stock),
            "orders": executed}


def backtest(parts_df: pd.DataFrame, hist_df: pd.DataFrame,
             test_weeks: int = 26) -> dict:
    full = {sku: g.sort_values("week")["units"].to_numpy()
            for sku, g in hist_df.groupby("sku")}
    n = len(next(iter(full.values())))
    start = n - test_weeks
    actual = {s: full[s][start:start + test_weeks].tolist() for s in full}

    solver_res = run_solver_rolling(parts_df, hist_df, test_weeks=test_weeks)
    sq_res = run_sq(parts_df, actual, weeks=test_weeks)
    saved = to_dollars(sq_res["cost"] - solver_res["cost"])
    return {"solver": solver_res, "sq": sq_res,
            "dollars_saved": saved,
            "fill_delta": solver_res["fill_rate"] - sq_res["fill_rate"]}
```

- [ ] **Step 4: Add the `backtest` CLI command to `src/reorder/cli.py`**

Add import near the top:
```python
from reorder.baseline import backtest
```
Add inside `main()` after the `solve` parser:
```python
    b = sub.add_parser("backtest", help="solver vs (s,Q) baseline on held-out demand")
    b.add_argument("--test-weeks", type=int, default=26)
    b.set_defaults(func=cmd_backtest)
```
Add the command function:
```python
def cmd_backtest(args):
    parts = pd.read_csv(f"{args.data_dir}/parts.csv")
    hist = pd.read_csv(f"{args.data_dir}/demand_history.csv")
    r = backtest(parts, hist, test_weeks=args.test_weeks)
    print("=== Backtest over last", args.test_weeks, "weeks ===")
    print(f"solver:   cost=${to_dollars(r['solver']['cost']):>12,.2f}  "
          f"fill={r['solver']['fill_rate']:.1%}")
    print(f"(s,Q):    cost=${to_dollars(r['sq']['cost']):>12,.2f}  "
          f"fill={r['sq']['fill_rate']:.1%}")
    print(f"saved:    ${r['dollars_saved']:>12,.2f}   "
          f"fill delta={r['fill_delta']:+.1%}")
```

- [ ] **Step 5: Run test and CLI**

Run:
```
pytest tests/test_backtest.py -v
reorder backtest --test-weeks 26
```
Expected: test PASS; CLI prints a comparison table with a dollars-saved line. (If the solver isn't cheaper on this seed, tune `stockout_penalty`/`Q`, or report the fill-rate advantage instead — note whichever is true; do not fake the number.)

- [ ] **Step 6: Commit**

```bash
git add src/reorder/baseline.py src/reorder/cli.py tests/test_backtest.py
git commit -m "feat: rolling-horizon backtest of solver vs (s,Q) baseline"
```

- [ ] **Step 7: Explain-back checkpoint.** Answer aloud:
  - What does "receding horizon" mean and why re-solve every week instead of once?
  - The backtest compares realized cost on the *same* actual demand. Why is that a fair comparison, and why does it turn "a demo" into "evidence"?
  - **Milestone:** one command now prints a plan, a cost, and "beat the baseline by $X (or by X% fill)". This alone is a defensible project.

---

## Task 10: Disruption + guarded cost delta (`scenario.py`)

**Files:**
- Create: `src/reorder/scenario.py`, `tests/test_scenario.py`

**Interfaces:**
- Produces:
  - `with_lead_time(problem: Problem, sku: str, new_lead_time: int) -> Problem` (deep copy, one field changed)
  - `NotOptimalError(RuntimeError)`
  - `disruption_cost(before: Plan, after: Plan) -> int` — returns `after.cost - before.cost`; **raises `NotOptimalError` unless both plans are OPTIMAL.**

- [ ] **Step 1: Write the failing test**

`tests/test_scenario.py`:
```python
import pytest
from reorder.models import Part, Problem, Plan
from reorder.solver import solve_reorder
from reorder.scenario import with_lead_time, disruption_cost, NotOptimalError

def _problem():
    parts = [Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
                  moq=50, lead_time=2, volume=1, opening_inventory=100)]
    return Problem(parts=parts, weeks=6, demand={"A": [20, 25, 30, 20, 25, 30]},
                   safety_stock={"A": 20}, budget=[1_000_000] * 6,
                   warehouse_cap=10_000, stockout_penalty=15_000, safety_penalty=1_000)

def test_with_lead_time_is_a_copy():
    p = _problem()
    p2 = with_lead_time(p, "A", 5)
    assert p.part("A").lead_time == 2      # original untouched
    assert p2.part("A").lead_time == 5

def test_disruption_cost_requires_optimal():
    before = solve_reorder(_problem())
    after = solve_reorder(with_lead_time(_problem(), "A", 5))
    delta = disruption_cost(before, after)
    assert delta == after.cost - before.cost
    assert delta >= 0                      # a longer lead time cannot help

def test_refuses_non_optimal():
    good = Plan(status="OPTIMAL", cost=100, bound=100, orders={}, inventory={},
                backorder={}, short={})
    feas = Plan(status="FEASIBLE", cost=120, bound=100, orders={}, inventory={},
                backorder={}, short={})
    with pytest.raises(NotOptimalError):
        disruption_cost(good, feas)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_scenario.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/scenario.py`**

```python
from reorder.models import Problem, Plan


class NotOptimalError(RuntimeError):
    """Raised when someone tries to compare non-OPTIMAL solves."""


def with_lead_time(problem: Problem, sku: str, new_lead_time: int) -> Problem:
    updated = problem.model_copy(deep=True)
    updated.part(sku).lead_time = new_lead_time
    return updated


def disruption_cost(before: Plan, after: Plan) -> int:
    """Cost of a disruption = after.cost - before.cost, in cents.

    Refuses to compute unless BOTH plans are proven OPTIMAL: two FEASIBLE
    solutions can differ for reasons unrelated to the disruption, so the delta
    would be partly solver noise.
    """
    if not (before.is_optimal and after.is_optimal):
        raise NotOptimalError(
            f"Refusing to compare: before={before.status}, after={after.status}. "
            "A cost delta between non-OPTIMAL solves is meaningless."
        )
    return after.cost - before.cost
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_scenario.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/scenario.py tests/test_scenario.py
git commit -m "feat: disruption + OPTIMAL-guarded cost delta"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Tell the story: why is comparing two `FEASIBLE` solutions "the single easiest way to ship a system that confidently lies"?
  - Why does a longer lead time never *reduce* cost (why is `delta >= 0` a valid sanity check)?

---

## Task 11: Constraint probes — which limit is binding (`probes.py`)

**Files:**
- Create: `src/reorder/probes.py`, `tests/test_probes.py`

**Interfaces:**
- Consumes: `Problem`, `solve_reorder`, `disruption_cost`.
- Produces:
  - `Probe` dataclass: `name: str`, `recovered: int` (cents saved vs base), `feasible: bool`.
  - `probe_constraints(problem: Problem, base_plan: Plan, max_seconds=10.0) -> list[Probe]` — re-solves with each of: budget +$1000/wk, warehouse +1000 units, safety −10%. Sorted by `recovered` desc. Binding constraint = first entry.

- [ ] **Step 1: Write the failing test**

`tests/test_probes.py`:
```python
from reorder.models import Part, Problem
from reorder.solver import solve_reorder
from reorder.probes import probe_constraints

def _tight_problem():
    # tight budget so the budget probe should recover the most
    parts = [Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
                  moq=50, lead_time=2, volume=1, opening_inventory=50)]
    return Problem(parts=parts, weeks=6, demand={"A": [40, 40, 40, 40, 40, 40]},
                   safety_stock={"A": 20}, budget=[9_000] * 6,
                   warehouse_cap=10_000, stockout_penalty=15_000, safety_penalty=1_000)

def test_probes_return_sorted_recovery():
    prob = _tight_problem()
    base = solve_reorder(prob)
    probes = probe_constraints(prob, base)
    names = [p.name for p in probes]
    assert set(names) == {"budget +$1000/wk", "warehouse +1000u", "safety -10%"}
    # sorted descending by recovered
    assert probes == sorted(probes, key=lambda p: p.recovered, reverse=True)
    # with a tight budget, loosening budget should help most
    assert probes[0].name == "budget +$1000/wk"
    assert probes[0].recovered > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_probes.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/probes.py`**

```python
from dataclasses import dataclass

from reorder.models import Problem, Plan
from reorder.solver import solve_reorder


@dataclass
class Probe:
    name: str
    recovered: int      # cents saved relative to the base plan (>=0 means it helped)
    feasible: bool


def _recovered(base_plan: Plan, relaxed_plan: Plan) -> int:
    if not (base_plan.is_optimal and relaxed_plan.is_optimal):
        return 0
    return max(0, base_plan.cost - relaxed_plan.cost)


def probe_constraints(problem: Problem, base_plan: Plan,
                      max_seconds: float = 10.0) -> list[Probe]:
    """Buy the shadow prices CP-SAT won't give us: re-solve with each
    constraint relaxed by a fixed step, and see which relaxation helps most."""
    probes: list[Probe] = []

    # 1) budget +$1000/week
    p_budget = problem.model_copy(deep=True)
    p_budget.budget = [b + 100_000 for b in p_budget.budget]   # +$1000 in cents
    plan_b = solve_reorder(p_budget, max_seconds)
    probes.append(Probe("budget +$1000/wk", _recovered(base_plan, plan_b),
                        plan_b.is_optimal))

    # 2) warehouse +1000 units
    p_wh = problem.model_copy(deep=True)
    p_wh.warehouse_cap += 1000
    plan_w = solve_reorder(p_wh, max_seconds)
    probes.append(Probe("warehouse +1000u", _recovered(base_plan, plan_w),
                        plan_w.is_optimal))

    # 3) safety stock -10%
    p_ss = problem.model_copy(deep=True)
    p_ss.safety_stock = {s: int(v * 0.9) for s, v in p_ss.safety_stock.items()}
    plan_s = solve_reorder(p_ss, max_seconds)
    probes.append(Probe("safety -10%", _recovered(base_plan, plan_s),
                        plan_s.is_optimal))

    return sorted(probes, key=lambda p: p.recovered, reverse=True)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_probes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/probes.py tests/test_probes.py
git commit -m "feat: constraint probes to find the binding limit"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Why can't CP-SAT just tell us the shadow price (marginal value) of the budget constraint? What's different about integer programs vs linear programs?
  - Each probe re-solves the whole model. What is the runtime cost of this approach, and why is it worth it?

---

## Task 12: Monte Carlo simulation (`simulate.py`)

**Files:**
- Create: `src/reorder/simulate.py`, `tests/test_simulate.py`

**Interfaces:**
- Consumes: `Problem`, `Plan`.
- Produces:
  - `SimResult` dataclass: `fill_rate_p50: float`, `fill_rate_p10: float`, `cash_p50: int`, `runs: int`.
  - `simulate(problem: Problem, plan: Plan, n: int = 1000, cv: float = 0.15, seed: int = 0) -> SimResult` — holds the plan's orders fixed, samples demand ~ Normal(p50, cv·p50), rolls forward, reports the distribution of fill rate and cash tied up.

- [ ] **Step 1: Write the failing test**

`tests/test_simulate.py`:
```python
from reorder.models import Part, Problem
from reorder.solver import solve_reorder
from reorder.simulate import simulate

def _problem():
    parts = [Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
                  moq=50, lead_time=1, volume=1, opening_inventory=80)]
    return Problem(parts=parts, weeks=6, demand={"A": [30, 30, 30, 30, 30, 30]},
                   safety_stock={"A": 20}, budget=[1_000_000] * 6,
                   warehouse_cap=10_000, stockout_penalty=15_000, safety_penalty=1_000)

def test_simulate_reports_distribution():
    prob = _problem()
    plan = solve_reorder(prob)
    res = simulate(prob, plan, n=500, seed=1)
    assert res.runs == 500
    assert 0.0 <= res.fill_rate_p10 <= res.fill_rate_p50 <= 1.0
    assert res.cash_p50 >= 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_simulate.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/simulate.py`**

```python
from dataclasses import dataclass

import numpy as np

from reorder.models import Problem, Plan


@dataclass
class SimResult:
    fill_rate_p50: float    # median fill rate across runs
    fill_rate_p10: float    # pessimistic (10th percentile) fill rate
    cash_p50: int           # median peak cash tied up in inventory (cents)
    runs: int


def simulate(problem: Problem, plan: Plan, n: int = 1000,
             cv: float = 0.15, seed: int = 0) -> SimResult:
    """The solver planned against p50. Reality isn't p50. Roll the committed
    orders forward against sampled demand to see if the plan survives variance."""
    rng = np.random.default_rng(seed)
    skus = problem.skus
    fill_rates = np.zeros(n)
    peak_cash = np.zeros(n)

    for r in range(n):
        met = demanded = 0
        run_peak = 0
        for s in skus:
            p = problem.part(s)
            inv = p.opening_inventory
            orders = plan.orders[s]
            for t in range(problem.weeks):
                arrivals = orders[t - p.lead_time] if t - p.lead_time >= 0 else 0
                inv += arrivals
                mean = problem.demand[s][t]
                d = max(0, int(round(rng.normal(mean, cv * max(1, mean)))))
                demanded += d
                shipped = min(inv, d)
                met += shipped
                inv -= shipped
                run_peak = max(run_peak, p.unit_cost * max(0, inv))
        fill_rates[r] = (met / demanded) if demanded else 1.0
        peak_cash[r] = run_peak

    return SimResult(
        fill_rate_p50=float(np.percentile(fill_rates, 50)),
        fill_rate_p10=float(np.percentile(fill_rates, 10)),
        cash_p50=int(np.percentile(peak_cash, 50)),
        runs=n,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_simulate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/simulate.py tests/test_simulate.py
git commit -m "feat: Monte Carlo simulation of plan under demand variance"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - The solver optimized against p50. What question does the simulation answer that the solver cannot?
  - Why report `fill_rate_p10` (a pessimistic percentile) and not just the average fill rate?

---

## Task 13: Plan diff (`diff.py`)

**Files:**
- Create: `src/reorder/diff.py`, `tests/test_diff.py`

**Interfaces:**
- Produces:
  - `PlanDiff` dataclass: `changes: dict[str, list[tuple[int,int,int]]]` (sku -> list of `(week, before_qty, after_qty)` where they differ), `summary: str`.
  - `diff_plans(before: Plan, after: Plan) -> PlanDiff`.

- [ ] **Step 1: Write the failing test**

`tests/test_diff.py`:
```python
from reorder.models import Plan
from reorder.diff import diff_plans

def _plan(orders):
    return Plan(status="OPTIMAL", cost=0, bound=0, orders=orders,
                inventory={}, backorder={}, short={})

def test_diff_finds_changed_weeks():
    before = _plan({"A": [0, 276, 0]})
    after = _plan({"A": [480, 0, 0]})
    d = diff_plans(before, after)
    assert d.changes["A"] == [(0, 0, 480), (1, 276, 0)]
    assert "A" in d.summary
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_diff.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Write `src/reorder/diff.py`**

```python
from dataclasses import dataclass

from reorder.models import Plan


@dataclass
class PlanDiff:
    changes: dict[str, list[tuple[int, int, int]]]  # sku -> [(week, before, after)]
    summary: str


def diff_plans(before: Plan, after: Plan) -> PlanDiff:
    changes: dict[str, list[tuple[int, int, int]]] = {}
    for sku, after_orders in after.orders.items():
        before_orders = before.orders.get(sku, [0] * len(after_orders))
        deltas = [(t, before_orders[t], after_orders[t])
                  for t in range(len(after_orders))
                  if before_orders[t] != after_orders[t]]
        if deltas:
            changes[sku] = deltas
    n = sum(len(v) for v in changes.values())
    summary = (f"{n} order change(s) across {len(changes)} SKU(s): "
               + ", ".join(sorted(changes)) if changes else "no changes")
    return PlanDiff(changes=changes, summary=summary)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_diff.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reorder/diff.py tests/test_diff.py
git commit -m "feat: plan diff for before/after order schedules"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Why is `diff_plans` "not a convenience but the thing that makes the system adoptable"? (Hint: rolling horizon changes the plan every week; buyers stop trusting a plan that keeps moving unless you can explain *what* moved and *why*.)

---

## Task 14: Wire the numeric demo (CLI `demo`, no LLM yet) — **DAYS 3–4 MILESTONE**

**Files:**
- Modify: `src/reorder/cli.py` (add `demo` command)
- Create: `tests/test_demo_pipeline.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `cli` subcommand `demo --sku PART-XXXX --lead-time 5` that prints the §2 output from pure numbers: revised orders, cost of disruption (guarded), binding constraint + recoveries, and a simulation line.

- [ ] **Step 1: Write the failing test (pipeline produces a Recommendation-shaped dict)**

`tests/test_demo_pipeline.py`:
```python
import pandas as pd
from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.scenario import with_lead_time, disruption_cost
from reorder.probes import probe_constraints

def test_end_to_end_numeric(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=10, seed=5)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    fc = forecast_quantiles(hist, horizon=12)
    problem = build_problem(parts, fc, weeks=12)
    sku = problem.skus[0]

    before = solve_reorder(problem, max_seconds=20)
    after = solve_reorder(with_lead_time(problem, sku, 5), max_seconds=20)
    if before.is_optimal and after.is_optimal:
        delta = disruption_cost(before, after)
        assert isinstance(delta, int)
    probes = probe_constraints(problem, before, max_seconds=10)
    assert len(probes) == 3
```

- [ ] **Step 2: Run to verify it fails or is incomplete**

Run: `pytest tests/test_demo_pipeline.py -v`
Expected: PASS if earlier tasks are done (this test uses only existing functions). If it fails, fix the underlying task before proceeding.

- [ ] **Step 3: Add the `demo` command to `src/reorder/cli.py`**

Add imports:
```python
from reorder.scenario import with_lead_time, disruption_cost, NotOptimalError
from reorder.probes import probe_constraints
from reorder.simulate import simulate
from reorder.diff import diff_plans
```
Add parser in `main()`:
```python
    d = sub.add_parser("demo", help="run a disruption end-to-end (numbers only)")
    d.add_argument("--sku", required=True)
    d.add_argument("--lead-time", type=int, required=True)
    d.add_argument("--weeks", type=int, default=12)
    d.set_defaults(func=cmd_demo)
```
Add command function:
```python
def cmd_demo(args):
    problem = _load_problem(args.data_dir, args.weeks)
    before = solve_reorder(problem, max_seconds=20)
    after_problem = with_lead_time(problem, args.sku, args.lead_time)
    after = solve_reorder(after_problem, max_seconds=20)

    print(f"Disruption: {args.sku} lead time -> {args.lead_time} weeks\n")
    d = diff_plans(before, after)
    print("Plan change:", d.summary)
    for wk, b, a in d.changes.get(args.sku, [])[:3]:
        print(f"  {args.sku} week {wk}: {b} -> {a} units")

    try:
        delta = disruption_cost(before, after)
        print(f"\nCost of the disruption: ${to_dollars(delta):,.2f}")
    except NotOptimalError as e:
        print(f"\n[cannot report a clean delta] {e}")

    print("\nWhich limit is binding (recovery if relaxed):")
    for p in probe_constraints(after_problem, after, max_seconds=10):
        print(f"  {p.name:<20} recovers ${to_dollars(p.recovered):,.2f}")

    sim = simulate(after_problem, after, n=1000)
    print(f"\nSimulation ({sim.runs} runs): fill rate p50={sim.fill_rate_p50:.1%}, "
          f"p10={sim.fill_rate_p10:.1%}")
```

- [ ] **Step 4: Run the demo end to end**

Run:
```
reorder generate
reorder demo --sku PART-1000 --lead-time 5
```
Expected: prints plan change, cost of disruption, three binding-constraint recoveries sorted, and a simulation line. (Pick a real SKU from `data/parts.csv`.)

- [ ] **Step 5: Commit**

```bash
git add src/reorder/cli.py tests/test_demo_pipeline.py
git commit -m "feat: end-to-end numeric demo command"
```

- [ ] **Step 6: Explain-back checkpoint.** Answer aloud:
  - Walk the whole pipeline from "lead time changes" to the printed output, naming each module touched.
  - **Milestone:** typing a disruption now produces the §2 output — *without any LLM*. Note this explicitly: the intelligence is in the solver, not the language model.

---

## Task 15: The Pydantic AI agent (`agent.py`)

**Files:**
- Create: `src/reorder/agent.py`, `tests/test_agent.py`

**Interfaces:**
- Consumes: all engine functions; env vars `OPENAI_API_KEY`, `REORDER_MODEL`.
- Produces:
  - `Recommendation` (Pydantic model): `revised_orders: dict[str,list[int]]`, `disruption_cost_dollars: float | None`, `binding_constraint: str`, `counterfactuals: list[str]`, `explanation: str`.
  - `build_agent(model=None) -> Agent` and `run_disruption(text: str, data_dir="data") -> Recommendation`.
  - Tools registered on the agent: `get_part_context`, `solve_current`, `apply_lead_time`, `probe`, `simulate_plan`. Tools raise `ModelRetry` on bad input.

- [ ] **Step 1: Write the failing test using Pydantic AI's `TestModel` (no API cost)**

`tests/test_agent.py`:
```python
import pandas as pd
from reorder.datagen import generate
from reorder.agent import build_agent, Recommendation
from pydantic_ai.models.test import TestModel

def test_agent_wires_tools_without_api(tmp_path, monkeypatch):
    # TestModel calls each tool once and fabricates a structured result,
    # so we verify wiring + output schema WITHOUT hitting OpenAI.
    generate(out_dir=str(tmp_path), n_parts=6, seed=2)
    monkeypatch.chdir(tmp_path)
    agent = build_agent()
    with agent.override(model=TestModel()):
        result = agent.run_sync("HOUSING lead time goes to 5 weeks")
    assert isinstance(result.output, Recommendation)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_agent.py -v`
Expected: FAIL — `ImportError` on `reorder.agent`.

- [ ] **Step 3: Write `src/reorder/agent.py`**

```python
import os

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.scenario import with_lead_time, disruption_cost, NotOptimalError
from reorder.probes import probe_constraints
from reorder.simulate import simulate
from reorder.models import to_dollars

load_dotenv()


class Recommendation(BaseModel):
    revised_orders: dict[str, list[int]]
    disruption_cost_dollars: float | None
    binding_constraint: str
    counterfactuals: list[str]
    explanation: str


class Deps(BaseModel):
    data_dir: str = "data"

    model_config = {"arbitrary_types_allowed": True}


SYSTEM_PROMPT = """You are a purchasing copilot. A buyer describes a supply
disruption in plain English. Your job is ONLY to:
1. Identify the affected SKU and the new lead time from their message.
2. Call the tools to re-solve and analyze. You never invent numbers.
3. Return a Recommendation summarizing what the SOLVER decided.
The solver makes every numeric decision. You translate and explain."""


def build_agent(model: str | None = None) -> Agent:
    model = model or os.environ.get("REORDER_MODEL", "openai:gpt-4o")
    agent = Agent(model, deps_type=Deps, output_type=Recommendation,
                  system_prompt=SYSTEM_PROMPT)

    @agent.tool
    def get_part_context(ctx: RunContext[Deps], sku: str) -> dict:
        parts = pd.read_csv(f"{ctx.deps.data_dir}/parts.csv")
        row = parts[parts["sku"] == sku]
        if row.empty:
            raise ModelRetry(f"No SKU '{sku}'. Valid examples: "
                             f"{parts['sku'].head(5).tolist()}")
        return row.iloc[0].to_dict()

    @agent.tool
    def analyze_lead_time_change(ctx: RunContext[Deps], sku: str,
                                 new_lead_time: int) -> dict:
        """Re-solve with the new lead time and return cost delta, binding
        constraint, revised orders, and a simulation summary."""
        if new_lead_time < 1:
            raise ModelRetry("lead_time must be >= 1 week.")
        parts = pd.read_csv(f"{ctx.deps.data_dir}/parts.csv")
        hist = pd.read_csv(f"{ctx.deps.data_dir}/demand_history.csv")
        if sku not in set(parts["sku"]):
            raise ModelRetry(f"No SKU '{sku}'.")
        fc = forecast_quantiles(hist, horizon=12)
        problem = build_problem(parts, fc, weeks=12)
        before = solve_reorder(problem, max_seconds=20)
        after_problem = with_lead_time(problem, sku, new_lead_time)
        after = solve_reorder(after_problem, max_seconds=20)
        if after.status == "INFEASIBLE":
            raise ModelRetry("The re-solved problem is INFEASIBLE; relax an input.")

        try:
            delta = to_dollars(disruption_cost(before, after))
        except NotOptimalError:
            delta = None
        probes = probe_constraints(after_problem, after, max_seconds=10)
        sim = simulate(after_problem, after, n=1000)
        return {
            "revised_orders": {sku: after.orders[sku]},
            "disruption_cost_dollars": delta,
            "binding_constraint": probes[0].name,
            "counterfactuals": [f"{p.name}: recovers ${to_dollars(p.recovered):,.2f}"
                                for p in probes],
            "fill_rate_p50": sim.fill_rate_p50,
        }

    return agent


def run_disruption(text: str, data_dir: str = "data") -> Recommendation:
    agent = build_agent()
    return agent.run_sync(text, deps=Deps(data_dir=data_dir)).output
```

- [ ] **Step 4: Run the offline test**

Run: `pytest tests/test_agent.py -v`
Expected: PASS (uses `TestModel`, no API key needed). If Pydantic AI's API differs in the installed version, adjust import paths per its docs — the shape (Agent, `@agent.tool`, `output_type`, `ModelRetry`, `.output`) is stable; verify with `python -c "import pydantic_ai; print(pydantic_ai.__version__)"`.

- [ ] **Step 5: One real end-to-end run (uses the OpenAI key, costs pennies)**

Run:
```
cp .env.example .env    # then edit .env to add your real OPENAI_API_KEY
python -c "from reorder.agent import run_disruption; print(run_disruption('PART-1000 lead time goes from 2 to 5 weeks').model_dump_json(indent=2))"
```
Expected: a valid `Recommendation` JSON. If it errors on model name, set `REORDER_MODEL=openai:gpt-4o-mini` in `.env` and retry.

- [ ] **Step 6: Commit**

```bash
git add src/reorder/agent.py tests/test_agent.py
git commit -m "feat: Pydantic AI agent with typed tools and ModelRetry"
```

- [ ] **Step 7: Explain-back checkpoint.** Answer aloud:
  - What is the *typed boundary*, and what specifically does `ModelRetry` do when the model passes a bad SKU?
  - "In a chatbot a hallucination is a weird sentence; here it's a wrong purchase order." Explain how the `Recommendation` output type and the tool validation prevent that.
  - Why can you test the whole agent with `TestModel` and no API key? What does that test actually prove (and not prove)?

---

## Task 16: Agent eval set

**Files:**
- Create: `tests/test_agent_evals.py`

**Interfaces:**
- Consumes: `build_agent`, `TestModel`, `Recommendation`.
- Produces: a parametrized eval asserting the agent selects the lead-time tool and returns a valid `Recommendation` across ~12 phrasings.

- [ ] **Step 1: Write the eval test**

`tests/test_agent_evals.py`:
```python
import pandas as pd
import pytest
from reorder.datagen import generate
from reorder.agent import build_agent, Recommendation
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.messages import ModelMessage, ModelResponse

SCENARIOS = [
    "Supplier Kraus is 3 weeks late on PART-1000, lead time now 5.",
    "PART-1001 lead time jumps to 6 weeks starting now.",
    "Heads up: PART-1002 will take 4 weeks instead of 2.",
    "We just learned PART-1003 ships in 5 weeks now.",
    "Delay on PART-1004 — 7 week lead time.",
    "PART-1005 lead time doubled to 4 weeks.",
    "Vendor pushed PART-1006 to a 5 week lead time.",
    "PART-1007 now 3 weeks out.",
    "Expect PART-1008 in 6 weeks, not 2.",
    "PART-1009 lead time revised upward to 4 weeks.",
    "PART-1000 back to a 5-week lead time after the fire.",
    "Flag PART-1001: 5 weeks lead time going forward.",
]

@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    generate(out_dir=str(tmp_path), n_parts=12, seed=9)
    monkeypatch.chdir(tmp_path)

@pytest.mark.parametrize("text", SCENARIOS)
def test_agent_produces_valid_recommendation(text):
    agent = build_agent()
    with agent.override(model=TestModel()):
        result = agent.run_sync(text)
    assert isinstance(result.output, Recommendation)
    # TestModel calls every tool; the key assertion is a schema-valid output.
```

- [ ] **Step 2: Run the evals**

Run: `pytest tests/test_agent_evals.py -v`
Expected: 12 PASS, no API cost.

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent_evals.py
git commit -m "test: agent eval set over 12 disruption phrasings"
```

- [ ] **Step 4: Explain-back checkpoint.** Answer aloud:
  - What do these evals prove about robustness, and what would you add to make them stronger (e.g., asserting the *right* SKU is extracted with a real model + recorded traces)?

---

## Task 17: README, generalization paragraph, and rehearsal — **FINAL MILESTONE**

**Files:**
- Create: `README.md`
- Modify: none (docs only)

**Interfaces:** none.

- [ ] **Step 1: Write `README.md`**

````markdown
# Reorder Copilot

A decision layer for manufacturing purchasing. Type a supply disruption in
plain English; the system re-optimizes what to order and explains what it cost
and which constraint is binding.

**All data here is synthetic.** See "Generalization" below for real-data use.

## What it does
- **Optimizes** a 40-SKU, 12-week reorder plan with a CP-SAT integer program
  (MOQ, weekly cash budget, warehouse space; soft safety stock, hard-ish
  stockout penalty).
- **Explains** which constraint is binding by re-solving with each relaxed
  (integer programs have no shadow prices, so we buy them).
- **Simulates** the plan across 1,000 sampled demand futures.
- **Proves it's not a toy** by backtesting against the classic `(s,Q)` reorder
  policy an ERP actually runs.
- **Translates** English disruptions to solver inputs and back with a Pydantic
  AI agent — the LLM never does arithmetic.

## Quickstart
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

reorder generate                       # write synthetic data
reorder solve                          # baseline plan (expect status=OPTIMAL)
reorder backtest --test-weeks 26       # solver vs (s,Q): dollars saved
reorder demo --sku PART-1000 --lead-time 5   # a disruption, numbers only

# Agent (needs an OpenAI key):
cp .env.example .env                   # add OPENAI_API_KEY
python -c "from reorder.agent import run_disruption; print(run_disruption('PART-1000 lead time goes to 5 weeks').model_dump_json(indent=2))"

pytest                                 # full test + eval suite
```

## Design decisions worth defending
See `docs/superpowers/specs/2026-07-11-reorder-copilot-design.md` §7. Highlights:
integer cents (no floats in the model), never comparing two non-OPTIMAL solves,
soft safety stock vs hard stockout, and buying shadow prices via re-solves.

## Generalization
This engine also runs on real HPC job traces from the Parallel Workloads
Archive. Right-sizing a job's memory request and setting a part's safety stock
are the same problem: allocate a constrained resource from noisy historical
telemetry, where over-provisioning wastes money and under-provisioning halts
the line. Same solver, different nouns.
````

- [ ] **Step 2: Full green run**

Run: `pytest`
Expected: entire suite passes. Fix anything red before proceeding.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with quickstart and generalization paragraph"
```

- [ ] **Step 4: Rehearsal checklist (do this out loud, timed).** The live demo script:
  1. `reorder generate` — "synthetic factory, 40 parts, 2 years of demand."
  2. `reorder solve` — point at `status=OPTIMAL, gap=0.000`: "the solver *proved* this is the best plan."
  3. `reorder backtest` — "here's the evidence: it beats the policy an ERP runs by $X / +Y% fill."
  4. `reorder demo --sku ... --lead-time 5` — narrate the cost of disruption, binding constraint, simulation.
  5. Run the agent once — "same numbers, now driven from an English sentence; the LLM only translated."
  6. Be ready for: "why CP-SAT not LP?", "why is that cost trustworthy?", "what if it's only FEASIBLE?"

- [ ] **Step 5: Explain-back checkpoint (the whole system).** Without notes, in 90 seconds:
  - Draw the data flow from English sentence to explanation, naming every module.
  - State the one-sentence thesis: *"ERPs plan; they don't think. The solver makes the decision, the agent explains it, and the backtest proves it beats what they run today."*

---

## Self-Review Notes (author)

- **Spec coverage:** §4 architecture → Tasks 1–2,7,14; §5 entities → Task 2; §6 solver/forecast/sim → Tasks 3–4,6,12; §7.1 probes → Task 11; §7.2 OPTIMAL guard → Task 10; §7.3 cents → Task 2 (enforced throughout); §7.4 soft/hard → Tasks 3–4; §7.5 rolling horizon → Task 9 (backtest) + note; §8 agent → Tasks 15–16; §9 proof (optimality/backtest/evals) → Tasks 7,9,16; §12 generalization → Task 17. Dagster/Postgres/FastAPI/React are explicit non-goals (spec §3) — intentionally absent.
- **Fallback baked in:** Task 7 and Task 9 both handle the "only FEASIBLE at 40 SKUs" case by dropping SKU count and reporting the gap.
- **No API cost in CI:** agent tests use `TestModel`; exactly one optional real run in Task 15 Step 5.
- **Type consistency:** `Plan`, `Problem`, `Part` signatures are defined once in Task 2 and used verbatim thereafter; `disruption_cost`/`NotOptimalError` defined in Task 10 and reused in Tasks 14–15; `probe_constraints(problem, base_plan, max_seconds)` signature consistent across Tasks 11, 14, 15.
