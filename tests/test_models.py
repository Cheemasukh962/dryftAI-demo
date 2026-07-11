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
