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
