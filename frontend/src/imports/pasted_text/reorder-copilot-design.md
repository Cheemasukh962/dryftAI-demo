# Design PRD — Reorder Copilot Front End

**Companion to:** the product PRD (“Reorder Copilot, Front End”).
**Scope:** visual design system, layout, component specs, and screen direction for the 4-section single-page app.
**Stack it targets:** React + TypeScript · Vite · **Chakra UI v3** · TanStack Router/Query · Recharts.
**Status:** ready to build against. Every visual decision below is expressed as design tokens so it maps 1:1 onto Chakra v3’s `createSystem` theme.

---

## 0. How to read this document

This is the *look-and-feel* spec that sits on top of the product PRD. The product PRD owns **what data shows and what the numbers mean**; this doc owns **how it looks, feels, and holds together**. Where the two ever disagree, the product PRD wins on data/integrity rules (the `null` cost, the unproven-constraint rule); this doc wins on spacing, color, and type.

Read sections 1–3 once to absorb the system. Sections 4–7 are what you keep open while building. Section 12 is the checklist you run before calling a screen done.

**One rule that overrides everything aesthetic:** the product must feel *trustworthy and precise*, because its entire pitch is “we show our error bars.” If a design choice makes the tool look like a marketing dashboard instead of an instrument a buyer would bet $360k/week on, it’s wrong — no matter how pretty.

---

## 1. The reference image, decoded

You supplied the **emitly** dashboard as the visual target. Here is exactly what we take from it, what we change, and why. This table *is* the design brief in miniature.

| Element in the reference | Verdict | What we do |
|---|---|---|
| Floating app window, big outer radius (~24–28px), soft shadow on a calm canvas | **Keep** | Same shell language. It reads “focused workspace,” which suits an ops console. |
| Generous whitespace, one idea per card, calm density | **Keep** | Panels breathe. Density comes from *data precision*, not cramming. |
| Large confident metric numbers with small delta pills | **Keep** | This is exactly our headline + stat treatment. |
| Pill-shaped badges, tinted backgrounds, up/down arrows | **Keep** | Reused for delta pills and status chips. |
| **One highlighted bar (coral) among muted grey bars** | **Keep — and make it the thesis** | This is our reallocation chart. One part is the *cause* (accent); the rest are muted or cut. The reference already proves this pattern reads instantly. |
| Left sidebar nav with brand + line icons | **Keep, repurpose** | Becomes a *section navigator* + solver-status rail (we’re single-page, not multi-route). |
| Clean line iconography, ~1.5px stroke | **Keep** | Lucide, 20px grid. |
| Soft ambient gradient behind the window | **Keep, dial down** | A faint cool-steel wash, not a lush green photo. Restraint. |
| **Warm green brand + lime active pills + pastel yellow/pink cards** | **Change** | Consumer-friendly and, worse, *green collides with our semantic “recovered/good.”* We reserve green for meaning, not brand. |
| Friendly, rounded, marketing tone | **Change** | Cooler, more instrument-like. Softness stays in the *radius and shadow*, not the *palette*. |
| Playful multi-color accents | **Change** | Exactly **one** brand accent: copper/amber, reserved for *the decision* (solver output, the binding constraint, the cause part). |

**The core translation:** keep emitly’s *craft* (shell, whitespace, confident numerals, single-accent-among-neutrals, pill badges), swap its *mood* (warm consumer → cool instrument). The single most important borrowed idea is the highlighted-bar-among-neutrals — we spend it on the reallocation chart, which is the one thing the whole UI exists to convey.

---

## 2. Design principles

Six principles, in priority order. When two conflict, the earlier one wins.

1. **Provable over pretty.** Every number looks computed, aligned, and defensible. Ranges and error bars are first-class, not fine print. Tabular numerals everywhere money appears.
2. **One accent, spent on the decision.** Copper/amber appears only on: the solver’s output, the binding constraint, and the *cause* part in the reallocation. Everywhere else is steel neutral + semantic green/red. If copper is on more than ~3 things on screen, remove one.
3. **The reallocation is the hero.** Section 3b gets the most design budget, the boldest layout, and the clearest cause→victims read. Everything else is supporting cast.
4. **Muted by default, loud on meaning.** Neutral parts are quiet grey. Color is earned: green = recovered/good, red = cut/at-risk, copper = the decision. A screen where everything is colored is a screen that says nothing.
5. **Honesty is a design feature, not a caveat.** The `null` cost message, the unproven-constraint no-badge state, and the backtest “only ties when cash is slack” caveat are *designed*, legible, and calm — not buried grey disclaimers. They make the tool *more* credible.
6. **Instrument, not app.** No decorative motion, no confetti, no gradients-for-vibe. The only place motion earns its keep is the honest 20–30s loading sequence, where showing the work *is* the feature.

---

## 3. Foundations (design tokens)

All values below are written to drop into Chakra v3 (`tokens` for raw scales, `semanticTokens` for the light/dark mappings). Section 11 shows the exact `createSystem` shape.

### 3.1 Color

#### Raw palettes (`theme.tokens.colors`)

**Steel** — the neutral spine (cool slate). This is 90% of every screen.

| Token | Hex | Typical use |
|---|---|---|
| `steel.25` | `#F7F9FB` | Light canvas |
| `steel.50` | `#EEF2F6` | Light inset / well / muted bar fill |
| `steel.100` | `#E2E8EF` | Light border-subtle, table row hover |
| `steel.200` | `#CDD7E1` | Light border-default, dividers |
| `steel.300` | `#AEBAC8` | Disabled text (light), muted bar (light) |
| `steel.400` | `#8593A5` | fg-muted (light) |
| `steel.500` | `#63728A` | fg-secondary (light) |
| `steel.600` | `#48576B` | icon default (light) |
| `steel.700` | `#33404F` | Dark border-default |
| `steel.800` | `#222E3A` | Dark card surface / muted bar (dark) |
| `steel.900` | `#161F29` | Dark elevated surface |
| `steel.950` | `#0C121A` | Dark canvas |
| `ink` | `#0F1720` | fg-primary (light) |
| `paper` | `#FFFFFF` | Light card surface |

