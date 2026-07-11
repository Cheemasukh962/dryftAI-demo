"""Invent a believable, fully synthetic factory and write it to CSV.

Nothing here is real data. We generate 40 parts (with plausible costs and order
rules) and two years of weekly demand per part. Demand is built from three
ingredients so it looks like the real thing:
    demand = base level  x  seasonal factor  x  random noise
A fixed random `seed` makes the whole factory reproducible -- essential for a
live demo, where you never want the numbers to change between runs.
"""
import os

import numpy as np
import pandas as pd

from reorder.models import to_cents


def generate(out_dir: str = "data", n_parts: int = 40,
             weeks_history: int = 104, seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)

    skus = [f"PART-{1000 + i}" for i in range(n_parts)]

    # --- Parts table: costs (in cents), order rules, and starting stock ---
    rows = []
    base_levels = {}
    for s in skus:
        unit_cost_dollars = float(rng.uniform(2, 200))
        base_level = int(rng.integers(20, 400))       # average weekly demand
        base_levels[s] = base_level
        rows.append({
            "sku": s,
            "unit_cost": to_cents(unit_cost_dollars),
            # holding a unit for a week costs ~0.5% of its price; ordering is a flat fee
            "holding_cost": max(1, to_cents(unit_cost_dollars * 0.005)),
            "order_cost": to_cents(float(rng.uniform(20, 100))),
            "moq": int(rng.choice([25, 50, 100, 200])),
            "lead_time": int(rng.integers(1, 5)),      # 1-4 weeks
            "volume": int(rng.integers(1, 5)),
            "opening_inventory": int(base_level * rng.uniform(1.5, 3.0)),
        })
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, "parts.csv"), index=False)

    # --- Demand history: seasonal sine wave x random noise, per part per week ---
    hist_rows = []
    for s in skus:
        level = base_levels[s]
        phase = rng.uniform(0, 2 * np.pi)              # where the season peaks
        amp = rng.uniform(0.1, 0.4)                    # how strong the season is
        for w in range(weeks_history):
            seasonal = 1.0 + amp * np.sin(2 * np.pi * w / 52.0 + phase)
            noise = rng.normal(1.0, 0.15)
            units = max(0, int(round(level * seasonal * noise)))
            hist_rows.append({"sku": s, "week": w, "units": units})
    pd.DataFrame(hist_rows).to_csv(os.path.join(out_dir, "demand_history.csv"), index=False)
