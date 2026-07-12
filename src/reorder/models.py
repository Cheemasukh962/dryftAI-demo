"""The typed core: the data shapes every other module speaks in.

These Pydantic classes are the single source of truth for what a Part, a Problem,
and a Plan look like. Because the solver, the simulator, the backtest, and the AI
agent all pass these exact objects around, a bad value gets caught at the boundary
(wrong type -> Pydantic raises) instead of silently becoming a wrong purchase order.
"""
from pydantic import BaseModel


def to_cents(dollars: float) -> int:
    """Money is integer cents everywhere in the model. CP-SAT cannot do floats,
    so we convert dollars -> cents once, at the edges, and stay integer within."""
    return round(dollars * 100)


def to_dollars(cents: int) -> float:
    """Inverse of to_cents, used only for human-readable display."""
    return cents / 100.0


class Part(BaseModel):
    """One purchasable SKU and everything the solver needs to know about it.
    All money fields are in CENTS (see to_cents)."""
    sku: str
    unit_cost: int          # cents per unit purchased
    holding_cost: int       # cents to keep one unit in the warehouse for one week
    order_cost: int         # flat cents charged whenever we place ANY order for this part
    moq: int                # minimum order quantity: order 0, or at least this many
    lead_time: int          # weeks between placing an order and receiving it
    volume: int             # warehouse space one unit occupies
    opening_inventory: int  # units already on hand at week 0


class Problem(BaseModel):
    """A complete reorder question: these parts, this many weeks, under these limits.
    Feed it to solve_reorder() to get a Plan back."""
    parts: list[Part]
    weeks: int                       # planning horizon length
    demand: dict[str, list[int]]     # sku -> expected units per week (the p50 forecast)
    safety_stock: dict[str, int]     # sku -> buffer we'd like to keep on hand
    budget: list[int]                # cents we're allowed to spend each week
    warehouse_cap: int               # total volume the warehouse can hold
    stockout_penalty: int            # cents charged per unit of UNMET demand per week
    safety_penalty: int              # cents charged per unit BELOW safety stock per week
    pipeline: dict[str, list[int]] = {}  # sku -> units already ORDERED that arrive
                                         # each week (from earlier commitments). Lets a
                                         # rolling re-solve honor orders still in transit.

    def part(self, sku: str) -> Part:
        """Look up one Part by its SKU."""
        return next(p for p in self.parts if p.sku == sku)

    @property
    def skus(self) -> list[str]:
        return [p.sku for p in self.parts]


class Plan(BaseModel):
    """The solver's answer. Carries its solver `status` so callers can never
    accidentally trust an unproven result (see is_optimal / gap)."""
    status: str                      # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
    cost: int | None                 # achieved total cost in cents (None if no plan found)
    bound: int | None                # best cost the solver could prove reachable, in cents
    orders: dict[str, list[int]]     # sku -> units ordered per week (the actual decision)
    inventory: dict[str, list[int]]  # sku -> units on hand per week
    backorder: dict[str, list[int]]  # sku -> unmet demand per week
    short: dict[str, list[int]]      # sku -> units below safety stock per week

    @property
    def is_optimal(self) -> bool:
        """True only when the solver PROVED nothing cheaper exists. The guard that
        stops us comparing two merely-'good-enough' plans and reporting noise."""
        return self.status == "OPTIMAL"

    @property
    def gap(self) -> float:
        """How far this plan might be from optimal, as a fraction. 0.0 = proven optimal.
        If it's, say, 0.05, the true best could be up to 5% cheaper than what we found."""
        if self.cost is None or self.bound is None or self.cost == 0:
            return 0.0
        return abs(self.cost - self.bound) / abs(self.cost)