**Copper** — the single brand accent. *The decision.*

| Token | Hex | Use |
|---|---|---|
| `copper.50` | `#FBF3EA` | Accent tint bg (light) |
| `copper.100` | `#F4DFC6` | Accent subtle |
| `copper.300` | `#E2A567` | Accent emphasized (dark-mode fills) |
| `copper.400` | `#D6863A` | **`accent.solid` — primary accent fill** |
| `copper.500` | `#BC6F26` | `accent.fg` on light (passes contrast on `paper`) |
| `copper.600` | `#98591E` | Pressed / accent text on tint |

**Green** — semantic *recovered / good / better service*. Never used as brand.

| Token | Hex | Use |
|---|---|---|
| `green.50` | `#E7F4EC` | Positive tint bg (light) |
| `green.400` | `#33B37C` | Positive fill (dark) |
| `green.500` | `#1E9A61` | Positive fill / text (light) |
| `green.600` | `#157A4C` | Positive text on tint |

**Red / coral** — semantic *cut / at-risk / cancelled*. (Coral echoes the reference’s one highlighted bar, now given meaning.)

| Token | Hex | Use |
|---|---|---|
| `red.50` | `#FBE9E6` | Negative tint bg (light) |
| `red.400` | `#E5654E` | Negative fill (dark) / “cut” bars |
| `red.500` | `#D4463A` | Negative fill / text (light) |
| `red.600` | `#A8302A` | Negative text on tint |

**Blue** — optional neutral-data accent for probes/simulation when they must be distinct from green/red/copper (use sparingly).

| Token | Hex | Use |
|---|---|---|
| `blue.400` | `#4285D4` | Sim/probe neutral series (dark) |
| `blue.500` | `#2E68BE` | Sim/probe neutral series (light) |

#### Semantic tokens (`theme.semanticTokens.colors`) — light / dark

Build components against **only these**, never raw hex. This is what makes dark mode a non-event.

| Semantic token | Light | Dark |
|---|---|---|
| `bg.canvas` | `steel.25` | `steel.950` |
| `bg.surface` (cards) | `paper` | `steel.900` |
| `bg.subtle` (wells, muted bars, inputs) | `steel.50` | `steel.800` |
| `bg.inset` (deep wells, code-ish) | `steel.100` | `#10171F` |
| `border.subtle` | `steel.100` | `steel.800` |
| `border.default` | `steel.200` | `steel.700` |
| `fg.primary` | `ink` | `#E7ECF2` |
| `fg.secondary` | `steel.500` | `steel.300` |
| `fg.muted` | `steel.400` | `steel.500` |
| `accent.solid` | `copper.400` | `copper.400` |
| `accent.fg` | `copper.500` | `copper.300` |
| `accent.subtle` | `copper.50` | `rgba(214,134,58,0.14)` |
| `positive.solid` | `green.500` | `green.400` |
| `positive.fg` | `green.600` | `green.400` |
| `positive.subtle` | `green.50` | `rgba(51,179,124,0.14)` |
| `negative.solid` | `red.500` | `red.400` |
| `negative.fg` | `red.600` | `red.400` |
| `negative.subtle` | `red.50` | `rgba(229,101,78,0.16)` |
| `chart.muted` (neutral bars) | `steel.200` | `steel.700` |
| `chart.grid` | `steel.100` | `steel.800` |
| `focusRing` | `copper.400` | `copper.300` |

**Color rules baked into the system:**
- Green means *recovered/good*. Red means *cut/at-risk*. Copper means *the decision*. Never repurpose these three.
- A part with no notable change renders in `chart.muted`. Muteness is information.
- `weeks_of_cover` coloring (Section 1 table) uses semantic *positive/warning/negative*, mapped: **red < 2.5, amber < 4, green otherwise.** The amber here is `copper` — the only place the accent doubles as a warning, which is intentional: low cover is what makes disruptions bite.

### 3.2 Typography

Three roles. Keep it disciplined — the reference uses essentially one humanist sans and looks calm; we add a data face because *this* product’s personality is “these numbers were proven.”

| Role | Family | Rationale |
|---|---|---|
| **UI / body** | **Inter** (variable) | Neutral, legible, matches the reference’s clean humanist sans. Workhorse for labels, table text, prose. |
| **Display / headings** | **Inter Tight** (or Inter at 700/800 with tight tracking) | Slightly condensed for confident section titles and the page title without importing a whole second personality. |
| **Data / money** | **IBM Plex Mono** (or Geist Mono / JetBrains Mono) | Reserved for the **hero cost number, provable ranges, and error-bar labels**. Monospaced digits reinforce “computed, provable.” This is the product’s signature. |

Load Inter + Inter Tight + one mono. Set `font-feature-settings: "tnum" 1, "cv05" 1` on all numeric contexts (`font-variant-numeric: tabular-nums` at minimum — mandated by the product PRD).

**Type scale** (px, line-height, weight, tracking):

