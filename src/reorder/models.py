from pydantic import BaseModel


def to_cents(dollars: float) -> int:
    """Money is integer cents everywhere in the model. CP-SAT cannot do floats."""
    return round(dollars * 100)


def to_dollars(cents: int) -> float:
    return cents / 100.0


class Part(BaseModel):
    sku: str
    unit_cost: int          # cents per unit
    holding_cost: int       # cents per unit per week held
    order_cost: int         # cents charged whenever we place any order
    moq: int                # minimum order quantity (units)
    lead_time: int          # weeks between placing and receiving
    volume: int             # warehouse space units per unit held
    opening_inventory: int  # units on hand at t=0


class Problem(BaseModel):
    parts: list[Part]
    weeks: int
    demand: dict[str, list[int]]     # sku -> p50 forecast units per week (len == weeks)
    safety_stock: dict[str, int]     # sku -> target buffer units
    budget: list[int]                # cents available to spend per week (len == weeks)
    warehouse_cap: int               # total volume units available
    stockout_penalty: int            # cents per unit of unmet demand per week
    safety_penalty: int              # cents per unit below safety stock per week

    def part(self, sku: str) -> Part:
        return next(p for p in self.parts if p.sku == sku)

    @property
    def skus(self) -> list[str]:
        return [p.sku for p in self.parts]


class Plan(BaseModel):
    status: str                      # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
    cost: int | None                 # objective value in cents (None if infeasible)
    bound: int | None                # best proven bound in cents
    orders: dict[str, list[int]]     # sku -> units ordered per week
    inventory: dict[str, list[int]]  # sku -> on-hand per week
    backorder: dict[str, list[int]]  # sku -> unmet demand per week
    short: dict[str, list[int]]      # sku -> units below safety stock per week

    @property
    def is_optimal(self) -> bool:
        return self.status == "OPTIMAL"

    @property
    def gap(self) -> float:
        """Relative optimality gap. 0.0 means proven optimal."""
        if self.cost is None or self.bound is None or self.cost == 0:
            return 0.0
        return abs(self.cost - self.bound) / abs(self.cost)
