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


def disruption_cost_bounds(before: Plan, after: Plan) -> tuple[int, int]:
    """A RIGOROUS interval for the disruption cost, in cents.

    Even an "OPTIMAL" plan carries a little slack: we stop the solver once it has
    proven it is within a small MIP gap, so each plan's true optimum lies
    somewhere in [bound, cost]. Subtracting two point estimates therefore hides
    some solver noise. The honest statement is an interval:

        true delta  in  [ after.bound - before.cost ,  after.cost - before.bound ]

    If that interval is wide relative to the delta itself, the number should not
    be trusted -- tighten `relative_gap` and re-solve.
    """
    if not (before.is_optimal and after.is_optimal):
        raise NotOptimalError(
            f"Refusing to compare: before={before.status}, after={after.status}."
        )
    return (after.bound - before.cost, after.cost - before.bound)
