from reorder.models import Problem, Plan


class NotOptimalError(RuntimeError):
    """Raised when someone tries to compare non-OPTIMAL solves."""


def with_lead_time(problem: Problem, sku: str, new_lead_time: int) -> Problem:
    updated = problem.model_copy(deep=True)
    updated.part(sku).lead_time = new_lead_time
    return updated


def disruption_cost(before: Plan, after: Plan) -> int:
    """Cost of a disruption = after.cost - before.cost, in cents.

    Refuses to compute unless BOTH plans are proven OPTIMAL: two FEASIBLE
    solutions can differ for reasons unrelated to the disruption, so the delta
    would be partly solver noise.
    """
    if not (before.is_optimal and after.is_optimal):
        raise NotOptimalError(
            f"Refusing to compare: before={before.status}, after={after.status}. "
            "A cost delta between non-OPTIMAL solves is meaningless."
        )
    return after.cost - before.cost
