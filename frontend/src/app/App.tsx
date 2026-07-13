import { useState, useEffect, useRef, Fragment } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
  Cell, ReferenceLine, ComposedChart, ErrorBar, LabelList,
} from "recharts";
import {
  CheckCircle, AlertTriangle, Moon, Sun, RotateCcw,
} from "lucide-react";
import {
  fetchParts, fetchBacktest, fetchDisruption, fetchAgent,
  toPartRows, toReallocation, toProbeRows, toSchedule, toBacktestRows,
  type DisruptionResult, type BacktestResult,
  type PartRow, type ReallocRow, type ProbeRow, type ScheduleRow, type BacktestRow,
} from "./api";

/* ─── Design tokens (dark instrument mode) ───────────────────────────────── */
const Dk = {
  copper:       "#D6863A",
  copperLight:  "#E2A567",
  copperSubtle: "rgba(214,134,58,0.14)",
  green:        "#33B37C",
  greenSubtle:  "rgba(51,179,124,0.14)",
  red:          "#E5654E",
  redSubtle:    "rgba(229,101,78,0.18)",
  chartMuted:   "#33404F",
  chartGrid:    "#222E3A",
  canvas:       "#0C121A",
  surface:      "#161F29",
  subtle:       "#222E3A",
  inset:        "#10171F",
  border:       "#33404F",
  borderSubtle: "#222E3A",
  fgPrimary:    "#E7ECF2",
  fgSecondary:  "#AEBAC8",
  fgMuted:      "#63728A",
};

const Lt = {
  copper:       "#D6863A",
  copperLight:  "#BC6F26",
  copperSubtle: "#FBF3EA",
  green:        "#1E9A61",
  greenSubtle:  "#E7F4EC",
  red:          "#D4463A",
  redSubtle:    "#FBE9E6",
  chartMuted:   "#CDD7E1",
  chartGrid:    "#E2E8EF",
  canvas:       "#F7F9FB",
  surface:      "#FFFFFF",
  subtle:       "#EEF2F6",
  inset:        "#E2E8EF",
  border:       "#CDD7E1",
  borderSubtle: "#E2E8EF",
  fgPrimary:    "#0F1720",
  fgSecondary:  "#63728A",
  fgMuted:      "#8593A5",
};

/* ─── Fixture data ───────────────────────────────────────────────────────── */
const PARTS_FALLBACK = [
  { sku: "PART-1003", cost: 111.59, lead: 3,  moq: 200,  onHand:   635, avgWeek:  203, woc:  3.1 },
  { sku: "PART-1012", cost:  87.40, lead: 4,  moq: 150,  onHand:   572, avgWeek:  151, woc:  3.8 },
  { sku: "PART-1000", cost:  43.20, lead: 2,  moq: 500,  onHand:  2814, avgWeek:  540, woc:  5.2 },
  { sku: "PART-1007", cost: 210.50, lead: 6,  moq:  50,  onHand:   390, avgWeek:   62, woc:  6.3 },
  { sku: "PART-1001", cost:  15.30, lead: 2,  moq:1000,  onHand:  8200, avgWeek: 1025, woc:  8.0 },
  { sku: "PART-1005", cost: 330.00, lead: 8,  moq:  25,  onHand:   180, avgWeek:   18, woc: 10.0 },
  { sku: "PART-1009", cost:  67.80, lead: 3,  moq: 300,  onHand:  3600, avgWeek:  300, woc: 12.0 },
  { sku: "PART-1014", cost:  22.10, lead: 2,  moq: 800,  onHand: 11200, avgWeek:  800, woc: 14.0 },
  { sku: "PART-1002", cost:  58.90, lead: 4,  moq: 200,  onHand:  3100, avgWeek:  195, woc: 15.9 },
  { sku: "PART-1006", cost: 145.00, lead: 5,  moq: 100,  onHand:  2000, avgWeek:  120, woc: 16.7 },
  { sku: "PART-1010", cost:  29.50, lead: 2,  moq: 600,  onHand: 10800, avgWeek:  620, woc: 17.4 },
  { sku: "PART-1008", cost:  88.00, lead: 4,  moq: 150,  onHand:  2850, avgWeek:  155, woc: 18.4 },
  { sku: "PART-1013", cost: 190.00, lead: 6,  moq:  60,  onHand:  1260, avgWeek:   65, woc: 19.4 },
  { sku: "PART-1004", cost:  36.70, lead: 3,  moq: 400,  onHand:  8000, avgWeek:  410, woc: 19.5 },
  { sku: "PART-1011", cost:  72.30, lead: 4,  moq: 200,  onHand:  4200, avgWeek:  200, woc: 21.0 },
  { sku: "PART-1015", cost:  55.00, lead: 3,  moq: 300,  onHand:  6900, avgWeek:  310, woc: 22.3 },
  { sku: "PART-1016", cost: 118.00, lead: 5,  moq: 100,  onHand:  2500, avgWeek:  100, woc: 25.0 },
  { sku: "PART-1017", cost:  24.80, lead: 2,  moq: 750,  onHand: 20000, avgWeek:  760, woc: 26.3 },
  { sku: "PART-1018", cost: 410.00, lead: 8,  moq:  20,  onHand:   560, avgWeek:   20, woc: 28.0 },
  { sku: "PART-1019", cost:  31.20, lead: 2,  moq: 500,  onHand: 15600, avgWeek:  500, woc: 31.2 },
];

const REALLOCATION_FALLBACK = [
  { sku: "PART-1003", delta:  85812, cancelled: false },
  { sku: "PART-1012", delta: -60412, cancelled: false },
  { sku: "PART-1000", delta: -25908, cancelled: true  },
  { sku: "PART-1007", delta:  -8204, cancelled: false },
  { sku: "PART-1001", delta:  -3120, cancelled: false },
  { sku: "PART-1005", delta:   1842, cancelled: false },
  { sku: "PART-1009", delta:   -990, cancelled: false },
  { sku: "PART-1014", delta:    480, cancelled: false },
  { sku: "PART-1002", delta:   -320, cancelled: false },
  { sku: "PART-1006", delta:    200, cancelled: false },
];

const PROBE_DATA_FALLBACK = [
  { label: "Budget cap",      recovered: 322458, low: 298200, high: 340100, binding: true  },
  { label: "Lead-time floor", recovered:  79231, low:  61000, high:  95000, binding: false },
  { label: "MOQ constraint",  recovered:  44100, low:  30200, high:  58400, binding: false },
  { label: "Safety stock",    recovered:  12800, low:   8100, high:  19500, binding: false },
].map(p => ({ ...p, errorRange: [p.recovered - p.low, p.high - p.recovered] as [number, number] }));

