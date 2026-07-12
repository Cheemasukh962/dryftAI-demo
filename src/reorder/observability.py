"""Optional tracing: record every agent run to Langfuse.

WHY: the agent is the one non-deterministic part of this system. The solver either
proves OPTIMAL or it doesn't -- but the LLM can pick the wrong tool, misread a SKU,
or take three tries to get it right, and none of that shows up in a return value.
Tracing is how you SEE what it actually did: which tool it called, with what
arguments, what came back, how long it took, and what it cost in tokens.

HOW: Pydantic AI emits OpenTelemetry spans, and Langfuse ingests OpenTelemetry.
So there is no Langfuse SDK here and no new dependency -- we just point the OTel
exporter at Langfuse's endpoint and turn Pydantic AI's instrumentation on.

Entirely optional. With no Langfuse keys set, `configure_tracing()` is a no-op and
the app behaves exactly as before -- so tests stay free, offline, and fast.
"""
import base64
import os

from dotenv import load_dotenv

load_dotenv()

_configured = False


def configure_tracing(service_name: str = "reorder-copilot") -> bool:
    """Send agent runs to Langfuse if credentials are present.

    Returns True if tracing was switched on, False if we no-op'd (no keys).
    Safe to call repeatedly; only the first call does anything.
    """
    global _configured
    if _configured:
        return True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not (public_key and secret_key):
        return False        # no keys -> tracing off, everything else unchanged

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    # Langfuse authenticates the OTLP endpoint with HTTP Basic (public:secret).
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", f"{host}/api/public/otel")
    os.environ.setdefault("OTEL_EXPORTER_OTLP_HEADERS", f"Authorization=Basic {auth}")

    import logfire
    # send_to_logfire=False: we are NOT using Logfire's own backend, only its
    # OpenTelemetry plumbing, which then ships the spans to Langfuse.
    logfire.configure(service_name=service_name, send_to_logfire=False, console=False)
    logfire.instrument_pydantic_ai()

    _configured = True
    return True


def flush_traces() -> None:
    """Force-send any buffered spans. Useful in short-lived scripts/CLI runs that
    would otherwise exit before the exporter's background flush."""
    if not _configured:
        return
    import logfire
    logfire.force_flush()
