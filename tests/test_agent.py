"""Offline agent tests. These must NEVER hit the network or cost money.

Two things are worth proving, and they need two different fake models:

1. `TestModel` invents dummy tool arguments (sku='a', lead_time=0). Our typed
   boundary must REJECT those via ModelRetry rather than pass garbage to the
   solver. So "the run blows up" is the CORRECT behaviour, and we assert it.
2. `FunctionModel` lets us script a well-formed tool call, so we can drive the
   real solver end-to-end offline and check we get a validated Recommendation.
"""
import pandas as pd
import pytest
from pydantic_ai import ModelRetry
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

from reorder.datagen import generate
from reorder.agent import (build_agent, run_disruption, Deps, Recommendation,
                           _analyze_lead_time_change)


@pytest.fixture
def data_dir(tmp_path):
    generate(out_dir=str(tmp_path), n_parts=6, seed=2)
    return str(tmp_path)


def _scripted_model(sku: str, lead_time: int = 5) -> FunctionModel:
    """A fake LLM that calls our tool with VALID args, then turns the tool's
    result into a Recommendation -- exactly what a real model should do."""
    def fn(messages, info):
        tool_results = [p for m in messages for p in getattr(m, "parts", [])
                        if isinstance(p, ToolReturnPart)]
        if not tool_results:
            return ModelResponse(parts=[ToolCallPart(
                "analyze_lead_time_change",
                {"sku": sku, "new_lead_time": lead_time})])

        # The solver has spoken. Package its numbers into the output schema.
        r = tool_results[-1].content
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "revised_orders": r["revised_orders"],
            "disruption_cost_dollars": r["disruption_cost_dollars"],
            "binding_constraint": r["binding_constraint"],
            "counterfactuals": r["counterfactuals"],
            "explanation": f"{sku} lead time moved to {lead_time} weeks.",
        })])
    return FunctionModel(fn)


def test_agent_builds_without_api_key(monkeypatch):
    # Constructing the agent must not require OPENAI_API_KEY -- only a live run does.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert build_agent() is not None


def test_happy_path_returns_validated_recommendation(data_dir):
    rec = run_disruption("PART-1000 lead time goes to 5 weeks",
                         data_dir=data_dir, model=_scripted_model("PART-1000"))
    assert isinstance(rec, Recommendation)
    assert "PART-1000" in rec.revised_orders
    assert rec.binding_constraint          # the solver named a binding limit
    assert len(rec.counterfactuals) == 3   # three constraint probes


def test_typed_boundary_rejects_hallucinated_args(data_dir):
    """TestModel passes made-up arguments. The agent must NOT quietly accept them:
    ModelRetry fires, and when the model can't fix itself the run fails loudly
    instead of producing a wrong purchase order."""
    agent = build_agent()
    with agent.override(model=TestModel()):
        with pytest.raises(UnexpectedModelBehavior):
            agent.run_sync("nonsense", deps=Deps(data_dir=data_dir))


def test_unknown_sku_raises_model_retry(data_dir):
    with pytest.raises(ModelRetry):
        _analyze_lead_time_change(data_dir, "NOT-A-REAL-SKU", 5)


def test_bad_lead_time_raises_model_retry(data_dir):
    with pytest.raises(ModelRetry):
        _analyze_lead_time_change(data_dir, "PART-1000", 0)