const SCHEDULE_FALLBACK = [
  { week: "W0",  before: 298,  after: 1067 },
  { week: "W1",  before: 218,  after: 245  },
  { week: "W2",  before: 225,  after: 251  },
  { week: "W3",  before: 212,  after: 238  },
  { week: "W4",  before: 198,  after: 220  },
  { week: "W5",  before: 205,  after: 228  },
  { week: "W6",  before: 210,  after: 235  },
  { week: "W7",  before: 203,  after: 225  },
  { week: "W8",  before: 215,  after: 240  },
  { week: "W9",  before: 200,  after: 222  },
  { week: "W10", before: 208,  after: 231  },
  { week: "W11", before: 195,  after: 218  },
];

const BACKTEST_FALLBACK = [
  { label: "(s,Q) rule",   cost: 2021032, fill: 77.9 },
  { label: "This solver",  cost: 1329961, fill: 84.4 },
];

const LOADING_STEPS = [
  "Building the scenario",
  "Running 5 optimizations",
  "Simulating 1,000 futures",
  "Diffing the plan",
];

/* ─── Utils ──────────────────────────────────────────────────────────────── */
const fmt = (n: number) => "$" + n.toLocaleString("en-US");
const fmtSigned = (n: number) =>
  (n >= 0 ? "+" : "−") + "$" + Math.abs(n).toLocaleString("en-US");
const wocColor = (woc: number, d: typeof Dk) =>
  woc < 2.5 ? d.red : woc < 4 ? d.copper : d.green;
const mono = "'IBM Plex Mono', ui-monospace, monospace";
const sans = "'Inter', system-ui, sans-serif";

/* ─── Tiny SVG sparkline ─────────────────────────────────────────────────── */
function Sparkline({ color }: { color: string }) {
  const pts = [198,215,189,204,221,196,208,215,201,188,210,225,195,203,215,198,210,204,196,218,203,208,195,212,199,205];
  const min = Math.min(...pts), max = Math.max(...pts) + 1;
  const W = 120, H = 32;
  const d = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * W;
    const y = H - ((v - min) / (max - min)) * H;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} fill="none">
      <path d={d} stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ─── StatusChip ─────────────────────────────────────────────────────────── */
function StatusChip({ status, d }: { status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "none"; d: typeof Dk }) {
  const map = {
    OPTIMAL:    { bg: d.greenSubtle,   fg: d.green,       icon: <CheckCircle size={12} />, label: "OPTIMAL" },
    FEASIBLE:   { bg: d.subtle,        fg: d.fgSecondary,  icon: null,                     label: "FEASIBLE" },
    INFEASIBLE: { bg: d.redSubtle,     fg: d.red,          icon: <AlertTriangle size={12} />, label: "INFEASIBLE" },
    none:       { bg: d.subtle,        fg: d.fgMuted,      icon: null,                     label: "NO RUN" },
  };
  const c = map[status];
  return (
    <span style={{ background: c.bg, color: c.fg, borderRadius: 999, padding: "4px 12px", fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, display: "inline-flex", alignItems: "center", gap: 5, whiteSpace: "nowrap" as const }}>
      {c.icon}{c.label}
    </span>
  );
}

/* ─── Panel ──────────────────────────────────────────────────────────────── */
function Panel({ children, title, eyebrow, accent = false, style = {}, d }: {
  children: React.ReactNode; title?: string; eyebrow?: string;
  accent?: boolean; style?: React.CSSProperties; d: typeof Dk;
}) {
  return (
    <div style={{
      background: d.surface, border: `1px solid ${d.border}`, borderRadius: 16,
      boxShadow: accent
        ? "0 2px 6px rgba(16,24,40,.14), 0 20px 48px -18px rgba(16,24,40,.36)"
        : "0 1px 3px rgba(16,24,40,.08), 0 10px 28px -14px rgba(16,24,40,.18)",
      borderTop: accent ? `2px solid ${d.copper}` : `1px solid ${d.border}`,
      overflow: "hidden", ...style,
    }}>
      {(title || eyebrow) && (
        <div style={{ padding: "20px 24px 16px", borderBottom: `1px solid ${d.borderSubtle}` }}>
          {eyebrow && <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 4, fontFamily: sans }}>{eyebrow}</div>}
          {title && <div style={{ fontSize: 15, fontWeight: 600, color: d.fgPrimary, fontFamily: sans }}>{title}</div>}
        </div>
      )}
      <div style={{ padding: 24 }}>{children}</div>
    </div>
  );
}

