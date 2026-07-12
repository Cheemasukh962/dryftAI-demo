# Team Brief B — Analysis tools: probes, simulation, and plan diff

Branch: `teammate-b-analysis`
Owner: Teammate B
Scope: Tasks 11, 12, 13

## What to build
Create the following files:
- `src/reorder/probes.py`
- `src/reorder/simulate.py`
- `src/reorder/diff.py`

Add the matching tests:
- `tests/test_probes.py`
- `tests/test_simulate.py`
- `tests/test_diff.py`

## Deliverables
### 1) Constraint probes
Implement:
- `Probe` dataclass with `name`, `recovered`, `feasible`
- `probe_constraints(problem: Problem, base_plan: Plan, max_seconds=10.0) -> list[Probe]`

Probe the three relaxations:
- budget +$1000/week
- warehouse +1000 units
- safety stock −10%

Sort by `recovered` descending. The first probe is the binding constraint to explain.

### 2) Monte Carlo simulation
Implement:
- `SimResult` dataclass
- `simulate(problem: Problem, plan: Plan, n=1000, cv=0.15, seed=0) -> SimResult`

This holds the solved orders fixed, samples demand noise, and reports the distribution of fill rate and cash tied up.

### 3) Plan diff
Implement:
- `PlanDiff` dataclass
- `diff_plans(before: Plan, after: Plan) -> PlanDiff`

This is the human-facing explanation layer: what moved between two plans, week by week.

## Test-first flow
Run the three new tests in one shot:

```powershell
pytest tests/test_probes.py tests/test_simulate.py tests/test_diff.py -v
```

Expected first failure: `ImportError` on the new modules.

## Important design rules
- `recovered` is measured as cents saved relative to the base plan; never let it go negative.
- `simulate()` is about robustness under demand variance, not the optimization itself.
- `diff_plans()` should emit a compact summary and a per-SKU list of week-level changes.

## Verification
After the implementation, re-run:

```powershell
pytest tests/test_probes.py tests/test_simulate.py tests/test_diff.py -v
```

Expected status: all tests pass.

## Merge dependency
B is independent from A and can land in parallel. D depends on the interfaces from A + B.
