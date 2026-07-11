import pandas as pd
from reorder.datagen import generate
from reorder.baseline import run_sq


def test_sq_runs_and_reports(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=10, seed=1)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    # use the last 26 weeks of history as "actuals" to replay
    actual = {}
    for sku, g in hist.groupby("sku"):
        actual[sku] = g.sort_values("week")["units"].to_numpy()[-26:].tolist()
    result = run_sq(parts, actual, weeks=26)
    assert result["cost"] > 0
    assert 0.0 <= result["fill_rate"] <= 1.0
