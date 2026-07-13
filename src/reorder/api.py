"""HTTP layer for the front end. A thin wrapper -- it adds NO logic of its own.

Every number it returns comes from the same functions the CLI uses, so the UI and
`reorder demo` can never disagree. Run it with:

    uvicorn reorder.api:app --reload --port 8000

Note the honesty guards survive the trip to the browser:
  * `disruption_cost_dollars` is null when the solver could not PROVE a cost.
  * `binding_constraint.proven` is false when the solver's slack is wider than the
    gap between the probes. The UI must not claim a winner in that case.
"""
import functools
import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.scenario import (with_lead_time, disruption_cost,
                              disruption_cost_bounds, NotOptimalError)
from reorder.probes import probe_constraints, binding_constraint
from reorder.simulate import simulate
from reorder.diff import diff_plans
from reorder.baseline import backtest as run_backtest
from reorder.models import to_dollars

DATA_DIR = "data"
WEEKS = 12
BUDGET_FACTOR = 0.9     # <1 makes the weekly cash cap BIND -- the premise of the problem
RELATIVE_GAP = 0.005
MAX_SECONDS = 60.0

app = FastAPI(title="Reorder Copilot API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _load():
    parts = pd.read_csv(f"{DATA_DIR}/parts.csv")
    hist = pd.read_csv(f"{DATA_DIR}/demand_history.csv")
    return parts, hist


def _problem():
    """Build the Problem with a BINDING cash budget (see BUDGET_FACTOR)."""
    parts, hist = _load()
    fc = forecast_quantiles(hist, horizon=WEEKS)
    p = build_problem(parts, fc, weeks=WEEKS)
    weekly_spend = sum(p.part(s).unit_cost * (sum(p.demand[s]) / WEEKS) for s in p.skus)
    p.budget = [int(round(weekly_spend * BUDGET_FACTOR))] * WEEKS
    return p


@app.get("/api/parts")
def get_parts():
    parts, hist = _load()
    means = hist.groupby("sku")["units"].mean()
    out = []
    for r in parts.to_dict("records"):
        avg = float(means.get(r["sku"], 1)) or 1.0
        out.append({
            "sku": r["sku"],
            "unit_cost_dollars": round(r["unit_cost"] / 100, 2),
            "lead_time_weeks": int(r["lead_time"]),
            "moq": int(r["moq"]),
            "opening_inventory": int(r["opening_inventory"]),
            "avg_weekly_demand": int(round(avg)),
            "weeks_of_cover": round(r["opening_inventory"] / avg, 1),
        })
    # thinnest cover first -- the most at-risk parts lead the table
    return sorted(out, key=lambda x: x["weeks_of_cover"])


@app.get("/api/parts/{sku}/demand")
def get_demand(sku: str):
    _, hist = _load()
    h = hist[hist["sku"] == sku].sort_values("week")
    if h.empty:
        raise HTTPException(404, f"No such SKU '{sku}'")
    return [{"week": int(w), "units": int(u)} for w, u in zip(h["week"], h["units"])]


class DisruptRequest(BaseModel):
    sku: str
    new_lead_time_weeks: int


def _disrupt_payload(sku: str, new_lead_time_weeks: int) -> dict:
    """The full analysis. Shared by /api/disrupt and /api/agent so the AI path and
    the plain path can never disagree -- and so the agent path only solves ONCE."""
    req = DisruptRequest(sku=sku, new_lead_time_weeks=new_lead_time_weeks)
    if req.new_lead_time_weeks < 1:
        raise HTTPException(400, "new_lead_time_weeks must be >= 1")
    problem = _problem()
    if req.sku not in problem.demand:
        raise HTTPException(404, f"No such SKU '{req.sku}'")

    old_lead = problem.part(req.sku).lead_time
    before = solve_reorder(problem, MAX_SECONDS, RELATIVE_GAP)
    after_problem = with_lead_time(problem, req.sku, req.new_lead_time_weeks)
    after = solve_reorder(after_problem, MAX_SECONDS, RELATIVE_GAP)
    if after.status == "INFEASIBLE":
        raise HTTPException(422, "No valid plan exists with that lead time.")

    # Honesty guard: refuse to report a cost we cannot prove.
    try:
        cost = round(to_dollars(disruption_cost(before, after)), 2)
        lo, hi = disruption_cost_bounds(before, after)
        cost_range = [round(to_dollars(lo), 2), round(to_dollars(hi), 2)]
    except NotOptimalError:
        cost, cost_range = None, None

    probes = probe_constraints(after_problem, after, MAX_SECONDS, RELATIVE_GAP)
    top, proven = binding_constraint(probes)
    sim = simulate(after_problem, after, n=1000)
    d = diff_plans(before, after)

    changes = []
    for s in problem.skus:
        b, a = before.orders[s][0], after.orders[s][0]
        if b != a:
            changes.append({
                "sku": s, "before": b, "after": a, "delta": a - b,
                "cash_delta_dollars": round(
                    to_dollars(problem.part(s).unit_cost * (a - b)), 2),
                "cancelled": a == 0 and b > 0,
            })
    changes.sort(key=lambda r: -abs(r["cash_delta_dollars"]))

    spend = lambda plan: round(to_dollars(sum(   # noqa: E731
        problem.part(s).unit_cost * plan.orders[s][0] for s in problem.skus)), 2)

    return {
        "sku": req.sku,
        "old_lead_time_weeks": old_lead,
        "new_lead_time_weeks": req.new_lead_time_weeks,
        "solver_status": after.status,
        "weeks": WEEKS,
        "disruption_cost_dollars": cost,
        "disruption_cost_range_dollars": cost_range,
        "binding_constraint": {
            "name": top.name,
            "proven": proven,
            "recovered_dollars": round(to_dollars(top.recovered), 2),
        },
        "probes": [{
            "name": p.name,
            "recovered_dollars": round(to_dollars(p.recovered), 2),
            "provable_low_dollars": round(to_dollars(p.lo), 2),
            "provable_high_dollars": round(to_dollars(p.hi), 2),
        } for p in probes],
        "simulation": {
            "runs": sim.runs,
            "fill_rate_p50": round(sim.fill_rate_p50, 4),
            "fill_rate_p10": round(sim.fill_rate_p10, 4),
            "peak_cash_p50_dollars": round(to_dollars(sim.cash_p50), 2),
        },
        "weekly_budget_dollars": round(to_dollars(problem.budget[0]), 2),
        "cash_spent_week0_before_dollars": spend(before),
        "cash_spent_week0_after_dollars": spend(after),
        "parts_affected": len(d.changes),
        "total_parts": len(problem.skus),
        "order_changes_week0": changes,
        "focus_part_schedule": {
            "before": before.orders[req.sku],
            "after": after.orders[req.sku],
        },
    }


@app.post("/api/disrupt")
def disrupt(req: DisruptRequest):
    return _disrupt_payload(req.sku, req.new_lead_time_weeks)


CACHE_PATH = f"{DATA_DIR}/backtest_cache.json"


def _compute_backtest():
    parts, hist = _load()
    r = run_backtest(parts, hist, test_weeks=12,
                     budget_factor=BUDGET_FACTOR, max_seconds=3.0)
    return {
        "test_weeks": 12,
        "weekly_budget_dollars": round(to_dollars(r["budget_per_week"]), 2),
        "solver": {"cost_dollars": round(to_dollars(r["solver"]["cost"]), 2),
                   "fill_rate": round(r["solver"]["fill_rate"], 4)},
        "baseline_sq": {"cost_dollars": round(to_dollars(r["sq"]["cost"]), 2),
                        "fill_rate": round(r["sq"]["fill_rate"], 4)},
        "dollars_saved": round(r["dollars_saved"], 2),
        "fill_rate_delta": round(r["fill_delta"], 4),
    }


@functools.lru_cache(maxsize=1)
def _cached_backtest():
    """The backtest re-solves the whole plan once per week -- ~40s. That is far too
    long to block a page load, and while it ran the UI would be showing FALLBACK
    numbers, i.e. lying. So we persist it to disk: computed once, instant forever
    after. Delete data/backtest_cache.json to force a recompute."""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    result = _compute_backtest()
    with open(CACHE_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


@app.get("/api/backtest")
def get_backtest():
    return _cached_backtest()


class AgentRequest(BaseModel):
    text: str


@app.post("/api/agent")
def agent(req: AgentRequest):
    """The natural-language path. This is the ONLY endpoint that uses an LLM.

    Pydantic AI is used at BOTH ends and nowhere in between:
      1. EXTRACT  - the model reads the buyer's sentence and must return a
                    validated DisruptionInput. A hallucinated SKU is rejected
                    (ModelRetry) before it can reach the solver.
      2. SOLVE    - plain Python. CP-SAT decides every number. No AI.
      3. EXPLAIN  - the model turns the solver's numbers into prose for a buyer.

    Needs OPENAI_API_KEY. Everything else in this API works without one.
    """
    parts, _ = _load()
    valid = sorted(parts["sku"].tolist())
    try:
        from reorder.agent import extract_disruption, explain_result
    except Exception as e:
        raise HTTPException(503, f"Agent unavailable: {e}")

    try:
        parsed = extract_disruption(req.text, valid)          # 1. LLM in
    except Exception as e:
        raise HTTPException(422, f"Could not read that sentence: {e}")

    payload = _disrupt_payload(parsed.sku, parsed.new_lead_time_weeks)  # 2. solver

    try:
        explanation = explain_result(payload)                 # 3. LLM out
    except Exception as e:
        explanation = f"(The solver answered, but the explanation step failed: {e})"

    return {"explanation": explanation,
            "parsed": {"sku": parsed.sku,
                       "new_lead_time_weeks": parsed.new_lead_time_weeks},
            "recommendation": payload}


@app.get("/api/health")
def health():
    return {"ok": True}
