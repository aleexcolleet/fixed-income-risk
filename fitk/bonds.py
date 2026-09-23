from dataclasses import dataclass
from fitk.cashflows import Cashflow

@dataclass(frozen=True)
class Bond:
    face: float         # Principal repaid at maturity
    coupon: float       # Annual coupon rate as decimal
    maturity: int       # Years to maturity
    frequency: int = 1  # Coupon payments per year

    def cashflows(self) -> list[Cashflow]:
        n = self.maturity * self.frequency
        payment = self.face * self.coupon / self.frequency
        flows = [Cashflow(k / self.frequency, payment) for k in range(1, n + 1)]
        last = flows[-1]
        flows[-1] = Cashflow(last.t, last.amount + self.face)
        return flows