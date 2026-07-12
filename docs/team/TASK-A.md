# Team Brief A — Disruption + guarded cost delta

Branch: `teammate-a-disruption`
Owner: Teammate A
Scope: Task 10

## What to build
Create the new engine module:
- `src/reorder/scenario.py`
- `tests/test_scenario.py`

## Deliverables
You are responsible for the disruption layer:
- `with_lead_time(problem: Problem, sku: str, new_lead_time: int) -> Problem`
- `NotOptimalError(RuntimeError)`
- `disruption_cost(before: Plan, after: Plan) -> int`

## Contracts
- `with_lead_time()` must return a deep copy and change only one part's `lead_time`.
- `disruption_cost()` is only meaningful when both plans are `OPTIMAL`.
- If either plan is not `OPTIMAL`, raise `NotOptimalError`.
- Cost delta is reported in integer cents.

## Test-first check
Run the first failing test:

```powershell
pytest tests/test_scenario.py -v
```

Expected failure at first: `ImportError` because the new module is missing.

## Implementation notes
- Use `problem.model_copy(deep=True)` to avoid mutating the source problem.
- Use `updated.part(sku).lead_time = new_lead_time`.
- Guard the comparison with:
  - `before.is_optimal`
  - `after.is_optimal`
- Keep the explanation brief and honest: comparing two `FEASIBLE` plans is not evidence; it hides noise from the solver.

## Verification
Once the code is in place, run:

```powershell
pytest tests/test_scenario.py -v
```

Expected result: all 3 tests pass.

## Merge dependency
A is independent and can land first. B, C, and D may all build against the public interfaces once this is merged.
