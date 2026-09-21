from dataclasses import dataclass
from fitk.cashflows import Cashflow

@dataclass(frozen=True)
class Bond:
    face: float   # Principal repaid at maturity
    coupon: float # Annual coupon rate as decimal
    maturity: int # Years to maturity

    def cashflows(self) -> list[Cashflow]:
        payment = self.face * self.coupon
        flows = [Cashflow(t, payment) for t in range(1, self.maturity + 1)]
        last = flows[-1]
        flows[-1] = Cashflow(last.t, last.amount + self.face)
        return flows