| Style token | Size / LH | Weight | Tracking | Use |
|---|---|---|---|---|
| `display.hero` | 44 / 48 | 700 | −0.01em | Hero cost `$808,203` (mono) |
| `display.lg` | 32 / 38 | 700 | −0.01em | Big stat numbers, backtest figures (mono) |
| `heading.page` | 26 / 32 | 700 | −0.005em | “Reorder Copilot” page title |
| `heading.section` | 20 / 26 | 650 | 0 | Section titles (“The Reallocation”) |
| `heading.card` | 15 / 20 | 600 | 0 | Card/panel titles |
| `body` | 14 / 21 | 400–500 | 0 | Prose, table cells |
| `body.strong` | 14 / 21 | 600 | 0 | Emphasis in prose |
| `label` (eyebrow) | 11 / 14 | 600 | +0.08em, UPPERCASE | Section eyebrows, column headers, badge text |
| `caption` | 12 / 16 | 400 | 0 | Captions, helper text, `fg.muted` |
| `data.table` | 13 / 18 | 500 (mono opt.) | 0 | Numeric table cells, tabular |

**Money formatting (non-negotiable):** always `$1,234,567` with thousands separators, tabular. Never a raw float, never `$361132.1`. Cents only where the product PRD shows them (the before/after/cap strip). Provide one formatter util; use it everywhere.

### 3.3 Spacing & layout grid

4px base unit. Scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

- **App max width:** 1440px content area, centered, with the shell inset ~16–24px from the viewport on the canvas.
- **Sidebar rail:** 248px fixed (collapses to 64px icon-rail below 1024px; hidden behind a toggle below 768px — tablet is the floor, no true mobile).
- **Content gutter:** 32px between sidebar and content on desktop; 24px page padding.
- **Card padding:** 24px desktop, 20px compact panels.
- **Vertical rhythm between sections:** 32px. Between cards in a row: 24px.
- **12-column grid** inside the content area, 24px gutters, for arranging the paired panels (Campaign-Performance-style two-up like the reference’s bottom row).

### 3.4 Radius (`theme.tokens.radii`)

Softer than a spreadsheet, tighter than the reference’s bubbliness.

| Token | Value | Use |
|---|---|---|
| `radii.sm` | 8px | Inputs, badge inner, table container corners |
| `radii.md` | 12px | Buttons, small cards, chart tiles |
| `radii.lg` | 16px | Panels / cards (the primary card radius) |
| `radii.xl` | 24px | The outer app shell window (echoes the reference) |
| `radii.pill` | 999px | Delta pills, status chips, search field |

### 3.5 Elevation / shadow (`theme.tokens.shadows`)

Soft, low-opacity, layered — the reference’s calm float, not drop-shadow drama. In dark mode, shadows nearly vanish; separation comes from `border.subtle` + a half-step surface lift.

| Token | Light value | Notes |
|---|---|---|
| `shadow.sm` | `0 1px 2px rgba(16,24,40,.04), 0 1px 1px rgba(16,24,40,.03)` | Inputs, chips |
| `shadow.card` | `0 1px 3px rgba(16,24,40,.05), 0 10px 28px -14px rgba(16,24,40,.12)` | Panels/cards |
| `shadow.hero` | `0 2px 6px rgba(16,24,40,.06), 0 20px 48px -18px rgba(16,24,40,.18)` | The answer/hero card, popovers |
| `shadow.shell` | `0 30px 80px -40px rgba(16,24,40,.28)` | The outer app window float |

Dark mode: replace with `0 0 0 1px var(border.subtle)` rings + very subtle `0 8px 24px -16px rgba(0,0,0,.6)`.

**Ambient background:** the canvas gets a faint cool wash — a `radial-gradient` at the top-left in `steel.50`→`steel.25` (light) or `steel.900`→`steel.950` (dark), plus an *optional* whisper of copper glow (≤6% opacity) behind the hero. Keep it subliminal; if you can consciously notice it, it’s too strong.

### 3.6 Iconography

- **Lucide** line icons, 1.5px stroke, 20px on a 24px touch target. Matches the reference’s clean line style.
- Icons are `fg.secondary` by default, `fg.primary` on hover/active, `accent.fg` only when marking the decision.
- Semantic icons: `trending-up`/`trending-down` for deltas, `shield` for safety stock, `wallet`/`banknote` for budget, `package` for parts, `alert-triangle` for at-risk, `check-circle` for OPTIMAL/PROVEN.

### 3.7 Motion

Deliberately minimal (product PRD: “no animation flourishes”).

- **State transitions:** 120–160ms, `ease-out`. Hover, focus, theme toggle.
- **Panel entrance:** 200ms fade + 4px rise, *once*, on first data arrival. Not on every re-render.
- **The loading sequence is the one designed motion moment** (Section 8). It’s informational, not decorative.
- Respect `prefers-reduced-motion`: drop the rise, keep opacity.

---

## 4. Layout & app shell

