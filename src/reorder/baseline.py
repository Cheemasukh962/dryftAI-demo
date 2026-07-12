"""The dumb baseline an ERP actually runs, plus the machinery to score any policy.

`(s, Q)` reorder policy: watch each part's inventory; when it drops to a reorder
point `s`, order a fixed batch `Q`. No optimization, no forecast of the future --
just a threshold and a fixed quantity. This is the honest thing to beat.

The interesting comparison is under a BINDING weekly cash budget (the premise of
the whole project: cash is capped per week). There, (s,Q) has to ration crudely
-- it orders the most urgent parts first until the cash runs out -- while the
solver rations optimally across all parts at once. That gap is the solver's value.
"""
import numpy as np
import pandas as pd


def realized_cost(parts_df: pd.DataFrame, orders: dict, actual_demand: dict,
                  weeks: int, stockout_penalty: int, safety_penalty: int,
                  safety_stock: dict) -> dict:
    """Roll a FIXED order schedule forward against ACTUAL demand and price it.

    This is the fair scorer: give it whatever weekly orders a policy chose and the
    demand that really happened, and it returns realized cost + fill rate. Both
    policies are scored by this same function, on the same demand.
    """
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    total_cost = 0
    met = demanded = 0
    for s, p in part.items():
        inv = p["opening_inventory"]
        L = p["lead_time"]
        placed = orders.get(s, [0] * weeks)
        for t in range(weeks):
            arrivals = placed[t - L] if t - L >= 0 else 0
            inv += arrivals
            d = actual_demand[s][t]
            demanded += d
            shipped = min(inv, d)                 # can only ship what's on hand
            met += shipped
            inv -= shipped
            unmet = d - shipped
            total_cost += p["holding_cost"] * max(0, inv)          # holding
            total_cost += stockout_penalty * unmet                 # stockout (lost sale)
            total_cost += safety_penalty * max(0, safety_stock.get(s, 0) - inv)  # safety dip
            if placed[t] > 0:
                total_cost += p["order_cost"]                      # fixed order fee
    fill = (met / demanded) if demanded else 1.0
    return {"cost": int(total_cost), "fill_rate": fill, "met": met, "demanded": demanded}


def run_sq(parts_df: pd.DataFrame, actual_demand: dict, weeks: int,
           budget_per_week: int | None = None,
           stockout_penalty: int = 15_000, safety_penalty: int = 1_000) -> dict:
    """Simulate the (s,Q) policy week by week and score what it did.

    If `budget_per_week` is set, the policy can't spend more than that in a week:
    it orders the most urgent parts (lowest weeks-of-cover) first until the cash
    is gone, and the rest wait -- a realistic cash-strapped buyer.
    """
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    orders = {s: [0] * weeks for s in part}
    mw, s_point, Q, safety_stock = {}, {}, {}, {}
    for s, p in part.items():
        mw[s] = max(1.0, float(np.mean(actual_demand[s])))
        safety_stock[s] = int(round(mw[s]))                    # ~1 week buffer
        s_point[s] = int(round(p["lead_time"] * mw[s] + safety_stock[s]))
        Q[s] = int(max(p["moq"], round(4 * mw[s])))

    on_hand = {s: part[s]["opening_inventory"] for s in part}
    intransit = {s: {} for s in part}
    for t in range(weeks):
        for s in part:
            on_hand[s] += intransit[s].pop(t, 0)
        # who wants to reorder this week, most urgent first?
        wanters = []
        for s in part:
            position = on_hand[s] + sum(intransit[s].values())
            if position <= s_point[s]:
                wanters.append((position / mw[s], s))          # weeks-of-cover
        wanters.sort()
        spent = 0
        for _cover, s in wanters:
            cost = part[s]["unit_cost"] * Q[s]
            if budget_per_week is None or spent + cost <= budget_per_week:
                orders[s][t] = Q[s]
                arrive = t + part[s]["lead_time"]
                intransit[s][arrive] = intransit[s].get(arrive, 0) + Q[s]
                spent += cost
        for s in part:
            on_hand[s] = max(0, on_hand[s] - actual_demand[s][t])
    return realized_cost(parts_df, orders, actual_demand, weeks,
                         stockout_penalty, safety_penalty, safety_stock)


from reorder.forecast import forecast_quantiles          # noqa: E402
from reorder.problem_builder import build_problem         # noqa: E402
from reorder.solver import solve_reorder                  # noqa: E402
from reorder.models import to_dollars                     # noqa: E402


