"""The optimization engine: turn a purchasing Problem into the cheapest legal Plan.

We do NOT write an algorithm that computes order quantities. Instead we *declare*
the problem to Google OR-Tools' CP-SAT solver and let it search for the optimum:
  - decision variables  = the choices we're allowed to make (how much to order, etc.)
  - constraints         = the rules those choices must obey (MOQ, budget, space, ...)
  - objective           = the single number to minimize (total cost)

CP-SAT is an INTEGER solver: it cannot use fractional values, which is why every
money amount is stored as integer cents (see models.py) and every quantity is a
whole number of units.
"""
from ortools.sat.python import cp_model

from reorder.models import Problem, Plan


def solve_reorder(problem: Problem, max_seconds: float = 10.0,
                  relative_gap: float = 0.005) -> Plan:
    """Solve one reorder Problem and return the proven-or-best Plan.

    Decision variables, defined per part `s`, per week `t`:
      q[s,t]     units ordered this week            (integer >= 0)
      y[s,t]     did we place an order at all?       (boolean 0/1)
      inv[s,t]   units on hand at end of week        (integer >= 0)
      back[s,t]  demand we failed to meet            (integer >= 0)
      short[s,t] units we fell below safety stock    (integer >= 0)

    `relative_gap` is the MIP gap tolerance. CP-SAT finds a near-perfect plan in
    seconds, but *proving* it is exactly best can take minutes -- a fixed-charge
    integer program has a long proof tail. So we accept "proven within this
    fraction of the best possible" as optimal-for-our-purposes (standard MIP
    practice). The Plan still reports its true gap, so nothing is hidden.
    """
    m = cp_model.CpModel()
    skus = problem.skus

    # Upper bound for order size and inventory. No sane plan ever orders or holds
    # more than the entire horizon's demand at once. A TIGHT bound shrinks the
    # search space, so the solver proves optimality faster -- this is a real
    # performance lever, not cosmetic.
    BIG = {s: max(1, sum(problem.demand[s])) for s in skus}

    # --- Create every decision variable up front ---
    q, y, inv, back, short = {}, {}, {}, {}, {}
    for s in skus:
        p = problem.part(s)
        cap = BIG[s] + p.opening_inventory
        for t in range(problem.weeks):
            q[s, t] = m.NewIntVar(0, BIG[s], f"q_{s}_{t}")
            y[s, t] = m.NewBoolVar(f"y_{s}_{t}")
            inv[s, t] = m.NewIntVar(0, cap, f"inv_{s}_{t}")
            back[s, t] = m.NewIntVar(0, BIG[s], f"back_{s}_{t}")
            # short can never exceed the safety target itself (you can't dip below 0).
            short[s, t] = m.NewIntVar(0, problem.safety_stock[s], f"short_{s}_{t}")

    # --- The rules (constraints) that every solution must satisfy ---
    for s in skus:
        p = problem.part(s)
        for t in range(problem.weeks):
            # Lead time as an index shift: an order placed L weeks ago ARRIVES now.
            # Before week L there is nothing in the pipeline yet, so arrivals = 0.
            arrivals = q[s, t - p.lead_time] if t - p.lead_time >= 0 else 0

            # "Net inventory position" = on-hand minus what we owe (backorders).
            # Last week's net carries into this week; week 0 starts from opening stock.
            prev_net = (inv[s, t - 1] - back[s, t - 1]) if t >= 1 else p.opening_inventory

            # Flow balance: what we have now = what we had + what arrived - what was demanded.
            # Splitting the single net value into inv (>=0) and back (>=0) lets the
            # solver represent a shortage as a positive `back` instead of negative stock.
            m.Add(inv[s, t] - back[s, t] == prev_net + arrivals - problem.demand[s][t])

            # Minimum order quantity, enforced through the on/off switch y:
            #   y = 0  -> both lines force q = 0        (order nothing)
            #   y = 1  -> moq <= q <= BIG               (order at least the MOQ)
            # This is the classic "big-M" trick to link a quantity to a yes/no decision.
            m.Add(q[s, t] >= p.moq * y[s, t])
            m.Add(q[s, t] <= BIG[s] * y[s, t])

            # Safety stock is SOFT. We measure how far we dip below the target (`short`)
            # and price it in the objective, rather than forbidding it. A hard rule
            # (inv >= safety) would make the model "infeasible" the instant anything
            # slips -- useless to a buyer who needs to know HOW bad, not just "no plan".
            m.Add(short[s, t] >= problem.safety_stock[s] - inv[s, t])

    for t in range(problem.weeks):
        # Weekly cash cap: this week's spend can't exceed the budget (all in cents).
        m.Add(sum(problem.part(s).unit_cost * q[s, t] for s in skus) <= problem.budget[t])
        # Warehouse space: total volume of everything on hand fits in the warehouse.
        m.Add(sum(problem.part(s).volume * inv[s, t] for s in skus) <= problem.warehouse_cap)

    # --- The single number to minimize: total cost over the whole horizon ---
    # Four terms, all in cents. The stockout penalty is set ~15x the safety penalty
    # (see problem_builder / callers), so the solver treats an actual shortage as far
    # worse than merely dipping into the safety buffer.
    m.Minimize(
        sum(problem.part(s).holding_cost * inv[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.part(s).order_cost * y[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.stockout_penalty * back[s, t] for s in skus for t in range(problem.weeks))
        + sum(problem.safety_penalty * short[s, t] for s in skus for t in range(problem.weeks))
    )

    # --- Hand the whole description to the solver and let it search ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds     # give up (as FEASIBLE) after this
    solver.parameters.relative_gap_limit = relative_gap     # "optimal" once proven this close
    solver.parameters.num_search_workers = 8                # search in parallel across cores
    status = solver.Solve(m)
    status_name = solver.StatusName(status)  # "OPTIMAL", "FEASIBLE", "INFEASIBLE", ...

    # If the solver couldn't even find a valid plan, return an empty Plan carrying
    # the status so callers can react honestly instead of crashing.
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Plan(status=status_name, cost=None, bound=None,
                    orders={}, inventory={}, backorder={}, short={})

    def series(var):
        """Read a solved variable back out into a plain {sku: [value per week]} dict."""
        return {s: [solver.Value(var[s, t]) for t in range(problem.weeks)] for s in skus}

    return Plan(
        status=status_name,
        cost=round(solver.ObjectiveValue()),      # the achieved total cost, in cents
        bound=round(solver.BestObjectiveBound()),  # best cost the solver could PROVE possible;
                                                    # cost == bound  <=>  proven OPTIMAL
        orders=series(q), inventory=series(inv),
        backorder=series(back), short=series(short),
    )