/* ─── WOC bar ────────────────────────────────────────────────────────────── */
function WOCBar({ woc, d }: { woc: number; d: typeof Dk }) {
  const color = wocColor(woc, d);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
      <div style={{ width: 56, height: 6, background: d.subtle, borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${Math.min(woc / 32, 1) * 100}%`, height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontFamily: mono, fontSize: 12, color: d.fgPrimary, fontVariantNumeric: "tabular-nums", minWidth: 24, textAlign: "right" as const }}>{woc.toFixed(1)}</span>
      <div style={{ width: 7, height: 7, borderRadius: "50%", background: color, flexShrink: 0 }} />
    </div>
  );
}

/* ─── Section 1: Factory ─────────────────────────────────────────────────── */
function Section1Factory({ sRef, d, parts }: { sRef: React.RefObject<HTMLDivElement | null>; d: typeof Dk; parts: PartRow[] }) {
  const [expanded, setExpanded] = useState<string | null>("PART-1003");
  const headers = ["SKU", "UNIT COST", "LEAD", "MOQ", "ON HAND", "AVG/WK", "WEEKS OF COVER"];

  return (
    <div ref={sRef} style={{ marginBottom: 32 }}>
      <Panel eyebrow="20 parts · weekly buy" title="① The Factory" d={d}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: sans }}>
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={h} style={{ padding: "8px 12px", textAlign: i === 0 ? "left" : "right", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, borderBottom: `1px solid ${d.border}`, background: d.subtle, whiteSpace: "nowrap" as const }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parts.map((p) => {
                const isExp = expanded === p.sku;
                const isFocus = p.sku === "PART-1003";
                const rowBg = isExp ? d.inset : isFocus ? "rgba(214,134,58,0.04)" : "transparent";
                return (
                  <Fragment key={p.sku}>
                    <tr
                      onClick={() => setExpanded(isExp ? null : p.sku)}
                      style={{ cursor: "pointer", background: rowBg, transition: "background 100ms" }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = d.subtle; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = rowBg; }}
                    >
                      <td style={{ padding: "10px 12px", color: isFocus ? d.copper : d.fgPrimary, fontWeight: isFocus ? 600 : 400, fontFamily: mono, fontSize: 12, borderBottom: `1px solid ${d.borderSubtle}` }}>
                        {p.sku}
                      </td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: mono, fontSize: 12, color: d.fgSecondary, fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${d.borderSubtle}` }}>${p.cost.toFixed(2)}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontSize: 13, color: d.fgSecondary, borderBottom: `1px solid ${d.borderSubtle}` }}>{p.lead} wk</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: mono, fontSize: 12, color: d.fgSecondary, fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${d.borderSubtle}` }}>{p.moq.toLocaleString()}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: mono, fontSize: 12, color: d.fgSecondary, fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${d.borderSubtle}` }}>{p.onHand.toLocaleString()}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", fontFamily: mono, fontSize: 12, color: d.fgSecondary, fontVariantNumeric: "tabular-nums", borderBottom: `1px solid ${d.borderSubtle}` }}>{p.avgWeek.toLocaleString()}</td>
                      <td style={{ padding: "10px 12px", borderBottom: `1px solid ${d.borderSubtle}` }}>
                        <WOCBar woc={p.woc} d={d} />
                      </td>
                    </tr>
                    {isExp && (
                      <tr>
                        <td colSpan={7} style={{ padding: "16px 24px", background: d.inset, borderBottom: `1px solid ${d.border}` }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 8, fontFamily: sans }}>Demand history (104 wk)</div>
                              <Sparkline color={d.chartMuted} />
                            </div>
                            {isFocus && (
                              <div style={{ flex: 1, minWidth: 220, background: d.redSubtle, border: `1px solid ${d.red}44`, borderRadius: 8, padding: "10px 14px", display: "flex", alignItems: "center", gap: 8 }}>
                                <AlertTriangle size={14} color={d.red} style={{ flexShrink: 0 }} />
                                <span style={{ color: d.red, fontSize: 13 }}>3.1 weeks of cover against a 3-week lead time. <strong>No slack.</strong></span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

/* ─── Section 2: Disruption ──────────────────────────────────────────────── */
function Section2Disruption({ onSubmit, onAsk, loading, sRef, d, parts }: { onSubmit: (sku: string, lead: number) => void; onAsk: (text: string) => void; loading: boolean; sRef: React.RefObject<HTMLDivElement | null>; d: typeof Dk; parts: PartRow[] }) {
  const [sku, setSku] = useState("PART-1003");
  const [leadTime, setLeadTime] = useState(6);
  const [nlText, setNlText] = useState("Kraus emailed — PART-1003 is going from 3 weeks to 6 weeks.");

  const inputBase: React.CSSProperties = {
    width: "100%", background: d.subtle, border: `1px solid ${d.border}`, borderRadius: 8,
    color: d.fgPrimary, fontSize: 13, fontFamily: mono, outline: "none", boxSizing: "border-box",
  };

  return (
    <div ref={sRef} style={{ marginBottom: 32, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
      {/* Structured */}
      <Panel eyebrow="Structured input" title="② The Disruption" d={d}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 6, fontFamily: sans }}>Part</label>
            <select value={sku} onChange={e => setSku(e.target.value)} style={{ ...inputBase, height: 40, padding: "0 12px", cursor: "pointer" }}>
              {parts.map(p => <option key={p.sku} value={p.sku}>{p.sku}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 6, fontFamily: sans }}>New lead time</label>
            <div style={{ position: "relative" }}>
              <input type="number" min={1} max={52} value={leadTime} onChange={e => setLeadTime(Number(e.target.value))} style={{ ...inputBase, height: 40, padding: "0 52px 0 12px" }} />
              <span style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", color: d.fgMuted, fontSize: 12, pointerEvents: "none", fontFamily: sans }}>weeks</span>
            </div>
          </div>
          <button onClick={() => onSubmit(sku, leadTime)} disabled={loading} style={{ height: 40, background: loading ? d.border : d.copper, color: "#fff", border: "none", borderRadius: 12, fontWeight: 600, fontSize: 14, cursor: loading ? "default" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, transition: "background 120ms", marginTop: 8, fontFamily: sans }}>
            <RotateCcw size={14} />
            {loading ? "Running…" : "Re-plan"}
          </button>
        </div>
      </Panel>

      {/* Natural language */}
      <Panel eyebrow="Natural language" title="② The Disruption" d={d}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 6, fontFamily: sans }}>
              <span style={{ color: d.copper }}>✦ AI</span> — describe the disruption
            </label>
            <textarea value={nlText} onChange={e => setNlText(e.target.value)} rows={4} style={{ width: "100%", background: d.subtle, border: `1px solid ${d.border}`, borderRadius: 12, color: d.fgPrimary, padding: 12, fontSize: 13, resize: "vertical", outline: "none", lineHeight: 1.6, boxSizing: "border-box", fontFamily: sans }} />
          </div>
          <button onClick={() => onAsk(nlText)} disabled={loading} style={{ height: 40, background: d.subtle, color: d.fgPrimary, border: `1px solid ${d.border}`, borderRadius: 12, fontWeight: 600, fontSize: 14, cursor: loading ? "default" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, transition: "background 120ms", fontFamily: sans }}>
            <span style={{ color: d.copper }}>✦</span>
            {loading ? "Reasoning…" : "Ask the copilot"}
          </button>
          <p style={{ fontSize: 12, color: d.fgMuted, margin: 0, fontFamily: sans }}>Reads the email and reasons about the delay. ~2 extra LLM round-trips.</p>
        </div>
      </Panel>
    </div>
  );
}

/* ─── Loading sequence ───────────────────────────────────────────────────── */
function LoadingSequence({ step, elapsed, d }: { step: number; elapsed: number; d: typeof Dk }) {
  const mm = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const ss = (elapsed % 60).toString().padStart(2, "0");
  return (
    <div style={{ padding: "8px 0 16px" }}>
      <div style={{ fontSize: 15, fontWeight: 600, color: d.fgPrimary, marginBottom: 24, fontFamily: sans }}>Re-optimizing 20 parts…</div>
      {LOADING_STEPS.map((s, i) => {
        const done = i < step;
        const active = i === step;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, color: done ? d.green : active ? d.fgPrimary : d.fgMuted, fontSize: 14, fontFamily: sans }}>
            <div style={{ width: 18, height: 18, borderRadius: "50%", flexShrink: 0, background: done ? d.greenSubtle : active ? d.copperSubtle : d.subtle, border: `1.5px solid ${done ? d.green : active ? d.copper : d.border}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
              {done && <CheckCircle size={10} />}
              {active && <div style={{ width: 6, height: 6, borderRadius: "50%", background: d.copper }} />}
            </div>
            <span>{s}</span>
            {active && <span style={{ marginLeft: "auto", color: d.fgMuted, fontSize: 12 }}>⟳</span>}
          </div>
        );
      })}
      <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${d.border}`, display: "flex", justifyContent: "space-between", fontSize: 12, color: d.fgMuted, fontFamily: sans }}>
        <span style={{ fontFamily: mono }}>elapsed {mm}:{ss}</span>
        <span>This takes 10–30 s — the solver is proving the answer.</span>
      </div>
    </div>
  );
}

/* ─── Reallocation diverging bar chart ───────────────────────────────────── */
function makeBarLabel(d: typeof Dk, rows: ReallocRow[]) {
  return ({ x, y, width, height, value, index }: Record<string, number>) => {
    const isPos = value >= 0;
    const cancelled = rows[index]?.cancelled;
    const lx = isPos ? x + width + 8 : x - 8;
    return (
      <g>
        <text x={lx} y={y + height / 2 + 1} fill={isPos ? d.copperLight : d.fgSecondary} fontSize={11} fontFamily={mono} textAnchor={isPos ? "start" : "end"} dominantBaseline="middle">
          {fmtSigned(value)}{cancelled ? " ✕ cancelled" : ""}
        </text>
      </g>
    );
  };
}

function ReallocationChart({ d, rows }: { d: typeof Dk; rows: ReallocRow[] }) {
  const barLabel = makeBarLabel(d, rows);
  const span = Math.max(...rows.map(r => Math.abs(r.delta)), 1) * 1.35;
  const spent = rows.filter(r => r.delta > 0).reduce((a, r) => a + r.delta, 0);
  const cut = rows.filter(r => r.delta < 0).reduce((a, r) => a + r.delta, 0);
  const net = spent + cut;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, fontSize: 11, color: d.fgMuted, fontFamily: sans }}>
        <span>cut ◀</span>
        <div style={{ flex: 1, height: 1, background: d.border }} />
        <span style={{ fontFamily: mono }}>$0</span>
        <div style={{ flex: 1, height: 1, background: d.border }} />
        <span>▶ spend</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: 520 }}>
          <ResponsiveContainer width="100%" height={264}>
            <BarChart layout="vertical" data={rows} margin={{ top: 0, right: 140, left: 88, bottom: 0 }}>
              <XAxis type="number" domain={[-span, span]} tickFormatter={v => v === 0 ? "$0" : `$${Math.abs(v / 1000).toFixed(0)}k`} tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="sku" width={88} tick={{ fill: d.fgSecondary, fontSize: 12, fontFamily: mono }} axisLine={false} tickLine={false} />
              <CartesianGrid horizontal={false} stroke={d.chartGrid} strokeDasharray="3 3" />
              <ReferenceLine x={0} stroke={d.border} strokeWidth={1.5} />
              <Bar dataKey="delta" maxBarSize={20} label={barLabel as never} radius={[3, 3, 3, 3]}>
                {rows.map((entry, i) => (
                  <Cell key={i} fill={entry.delta > 2000 ? d.copper : entry.delta < -2000 ? d.red : d.chartMuted} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      {/* The whole insight in one line: the money did not appear, it MOVED. */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, flexWrap: "wrap", marginTop: 12, padding: "10px 14px", background: d.subtle, borderRadius: 8, fontFamily: mono, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: d.copper }}>{fmtSigned(spent)} spent</span>
        <span style={{ color: d.fgMuted }}>+</span>
        <span style={{ color: d.red }}>{fmtSigned(cut)} cut</span>
        <span style={{ color: d.fgMuted }}>=</span>
        <span style={{ color: d.fgPrimary, fontWeight: 700 }}>{fmtSigned(Math.round(net))} net</span>
        <span style={{ color: d.fgMuted, fontFamily: sans, fontSize: 12 }}>— the budget never grew, the money just moved</span>
      </div>
    </div>
  );
}