Single page, four stacked sections, one TanStack route. The reference’s chrome (sidebar + topbar + floating window) is kept but repurposed: the sidebar becomes a **section navigator + solver status rail** instead of multi-page nav.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ░░ calm cool canvas, faint steel wash, whisper of copper top-left ░░       │
│  ┌────────────────────────────────────────────────────────────────────┐   │  ← app shell
│  │ SIDEBAR 248px │  TOPBAR                                             │   │    radii.xl
│  │               │  Reorder Copilot        scenario chip · ☾ theme · ↗ │   │    shadow.shell
│  │ ◆ Reorder     ├────────────────────────────────────────────────────┤   │
│  │   Copilot     │                                                     │   │
│  │               │  ① THE FACTORY        (parts table, weeks-of-cover) │   │
│  │ ① Factory     │                                                     │   │
│  │ ② Disruption  │  ② THE DISRUPTION     (structured + NL inputs)      │   │
│  │ ③ Answer      │                                                     │   │
│  │ ④ Evidence    │  ③ THE ANSWER         ← hero. headline / reallocate │   │
│  │               │                          / binding constraint       │   │
│  │ ───────────   │                                                     │   │
│  │ solver status │  ④ THE EVIDENCE       (backtest: solver vs (s,Q))   │   │
│  │ ● OPTIMAL     │                                                     │   │
│  │ ☾ theme       │                                                     │   │
│  └───────────────┴────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Sidebar (248px, `bg.surface`, right `border.subtle`):**
- Top: wordmark. “Reorder Copilot” — set in `heading.card` weight 700, with a small copper diamond/mark. No cartoon logo.
- Nav = four section anchors (①–④) that scroll-spy: the in-view section gets an **active treatment** — *not* the reference’s loud lime pill, but a `bg.subtle` fill + a 3px `accent.solid` left bar + `fg.primary` text. Restrained, unmistakable.
- Bottom cluster: **solver status chip** (`● OPTIMAL` / `FEASIBLE` / `INFEASIBLE` / `no run yet`), theme toggle, and — if `trace_url` exists after an agent run — a “View trace ↗” link.

**Topbar (64px, `bg.surface`, bottom `border.subtle`):**
- Left: page title “Reorder Copilot” + one-line subtitle (“Re-optimize the weekly buy when a supplier slips”).
- Right: **scenario chip** (once a run exists: `PART-1003 · 3 → 6 wks · OPTIMAL`), theme toggle, trace link. No search bar (the reference has one; we don’t need it — don’t add chrome that does nothing).

**Content canvas (`bg.canvas`):** the four sections as `bg.surface` panels with `radii.lg` + `shadow.card`, 32px vertical rhythm.

---

## 5. Component library

Specs for the reusable pieces. All reference semantic tokens only.

### 5.1 Panel / Card
`bg.surface` · `radii.lg` · `shadow.card` · `border.subtle` (1px) · padding 24. Header row: `heading.card` title left, optional actions right (icon buttons, `fg.secondary`). Body separated from header by 16px. Every panel must define its **empty**, **loading**, and **error** state (Section 8).

### 5.2 Stat block (metric)
Mirrors the reference’s Delivered/Opened tiles, minus the marketing gloss.
```
LABEL (label style, fg.secondary)          ┌──────────┐
$808,203                                    │ ▲ 2.4%   │  ← delta pill
provably $799,241–$816,619 (caption, mono)  └──────────┘
```
- Number: `display.lg` mono, `fg.primary`, tabular.
- Delta pill: `radii.pill`, `positive.subtle`/`negative.subtle` bg, `positive.fg`/`negative.fg` text, 11px, arrow glyph. **Only use for genuinely signed values.** Many of our numbers aren’t “good/bad” — don’t slap a green pill on them.
- Sub-line (range) in mono caption; this is where the credibility lives.

### 5.3 Status chip / badge
`radii.pill` or `radii.sm`, `label` type. Variants:
- `OPTIMAL` → `positive.subtle` bg + `positive.fg` + check glyph.
- `FEASIBLE` → neutral `bg.subtle` + `fg.secondary`.
- `INFEASIBLE` → `negative.subtle` + `negative.fg` + alert glyph.
- `BINDING — PROVEN` → `accent.subtle` bg + `accent.fg` + copper dot. **Rendered only when `binding_constraint.proven === true`.**
- Never invent a “winner” chip when `proven === false` (Section 8).

### 5.4 Buttons
- **Primary** (`Re-plan`): `accent.solid` bg, white text, `radii.md`, weight 600, height 40. Hover → `copper.500`. This is the one place copper is a call to action, because pressing it *is* the decision.
- **Secondary**: `bg.surface`, `border.default`, `fg.primary`. Hover → `bg.subtle`.
- **Ghost/icon**: transparent, `fg.secondary`, hover `bg.subtle`.
- Focus: 2px `focusRing` outline, 2px offset. Always visible on keyboard nav.

### 5.5 Inputs (Section 2)
- **SKU select** + **lead-time number input**: height 40, `radii.sm`, `bg.subtle` fill, `border.default`, focus ring copper. Number input shows unit suffix “weeks.”
- **NL textarea**: `bg.subtle`, `radii.md`, min 2 lines, pre-filled with *“Kraus emailed — PART-1003 is going from 3 weeks to 6 weeks.”* A small copper “✦ AI” marker distinguishes the agent path from the structured path.

### 5.6 Data table (Section 1)
- Container: `radii.sm`, `border.subtle`, header row `bg.subtle`.
- Header cells: `label` style, `fg.secondary`, right-aligned for numerics.
- Body cells: `data.table`, tabular, numerics right-aligned so digits stack.
- Row hover: `bg.subtle`. Expandable row reveals the demand sparkline.
- **`weeks_of_cover` cell** is the star: value + a tiny inline bar or a colored dot. Color by threshold (red < 2.5, amber/copper < 4, green otherwise). PART-1003 (3.1) sits in amber — make that visible; it’s the razor-thin margin that explains the whole demo.

### 5.7 Delta pill (chart & table)
Small, `radii.pill`, tinted, arrow + tabular value. Reused in stat blocks, table deltas, and backtest.

### 5.8 Sparkline
`fixture-demand-PART-1003.json`, 104 weeks, in the expanded table row. `chart.muted` stroke, no axes, ~120×32px, last point dotted. Purely contextual — no labels.

---

## 6. Screens (section-by-section direction)

### Section 1 — The Factory (the setup)

**Job:** establish tension. 20 parts; PART-1003 is one delay away from stopping the line.

