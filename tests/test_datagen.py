import pandas as pd
from reorder.datagen import generate


def test_generate_writes_expected_shapes(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=40, weeks_history=104, seed=7)
    parts = pd.read_csv(tmp_path / "parts.csv")
    hist = pd.read_csv(tmp_path / "demand_history.csv")
    assert len(parts) == 40
    assert set(parts.columns) == {
        "sku", "unit_cost", "holding_cost", "order_cost", "moq",
        "lead_time", "volume", "opening_inventory"}
    assert (parts["unit_cost"] > 0).all()
    assert len(hist) == 40 * 104
    assert (hist["units"] >= 0).all()


def test_generate_is_deterministic(tmp_path):
    generate(out_dir=str(tmp_path / "a"), seed=7)
    generate(out_dir=str(tmp_path / "b"), seed=7)
    a = pd.read_csv(tmp_path / "a" / "demand_history.csv")
    b = pd.read_csv(tmp_path / "b" / "demand_history.csv")
    assert a.equals(b)
