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


def test_a_timed_out_probe_must_not_be_scored_as_zero_recovery():
    """The nastiest bug in the project.

    When a probe fails to prove optimality we record its recovery as 0. But
    "this solve ran out of time" and "relaxing this recovers nothing" are
    completely different claims, and 0 cannot tell them apart. A timed-out probe
    could actually be the BIGGEST lever -- so it must never be silently demoted
    to last place and let a lesser constraint be crowned PROVEN.

    This really happened live: under load the budget probe timed out, scored 0,
    and `safety` was named the binding constraint with a PROVEN badge. Wrong.
    """
    probes = [
        Probe("safety -50%", recovered=48_000, lo=40_000, hi=55_000, feasible=True),
        Probe("budget +$10k/wk", recovered=0, lo=0, hi=0, feasible=False),  # timed out!
    ]
    top, proven = binding_constraint(probes)
    assert top.name == "safety -50%"
    # Without the guard, safety.lo (40k) > budget.hi (0) => it would claim PROVEN.
    assert proven is False, "must not crown a winner while a probe is unsolved"
