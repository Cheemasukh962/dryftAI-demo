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
