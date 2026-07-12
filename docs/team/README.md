# Team split — Reorder Copilot

Four parallel jobs finish the project. The **engine is already built and passing
tests** (Tasks 1–9): synthetic data, forecast, CP-SAT solver, and a backtest that
proves the solver beats the dumb `(s,Q)` baseline under a binding budget. What's
left is the disruption + explanation layer, the AI agent, and the demo/docs.

## Read these first (they travel with the repo)
- **Spec (what & why):** `docs/superpowers/specs/2026-07-11-reorder-copilot-design.md`
- **Plan (how, with full code for every task):** `docs/superpowers/plans/2026-07-11-reorder-copilot.md`
- Your own brief: `docs/team/TASK-<A|B|C|D>.md`

Each task in the plan is written as: write a failing test → run it → write the
code → run it green → commit. **The full code for your tasks is already in the
plan** — your job is to implement it, verify it, and adapt where the interfaces
below require.

## The four jobs

| Branch | Owner | Plan tasks | New files | Can start |
|---|---|---|---|---|
| `teammate-a-disruption`   | A | 10        | `src/reorder/scenario.py` | now (independent) |
| `teammate-b-analysis`     | B | 11, 12, 13 | `src/reorder/probes.py`, `simulate.py`, `diff.py` | now (independent) |
| `teammate-c-agent`        | C | 15, 16    | `src/reorder/agent.py`, `tests/test_agent*.py` | now (code to interfaces) |
| `teammate-d-integration`  | D | 14, 17    | edits `src/reorder/cli.py`, adds `README.md` | after A + B land |

## Dependency order
- **A** and **B** are fully independent — do them first, in parallel.
- **C** (agent) calls the analysis tools but can be built against the documented
  interfaces in TASK-C.md before A/B merge; final wiring uses A+B modules.
- **D** (demo CLI) wires A + B (+ C) together, so it merges last.

## Ground rules that keep merges clean
- Work only in the files your brief lists. Don't edit another job's file.
- Every task ends green: run `pytest` before you commit.
- Keep commits small and per-task (matches the existing history).
- One shared contract, project-wide: **all money is integer cents; never compare
  two non-OPTIMAL plans** (the solver returns status OPTIMAL to a 0.5% MIP gap).

## Setup (identical for everyone)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest                     # confirm the engine is green before you start
```
