"""Monte Carlo simulation: does the plan survive contact with variance?

The solver planned against the p50 (middle-of-the-road) forecast. Reality isn't
p50. This module holds the solver's chosen orders FIXED and rolls them forward
against many sampled demand futures, reporting the distribution of outcomes --
not just a single number -- so a buyer can see how the plan behaves in a bad week,
not only an average one.
"""
from dataclasses import dataclass

import numpy as np

from reorder.models import Problem, Plan


@dataclass
class SimResult:
    fill_rate_p50: float    # median fill rate across runs
    fill_rate_p10: float    # pessimistic (10th percentile) fill rate
    cash_p50: int           # median peak cash tied up in inventory (cents)
    runs: int


def simulate(problem: Problem, plan: Plan, n: int = 1000,
             cv: float = 0.15, seed: int = 0) -> SimResult:
    rng = np.random.default_rng(seed)
    skus = problem.skus
    fill_rates = np.zeros(n)
    peak_cash = np.zeros(n)

    for r in range(n):
        met = demanded = 0
        run_peak = 0
        for s in skus:
            p = problem.part(s)
            inv = p.opening_inventory
            orders = plan.orders[s]
            for t in range(problem.weeks):
                arrivals = orders[t - p.lead_time] if t - p.lead_time >= 0 else 0
                inv += arrivals
                mean = problem.demand[s][t]
                # sample demand around the forecast mean with coefficient-of-variation cv
                d = max(0, int(round(rng.normal(mean, cv * max(1, mean)))))
                demanded += d
                shipped = min(inv, d)
                met += shipped
                inv -= shipped
                run_peak = max(run_peak, p.unit_cost * max(0, inv))
        fill_rates[r] = (met / demanded) if demanded else 1.0
        peak_cash[r] = run_peak

    return SimResult(
        fill_rate_p50=float(np.percentile(fill_rates, 50)),
        fill_rate_p10=float(np.percentile(fill_rates, 10)),
        cash_p50=int(np.percentile(peak_cash, 50)),
        runs=n,
    )
