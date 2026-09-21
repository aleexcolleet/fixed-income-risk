from dataclasses import dataclass

@dataclass(frozen=True)
class Cashflow:
    t: float
    amount: float

