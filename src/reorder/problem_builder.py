"""Assemble a solvable Problem from a parts table + a forecast.

This is the glue between the data layer and the solver: it decides the numbers
the solver treats as fixed inputs -- safety stock, the weekly cash budget, the
warehouse cap, and the penalty sizes -- deriving sensible defaults from the data
so the demo works out of the box.
"""
import numpy as np
import pandas as pd

from reorder.models import Part, Problem


def build_problem(parts_df: pd.DataFrame, forecast: dict, weeks: int = 12,
                  service_z: float = 1.2816, budget_per_week: int | None = None,
                  warehouse_cap: int | None = None,
                  stockout_penalty: int | None = None,
                  safety_penalty: int = 1_000) -> Problem:
    parts = [Part(**row) for row in parts_df.to_dict("records")]
    skus = [p.sku for p in parts]

    part_by_sku = {p.sku: p for p in parts}

    # The solver plans against the middle-of-the-road (p50) demand.
    demand = {s: forecast[s]["p50"][:weeks] for s in skus}

    # Safety stock must cover demand variability over the RISK WINDOW -- the lead
    # time plus one review period -- not just a single week. If weekly forecast
    # errors are roughly independent, the spread over L+1 weeks grows like
    # sqrt(L+1). (p90 - p50) is ~1 week of spread, so we scale it by sqrt(L+1).
    # Ignoring lead time here badly under-buffers long-lead parts (the bug that
    # first made the optimizer lose to the (s,Q) baseline).
    safety_stock = {}
    for s in skus:
        weekly_spread = np.mean([forecast[s]["p90"][t] - forecast[s]["p50"][t]
                                 for t in range(weeks)])
        risk_window = part_by_sku[s].lead_time + 1
        safety_stock[s] = max(0, int(round(weekly_spread * np.sqrt(risk_window))))

    if budget_per_week is None:
        # default: 1.2x the average weekly spend needed to buy expected demand
        weekly_spend = sum(part_by_sku[s].unit_cost * np.mean(demand[s]) for s in skus)
        budget_per_week = int(round(weekly_spend * 1.2))
    budget = [budget_per_week] * weeks

    if warehouse_cap is None:
        # default: 1.5x the volume of a peak week's expected demand
        peak_vol = sum(part_by_sku[s].volume * max(demand[s]) for s in skus)
        warehouse_cap = int(round(peak_vol * 1.5))

    if stockout_penalty is None:
        # make a stockout dominate holding decisions (~200x an average holding cost)
        avg_holding = int(np.mean([p.holding_cost for p in parts]))
        stockout_penalty = max(15_000, avg_holding * 200)

    return Problem(
        parts=parts, weeks=weeks, demand=demand, safety_stock=safety_stock,
        budget=budget, warehouse_cap=warehouse_cap,
        stockout_penalty=stockout_penalty, safety_penalty=safety_penalty,
    )
