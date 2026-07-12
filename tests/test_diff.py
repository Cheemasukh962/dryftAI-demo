from reorder.models import Plan
from reorder.diff import diff_plans


def _plan(orders):
    return Plan(status="OPTIMAL", cost=0, bound=0, orders=orders,
                inventory={}, backorder={}, short={})


def test_diff_finds_changed_weeks():
    before = _plan({"A": [0, 276, 0]})
    after = _plan({"A": [480, 0, 0]})
    d = diff_plans(before, after)
    assert d.changes["A"] == [(0, 0, 480), (1, 276, 0)]
    assert "A" in d.summary
