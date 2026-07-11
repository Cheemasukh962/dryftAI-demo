from ortools.sat.python import cp_model

from reorder.models import Problem, Plan


def solve_reorder(problem: Problem, max_seconds: float = 10.0) -> Plan:
    """Build and solve the reorder problem as an integer program.

    Decision variables per part i, week t:
      q[i,t]     units ordered (integer)
      y[i,t]     did we order at all (bool -> drives MOQ + fixed order cost)
      inv[i,t]   on-hand inventory (>= 0)
      back[i,t]  unmet demand carried (>= 0)
      short[i,t] units below safety stock (>= 0, soft)
    """
    m = cp_model.CpModel()
    skus = problem.skus

    # Tight-ish upper bound: nobody ever needs to hold/order more than total demand.
    BIG = {s: max(1, sum(problem.demand[s])) for s in skus}

    q, y, inv, back, short = {}, {}, {}, {}, {}
    for s in skus:
        p = problem.part(s)
        cap = BIG[s] + p.opening_inventory
        for t in range(problem.weeks):
            q[s, t] = m.NewIntVar(0, BIG[s], f"q_{s}_{t}")
            y[s, t] = m.NewBoolVar(f"y_{s}_{t}")
            inv[s, t] = m.NewIntVar(0, cap, f"inv_{s}_{t}")
            back[s, t] = m.NewIntVar(0, BIG[s], f"back_{s}_{t}")
            short[s, t] = m.NewIntVar(0, problem.safety_stock[s], f"short_{s}_{t}")

    for s in skus:
        p = problem.part(s)
        for t in range(problem.weeks):
            # An order placed at t-L arrives now. Before that, nothing arrives.
            arrivals = q[s, t - p.lead_time] if t - p.lead_time >= 0 else 0
            prev_net = (inv[s, t - 1] - back[s, t - 1]) if t >= 1 else p.opening_inventory
            # net inventory = previous net + arrivals - demand
            m.Add(inv[s, t] - back[s, t] == prev_net + arrivals - problem.demand[s][t])
            # order nothing, or at least the MOQ (big-M links q to the y switch)
            m.Add(q[s, t] >= p.moq * y[s, t])
            m.Add(q[s, t] <= BIG[s] * y[s, t])
            # soft safety stock: measure the dip below target, do not forbid it
            m.Add(short[s, t] >= problem.safety_stock[s] - inv[s, t])

    for t in range(problem.weeks):
        m.Add(sum(problem.part(s).unit_cost * q[s, t] for s in skus) <= problem.budget[t])
        m.Add(sum(problem.part(s).volume * inv[s, t] for s in skus) <= problem.warehouse_cap)

    m.Minimize(
        sum(problem.part(s).holding_cost * inv[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.part(s).order_cost * y[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.stockout_penalty * back[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.safety_penalty * short[s, t] for s in skus for t in range(problem.weeks))
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(m)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Plan(status=status_name, cost=None, bound=None,
                    orders={}, inventory={}, backorder={}, short={})

    def series(var):
        return {s: [solver.Value(var[s, t]) for t in range(problem.weeks)] for s in skus}

    return Plan(
        status=status_name,
        cost=round(solver.ObjectiveValue()),
        bound=round(solver.BestObjectiveBound()),
        orders=series(q), inventory=series(inv),
        backorder=series(back), short=series(short),
    )
