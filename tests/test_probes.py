from reorder.models import Part, Problem
from reorder.solver import solve_reorder
from reorder.probes import Probe, probe_constraints, binding_constraint


def _tight_budget_problem():
    # Cash is the scarce resource here, so the budget probe must win -- provably.
    parts = [Part(sku="A", unit_cost=500, holding_cost=10, order_cost=5000,
                  moq=50, lead_time=2, volume=1, opening_inventory=50)]
    return Problem(parts=parts, weeks=6, demand={"A": [40, 40, 40, 40, 40, 40]},
                   safety_stock={"A": 20}, budget=[9_000] * 6,
                   warehouse_cap=10_000, stockout_penalty=15_000, safety_penalty=1_000)


def test_probes_are_sorted_by_recovery():
    prob = _tight_budget_problem()
    probes = probe_constraints(prob, solve_reorder(prob))
    assert {p.name for p in probes} == {
        "budget +$10k/wk", "warehouse +10000u", "safety -50%"}
    assert probes == sorted(probes, key=lambda p: p.recovered, reverse=True)


def test_tight_budget_makes_budget_the_binding_constraint():
    prob = _tight_budget_problem()
    probes = probe_constraints(prob, solve_reorder(prob))
    top, proven = binding_constraint(probes)
    assert top.name == "budget +$10k/wk"
    assert top.recovered > 0
    assert proven is True          # its worst case beats the runner-up's best case


def test_recovery_never_claims_more_precision_than_the_solver_can_prove():
    prob = _tight_budget_problem()
    probes = probe_constraints(prob, solve_reorder(prob))
    for p in probes:
        assert p.lo >= 0 and p.hi >= p.lo
        if p.recovered > 0:
            assert p.lo <= p.recovered <= p.hi


def test_binding_constraint_refuses_to_guess_when_probes_overlap():
    """If the winner's WORST case does not beat the runner-up's BEST case, the
    solver's slack could explain the entire difference -- so we must not claim one.
    This is the bug that made three identical runs name three different winners."""
    ambiguous = [Probe("a", recovered=100, lo=10, hi=200, feasible=True),
                 Probe("b", recovered=90, lo=5, hi=190, feasible=True)]
    top, proven = binding_constraint(ambiguous)
    assert top.name == "a"
    assert proven is False

    clear = [Probe("a", recovered=500, lo=400, hi=600, feasible=True),
             Probe("b", recovered=100, lo=50, hi=150, feasible=True)]
    top, proven = binding_constraint(clear)
    assert top.name == "a"
    assert proven is True          # 400 > 150
