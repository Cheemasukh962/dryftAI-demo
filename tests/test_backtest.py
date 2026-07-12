import pandas as pd
from reorder.datagen import generate
from reorder.baseline import backtest


def test_solver_beats_baseline_under_binding_budget(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=8, seed=3)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    result = backtest(parts, hist, test_weeks=12, budget_factor=0.9, max_seconds=3.0)
    assert result["solver"]["cost"] > 0
    assert result["sq"]["cost"] > 0
    # Under a binding cash budget the optimizer rations across parts far better
    # than the greedy (s,Q) rule -> it should save money AND serve more demand.
    assert result["dollars_saved"] > 0
    assert result["fill_delta"] > 0
    print("solver:", result["solver"]["cost"], "sq:", result["sq"]["cost"],
          "saved$:", round(result["dollars_saved"], 2),
          "fill solver/sq:", round(result["solver"]["fill_rate"], 3),
          round(result["sq"]["fill_rate"], 3))
