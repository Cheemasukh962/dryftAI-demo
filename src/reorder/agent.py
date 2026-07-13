"""The agent layer: English in, explanation out. It never does the math.

This is the whole architectural point of the project. A language model is a
text-in/text-out machine that will happily invent numbers. So we give it a small
menu of real Python functions and force everything crossing the boundary through
strict Pydantic validation:

    buyer's sentence  ->  [LLM picks the tool + arguments]  ->  typed tool call
                                                                     |
                                        the SOLVER makes every numeric decision
                                                                     |
    explanation       <-  [LLM writes prose]              <-  typed Recommendation

If the model hallucinates a SKU or a nonsense lead time, the tool raises
`ModelRetry`, which hands the error back to the model to try again -- instead of
letting a made-up value reach the solver. In a chatbot a hallucination is a weird
sentence; in a purchasing system it is a wrong purchase order.
"""
import os

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from reorder.forecast import forecast_quantiles
from reorder.problem_builder import build_problem
from reorder.solver import solve_reorder
from reorder.scenario import (with_lead_time, disruption_cost,
                              disruption_cost_bounds, NotOptimalError)
from reorder.probes import probe_constraints
from reorder.simulate import simulate
from reorder.diff import diff_plans
from reorder.models import to_dollars
from reorder.observability import configure_tracing, flush_traces

load_dotenv()

DEFAULT_MODEL = os.environ.get("REORDER_MODEL", "openai:gpt-4o")


class Recommendation(BaseModel):
    """The validated shape of any answer the agent is allowed to give."""
    revised_orders: dict[str, list[int]]
    disruption_cost_dollars: float | None
    binding_constraint: str
    counterfactuals: list[str]
    explanation: str


class Deps(BaseModel):
    """Runtime dependencies handed to every tool call."""
    data_dir: str = "data"


SYSTEM_PROMPT = """You are a purchasing copilot for a factory buyer.

The buyer describes a supply disruption in plain English. Your job is ONLY to:
1. Identify the affected SKU and its new lead time (in weeks) from their message.
2. Call `analyze_lead_time_change` with those two values.
3. Return a Recommendation reporting what the SOLVER decided.

You NEVER invent, estimate, or calculate a number. Every quantity, cost and
constraint you state must come from a tool result.

Write `explanation` as 2-4 short sentences a busy buyer can act on. Cover:
  - what to order now (the first week's quantity from revised_orders)
  - what the delay costs (disruption_cost_dollars; if disruption_cost_range is
    given, say the cost is between those two numbers -- that is the solver's
    proven bound, not a guess)
  - which limit is holding them back (binding_constraint) and what relaxing it is
    worth (from counterfactuals)
If disruption_cost_dollars is null, say plainly that the solver could not PROVE a
reliable cost for this run, and do not invent one.

Speak in plain business English. Never mention JSON, fields, tools, or solvers by
name. Do not dump raw arrays at the buyer."""


# --- The real work. Kept as plain functions so they can be unit-tested directly,
# --- with thin @agent.tool wrappers below.

def _get_part_context(data_dir: str, sku: str) -> dict:
    parts = pd.read_csv(f"{data_dir}/parts.csv")
    row = parts[parts["sku"] == sku]
    if row.empty:
        raise ModelRetry(
            f"No such SKU '{sku}'. Valid examples: {parts['sku'].head(5).tolist()}")
    return row.iloc[0].to_dict()


# Solve settings for the agent path. These MUST match the tuning the CLI demo uses,
# or the agent quietly produces a worse answer than `reorder demo` does:
#   BUDGET_FACTOR < 1  -> the weekly cash cap actually BINDS. With a slack budget,
#                         relaxing the budget recovers $0 and "cash is your binding
#                         constraint" is simply false.
#   RELATIVE_GAP 0.01  -> tight enough to trust, loose enough that a 40-SKU instance
#                         can PROVE optimality. At 0.005 it times out as FEASIBLE and
#                         the honesty guard then (correctly) suppresses the cost delta.
#   MAX_SECONDS 60     -> generous HEADROOM. At gap 0.01 the disrupted solve needed
#                         ~20s of a 30s budget, so under the load of a real agent run
#                         it sometimes tipped over the limit, came back FEASIBLE, and
#                         the guard suppressed the cost. Flaky, not broken -- but a
#                         demo that intermittently says "not provable" is worthless.
#                         At gap 0.02 both solves prove in ~6s total, 10x inside the
#                         limit. The wider gap costs precision, but we publish the
#                         rigorous bound, so the honesty is preserved.
BUDGET_FACTOR = 0.9
RELATIVE_GAP = 0.02
MAX_SECONDS = 60.0


