"""Turn demand history into a low / middle / high forecast (p10 / p50 / p90).

Why a range and not a single number? Safety stock exists precisely because the
future is uncertain. A single point forecast can't express uncertainty; the
p10-p90 spread can, and that spread is what sizes the safety buffer.

Method: p50 is a recent demand level scaled by a week-of-year seasonal factor.
p10/p90 come from the spread of past forecast errors, POOLED across all weeks --
because two years of history gives only ~2 samples of any one calendar week,
far too few to read a percentile off directly.
"""
import numpy as np
import pandas as pd

# z-score for the 10th/90th percentile of a normal distribution.
_Z90 = 1.2816


def forecast_quantiles(history: pd.DataFrame, horizon: int = 12
                       ) -> dict[str, dict[str, list[int]]]:
    out: dict[str, dict[str, list[int]]] = {}
    for sku, g in history.groupby("sku"):
        g = g.sort_values("week")
        units = g["units"].to_numpy(dtype=float)
        weeks = g["week"].to_numpy(dtype=int)
        overall_mean = max(1.0, units.mean())

        # Seasonal factor per week-of-year = how that week compares to the average.
        woy = weeks % 52
        factor = np.ones(52)
        for k in range(52):
            sel = units[woy == k]
            if len(sel) > 0:
                factor[k] = max(0.05, sel.mean() / overall_mean)

        # Recent level = average of the last 12 weeks, with their season removed.
        recent = units[-12:]
        recent_woy = weeks[-12:] % 52
        recent_level = np.mean(recent / factor[recent_woy])

        # Compare our fitted curve to what actually happened -> pooled error spread.
        fitted = recent_level * factor[woy]
        resid_std = float(np.std(units - fitted)) or 1.0

        last_week = int(weeks[-1])
        p10, p50, p90 = [], [], []
        for h in range(1, horizon + 1):
            k = (last_week + h) % 52
            med = recent_level * factor[k]
            p50.append(max(0, int(round(med))))
            p10.append(max(0, int(round(med - _Z90 * resid_std))))
            p90.append(max(0, int(round(med + _Z90 * resid_std))))
        out[sku] = {"p10": p10, "p50": p50, "p90": p90}
    return out
