"""Prove the tracing pipe really works, without needing Langfuse credentials.

We stand up a local HTTP server that speaks the same OTLP endpoint Langfuse
exposes (/v1/traces), point the exporter at it, run the agent offline, and assert
that real spans actually arrive. If they land here, they will land in Langfuse --
the only difference is the URL and the auth header.
"""
import os
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

RECEIVED = []


class Catcher(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        RECEIVED.append({
            "path": self.path,
            "bytes": len(body),
            "auth": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            "body": body,
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 4318), Catcher)
threading.Thread(target=server.serve_forever, daemon=True).start()

# Pretend we have Langfuse credentials, but aim the exporter at our local catcher.
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-FAKE"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-FAKE"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:4318"

from reorder.observability import configure_tracing, flush_traces
from reorder.agent import build_agent, Deps, Recommendation
from reorder.datagen import generate
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

on = configure_tracing()
print(f"tracing configured: {on}")
print(f"OTLP endpoint     : {os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']}")

tmp = tempfile.mkdtemp()
generate(out_dir=tmp, n_parts=5, seed=2)

CANNED_SKU = "PART-1000"


def scripted(messages, info):
    returns = [p for m in messages for p in getattr(m, "parts", [])
               if isinstance(p, ToolReturnPart)]
    if not returns:
        return ModelResponse(parts=[ToolCallPart(
            "analyze_lead_time_change",
            {"sku": CANNED_SKU, "new_lead_time": 5})])
    r = returns[-1].content
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
        "revised_orders": r["revised_orders"],
        "disruption_cost_dollars": r["disruption_cost_dollars"],
        "binding_constraint": r["binding_constraint"],
        "counterfactuals": r["counterfactuals"],
        "explanation": "traced run",
    })])


agent = build_agent(model=FunctionModel(scripted))
result = agent.run_sync(f"{CANNED_SKU} lead time goes to 5 weeks", deps=Deps(data_dir=tmp))
print(f"agent output ok   : {isinstance(result.output, Recommendation)}")

flush_traces()
server.shutdown()

print(f"\nOTLP requests received: {len(RECEIVED)}")
for r in RECEIVED:
    print(f"  POST {r['path']}  {r['bytes']} bytes  "
          f"content-type={r['content_type']}  auth={'Basic ***' if r['auth'] else None}")

# Spans are protobuf, but the operation names appear as readable strings inside.
blob = b"".join(r["body"] for r in RECEIVED)
for marker in (b"agent run", b"analyze_lead_time_change", b"chat", b"reorder-copilot"):
    print(f"  span content contains {marker!r}: {marker in blob}")

assert RECEIVED, "FAIL: no spans were exported"
assert any(r["path"].endswith("/v1/traces") for r in RECEIVED), "FAIL: wrong OTLP path"
assert any(r["auth"] for r in RECEIVED), "FAIL: no Authorization header (Langfuse needs it)"
print("\nPASS: real spans exported to the OTLP /v1/traces endpoint with Basic auth.")
