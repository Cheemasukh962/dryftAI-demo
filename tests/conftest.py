"""Test-suite guarantees, enforced before any test module is imported.

Once a developer puts real LANGFUSE_* keys in their .env, `build_agent()` would
happily start shipping a trace to Langfuse on EVERY test -- making the suite slow,
network-dependent, and polluting the real project with junk traces.

So we blank the keys here. conftest.py is imported before the test modules, and
python-dotenv's load_dotenv() will not override a variable that already exists --
so this wins even though observability.py calls load_dotenv() at import time.

Net effect: the suite stays offline, free, and fast no matter what is in .env.
"""
import os

os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
