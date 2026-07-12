"""Agent eval set: does the agent behave across many ways of saying the same thing?

Two tiers, deliberately separated:

* OFFLINE (runs by default, free, fast). We stub the heavy solver tool with a
  canned result, because the solver is already tested to death elsewhere. What
  we are testing HERE is the agent layer: the tool gets called, its result flows
  into the output schema, and every scenario yields a valid `Recommendation`.

* LIVE (skipped unless you opt in). This is the eval that actually matters and
  the one that costs money: it sends the real sentences to the real LLM and
  checks it extracted the RIGHT SKU and lead time. Enable with:
      set REORDER_LIVE_EVAL=1   (and a valid OPENAI_API_KEY)
"""
import os

import pytest
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

import reorder.agent as agent_mod
from reorder.datagen import generate
from reorder.agent import build_agent, Deps, Recommendation

# (sentence, expected sku, expected new lead time)
SCENARIOS = [
    ("Supplier Kraus is 3 weeks late on PART-1000, lead time now 5.", "PART-1000", 5),
    ("PART-1001 lead time jumps to 6 weeks starting now.", "PART-1001", 6),
    ("Heads up: PART-1002 will take 4 weeks instead of 2.", "PART-1002", 4),
    ("We just learned PART-1003 ships in 5 weeks now.", "PART-1003", 5),
    ("Delay on PART-1004 - 7 week lead time.", "PART-1004", 7),
    ("PART-1005 lead time doubled to 4 weeks.", "PART-1005", 4),
    ("Vendor pushed PART-1006 to a 5 week lead time.", "PART-1006", 5),
    ("PART-1007 is now 3 weeks out.", "PART-1007", 3),
    ("Expect PART-1008 in 6 weeks, not 2.", "PART-1008", 6),
    ("PART-1009 lead time revised upward to 4 weeks.", "PART-1009", 4),
    ("PART-1010 back to a 5-week lead time after the fire.", "PART-1010", 5),
    ("Flag PART-1011: 5 weeks lead time going forward.", "PART-1011", 5),
]

CANNED = {
    "sku": "PART-1000",
    "new_lead_time": 5,
    "revised_orders": {"PART-1000": [480, 0, 0]},
    "disruption_cost_dollars": 37738.0,
    "solver_status": "OPTIMAL",
    "binding_constraint": "budget +$1000/wk",
    "counterfactuals": ["budget +$1000/wk: recovers $11,646.00",
                        "safety -10%: recovers $2,403.00",
                        "warehouse +1000u: recovers $540.00"],
    "plan_changes": "2 order change(s) across 1 SKU(s): PART-1000",
    "fill_rate_p50": 0.97,
    "fill_rate_p10": 0.91,
}


def _scripted(sku: str, lead: int) -> FunctionModel:
    """A stand-in model that calls the tool correctly and packages the result."""
    def fn(messages, info):
        returns = [p for m in messages for p in getattr(m, "parts", [])
                   if isinstance(p, ToolReturnPart)]
        if not returns:
            return ModelResponse(parts=[ToolCallPart(
                "analyze_lead_time_change", {"sku": sku, "new_lead_time": lead})])
        r = returns[-1].content
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "revised_orders": r["revised_orders"],
            "disruption_cost_dollars": r["disruption_cost_dollars"],
            "binding_constraint": r["binding_constraint"],
            "counterfactuals": r["counterfactuals"],
            "explanation": f"{sku} now has a {lead}-week lead time.",
        })])
    return FunctionModel(fn)


@pytest.mark.parametrize("text,sku,lead", SCENARIOS)
def test_scenario_yields_valid_recommendation(text, sku, lead, monkeypatch, tmp_path):
    """Every phrasing must end in a schema-valid Recommendation carrying the
    solver's numbers. Solver stubbed: this is an agent-layer test, not a solver test."""
    generate(out_dir=str(tmp_path), n_parts=12, seed=9)
    called = {}

    def fake_analyze(data_dir, s, lt):
        called["sku"], called["lead"] = s, lt
        return {**CANNED, "sku": s, "new_lead_time": lt,
                "revised_orders": {s: [480, 0, 0]}}

    monkeypatch.setattr(agent_mod, "_analyze_lead_time_change", fake_analyze)

    agent = build_agent(model=_scripted(sku, lead))
    result = agent.run_sync(text, deps=Deps(data_dir=str(tmp_path)))

    assert isinstance(result.output, Recommendation)
    assert called["sku"] == sku and called["lead"] == lead   # tool actually invoked
    assert sku in result.output.revised_orders
    assert len(result.output.counterfactuals) == 3


@pytest.mark.skipif(
    not (os.environ.get("REORDER_LIVE_EVAL") and os.environ.get("OPENAI_API_KEY")),
    reason="live eval costs money; set REORDER_LIVE_EVAL=1 and OPENAI_API_KEY to run",
)
@pytest.mark.parametrize("text,sku,lead", SCENARIOS)
def test_live_llm_extracts_correct_sku_and_lead_time(text, sku, lead, monkeypatch, tmp_path):
    """THE eval that matters: can the real model read a messy human sentence and
    pull out the right SKU and lead time? Solver stubbed so we pay only for tokens."""
    generate(out_dir=str(tmp_path), n_parts=12, seed=9)
    called = {}

    def fake_analyze(data_dir, s, lt):
        called["sku"], called["lead"] = s, lt
        return {**CANNED, "sku": s, "new_lead_time": lt,
                "revised_orders": {s: [480, 0, 0]}}

    monkeypatch.setattr(agent_mod, "_analyze_lead_time_change", fake_analyze)

    agent = build_agent()          # real model from REORDER_MODEL / default
    result = agent.run_sync(text, deps=Deps(data_dir=str(tmp_path)))

    assert isinstance(result.output, Recommendation)
    assert called.get("sku") == sku, f"model extracted {called.get('sku')!r}, want {sku!r}"
    assert called.get("lead") == lead, f"model extracted lead {called.get('lead')!r}, want {lead}"
