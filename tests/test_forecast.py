import numpy as np
import pandas as pd
from reorder.forecast import forecast_quantiles


def _history():
    rows = []
    rng = np.random.default_rng(0)
    for w in range(104):
        seasonal = 1.0 + 0.3 * np.sin(2 * np.pi * w / 52.0)
        rows.append({"sku": "X", "week": w,
                     "units": max(0, int(100 * seasonal * rng.normal(1, 0.1)))})
    return pd.DataFrame(rows)


def test_shape_and_ordering():
    fc = forecast_quantiles(_history(), horizon=12)
    assert set(fc["X"]) == {"p10", "p50", "p90"}
    assert len(fc["X"]["p50"]) == 12
    for i in range(12):
        assert fc["X"]["p10"][i] <= fc["X"]["p50"][i] <= fc["X"]["p90"][i]
        assert fc["X"]["p10"][i] >= 0
        assert isinstance(fc["X"]["p50"][i], int)


def test_p50_near_recent_level():
    fc = forecast_quantiles(_history(), horizon=12)
    assert 70 <= np.mean(fc["X"]["p50"]) <= 130   # roughly the ~100 base level