Panel title “The Factory,” eyebrow “20 parts · weekly buy.” Table columns: SKU · unit cost · lead time · MOQ · on hand · avg weekly demand · **weeks of cover**. Right-align every numeric. `weeks_of_cover` gets the color treatment and a tiny bar. Sort default by weeks-of-cover ascending so the at-risk parts (including PART-1003) surface at the top. Expanded PART-1003 row shows the demand sparkline and a one-line callout: *“3.1 weeks of cover against a 3-week lead time. No slack.”*

```
┌─ The Factory ─────────────────────────────────────────────────────────────┐
│ SKU        UNIT COST   LEAD   MOQ    ON HAND   AVG/WK   WEEKS OF COVER      │
│ PART-1003   $111.59     3 wk   200      635       203    ▮▮▮░░ 3.1  ●amber  │
│ PART-1012   …                                          ▮▮▮▮░ 3.8  ●amber   │
│ PART-1000   …                                          ▮▮▮▮▮ 5.2  ●green   │
│ …                                                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

### Section 2 — The Disruption (the interaction)

**Job:** let the user trigger a re-plan two ways, and make the 10–30s wait feel like work, not a hang.

Two side-by-side input cards (2-up grid, stack on tablet):
- **Structured** — SKU select + lead-time input + **Re-plan** primary button. Wires to `POST /api/disrupt`.
- **Natural language** — textarea pre-filled with the Kraus sentence + **Ask the copilot** button, marked with the copper ✦ AI dot. Wires to `POST /api/agent`.

On submit, the Answer section (③) enters its **loading sequence** (Section 8) — the honest stepper. Don’t block the whole page; only the answer panels show skeletons.

### Section 3 — The Answer (the hero) ★ spend the design budget here

Three stacked blocks inside one prominent hero panel (`shadow.hero`, slightly larger radius, a hairline copper top-accent to mark it as *the output*).

#### 3a. The headline
```
THIS DELAY COSTS
$808,203            [ OPTIMAL ✓ ]
provably between $799,241 and $816,619
```
- `$808,203` in `display.hero` mono, `fg.primary`.
- Range directly beneath in mono caption — *always shown next to the cost*. This one line is the product’s credibility.
- `OPTIMAL` status chip to the right.
- **Integrity:** if `disruption_cost_dollars` is `null`, replace the number with the honest message (Section 8.3). Never `$0`, never a spinner-forever.

#### 3b. The Reallocation — the money shot ★★★

This is the single most important visual in the product. Build it with care.

**Diverging horizontal bar chart** of `order_changes_week0`, sorted by `|cash_delta_dollars|` descending, labeled in **dollars** (not units):
- Zero line centered. Bars grow **right = money spent** (the cause), **left = money freed** (the cuts).
- **PART-1003** grows right, `accent.solid` copper (+$85,812) — the cause.
- **PART-1012** (−$60,412), **PART-1000** (−$25,908, *cancelled entirely*) grow left, `negative.solid` red — the victims. A cancelled part gets a small “✕ cancelled” tag.
- Row label = SKU (left gutter, mono). Value label at the bar’s outer end (mono, tabular, signed).
- Neutral/near-zero changes render in `chart.muted`.

Directly beneath, the **punchline strip** — three big numbers pinned to a copper “ceiling” hairline to make “this is the same money both times” land:

```
                      ── BUDGET CAP  $361,135 ──────────────────  (copper hairline + label)
   cash before            cash after
   $361,132               $361,134
   ▲ (both sit just under the same ceiling)
```
- Render the cap as a horizontal copper hairline spanning the strip, labeled `BUDGET CAP $361,135`.
- `before` and `after` sit *just below* it as two mono `display.lg` numbers, visibly almost touching the line and each other — the visual says *the wall didn’t move*.
- Caption (`body`, `fg.secondary`): **“One part got late. 17 of 20 parts had their orders rewritten — because the budget didn’t grow. Paying for PART-1003 means cancelling someone else.”**
- A small `17 / 20 parts rewritten` stat sits beside it.

Then the **focus-part schedule**, before vs after, from `focus_part_schedule` (12 weeks each): grouped bars, *before* in `chart.muted`, *after* in `accent.solid`. The week-0 spike (“buy 1,067 now instead of 298”) is the readable moment — annotate week 0.

```
┌─ The Reallocation ────────────────────────────────────────────────────────┐
│  cut ◀──────────────── $0 ───────────────▶ spend                           │
│  PART-1003        │                    ████████████ +$85,812  ●copper      │
│  PART-1012  ████████████ −$60,412 │                            ●red        │
│  PART-1000  █████ −$25,908 ✕cancelled │                        ●red        │
│  PART-1007       ██ −$8,204 │                                  ●red        │
│  …                          │                                              │
│  ─────────────────────────────────────────────────────────────────────    │
│        ── BUDGET CAP $361,135 ────────────────────────────────────         │
│        before $361,132     after $361,134     17/20 rewritten              │
│  “One part got late. 17 of 20 orders rewritten — the budget didn’t grow.”  │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 3c. The binding constraint

Render `probes[]` as horizontal bars of `recovered_dollars`, **each with a provable-range error bar** (`provable_low` → `provable_high`) drawn as a capped whisker. Showing error bars is the point — style them as first-class, in `fg.secondary`, with mono end labels.

- If `binding_constraint.proven === true`: badge the winning probe **`BINDING — PROVEN`** (copper chip), and add the caption: *“Its worst case ($322,458) still beats the runner-up’s best case ($79,231).”*
- If `false`: **no badge on anything.** Show the probes plus the honest line *“Cannot name a bottleneck at this tolerance.”* (Section 8.4.)

