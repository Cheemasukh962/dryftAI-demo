"""What changed between two plans -- the human-facing explanation layer.

Under a rolling horizon the plan is re-solved every week and it WILL move, even
without a disruption. A buyer stops trusting a plan that keeps shifting unless
someone can say exactly what changed and why. This module answers "what changed":
diff_plans() does not explain WHY (that's the agent's job upstream), it only
gives the precise, week-by-week facts to explain from.
"""
from dataclasses import dataclass

from reorder.models import Plan


@dataclass
class PlanDiff:
    changes: dict[str, list[tuple[int, int, int]]]  # sku -> [(week, before, after)]
    summary: str


def diff_plans(before: Plan, after: Plan) -> PlanDiff:
    changes: dict[str, list[tuple[int, int, int]]] = {}
    for sku, after_orders in after.orders.items():
        before_orders = before.orders.get(sku, [0] * len(after_orders))
        deltas = [(t, before_orders[t], after_orders[t])
                  for t in range(len(after_orders))
                  if before_orders[t] != after_orders[t]]
        if deltas:
            changes[sku] = deltas
    n = sum(len(v) for v in changes.values())
    summary = (f"{n} order change(s) across {len(changes)} SKU(s): "
               + ", ".join(sorted(changes)) if changes else "no changes")
    return PlanDiff(changes=changes, summary=summary)