def _analyze_lead_time_change(data_dir: str, sku: str, new_lead_time: int) -> dict:
    """Re-solve with the new lead time; return the cost delta, the binding
    constraint, the revised orders, and how the plan holds up under variance."""
    if new_lead_time < 1:
        raise ModelRetry("lead_time must be a whole number of weeks >= 1.")

    parts = pd.read_csv(f"{data_dir}/parts.csv")
    if sku not in set(parts["sku"]):
        raise ModelRetry(
            f"No such SKU '{sku}'. Valid examples: {parts['sku'].head(5).tolist()}")
    hist = pd.read_csv(f"{data_dir}/demand_history.csv")

    fc = forecast_quantiles(hist, horizon=12)
    problem = build_problem(parts, fc, weeks=12)
    # Make the weekly cash cap bind -- the premise of the whole problem.
    weekly_spend = sum(problem.part(s).unit_cost * (sum(problem.demand[s]) / problem.weeks)
                       for s in problem.skus)
    problem.budget = [int(round(weekly_spend * BUDGET_FACTOR))] * problem.weeks

    before = solve_reorder(problem, max_seconds=MAX_SECONDS, relative_gap=RELATIVE_GAP)
    after_problem = with_lead_time(problem, sku, new_lead_time)
    after = solve_reorder(after_problem, max_seconds=MAX_SECONDS, relative_gap=RELATIVE_GAP)

    if after.status == "INFEASIBLE":
        raise ModelRetry(
            "With that lead time the problem is INFEASIBLE -- no valid plan exists. "
            "Ask the buyer to relax a constraint (budget, warehouse, or safety stock).")

    # Honesty guard: only report a delta if BOTH solves were proven optimal, and
    # report the rigorous interval alongside it (an "OPTIMAL" plan still carries
    # up to `RELATIVE_GAP` of slack, which a bare point estimate would hide).
    try:
        delta = to_dollars(disruption_cost(before, after))
        lo, hi = disruption_cost_bounds(before, after)
        cost_range = [to_dollars(lo), to_dollars(hi)]
    except NotOptimalError:
        delta, cost_range = None, None

    probes = probe_constraints(after_problem, after, max_seconds=MAX_SECONDS,
                               relative_gap=RELATIVE_GAP)
    sim = simulate(after_problem, after, n=1000)
    changes = diff_plans(before, after)

    return {
        "sku": sku,
        "new_lead_time": new_lead_time,
        "revised_orders": {sku: after.orders[sku]},
        "disruption_cost_dollars": delta,
        "disruption_cost_range": cost_range,
        "solver_status": after.status,
        "binding_constraint": probes[0].name,
        "counterfactuals": [
            f"{p.name}: recovers ${to_dollars(p.recovered):,.2f}" for p in probes],
        "plan_changes": changes.summary,
        "fill_rate_p50": round(sim.fill_rate_p50, 4),
        "fill_rate_p10": round(sim.fill_rate_p10, 4),
    }


def build_agent(model=None) -> Agent:
    """Construct the agent. `defer_model_check=True` means we do NOT need an API
    key just to build it -- only an actual live run needs one. That keeps the test
    suite free and offline."""
    # Switches on Langfuse tracing IF Langfuse keys are set; otherwise a no-op.
    configure_tracing()

    agent = Agent(
        model or DEFAULT_MODEL,
        deps_type=Deps,
        output_type=Recommendation,
        system_prompt=SYSTEM_PROMPT,
        defer_model_check=True,
    )

    @agent.tool
    def get_part_context(ctx: RunContext[Deps], sku: str) -> dict:
        """Look up one part's costs, MOQ, lead time and opening stock."""
        return _get_part_context(ctx.deps.data_dir, sku)

    @agent.tool
    def analyze_lead_time_change(ctx: RunContext[Deps], sku: str,
                                 new_lead_time: int) -> dict:
        """Re-plan for a new lead time and return what it cost and what binds."""
        return _analyze_lead_time_change(ctx.deps.data_dir, sku, new_lead_time)

    return agent


def run_disruption(text: str, data_dir: str = "data", model=None) -> Recommendation:
    """Entry point: a buyer's sentence in, a validated Recommendation out."""
    agent = build_agent(model)
    try:
        return agent.run_sync(text, deps=Deps(data_dir=data_dir)).output
    finally:
        # Short-lived CLI/script runs can exit before the exporter flushes.
        flush_traces()
