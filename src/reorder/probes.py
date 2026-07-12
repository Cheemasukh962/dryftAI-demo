"""Buy the shadow prices CP-SAT won't give us.

Linear programs hand you, for free, the marginal value of relaxing each
constraint (the "dual"). CP-SAT is an INTEGER solver -- it has no such thing.
So to find out which limit is actually binding a plan, we re-solve the problem
three times, each time loosening exactly one constraint, and see which
loosening recovers the most cost. Whichever probe recovers the most money
names the real bottleneck -- the buyer's actual action item.
"""
from dataclasses import dataclass

from reorder.models import Problem, Plan
from reorder.solver import solve_reorder


@dataclass
class Probe:
    name: str
    recovered: int      # cents saved relative to the base plan (>=0 means it helped)
    feasible: bool


def _recovered(base_plan: Plan, relaxed_plan: Plan) -> int:
    # Only trust the delta if BOTH solves are proven -- same OPTIMAL-only rule
    # that governs disruption_cost() in scenario.py.
    if not (base_plan.is_optimal and relaxed_plan.is_optimal):
        return 0
    return max(0, base_plan.cost - relaxed_plan.cost)


def probe_constraints(problem: Problem, base_plan: Plan,
                      max_seconds: float = 10.0,
                      relative_gap: float = 0.005) -> list[Probe]:
    """Re-solve with each constraint relaxed by a fixed step; report the
    resulting cost recovery, sorted so the biggest lever comes first.

    `relative_gap` must match the tolerance the base plan was solved at, or the
    two costs aren't measured with the same ruler.
    """
    probes: list[Probe] = []

    # 1) budget +$1000/week
    p_budget = problem.model_copy(deep=True)
    p_budget.budget = [b + 100_000 for b in p_budget.budget]   # +$1000 in cents
    plan_b = solve_reorder(p_budget, max_seconds, relative_gap)
    probes.append(Probe("budget +$1000/wk", _recovered(base_plan, plan_b),
                        plan_b.is_optimal))

    # 2) warehouse +1000 units
    p_wh = problem.model_copy(deep=True)
    p_wh.warehouse_cap += 1000
    plan_w = solve_reorder(p_wh, max_seconds, relative_gap)
    probes.append(Probe("warehouse +1000u", _recovered(base_plan, plan_w),
                        plan_w.is_optimal))

    # 3) safety stock -10%
    p_ss = problem.model_copy(deep=True)
    p_ss.safety_stock = {s: int(v * 0.9) for s, v in p_ss.safety_stock.items()}
    plan_s = solve_reorder(p_ss, max_seconds, relative_gap)
    probes.append(Probe("safety -10%", _recovered(base_plan, plan_s),
                        plan_s.is_optimal))

    return sorted(probes, key=lambda p: p.recovered, reverse=True)