Then the **simulation**: fill rate median **81.2%**, bad-case (p10) **80.4%**, from 1,000 sampled futures. A simple horizontal gauge or slim distribution; **emphasize p10** with the caption *“even in a bad week.”* p50 is a marker; p10 is the highlighted value.

### Section 4 — The Evidence (why believe it)

From `fixture-backtest.json`. Two grouped bars, cost and fill rate side by side:

| | Cost | Fill rate |
|---|---|---|
| `(s,Q)` rule (what an ERP runs) | $2,021,032 (muted) | 77.9% (muted) |
| **This solver** | **$1,329,961** (copper) | **84.4%** (green) |

Headline: **“Saves $691,071 and serves 6.5 points more demand — cheaper *and* better service, not a trade-off.”**

Honest caveat as body text (it *strengthens* the claim): *“With slack cash, the optimizer only ties the simple rule. Its advantage appears when the cash budget binds and it must ration across parts — which a per-part rule cannot do.”*

If `trace_url` exists, a **“View the agent’s trace ↗”** link.

---

## 7. Chart design specs (Recharts)

Global chart rules: theme via CSS variables / Chakra `token()` so charts follow light/dark automatically. Tabular mono labels. No 3D, no gradients-for-decoration, gridlines in `chart.grid` at low opacity, no chart legends when a one-line caption does the job. Charts live in a horizontally-scrollable container so the page body never scrolls sideways (product PRD).

| Chart | Type | Color logic | Notes |
|---|---|---|---|
| **Reallocation** (3b) | Diverging horizontal bar | Right/cause = `accent.solid`; left/cuts = `negative.solid`; neutral = `chart.muted` | Sorted by `|cash_delta|`. Dollar axis. Value labels at bar ends. This is the hero — give it the most vertical room. |
| **Focus schedule** (3b) | Grouped vertical bar, 12 weeks | before = `chart.muted`; after = `accent.solid` | Annotate week 0. |
| **Probes** (3c) | Horizontal bar + error whisker | bars neutral/`blue`; whisker `fg.secondary`; winner bar `accent.solid` *iff proven* | Error bar is the feature. Mono end labels. |
| **Simulation** (3c) | Gauge or slim distribution | track `chart.muted`; p50 marker `fg.primary`; **p10 highlighted** `accent.fg` | Emphasize p10. |
| **Backtest** (4) | Grouped bar ×2 (cost, fill) | baseline `chart.muted`; solver cost `accent.solid`, solver fill `positive.solid` | Big savings number above. |
| **Sparkline** (1) | Line, no axes | `chart.muted` | Contextual only. |

---

## 8. States — loading, empty, error, and the two integrity rules

Every panel needs all four. The 20–30s solve **will** be seen; the two integrity rules are the product’s spine.

### 8.1 The loading sequence (the one designed motion moment)
When `/api/disrupt` or `/api/agent` is running, the Answer panels show an **honest stepped progress**, not a spinner:

```
Re-optimizing 20 parts…
  ✓ Building the scenario
  ● Running 5 optimizations        ⟳
  ○ Simulating 1,000 futures
  ○ Diffing the plan
                                    elapsed 00:14 · this takes 10–30s
```
- Steps light up as they’d plausibly complete (drive from real events later; sequence sensibly on fixtures now).
- Result panels show **skeletons** shaped like their real content (a skeleton hero number, skeleton bars) so the layout doesn’t jump.
- An elapsed counter + the line *“this takes 10–30 seconds — the solver is proving the answer.”* The wait is framed as rigor, not lag.
- Agent path adds a step: *“Reading the email… reasoning…”* (+~2 LLM round trips).

### 8.2 Empty (no run yet)
Answer/Evidence panels before any run: a calm placeholder in the interface voice, not a shrug. *“Pick a part and a new lead time, then re-plan. The result appears here.”* Copper-outlined ghost of the hero number. An empty screen is an invitation to act, never a dead end.

### 8.3 Cost is `null` (integrity rule 1)
When `disruption_cost_dollars === null`, the headline shows, in `fg.primary` at a legible size (not tiny grey):
> **The solver could not prove a reliable cost for this run.**
Sub-line: *“It won’t report a number it can’t stand behind.”* Never `$0`, never an infinite spinner, never an invented figure. This is a *feature*, styled with the same care as a real number.

### 8.4 Binding constraint unproven (integrity rule 2)
When `binding_constraint.proven === false`: show the probe bars and their error bars, **omit every winner badge**, and display *“Cannot name a bottleneck at this tolerance.”* in `fg.secondary`. The absence of a badge is the correct, designed outcome — do not let a default “top bar = winner” styling sneak a crown back on.

### 8.5 INFEASIBLE / error
- `solver_status === "INFEASIBLE"`: a `negative.subtle` panel, alert glyph, *“No feasible plan at this lead time under the current budget.”* Offer the probes if present (they show *what to relax*).
- Network/API error: `negative.subtle`, plain-language cause + a **Retry** button. Errors don’t apologize and are never vague: say what failed and what to do.

---

## 9. Dark mode

Chakra v3 + `next-themes` drives it; because components use only semantic tokens, dark mode is a token swap, not a re-skin. Specifics:
- Canvas `steel.950`, cards `steel.900`, elevated `steel.800`. Separation via `border.subtle` + half-step surface lift, since shadows barely read on dark.
- Copper stays `copper.400` for fills but text-on-dark uses `copper.300` (`accent.fg` dark) for contrast.
- Green/red fills brighten one step (`green.400`/`red.400`) so bars stay legible on dark.
- The ambient wash flips to `steel.900→950`; the copper glow drops to ≤4% opacity.
- **Verify both modes for every panel** — it’s an acceptance criterion. The hero number, the reallocation bars, and the error-bar labels are the usual first things to break.