/* ─── Budget strip ───────────────────────────────────────────────────────── */
function BudgetStrip({ d, r }: { d: typeof Dk; r: DisruptionResult }) {
  return (
    <div style={{ marginTop: 20, borderTop: `1px solid ${d.border}`, paddingTop: 20 }}>
      <div style={{ position: "relative", marginBottom: 20 }}>
        <div style={{ borderTop: `1.5px solid ${d.copper}`, position: "relative" }}>
          <span style={{ position: "absolute", right: 0, top: -10, fontSize: 11, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" as const, color: d.copper, fontFamily: mono, background: d.surface, paddingLeft: 10, whiteSpace: "nowrap" as const }}>BUDGET CAP {fmt(Math.round(r.weekly_budget_dollars))}</span>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 32, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 4, fontFamily: sans }}>Cash before</div>
          <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 700, color: d.fgPrimary, fontVariantNumeric: "tabular-nums" }}>{fmt(Math.round(r.cash_spent_week0_before_dollars))}</div>
        </div>
        <div style={{ fontSize: 22, color: d.fgMuted, paddingBottom: 6 }}>→</div>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 4, fontFamily: sans }}>Cash after</div>
          <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 700, color: d.fgPrimary, fontVariantNumeric: "tabular-nums" }}>{fmt(Math.round(r.cash_spent_week0_after_dollars))}</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right", paddingBottom: 4 }}>
          <div style={{ fontFamily: mono, fontSize: 24, fontWeight: 700, color: d.fgPrimary, fontVariantNumeric: "tabular-nums" }}>{r.order_changes_week0.length} / {r.total_parts}</div>
          <div style={{ fontSize: 12, color: d.fgMuted, fontFamily: sans }}>this week&apos;s orders changed</div>
          <div style={{ fontSize: 11, color: d.fgMuted, fontFamily: sans, marginTop: 2 }}>({r.parts_affected} of {r.total_parts} across all {r.weeks} weeks)</div>
        </div>
      </div>
      <p style={{ fontSize: 13, color: d.fgSecondary, lineHeight: 1.65, margin: 0, borderLeft: `3px solid ${d.border}`, paddingLeft: 12, fontFamily: sans }}>
        One part got late — and {r.order_changes_week0.length} of {r.total_parts} parts had <strong>this week&apos;s</strong> order rewritten ({r.parts_affected} of {r.total_parts} across the full {r.weeks} weeks). The budget didn&apos;t grow, so paying for {r.sku} means cancelling someone else. The bars below net to roughly zero — that is the same money, moved.
      </p>
    </div>
  );
}

