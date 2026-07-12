"""Tracing must be strictly optional: no Langfuse keys -> no behaviour change.

The live "do spans actually reach Langfuse?" proof is a standalone script
(`scripts/verify_langfuse_tracing.py`) rather than a unit test, because turning
tracing on configures OpenTelemetry globally for the whole process.
"""
import reorder.observability as obs
from reorder.agent import build_agent


def test_tracing_is_off_without_keys(monkeypatch):
    monkeypatch.setattr(obs, "_configured", False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert obs.configure_tracing() is False


def test_flush_is_safe_when_tracing_off(monkeypatch):
    monkeypatch.setattr(obs, "_configured", False)
    obs.flush_traces()          # must not raise


def test_agent_still_builds_with_no_langfuse_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert build_agent() is not None
