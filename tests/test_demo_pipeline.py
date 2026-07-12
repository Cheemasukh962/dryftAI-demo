"""End-to-end pipeline test: the whole demo, with NO LLM involved.

This is the proof that the intelligence lives in the solver, not the language
model. Everything the buyer sees -- the revised plan, the cost of the delay, the
binding constraint, the simulation -- is produced here by pure numbers.
"""
import pandas as pd

from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.scenario import with_lead_time, disruption_cost, NotOptimalError
from reorder.probes import probe_constraints
from reorder.simulate import simulate
from reorder.diff import diff_plans


def test_end_to_end_numeric(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=10, seed=5)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")

    fc = forecast_quantiles(hist, horizon=12)
    problem = build_problem(parts, fc, weeks=12)
    sku = problem.skus[0]

    before = solve_reorder(problem, max_seconds=20)
    after_problem = with_lead_time(problem, sku, 5)
    after = solve_reorder(after_problem, max_seconds=20)
    assert before.status in ("OPTIMAL", "FEASIBLE")
    assert after.status in ("OPTIMAL", "FEASIBLE")

    # A longer lead time can never make the plan cheaper.
    if before.is_optimal and after.is_optimal:
        delta = disruption_cost(before, after)
        assert isinstance(delta, int)
        assert delta >= 0

    probes = probe_constraints(after_problem, after, max_seconds=10)
    assert len(probes) == 3
    assert probes == sorted(probes, key=lambda p: p.recovered, reverse=True)

    sim = simulate(after_problem, after, n=200, seed=1)
    assert 0.0 <= sim.fill_rate_p10 <= sim.fill_rate_p50 <= 1.0

    d = diff_plans(before, after)
    assert isinstance(d.summary, str)


def test_disruption_cost_refuses_unproven_comparison():
    """The honesty guard: never report a delta between two unproven solves."""
    from reorder.models import Plan
    import pytest

    good = Plan(status="OPTIMAL", cost=100, bound=100,
                orders={}, inventory={}, backorder={}, short={})
    feasible = Plan(status="FEASIBLE", cost=120, bound=100,
                    orders={}, inventory={}, backorder={}, short={})
    with pytest.raises(NotOptimalError):
        disruption_cost(good, feasible)