/* ─── Focus schedule ─────────────────────────────────────────────────────── */
function ScheduleChart({ d, rows, sku }: { d: typeof Dk; rows: ScheduleRow[]; sku: string }) {
  const w0 = rows[0];
  return (
    <div style={{ marginTop: 24, borderTop: `1px solid ${d.border}`, paddingTop: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: d.fgPrimary, marginBottom: 4, fontFamily: sans }}>{sku} order schedule — {rows.length}-week window</div>
      <div style={{ fontSize: 12, color: d.fgMuted, marginBottom: 12, display: "flex", gap: 16, fontFamily: sans }}>
        <span><span style={{ display: "inline-block", width: 10, height: 10, background: d.chartMuted, borderRadius: 2, marginRight: 5, verticalAlign: "middle" }} />Before</span>
        <span><span style={{ display: "inline-block", width: 10, height: 10, background: d.copper, borderRadius: 2, marginRight: 5, verticalAlign: "middle" }} />After</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: 400 }}>
          <ResponsiveContainer width="100%" height={148}>
            <BarChart data={rows} margin={{ top: 16, right: 0, left: 0, bottom: 0 }} barGap={2} barCategoryGap="20%">
              <XAxis dataKey="week" tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} width={32} />
              <CartesianGrid vertical={false} stroke={d.chartGrid} strokeDasharray="3 3" />
              <Bar dataKey="before" fill={d.chartMuted} radius={[3, 3, 0, 0]} maxBarSize={14} />
              <Bar dataKey="after" fill={d.copper} radius={[3, 3, 0, 0]} maxBarSize={14}>
                <LabelList dataKey="after" position="top" content={(props: Record<string, unknown>) => {
                  if ((props.index as number) !== 0) return null;
                  const x = props.x as number;
                  const y = props.y as number;
                  const width = props.width as number;
                  return <text x={x + width / 2} y={y - 4} textAnchor="middle" fill={d.copper} fontSize={10} fontFamily={mono}>{w0.after.toLocaleString()}↑</text>;
                }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <p style={{ fontSize: 11, color: d.fgMuted, marginTop: 4, fontFamily: sans }}>W0: buy {w0.after.toLocaleString()} units immediately vs. the previous {w0.before.toLocaleString()}. The front-load covers the extended wait.</p>
    </div>
  );
}

/* ─── Probe chart (binding constraint) ───────────────────────────────────── */
function ProbeChart({ proven, d, rows }: { proven: boolean; d: typeof Dk; rows: ProbeRow[] }) {
  const top = rows[0], runner = rows[1];
  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: 380 }}>
          <ResponsiveContainer width="100%" height={152}>
            <ComposedChart layout="vertical" data={rows} margin={{ top: 0, right: 96, left: 108, bottom: 0 }}>
              <XAxis type="number" tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="label" width={108} tick={{ fill: d.fgSecondary, fontSize: 11, fontFamily: sans }} axisLine={false} tickLine={false} />
              <CartesianGrid horizontal={false} stroke={d.chartGrid} strokeDasharray="3 3" />
              <Bar dataKey="recovered" maxBarSize={18} radius={[0, 4, 4, 0]}>
                {rows.map((entry, i) => (
                  <Cell key={i} fill={entry.binding && proven ? d.copper : d.chartMuted} />
                ))}
                <ErrorBar dataKey="errorRange" direction="x" strokeWidth={1.5} stroke={d.fgSecondary} width={5} />
                <LabelList dataKey="recovered" position="right" formatter={(v: number) => fmt(v)} style={{ fontSize: 10, fill: d.fgSecondary, fontFamily: mono }} />
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
      {proven ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginTop: 12, padding: "12px 14px", background: d.copperSubtle, border: `1px solid ${d.copper}33`, borderRadius: 8 }}>
          <span style={{ color: d.copper, fontSize: 11, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" as const, background: "rgba(214,134,58,0.18)", borderRadius: 999, padding: "3px 10px", whiteSpace: "nowrap" as const, fontFamily: sans }}>BINDING — PROVEN</span>
          <p style={{ margin: 0, fontSize: 13, color: d.fgSecondary, fontFamily: sans }}>Its worst case ({fmt(top.low)}) still beats the runner-up's best case ({fmt(runner ? runner.high : 0)}).</p>
        </div>
      ) : (
        <p style={{ fontSize: 13, color: d.fgMuted, marginTop: 12, fontStyle: "italic", fontFamily: sans }}>Cannot name a bottleneck at this tolerance.</p>
      )}
    </div>
  );
}

/* ─── Simulation gauge ───────────────────────────────────────────────────── */
function SimulationGauge({ d, sim }: { d: typeof Dk; sim: DisruptionResult["simulation"] }) {
  const p50 = +(sim.fill_rate_p50 * 100).toFixed(1);
  const p10 = +(sim.fill_rate_p10 * 100).toFixed(1);
  const min = Math.floor(p10 - 8), max = Math.ceil(p50 + 8);
  const pct = (v: number) => ((v - min) / (max - min)) * 100;
  return (
    <div style={{ fontFamily: sans }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: d.fgPrimary, marginBottom: 4 }}>
        Fill rate distribution
        <span style={{ fontWeight: 400, color: d.fgMuted, marginLeft: 8 }}>{sim.runs.toLocaleString()} simulated futures</span>
      </div>
      <div style={{ position: "relative", height: 72, marginTop: 12 }}>
        <div style={{ position: "absolute", top: 18, left: 0, right: 0, height: 10, background: d.subtle, borderRadius: 5 }} />
        <div style={{ position: "absolute", top: 18, left: 0, width: `${pct(p10)}%`, height: 10, background: d.copper + "55", borderRadius: 5 }} />
        <div style={{ position: "absolute", top: 12, left: `${pct(p10)}%`, transform: "translateX(-50%)" }}>
          <div style={{ width: 2, height: 22, background: d.copper, margin: "0 auto" }} />
        </div>
        <div style={{ position: "absolute", top: 14, left: `${pct(p50)}%`, transform: "translateX(-50%)" }}>
          <div style={{ width: 2, height: 18, background: d.fgPrimary, margin: "0 auto" }} />
        </div>
        <div style={{ position: "absolute", top: 36, left: `${pct(p10)}%`, transform: "translateX(-50%)", textAlign: "center" as const }}>
          <div style={{ fontFamily: mono, fontSize: 14, fontWeight: 600, color: d.copper }}>{p10}%</div>
          <div style={{ fontSize: 10, color: d.fgMuted, whiteSpace: "nowrap" as const }}>p10 (bad week)</div>
        </div>
        <div style={{ position: "absolute", top: 36, left: `${pct(p50)}%`, transform: "translateX(-50%)", textAlign: "center" as const }}>
          <div style={{ fontFamily: mono, fontSize: 14, color: d.fgPrimary }}>{p50}%</div>
          <div style={{ fontSize: 10, color: d.fgMuted }}>p50 median</div>
        </div>
      </div>
      <p style={{ fontSize: 12, color: d.fgMuted, margin: "8px 0 0" }}>Even in a bad week, fill rate holds at {p10}% — that is the p10 of {sim.runs.toLocaleString()} sampled demand futures.</p>
    </div>
  );
}

