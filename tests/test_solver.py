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