def run_solver_rolling(parts_df: pd.DataFrame, hist_df: pd.DataFrame,
                       test_weeks: int = 26, horizon: int = 12,
                       budget_per_week: int | None = None,
                       max_seconds: float = 5.0) -> dict:
    """Receding-horizon control: each test week, forecast from the data seen SO
    FAR (no peeking at the future), solve a `horizon`-week plan under the weekly
    budget, execute only the first week's order, then advance one week against
    ACTUAL demand -- exactly how a buyer would re-run this every Monday.
    """
    full = {sku: g.sort_values("week")["units"].to_numpy()
            for sku, g in hist_df.groupby("sku")}
    n = len(next(iter(full.values())))
    start = n - test_weeks
    skus = list(full)
    lead = {r["sku"]: r["lead_time"] for r in parts_df.to_dict("records")}
    open_inv = {r["sku"]: r["opening_inventory"] for r in parts_df.to_dict("records")}

    on_hand = dict(open_inv)                    # real evolving stock
    intransit = {s: {} for s in skus}           # {absolute_arrival_week: qty}
    executed = {s: [0] * test_weeks for s in skus}
    safety_stock = {}

    for w in range(test_weeks):
        abs_w = start + w
        for s in skus:                          # receive this week's arrivals
            on_hand[s] += intransit[s].pop(abs_w, 0)

        seen = hist_df[hist_df["week"] < abs_w]
        fc = forecast_quantiles(seen, horizon=horizon)
        problem = build_problem(parts_df, fc, weeks=horizon,
                                budget_per_week=budget_per_week,
                                stockout_penalty=15_000, safety_penalty=1_000)
        # Start from REAL on-hand, and tell the solver about orders still in transit
        # by placing them in the pipeline at the week they actually arrive -- NOT by
        # pretending they are already in the warehouse.
        pipeline = {s: [0] * horizon for s in skus}
        for s in skus:
            problem.part(s).opening_inventory = on_hand[s]
            for arrive_abs, qty in intransit[s].items():
                sub_t = arrive_abs - abs_w
                if 0 <= sub_t < horizon:
                    pipeline[s][sub_t] += qty
        problem.pipeline = pipeline
        safety_stock = problem.safety_stock

        plan = solve_reorder(problem, max_seconds=max_seconds)
        for s in skus:
            qty = plan.orders[s][0] if plan.cost is not None else 0
            executed[s][w] = qty
            if qty > 0:
                arrive = abs_w + lead[s]
                intransit[s][arrive] = intransit[s].get(arrive, 0) + qty
        for s in skus:                          # meet actual demand (lost sales)
            on_hand[s] = max(0, on_hand[s] - full[s][abs_w])

    actual = {s: full[s][start:start + test_weeks].tolist() for s in skus}
    return {**realized_cost(parts_df, executed, actual, test_weeks,
                            15_000, 1_000, safety_stock),
            "orders": executed}


def _binding_budget(parts_df: pd.DataFrame, hist_df: pd.DataFrame,
                    test_weeks: int, factor: float) -> int:
    """A weekly cash cap that actually binds: `factor` x the average weekly spend
    needed to buy recent demand. factor < 1 forces both policies to make choices."""
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    full = {sku: g.sort_values("week")["units"].to_numpy()
            for sku, g in hist_df.groupby("sku")}
    n = len(next(iter(full.values())))
    train_mean = {s: float(np.mean(full[s][: n - test_weeks])) for s in full}
    weekly_spend = sum(part[s]["unit_cost"] * train_mean[s] for s in part)
    return int(round(weekly_spend * factor))


def backtest(parts_df: pd.DataFrame, hist_df: pd.DataFrame,
             test_weeks: int = 26, budget_factor: float = 0.9,
             max_seconds: float = 5.0) -> dict:
    """Score the solver (rolling) and the (s,Q) baseline on the SAME held-out
    demand under the SAME binding weekly cash budget, and report the difference."""
    full = {sku: g.sort_values("week")["units"].to_numpy()
            for sku, g in hist_df.groupby("sku")}
    n = len(next(iter(full.values())))
    start = n - test_weeks
    actual = {s: full[s][start:start + test_weeks].tolist() for s in full}

    budget = _binding_budget(parts_df, hist_df, test_weeks, budget_factor)
    solver_res = run_solver_rolling(parts_df, hist_df, test_weeks=test_weeks,
                                    budget_per_week=budget, max_seconds=max_seconds)
    sq_res = run_sq(parts_df, actual, weeks=test_weeks, budget_per_week=budget)
    saved = to_dollars(sq_res["cost"] - solver_res["cost"])
    return {"solver": solver_res, "sq": sq_res, "budget_per_week": budget,
            "dollars_saved": saved,
            "fill_delta": solver_res["fill_rate"] - sq_res["fill_rate"]}