/* ─── Section 3: The Answer ──────────────────────────────────────────────── */
function Section3Answer({ runState, loadingStep, elapsed, sRef, d, result, error, explanation }: { runState: string; loadingStep: number; elapsed: number; sRef: React.RefObject<HTMLDivElement | null>; d: typeof Dk; result: DisruptionResult | null; error: string | null; explanation: string | null }) {
  // The backend can refuse to answer. The UI must NOT paper over that.
  const constraintProven = result ? result.binding_constraint.proven : false;
  const costIsNull = result ? result.disruption_cost_dollars === null : true;

  if (runState === "idle") {
    return (
      <div ref={sRef} style={{ marginBottom: 32 }}>
        <Panel d={d} style={{ textAlign: "center" }}>
          <div style={{ padding: "40px 0" }}>
            <div style={{ fontFamily: mono, fontSize: 72, fontWeight: 700, color: d.border, letterSpacing: "-0.02em", marginBottom: 16, fontVariantNumeric: "tabular-nums" }}>$—</div>
            <div style={{ fontSize: 15, color: d.fgMuted, maxWidth: 360, margin: "0 auto", lineHeight: 1.65, fontFamily: sans }}>Pick a part and a new lead time, then re-plan. The result appears here.</div>
          </div>
        </Panel>
      </div>
    );
  }

  if (runState === "loading") {
    return (
      <div ref={sRef} style={{ marginBottom: 32 }}>
        <Panel accent d={d}>
          <LoadingSequence step={loadingStep} elapsed={elapsed} d={d} />
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
            {[64, 20, 140].map((h, i) => (
              <div key={i} style={{ height: h, background: d.subtle, borderRadius: 8, opacity: 0.6 }} />
            ))}
          </div>
        </Panel>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div ref={sRef} style={{ marginBottom: 32 }}>
        <Panel d={d} style={{ textAlign: "center" }}>
          <div style={{ padding: "40px 0" }}>
            <div style={{ fontSize: 15, color: d.red, fontFamily: sans, marginBottom: 8 }}>Could not reach the solver.</div>
            <div style={{ fontSize: 13, color: d.fgMuted, fontFamily: mono, maxWidth: 520, margin: "0 auto" }}>{error ?? "No result."}</div>
            <div style={{ fontSize: 12, color: d.fgMuted, fontFamily: sans, marginTop: 12 }}>Is the API running?  uvicorn reorder.api:app --port 8000</div>
          </div>
        </Panel>
      </div>
    );
  }

  const realloc = toReallocation(result);
  const probes = toProbeRows(result);
  const schedule = toSchedule(result);

  return (
    <div ref={sRef} style={{ marginBottom: 32, display: "flex", flexDirection: "column", gap: 24 }}>
      {/* The AI's words -- shown ONLY when the copilot path was used. Every number
          inside it came from the solver below. */}
      {explanation && (
        <Panel eyebrow="✦ The copilot's read" d={d}>
          <p style={{ margin: 0, fontSize: 15, lineHeight: 1.7, color: d.fgPrimary, fontFamily: sans }}>{explanation}</p>
          <p style={{ margin: "10px 0 0", fontSize: 12, color: d.fgMuted, fontFamily: sans }}>
            The model wrote these sentences. It did not compute a single number in them — every figure came from the solver.
          </p>
        </Panel>
      )}

      {/* 3a Headline */}
      <Panel accent eyebrow="③ The Answer" d={d}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 10, fontFamily: sans }}>THIS DELAY COSTS</div>
            {costIsNull ? (
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, color: d.fgPrimary, marginBottom: 4, fontFamily: sans }}>The solver could not prove a reliable cost for this run.</div>
                <div style={{ fontSize: 14, color: d.fgMuted, fontFamily: sans }}>It won't report a number it can't stand behind.</div>
              </div>
            ) : (
              <>
                <div style={{ fontFamily: mono, fontSize: 48, fontWeight: 700, color: d.fgPrimary, letterSpacing: "-0.01em", fontVariantNumeric: "tabular-nums", lineHeight: 1.05 }}>{fmt(Math.round(result.disruption_cost_dollars!))}</div>
                {result.disruption_cost_range_dollars && (
                  <div style={{ fontFamily: mono, fontSize: 13, color: d.fgSecondary, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>provably {fmt(Math.round(result.disruption_cost_range_dollars[0]))} – {fmt(Math.round(result.disruption_cost_range_dollars[1]))}</div>
                )}
              </>
            )}
          </div>
          <StatusChip status={result.solver_status} d={d} />
        </div>
      </Panel>

      {/* 3b Reallocation */}
      <Panel eyebrow="The Reallocation" title="Where the money moved" d={d}>
        <ReallocationChart d={d} rows={realloc} />
        <BudgetStrip d={d} r={result} />
        <ScheduleChart d={d} rows={schedule} sku={result.sku} />
      </Panel>

      {/* 3c Binding constraint */}
      <Panel eyebrow="The Binding Constraint" title="What to fix to recover the most cost" d={d}>
        <ProbeChart proven={constraintProven} d={d} rows={probes} />
        <div style={{ marginTop: 24, borderTop: `1px solid ${d.border}`, paddingTop: 20 }}>
          <SimulationGauge d={d} sim={result.simulation} />
        </div>
      </Panel>
    </div>
  );
}

