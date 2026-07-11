"""The terminal entry point. Subcommands: generate, solve (more added later).

Run as `reorder <command>` (installed via pyproject) or
`python -m reorder.cli <command>`.
"""
import argparse

import pandas as pd

from reorder.datagen import generate
from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.models import to_dollars


def _load_problem(data_dir: str, weeks: int):
    parts = pd.read_csv(f"{data_dir}/parts.csv")
    hist = pd.read_csv(f"{data_dir}/demand_history.csv")
    fc = forecast_quantiles(hist, horizon=weeks)
    return build_problem(parts, fc, weeks=weeks)


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

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
