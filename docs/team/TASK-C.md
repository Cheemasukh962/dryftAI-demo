# Team Brief C — Pydantic AI agent and eval set

Branch: `teammate-c-agent`
Owner: Teammate C
Scope: Tasks 15, 16

## What to build
Create or extend:
- `src/reorder/agent.py`
- `tests/test_agent.py`
- `tests/test_agent_evals.py`

## Deliverables
Build a typed agent boundary that turns a plain-English disruption into a structured recommendation.

### Required output schema
Implement `Recommendation` as a Pydantic model with:
- `revised_orders: dict[str, list[int]]`
- `disruption_cost_dollars: float | None`
- `binding_constraint: str`
- `counterfactuals: list[str]`
- `explanation: str`

### Required entry points
- `build_agent(model=None) -> Agent`
- `run_disruption(text: str, data_dir="data") -> Recommendation`

### Required tool behavior
Register tools that:
- read part context from CSV
- solve the current problem
- apply a new lead time disruption
- probe constraints for binding limits
- simulate a plan under variance

Use `ModelRetry` on bad inputs so the agent can recover instead of fabricating a malformed answer.

## Test-first flow
Run the offline agent test:

```powershell
pytest tests/test_agent.py -v
```

Expected first failure: `ImportError` on `reorder.agent`.

## Important design rules
- The LLM never makes arithmetic decisions. The solver does.
- The CI path must be cost-free: use `TestModel` and avoid network API calls.
- The first real run is optional and should be a single manual smoke check using a real API key.

## Verification
Run:

```powershell
pytest tests/test_agent.py tests/test_agent_evals.py -v
```

Expected: the agent tests pass without hitting the network.

## Merge dependency
C should be implemented against the documented engine interfaces from A + B, but the test shape is stable enough to start early.