/* ─── Section 4: Evidence ─────────────────────────────────────────────────── */
function Section4Evidence({ sRef, d, backtest }: { sRef: React.RefObject<HTMLDivElement | null>; d: typeof Dk; backtest: BacktestResult | null }) {
  // Never render the fallback fixture here. Showing invented numbers while the real
  // backtest loads would mean demoing figures that aren't ours.
  if (!backtest) {
    return (
      <div ref={sRef} style={{ marginBottom: 32 }}>
        <Panel eyebrow="4 The Evidence" title="Why believe it - backtest against history" d={d}>
          <div style={{ padding: "32px 0", textAlign: "center" }}>
            <div style={{ fontSize: 14, color: d.fgSecondary, fontFamily: sans, marginBottom: 6 }}>
              Replaying held-out demand through both policies...
            </div>
            <div style={{ fontSize: 12, color: d.fgMuted, fontFamily: sans }}>
              First run re-solves the plan for every week (~40s), then it is cached.
            </div>
          </div>
        </Panel>
      </div>
    );
  }
  const rows: BacktestRow[] = toBacktestRows(backtest);
  const saved = Math.round(backtest.dollars_saved);
  const fillPts = +(backtest.fill_rate_delta * 100).toFixed(1);
  return (
    <div ref={sRef} style={{ marginBottom: 32 }}>
      <Panel eyebrow="④ The Evidence" title="Why believe it — backtest against history" d={d}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 700, color: d.fgPrimary, fontVariantNumeric: "tabular-nums", marginBottom: 6 }}>Saves {fmt(saved)}</div>
          <div style={{ fontSize: 14, color: d.fgSecondary, fontFamily: sans }}>and serves <strong>{fillPts} percentage points</strong> more demand — cheaper <em>and</em> better service, not a trade-off.</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 10, fontFamily: sans }}>Total cost over {backtest.test_weeks} weeks</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={rows} margin={{ top: 16, right: 0, left: 0, bottom: 0 }} barCategoryGap="40%">
                <XAxis dataKey="label" tick={{ fill: d.fgSecondary, fontSize: 11, fontFamily: sans }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={v => `$${(v / 1e6).toFixed(1)}M`} tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} width={44} />
                <CartesianGrid vertical={false} stroke={d.chartGrid} strokeDasharray="3 3" />
                <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                  <Cell fill={d.chartMuted} />
                  <Cell fill={d.copper} />
                  <LabelList dataKey="cost" position="top" formatter={(v: number) => fmt(v)} style={{ fontSize: 10, fill: d.fgSecondary, fontFamily: mono }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase" as const, color: d.fgMuted, marginBottom: 10, fontFamily: sans }}>Fill rate</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={rows} margin={{ top: 16, right: 0, left: 0, bottom: 0 }} barCategoryGap="40%">
                <XAxis dataKey="label" tick={{ fill: d.fgSecondary, fontSize: 11, fontFamily: sans }} axisLine={false} tickLine={false} />
                <YAxis domain={["dataMin - 4", "dataMax + 4"]} tickFormatter={v => `${v}%`} tick={{ fill: d.fgMuted, fontSize: 10, fontFamily: mono }} axisLine={false} tickLine={false} width={34} />
                <CartesianGrid vertical={false} stroke={d.chartGrid} strokeDasharray="3 3" />
                <Bar dataKey="fill" radius={[4, 4, 0, 0]}>
                  <Cell fill={d.chartMuted} />
                  <Cell fill={d.green} />
                  <LabelList dataKey="fill" position="top" formatter={(v: number) => `${v}%`} style={{ fontSize: 10, fill: d.fgSecondary, fontFamily: mono }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div style={{ background: d.subtle, borderRadius: 8, padding: "14px 16px", fontSize: 13, color: d.fgSecondary, lineHeight: 1.65, fontFamily: sans }}>
          <strong style={{ color: d.fgPrimary }}>Honest caveat:</strong>{" "}With slack cash, the optimizer only ties the simple rule. Its advantage appears when the cash budget binds and it must ration across parts — which a per-part rule cannot do.
        </div>
      </Panel>
    </div>
  );
}

