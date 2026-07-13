"""Buy the shadow prices CP-SAT won't give us -- and prove the answer.

Linear programs hand you the marginal value of relaxing each constraint for free
(the "dual"). CP-SAT is an INTEGER solver: it has no duals. So to find out which
limit is actually binding, we re-solve with each one loosened and see which
loosening recovers the most cost.

TWO TRAPS, both of which we hit for real:

1. THE PERTURBATION MUST BEAT THE NOISE.
   We stop the solver at a small MIP gap, so every plan carries slack -- on a $5M
   objective a 2% gap is ~$107k of slop. Our original probes (+$1000/wk budget)
   only recovered $20-35k... which is *smaller than the slack*. The "binding
   constraint" was therefore mostly solver noise: three identical runs named three
   different winners. Fix: relax by a MEANINGFUL amount (+$10k/wk, not +$1k), so
   the signal (~$330k) dwarfs the noise.

2. A POINT ESTIMATE STILL HIDES THE SLACK.
   `base.cost - relaxed.cost` looks precise but both terms carry gap slack. So each
   probe also reports a RIGOROUS interval for its recovery, and we only call a
   constraint "binding" when its worst case beats the runner-up's best case.
   Otherwise we say the probes cannot distinguish them -- rather than guess.
"""
from dataclasses import dataclass

from reorder.models import Problem, Plan
from reorder.solver import solve_reorder

# Relaxation step sizes. These are deliberately LARGE: the recovery has to be big
# enough to stand clear of the solver's MIP-gap slack, or the ranking is noise.
BUDGET_STEP_CENTS = 1_000_000     # +$10,000 per week
WAREHOUSE_STEP_UNITS = 10_000     # +10,000 volume units
SAFETY_SCALE = 0.5                # cut the safety-stock target in half


@dataclass
class Probe:
    name: str
    recovered: int      # point estimate of cost saved, in cents (>= 0)
    lo: int             # provable MINIMUM recovery, in cents
    hi: int             # provable MAXIMUM recovery, in cents
    feasible: bool


def _recovery(base: Plan, relaxed: Plan) -> tuple[int, int, int]:
    """Point estimate plus a rigorous [lo, hi] interval for the cost recovered.

    Each plan's true optimum lies in [bound, cost], so:
        recovery = base_true - relaxed_true
        lo = base.bound - relaxed.cost     (base as cheap as possible, relaxed as dear)
        hi = base.cost  - relaxed.bound    (base as dear as possible, relaxed as cheap)
    """
    if not (base.is_optimal and relaxed.is_optimal):
        return 0, 0, 0
    point = max(0, base.cost - relaxed.cost)
    lo = max(0, base.bound - relaxed.cost)
    hi = max(0, base.cost - relaxed.bound)
    return point, lo, hi


def probe_constraints(problem: Problem, base_plan: Plan,
                      max_seconds: float = 10.0,
                      relative_gap: float = 0.005) -> list[Probe]:
    """Re-solve with each constraint relaxed; return probes sorted by recovery,
    biggest lever first. `relative_gap` must match the tolerance the base plan was
    solved at, or the two costs aren't measured with the same ruler.
    """
    probes: list[Probe] = []

    def run(name: str, mutate) -> None:
        p = problem.model_copy(deep=True)
        mutate(p)
        plan = solve_reorder(p, max_seconds, relative_gap)
        point, lo, hi = _recovery(base_plan, plan)
        probes.append(Probe(name, point, lo, hi, plan.is_optimal))

    run("budget +$10k/wk",
        lambda p: setattr(p, "budget", [b + BUDGET_STEP_CENTS for b in p.budget]))
    run("warehouse +10000u",
        lambda p: setattr(p, "warehouse_cap", p.warehouse_cap + WAREHOUSE_STEP_UNITS))
    run("safety -50%",
        lambda p: setattr(p, "safety_stock",
                          {s: int(v * SAFETY_SCALE) for s, v in p.safety_stock.items()}))

    return sorted(probes, key=lambda x: x.recovered, reverse=True)


def binding_constraint(probes: list[Probe]) -> tuple[Probe, bool]:
    """Which limit is binding -- and can we actually PROVE it?

    Returns (top_probe, proven). `proven` is True only when the winner's WORST-CASE
    recovery still beats the runner-up's BEST-CASE recovery. If it doesn't, the
    solver's slack is wide enough to swallow the difference and we must not claim a
    winner.
    """
    if not probes:
        raise ValueError("no probes")
    top = probes[0]
    if len(probes) == 1:
        return top, top.lo > 0
    runner_up = probes[1]
    proven = top.lo > runner_up.hi and top.lo > 0
    return top, proven
