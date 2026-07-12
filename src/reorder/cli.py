"""The terminal entry point. Subcommands: generate, solve, backtest, demo.

Run as `reorder <command>` (installed via pyproject) or
`python -m reorder.cli <command>`.
"""
import argparse

import pandas as pd

from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.baseline import backtest
from reorder.scenario import (with_lead_time, disruption_cost,
                              disruption_cost_bounds, NotOptimalError)
from reorder.probes import probe_constraints
from reorder.simulate import simulate
from reorder.diff import diff_plans
from reorder.models import to_dollars


def _load_problem(data_dir: str, weeks: int, budget_factor: float | None = None):
    """Build the Problem. `budget_factor` < 1 makes the weekly cash cap BIND --
    which is the whole premise of the project (cash is capped) and the only
    regime where cross-part rationing, and therefore the solver, actually matters.
    Leave it None to use build_problem's slack default."""
    parts = pd.read_csv(f"{data_dir}/parts.csv")
    hist = pd.read_csv(f"{data_dir}/demand_history.csv")
    fc = forecast_quantiles(hist, horizon=weeks)
    problem = build_problem(parts, fc, weeks=weeks)
    if budget_factor is not None:
        weekly_spend = sum(problem.part(s).unit_cost * (sum(problem.demand[s]) / weeks)
                           for s in problem.skus)
        problem.budget = [int(round(weekly_spend * budget_factor))] * weeks
    return problem


def cmd_generate(args):
    generate(out_dir=args.data_dir, n_parts=args.n_parts, seed=args.seed)
    print(f"Wrote synthetic data for {args.n_parts} parts to {args.data_dir}/")


def cmd_solve(args):
    problem = _load_problem(args.data_dir, args.weeks)
    plan = solve_reorder(problem, max_seconds=args.max_seconds)
    if plan.cost is not None:
        print(f"status={plan.status}  gap={plan.gap:.3f}  "
              f"cost=${to_dollars(plan.cost):,.2f}")
    else:
        print(f"status={plan.status}")
    total_units = sum(sum(plan.orders[s]) for s in problem.skus)
    print(f"total units ordered over {args.weeks} weeks: {total_units}")


def cmd_backtest(args):
    parts = pd.read_csv(f"{args.data_dir}/parts.csv")
    hist = pd.read_csv(f"{args.data_dir}/demand_history.csv")
    r = backtest(parts, hist, test_weeks=args.test_weeks,
                 budget_factor=args.budget_factor, max_seconds=args.max_seconds)
    print(f"=== Backtest over last {args.test_weeks} weeks "
          f"(binding budget ${to_dollars(r['budget_per_week']):,.0f}/wk) ===")
    print(f"solver:   cost=${to_dollars(r['solver']['cost']):>13,.2f}  "
          f"fill={r['solver']['fill_rate']:.1%}")
    print(f"(s,Q):    cost=${to_dollars(r['sq']['cost']):>13,.2f}  "
          f"fill={r['sq']['fill_rate']:.1%}")
    print(f"saved:    ${r['dollars_saved']:>13,.2f}   "
          f"fill delta={r['fill_delta']:+.1%}")


def cmd_demo(args):
    """The 60-second demo, driven purely by numbers -- no LLM anywhere in here.

    A supplier is late. Re-solve, price the damage, name the binding constraint,
    and stress-test the new plan.
    """
    problem = _load_problem(args.data_dir, args.weeks, args.budget_factor)
    if args.sku not in problem.demand:
        raise SystemExit(f"No such SKU '{args.sku}'. Try one from {args.data_dir}/parts.csv")

    old_lead = problem.part(args.sku).lead_time
    gap = args.relative_gap
    before = solve_reorder(problem, max_seconds=args.max_seconds, relative_gap=gap)
    after_problem = with_lead_time(problem, args.sku, args.lead_time)
    after = solve_reorder(after_problem, max_seconds=args.max_seconds, relative_gap=gap)

    print(f"DISRUPTION: {args.sku} lead time {old_lead} -> {args.lead_time} weeks\n")

    d = diff_plans(before, after)
    print(f"REVISED PLAN: {d.summary}")
    for wk, b, a in d.changes.get(args.sku, [])[:4]:
        print(f"  {args.sku}  week {wk}: {b} -> {a} units")

    try:
        delta = disruption_cost(before, after)
        lo, hi = disruption_cost_bounds(before, after)
        print(f"\nCOST OF THE DISRUPTION: ${to_dollars(delta):,.2f}")
        print(f"  rigorous bound: ${to_dollars(lo):,.2f} .. ${to_dollars(hi):,.2f}  "
              f"(both solves {before.status})")
    except NotOptimalError as e:
        print(f"\nCOST OF THE DISRUPTION: not reportable -- {e}")

    print("\nWHICH LIMIT IS BINDING?  (cost recovered if we relax it)")
    for i, p in enumerate(probe_constraints(after_problem, after,
                                            max_seconds=args.max_seconds,
                                            relative_gap=gap)):
        marker = "  <-- binding constraint" if i == 0 and p.recovered > 0 else ""
        print(f"  {p.name:<20} recovers ${to_dollars(p.recovered):>12,.2f}{marker}")

    sim = simulate(after_problem, after, n=args.runs)
    print(f"\nSTRESS TEST ({sim.runs} sampled demand futures):")
    print(f"  fill rate  median={sim.fill_rate_p50:.1%}   bad case (p10)={sim.fill_rate_p10:.1%}")
    print(f"  peak cash tied up (median)  ${to_dollars(sim.cash_p50):,.2f}")


def main():
    ap = argparse.ArgumentParser(prog="reorder")
    ap.add_argument("--data-dir", default="data")
    sub = ap.add_subparsers(required=True)

    g = sub.add_parser("generate", help="write synthetic factory data")
    g.add_argument("--n-parts", type=int, default=40)
    g.add_argument("--seed", type=int, default=7)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("solve", help="solve the baseline reorder plan")
    s.add_argument("--weeks", type=int, default=12)
    s.add_argument("--max-seconds", type=float, default=20.0)
    s.set_defaults(func=cmd_solve)

    b = sub.add_parser("backtest", help="solver vs (s,Q) on held-out demand")
    b.add_argument("--test-weeks", type=int, default=26)
    b.add_argument("--budget-factor", type=float, default=0.9)
    b.add_argument("--max-seconds", type=float, default=5.0)
    b.set_defaults(func=cmd_backtest)

    d = sub.add_parser("demo", help="run a disruption end-to-end (numbers only, no LLM)")
    d.add_argument("--sku", required=True)
    d.add_argument("--lead-time", type=int, required=True)
    d.add_argument("--weeks", type=int, default=12)
    d.add_argument("--runs", type=int, default=1000)
    d.add_argument("--budget-factor", type=float, default=0.9,
                   help="<1 makes the weekly cash cap bind (the realistic case)")
    d.add_argument("--max-seconds", type=float, default=45.0)
    d.add_argument("--relative-gap", type=float, default=0.01,
                   help="MIP gap tolerance; 0.01 proves OPTIMAL on 40 SKUs, "
                        "0.005 is tighter and fast at 20 SKUs")
    d.set_defaults(func=cmd_demo)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
