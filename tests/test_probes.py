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