---

## 10. Accessibility & precision

- **Contrast:** body text ≥ 4.5:1, large display ≥ 3:1, in *both* modes. `accent.fg` values above are chosen to pass on their surfaces; re-check if you shift hues.
- **Never color-alone:** the reallocation encodes cause/cut by *direction + sign + label*, not just copper/red. Status is text + color, not color only. Weeks-of-cover uses a dot *and* the number.
- **Tabular numerals everywhere numeric** (product PRD mandate) so money columns align to the digit.
- **Focus:** visible 2px copper focus ring on every interactive element; full keyboard path through inputs → Re-plan → results.
- **Charts:** each has a text summary / caption conveying the same point for screen readers; data tables behind charts where feasible.
- **Reduced motion:** honor `prefers-reduced-motion` (drop the rise/step animation, keep content).

---

## 11. Chakra UI v3 implementation notes

Chakra v3 uses `createSystem(defaultConfig, defineConfig({...}))` (the v2 `extendTheme` API is gone). Put raw scales under `theme.tokens`, the light/dark mappings under `theme.semanticTokens`, then reference **only** semantic tokens in components. Verify against current Chakra v3 docs as you build — the API is stable but evolving.

```ts
// src/theme/system.ts
import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

const config = defineConfig({
  theme: {
    tokens: {
      colors: {
        steel: { 25:{value:"#F7F9FB"}, 50:{value:"#EEF2F6"}, 100:{value:"#E2E8EF"},
          200:{value:"#CDD7E1"}, 300:{value:"#AEBAC8"}, 400:{value:"#8593A5"},
          500:{value:"#63728A"}, 600:{value:"#48576B"}, 700:{value:"#33404F"},
          800:{value:"#222E3A"}, 900:{value:"#161F29"}, 950:{value:"#0C121A"} },
        copper: { 50:{value:"#FBF3EA"}, 100:{value:"#F4DFC6"}, 300:{value:"#E2A567"},
          400:{value:"#D6863A"}, 500:{value:"#BC6F26"}, 600:{value:"#98591E"} },
        green:  { 50:{value:"#E7F4EC"}, 400:{value:"#33B37C"}, 500:{value:"#1E9A61"}, 600:{value:"#157A4C"} },
        red:    { 50:{value:"#FBE9E6"}, 400:{value:"#E5654E"}, 500:{value:"#D4463A"}, 600:{value:"#A8302A"} },
        ink:    { value:"#0F1720" }, paper: { value:"#FFFFFF" },
      },
      fonts: {
        body:    { value: "'Inter', system-ui, sans-serif" },
        heading: { value: "'Inter Tight', 'Inter', sans-serif" },
        mono:    { value: "'IBM Plex Mono', ui-monospace, monospace" },
      },
      radii: { sm:{value:"8px"}, md:{value:"12px"}, lg:{value:"16px"}, xl:{value:"24px"}, pill:{value:"999px"} },
    },
    semanticTokens: {
      colors: {
        "bg.canvas":   { value: { _light: "{colors.steel.25}",  _dark: "{colors.steel.950}" } },
        "bg.surface":  { value: { _light: "{colors.paper}",     _dark: "{colors.steel.900}" } },
        "bg.subtle":   { value: { _light: "{colors.steel.50}",  _dark: "{colors.steel.800}" } },
        "border.subtle":  { value: { _light: "{colors.steel.100}", _dark: "{colors.steel.800}" } },
        "border.default": { value: { _light: "{colors.steel.200}", _dark: "{colors.steel.700}" } },
        "fg.primary":   { value: { _light: "{colors.ink}",       _dark: "#E7ECF2" } },
        "fg.secondary": { value: { _light: "{colors.steel.500}", _dark: "{colors.steel.300}" } },
        "fg.muted":     { value: { _light: "{colors.steel.400}", _dark: "{colors.steel.500}" } },
        // brand accent as a full colorPalette (solid/fg/subtle/contrast/focusRing)
        "accent.solid":   { value: { _light: "{colors.copper.400}", _dark: "{colors.copper.400}" } },
        "accent.fg":      { value: { _light: "{colors.copper.500}", _dark: "{colors.copper.300}" } },
        "accent.subtle":  { value: { _light: "{colors.copper.50}",  _dark: "rgba(214,134,58,0.14)" } },
        "positive.solid": { value: { _light: "{colors.green.500}",  _dark: "{colors.green.400}" } },
        "positive.fg":    { value: { _light: "{colors.green.600}",  _dark: "{colors.green.400}" } },
        "positive.subtle":{ value: { _light: "{colors.green.50}",   _dark: "rgba(51,179,124,0.14)" } },
        "negative.solid": { value: { _light: "{colors.red.500}",    _dark: "{colors.red.400}" } },
        "negative.fg":    { value: { _light: "{colors.red.600}",    _dark: "{colors.red.400}" } },
        "negative.subtle":{ value: { _light: "{colors.red.50}",     _dark: "rgba(229,101,78,0.16)" } },
        "chart.muted":    { value: { _light: "{colors.steel.200}",  _dark: "{colors.steel.700}" } },
        "chart.grid":     { value: { _light: "{colors.steel.100}",  _dark: "{colors.steel.800}" } },
      },
    },
  },
  globalCss: {
    "html, body": { background: "bg.canvas", color: "fg.primary" },
    // tabular numerals wherever data lives
    ".tnum": { fontVariantNumeric: "tabular-nums" },
  },
})

export const system = createSystem(defaultConfig, config)
```

