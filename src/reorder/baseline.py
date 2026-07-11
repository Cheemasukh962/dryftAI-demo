"""The dumb baseline an ERP actually runs, plus the machinery to score any policy.

`(s, Q)` reorder policy: watch each part's inventory; when it drops to a reorder
point `s`, order a fixed batch `Q`. No optimization, no forecast of the future --
just a threshold and a fixed quantity. This is the honest thing to beat: if our
solver can't out-perform this on replayed demand, it isn't worth the complexity.
"""
import numpy as np
import pandas as pd


def realized_cost(parts_df: pd.DataFrame, orders: dict, actual_demand: dict,
                  weeks: int, stockout_penalty: int, safety_penalty: int,
                  safety_stock: dict) -> dict:
    """Roll a FIXED order schedule forward against ACTUAL demand and price it.

    This is the fair scorer: give it whatever weekly orders a policy chose and the
    demand that really happened, and it returns realized cost + fill rate. Both
    policies get scored by this same function on the same demand.
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
            total_cost += stockout_penalty * unmet                 # stockout
            total_cost += safety_penalty * max(0, safety_stock.get(s, 0) - inv)  # safety dip
            if placed[t] > 0:
                total_cost += p["order_cost"]                      # fixed order fee
    fill = (met / demanded) if demanded else 1.0
    return {"cost": int(total_cost), "fill_rate": fill, "met": met, "demanded": demanded}


def run_sq(parts_df: pd.DataFrame, actual_demand: dict, weeks: int,
           stockout_penalty: int = 15_000, safety_penalty: int = 1_000) -> dict:
    """Simulate the (s,Q) policy week by week and score what it did."""
    part = {r["sku"]: r for r in parts_df.to_dict("records")}
    orders = {s: [0] * weeks for s in part}
    safety_stock = {}
    for s, p in part.items():
        mean_wk = max(1.0, float(np.mean(actual_demand[s])))
        safety = int(round(mean_wk))                       # ~1 week of buffer
        safety_stock[s] = safety
        s_point = int(round(p["lead_time"] * mean_wk + safety))  # reorder point
        Q = int(max(p["moq"], round(4 * mean_wk)))         # fixed batch size
        inv = p["opening_inventory"]
        pipeline = [0] * (weeks + p["lead_time"] + 1)      # orders in transit, by arrival week
        for t in range(weeks):
            inv += pipeline[t]
            position = inv + sum(pipeline[t + 1:])         # on-hand + already-ordered
            if position <= s_point:                        # time to reorder?
                orders[s][t] = Q
                pipeline[t + p["lead_time"]] += Q
            inv -= min(inv, actual_demand[s][t])
    return realized_cost(parts_df, orders, actual_demand, weeks,
                         stockout_penalty, safety_penalty, safety_stock)