/* ─── Sidebar ─────────────────────────────────────────────────────────────── */
function Sidebar({ active, onNav, lightMode, onToggle, runState, d }: {
  active: number; onNav: (n: number) => void; lightMode: boolean;
  onToggle: () => void; runState: string; d: typeof Dk;
}) {
  const navItems = [
    { n: 1, label: "The Factory" },
    { n: 2, label: "The Disruption" },
    { n: 3, label: "The Answer" },
    { n: 4, label: "The Evidence" },
  ];
  return (
    <div style={{ width: 248, flexShrink: 0, background: d.surface, borderRight: `1px solid ${d.border}`, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={{ padding: "22px 20px 18px", borderBottom: `1px solid ${d.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <div style={{ width: 9, height: 9, background: d.copper, transform: "rotate(45deg)", flexShrink: 0, borderRadius: 1 }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: d.fgPrimary, letterSpacing: "-0.01em", fontFamily: sans }}>Reorder Copilot</span>
        </div>
        <div style={{ fontSize: 11, color: d.fgMuted, marginTop: 5, marginLeft: 18, fontFamily: sans }}>Supply chain ops console</div>
      </div>
      <nav style={{ flex: 1, padding: "12px 0", overflowY: "auto" }}>
        {navItems.map(({ n, label }) => {
          const isActive = active === n;
          return (
            <button key={n} onClick={() => onNav(n)} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "10px 20px", background: isActive ? d.subtle : "transparent", borderLeft: `3px solid ${isActive ? d.copper : "transparent"}`, color: isActive ? d.fgPrimary : d.fgSecondary, fontSize: 13, fontWeight: isActive ? 600 : 400, border: "none", borderBottom: "none", borderRight: "none", borderTop: "none", outline: "none", cursor: "pointer", textAlign: "left" as const, transition: "all 120ms ease-out", fontFamily: sans }}>
              <span style={{ fontFamily: mono, fontSize: 10, color: isActive ? d.copper : d.fgMuted, fontWeight: 600 }}>0{n}</span>
              {label}
            </button>
          );
        })}
      </nav>
      <div style={{ padding: "16px 20px", borderTop: `1px solid ${d.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: runState === "done" ? d.green : d.fgMuted }} />
          <span style={{ fontSize: 12, fontWeight: 600, color: runState === "done" ? d.green : d.fgMuted, fontFamily: sans }}>{runState === "done" ? "OPTIMAL" : runState === "loading" ? "RUNNING" : "READY"}</span>
        </div>
        <button onClick={onToggle} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 0", background: "none", border: "none", color: d.fgSecondary, cursor: "pointer", fontSize: 12, fontFamily: sans }}>
          {lightMode ? <Moon size={13} /> : <Sun size={13} />}
          {lightMode ? "Dark mode" : "Light mode"}
        </button>
      </div>
    </div>
  );
}

/* ─── Topbar ─────────────────────────────────────────────────────────────── */
function TopBar({ runState, d }: { runState: string; d: typeof Dk }) {
  return (
    <div style={{ height: 64, borderBottom: `1px solid ${d.border}`, background: d.surface, display: "flex", alignItems: "center", padding: "0 32px", gap: 16, flexShrink: 0 }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: d.fgPrimary, letterSpacing: "-0.005em", fontFamily: sans }}>Reorder Copilot</div>
        <div style={{ fontSize: 12, color: d.fgMuted, fontFamily: sans }}>Re-optimize the weekly buy when a supplier slips</div>
      </div>
      {runState === "done" && (
        <div style={{ background: d.copperSubtle, border: `1px solid ${d.copper}44`, borderRadius: 999, padding: "4px 14px", fontSize: 12, color: d.copperLight, fontFamily: mono, fontVariantNumeric: "tabular-nums" }}>
          PART-1003 · 3 → 6 wks · OPTIMAL
        </div>
      )}
    </div>
  );
}

/* ─── App ─────────────────────────────────────────────────────────────────── */
export default function App() {
  const [runState, setRunState] = useState<"idle" | "loading" | "done">("idle");
  const [loadingStep, setLoadingStep] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [activeSection, setActiveSection] = useState(1);
  const [lightMode, setLightMode] = useState(false);

  // Real data from the Python backend. Fixtures are only a fallback so the page
  // still renders if the API is down.
  const [parts, setParts] = useState<PartRow[]>(PARTS_FALLBACK);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [result, setResult] = useState<DisruptionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);

  useEffect(() => {
    fetchParts().then(ps => setParts(toPartRows(ps))).catch(() => {});
    fetchBacktest().then(setBacktest).catch(() => {});
  }, []);

  const d = lightMode ? Lt : Dk;

  const s1 = useRef<HTMLDivElement>(null);
  const s2 = useRef<HTMLDivElement>(null);
  const s3 = useRef<HTMLDivElement>(null);
  const s4 = useRef<HTMLDivElement>(null);
  const scrollArea = useRef<HTMLDivElement>(null);

  // While the real solve is in flight, walk the step labels and tick the clock.
  // The request -- not a timer -- decides when we are done.
  useEffect(() => {
    if (runState !== "loading") return;
    const iv = setInterval(() => setElapsed(e => e + 1), 1000);
    const steps = setInterval(
      () => setLoadingStep(x => Math.min(x + 1, LOADING_STEPS.length - 1)), 6000);
    return () => { clearInterval(iv); clearInterval(steps); };
  }, [runState]);

  // Scroll-spy
  useEffect(() => {
    const refs = [s1, s2, s3, s4];
    const root = scrollArea.current;
    const obs = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            const i = refs.findIndex(r => r.current === e.target);
            if (i >= 0) setActiveSection(i + 1);
          }
        });
      },
      { root, threshold: 0.25 }
    );
    refs.forEach(r => { if (r.current) obs.observe(r.current); });
    return () => obs.disconnect();
  }, []);

  const handleNav = (n: number) => {
    const refs = [s1, s2, s3, s4];
    refs[n - 1].current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSection(n);
  };

  // The AI path: the LLM reads the sentence, the SOLVER answers it, the LLM
  // writes the prose. Two LLM round trips; zero LLM arithmetic.
  const handleAsk = async (text: string) => {
    setRunState("loading");
    setLoadingStep(0);
    setElapsed(0);
    setError(null);
    setResult(null);
    setExplanation(null);
    s3.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      const a = await fetchAgent(text);
      setResult(a.recommendation);
      setExplanation(a.explanation);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunState("done");
    }
  };

  // The plain path: no AI at all. Same solver, same numbers.
  const handleSubmit = async (sku: string, lead: number) => {
    setRunState("loading");
    setLoadingStep(0);
    setElapsed(0);
    setError(null);
    setResult(null);
    setExplanation(null);
    s3.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      setResult(await fetchDisruption(sku, lead));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunState("done");
    }
  };

  return (
    <div className={lightMode ? "rc-light" : ""} style={{ minHeight: "100vh", background: lightMode ? "#EEF2F6" : "#070D14", padding: 20, backgroundImage: lightMode ? "radial-gradient(ellipse 60% 50% at 15% 0%, rgba(214,134,58,0.06) 0%, transparent 70%)" : "radial-gradient(ellipse 60% 50% at 15% 0%, rgba(34,46,58,0.8) 0%, transparent 70%)", fontFamily: sans }}>
      <style>{`
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${d.border}; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: ${d.fgMuted}; }
        select option { background: ${d.surface}; color: ${d.fgPrimary}; }
        @keyframes rcPulse { 0%,100%{opacity:0.4} 50%{opacity:0.7} }
      `}</style>
      <div style={{ maxWidth: 1440, margin: "0 auto", height: "calc(100vh - 40px)", display: "flex", background: d.canvas, borderRadius: 24, boxShadow: lightMode ? "0 30px 80px -40px rgba(16,24,40,0.22)" : "0 30px 80px -40px rgba(0,0,0,0.7)", overflow: "hidden", border: `1px solid ${d.border}` }}>
        <Sidebar active={activeSection} onNav={handleNav} lightMode={lightMode} onToggle={() => setLightMode(v => !v)} runState={runState} d={d} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: d.canvas }}>
          <TopBar runState={runState} d={d} />
          <div ref={scrollArea} style={{ flex: 1, overflowY: "auto", padding: "32px", scrollbarWidth: "thin", scrollbarColor: `${d.border} transparent` }}>
            <Section1Factory sRef={s1} d={d} parts={parts} />
            <Section2Disruption onSubmit={handleSubmit} onAsk={handleAsk} loading={runState === "loading"} sRef={s2} d={d} parts={parts} />
            <Section3Answer runState={runState} loadingStep={loadingStep} elapsed={elapsed} sRef={s3} d={d} result={result} error={error} explanation={explanation} />
            <Section4Evidence sRef={s4} d={d} backtest={backtest} />
            <div style={{ height: 40 }} />
          </div>
        </div>
      </div>
    </div>
  );
}
