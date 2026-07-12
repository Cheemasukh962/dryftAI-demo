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
