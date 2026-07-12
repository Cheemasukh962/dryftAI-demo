# Team Brief D — Integration demo CLI + docs

Branch: `teammate-d-integration`
Owner: Teammate D
Scope: Tasks 14, 17

## What to build
Modify and complete:
- `src/reorder/cli.py` — add the `demo` command
- `tests/test_demo_pipeline.py`
- `README.md`

## Deliverables
### 1) Numeric demo command
Add a `demo` subcommand to the CLI:

```powershell
reorder demo --sku PART-1000 --lead-time 5
```

The command should print:
- plan change summary from the disruption
- cost of disruption, guarded by `NotOptimalError`
- binding constraint recoveries from `probe_constraints()`
- a simulation summary line

### 2) Final README and rehearsal
Write the repository landing page with:
- the one-line value proposition
- quickstart commands
- the solver/backtest evidence narrative
- a short generalization paragraph

## Test-first flow
Run the end-to-end pipeline test:

```powershell
pytest tests/test_demo_pipeline.py -v
```

That test should pass once the engine pieces from A + B + C are wired correctly.

## Important design rules
- `demo` should be numbers-only and must not rely on any LLM call.
- The narrative in the README should be crisp and interview-safe.
- This branch is the last integration step, so it should coordinate the final story rather than invent new architecture.

## Verification
Run:

```powershell
pytest
```

The final milestone is full green across the repo.

## Merge dependency
D integrates last because it depends on the work from A, B, and C.