**Notes:**
- Run `npx @chakra-ui/cli typegen ./src/theme/system.ts` for token autocompletion.
- Color mode uses `next-themes` in v3 (via the generated `color-mode` snippet), not the v2 built-in.
- For a true one-prop accent, promote `copper` to a `colorPalette` with `solid/contrast/fg/muted/subtle/emphasized/focusRing` slots so `<Button colorPalette="copper">` and `colorPalette="copper"` work idiomatically.
- **Recharts theming:** read Chakra CSS variables (e.g. `var(--chakra-colors-accent-solid)`) or the `token()` helper for `fill`/`stroke`, so charts follow light/dark for free. Keep every fetch behind a TanStack Query hook in `src/api/` (product PRD) — theme has nothing to do with data, don’t entangle them.

---

## 12. Design QA checklist (maps to the product PRD’s acceptance criteria)

Run this before calling the UI done. Each item ties to a product-PRD acceptance criterion.

- [ ] **Zero invented numbers** — every figure on screen traces to a fixture field (Appendix A). If you typed a number, it’s a bug.
- [ ] **Reallocation reads cause→victims at a glance** — copper right (PART-1003 +$85,812), red left (PART-1012, PART-1000 cancelled), under a fixed budget. A first-time viewer gets it in one look.
- [ ] **Budget-cap strip lands** — before/after/cap visibly pinned to the same ceiling; caption present; “17/20 rewritten” shown.
- [ ] **Provable range beside the cost AND as error bars** on the probes.
- [ ] **`disruption_cost_dollars: null`** → the honest “could not prove” message, styled with care. (Test by editing the fixture.)
- [ ] **`binding_constraint.proven: false`** → **no** winner badge anywhere; “cannot name a bottleneck” line shows. (Test by editing the fixture.)
- [ ] **20-second loading state** exists, is honest, explains the work, doesn’t look frozen; result panels use shaped skeletons.
- [ ] **weeks_of_cover** colored red<2.5 / amber<4 / green; PART-1003’s thin margin is visible.
- [ ] **Light AND dark** both legible for every panel — hero number, reallocation, error labels especially.
- [ ] **Tabular numerals** everywhere money appears; all money `$1,234,567` formatted.
- [ ] **Copper appears on ≤3 things** per screen (the decision, the constraint, the cause). If more, cut one.
- [ ] **Charts scroll horizontally in their own container**; page body never scrolls sideways.
- [ ] **Keyboard focus** visible on every control; full path through Re-plan to results.
- [ ] **The one-sentence test:** a viewer who’s never seen this watches once and says *“the money is fixed, so helping one part starves another — and the tool says cash is the thing to fix.”*

---

## Appendix A — Fixture numbers to design against (do not invent others)

| Where | Number |
|---|---|
| Disruption cost | **$808,203**, provably **$799,241 – $816,619** |
| PART-1003 (cause) | **+$85,812**, +769 units; buy 1,067 now vs 298 |
| PART-1012 (victim) | **−$60,412** |
| PART-1000 (victim) | **−$25,908**, cancelled entirely |
| Budget strip | before **$361,132** · after **$361,134** · cap **$361,135** (weekly budget $361,134.83) |
| Parts affected | **17 / 20** |
| Fill rate | p50 **81.2%**, p10 **80.4%**, from **1,000** runs |
| Binding-proven caption | worst case **$322,458** beats runner-up best case **$79,231** |
| Backtest | (s,Q) **$2,021,032 / 77.9%** · solver **$1,329,961 / 84.4%** · saved **$691,071**, **+6.5 pts** |
| PART-1003 profile | unit $111.59 · lead 3 wk · MOQ 200 · on hand 635 · avg 203/wk · 3.1 wks cover |
| weeks_of_cover thresholds | red < 2.5 · amber < 4 · green otherwise |

## Appendix B — Microcopy library (interface voice: plain, active, no apology)

| State | Copy |
|---|---|
| Empty answer | “Pick a part and a new lead time, then re-plan. The result appears here.” |
| Loading | “Re-optimizing 20 parts… running 5 optimizations and 1,000 simulations. This takes 10–30 seconds — the solver is proving the answer.” |
| Cost null | “The solver could not prove a reliable cost for this run. It won’t report a number it can’t stand behind.” |
| Constraint unproven | “Cannot name a bottleneck at this tolerance.” |
| Infeasible | “No feasible plan at this lead time under the current budget.” |
| Network error | “Couldn’t reach the solver. [Retry]” |
| Reallocation caption | “One part got late. 17 of 20 orders rewritten — because the budget didn’t grow. Paying for PART-1003 means cancelling someone else.” |
| Backtest caveat | “With slack cash, the optimizer only ties the simple rule. Its advantage appears when the cash budget binds and it must ration across parts — which a per-part rule cannot do.” |

## Appendix C — Where we diverge from the reference, and why

| Divergence | Reason |
|---|---|
| Green brand → copper brand | Green is reserved for the semantic meaning *recovered/good*; using it as brand would make the whole UI ambiguous. Copper is the single accent for *the decision*. |
| Lime active nav pill → subtle fill + copper left-bar | The loud lime reads consumer; a restrained active state suits an instrument and keeps copper meaningful. |
| Pastel yellow/pink cards → steel neutral panels | Multi-color surfaces dilute the one-accent discipline that makes the reallocation legible. |
| Marketing search bar → removed | Chrome that does nothing erodes trust in an ops tool. Add only controls that act. |
| Added a mono data face | The reference has no data personality; ours is “these numbers are proven.” Mono digits earn that. |

---

*Everything numeric in this document is illustrative of the fixtures in the product PRD. The frontend must render those exact values from the fixture JSON — if you find yourself computing a number in TypeScript, stop: that’s the backend’s job.*