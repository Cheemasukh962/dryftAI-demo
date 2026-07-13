/**
 * The only place the frontend talks to the backend.
 *
 * Every number rendered by the UI comes from here. Nothing is computed in
 * TypeScript -- if we recomputed a cost in the browser it could disagree with the
 * solver, and the demo would start lying.
 *
 * The backend runs at :8000; vite proxies /api to it (see vite.config.ts).
 */

/* ---------- wire types (exactly what FastAPI returns) ---------- */

export interface Part {
  sku: string;
  unit_cost_dollars: number;
  lead_time_weeks: number;
  moq: number;
  opening_inventory: number;
  avg_weekly_demand: number;
  weeks_of_cover: number;
}

export interface Probe {
  name: string;
  recovered_dollars: number;
  provable_low_dollars: number;
  provable_high_dollars: number;
}

export interface OrderChange {
  sku: string;
  before: number;
  after: number;
  delta: number;
  cash_delta_dollars: number;
  cancelled: boolean;
}

export interface DisruptionResult {
  sku: string;
  old_lead_time_weeks: number;
  new_lead_time_weeks: number;
  solver_status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE";
  weeks: number;
  /** null when the solver could NOT prove a reliable cost. Never render $0 instead. */
  disruption_cost_dollars: number | null;
  disruption_cost_range_dollars: [number, number] | null;
  binding_constraint: {
    name: string;
    /** false => the solver's slack is wider than the gap between probes.
     *  The UI must NOT badge a winner in that case. */
    proven: boolean;
    recovered_dollars: number;
  };
  probes: Probe[];
  simulation: {
    runs: number;
    fill_rate_p50: number;
    fill_rate_p10: number;
    peak_cash_p50_dollars: number;
  };
  weekly_budget_dollars: number;
  cash_spent_week0_before_dollars: number;
  cash_spent_week0_after_dollars: number;
  parts_affected: number;
  total_parts: number;
  order_changes_week0: OrderChange[];
  focus_part_schedule: { before: number[]; after: number[] };
}

export interface BacktestResult {
  test_weeks: number;
  weekly_budget_dollars: number;
  solver: { cost_dollars: number; fill_rate: number };
  baseline_sq: { cost_dollars: number; fill_rate: number };
  dollars_saved: number;
  fill_rate_delta: number;
}

/* ---------- fetchers ---------- */

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> ${r.status} ${await r.text()}`);
  return r.json();
}

export const fetchParts = () => get<Part[]>("/api/parts");
export const fetchBacktest = () => get<BacktestResult>("/api/backtest");

/** The real solve. Runs 5 optimizations + 1,000 simulations -- expect 20-40s. */
export async function fetchDisruption(
  sku: string,
  newLeadTimeWeeks: number,
): Promise<DisruptionResult> {
  const r = await fetch("/api/disrupt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sku, new_lead_time_weeks: newLeadTimeWeeks }),
  });
  if (!r.ok) throw new Error(`/api/disrupt -> ${r.status} ${await r.text()}`);
  return r.json();
}

/* ---------- adapters: API shape -> the shapes the charts already speak ---------- */

export type PartRow = {
  sku: string; cost: number; lead: number; moq: number;
  onHand: number; avgWeek: number; woc: number;
};

export const toPartRows = (parts: Part[]): PartRow[] =>
  parts.map(p => ({
    sku: p.sku,
    cost: p.unit_cost_dollars,
    lead: p.lead_time_weeks,
    moq: p.moq,
    onHand: p.opening_inventory,
    avgWeek: p.avg_weekly_demand,
    woc: p.weeks_of_cover,
  }));

export type ReallocRow = { sku: string; delta: number; cancelled: boolean };

/** Biggest cash swings first; cap the list so the chart stays readable. */
export const toReallocation = (r: DisruptionResult, limit = 10): ReallocRow[] =>
  r.order_changes_week0
    .slice(0, limit)
    .map(c => ({
      sku: c.sku,
      delta: Math.round(c.cash_delta_dollars),
      cancelled: c.cancelled,
    }));

export type ProbeRow = {
  label: string; recovered: number; low: number; high: number;
  binding: boolean; errorRange: [number, number];
};

/** `binding` is only true when the backend PROVED it. Never infer it here. */
export const toProbeRows = (r: DisruptionResult): ProbeRow[] =>
  r.probes.map(p => {
    const recovered = Math.round(p.recovered_dollars);
    const low = Math.round(p.provable_low_dollars);
    const high = Math.round(p.provable_high_dollars);
    return {
      label: p.name,
      recovered,
      low,
      high,
      binding: r.binding_constraint.proven && p.name === r.binding_constraint.name,
      errorRange: [recovered - low, high - recovered] as [number, number],
    };
  });

export type ScheduleRow = { week: string; before: number; after: number };

export const toSchedule = (r: DisruptionResult): ScheduleRow[] =>
  r.focus_part_schedule.before.map((b, i) => ({
    week: `W${i}`,
    before: b,
    after: r.focus_part_schedule.after[i],
  }));

export type BacktestRow = { label: string; cost: number; fill: number };

export const toBacktestRows = (b: BacktestResult): BacktestRow[] => [
  { label: "(s,Q) rule", cost: Math.round(b.baseline_sq.cost_dollars), fill: +(b.baseline_sq.fill_rate * 100).toFixed(1) },
  { label: "This solver", cost: Math.round(b.solver.cost_dollars), fill: +(b.solver.fill_rate * 100).toFixed(1) },
];

/* ---------- the AI path (the ONLY endpoint that uses an LLM) ----------
 * EXTRACT (LLM reads the sentence)  ->  SOLVE (no AI)  ->  EXPLAIN (LLM writes prose)
 * The model translates at both ends. It never touches the arithmetic.
 */
export interface AgentResult {
  explanation: string;                                   // the LLM's prose
  parsed: { sku: string; new_lead_time_weeks: number };  // what it understood
  recommendation: DisruptionResult;                      // what the SOLVER decided
}

export async function fetchAgent(text: string): Promise<AgentResult> {
  const r = await fetch("/api/agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(`/api/agent -> ${r.status} ${await r.text()}`);
  return r.json();
}
