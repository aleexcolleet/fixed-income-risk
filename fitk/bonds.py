from dataclasses import dataclass
from datetime import date
from typing import Callable

from fitk.cashflows import Cashflow
from fitk.daycount import thirty_360
from fitk.schedule import payment_schedule

@dataclass(frozen=True)
class Bond:
    """
    A bullet bond with calendar dates.

    The day count convention is a property of the instrument: it is written
    in the prospectus, like the coupon. The bond converts its own dates into
    year fractions, so the pricing engine still receives plain Cashflows and
    never learns that dates exist.
    """
    face: float            # Principal repaid at maturity
    coupon: float          # Annual coupon rate as decimal
    issue_date: date       # First date the bond accrues from
    maturity_date: date    # Contractual redemption date
    frequency: int = 1     # Coupon payments per year
    daycount: Callable[[date, date], float] = thirty_360

    def payment_dates(self) -> list[date]:
        return payment_schedule(self.issue_date, self.maturity_date,
                                self.frequency)

    def cashflows(self, valuation_date: date) -> list[Cashflow]:
        """Cashflows still outstanding at valuation_date, as (years, amount)."""
        payment = self.face * self.coupon / self.frequency
        dates = [d for d in self.payment_dates() if d > valuation_date]
        flows = [Cashflow(self.daycount(valuation_date, d), payment)
                 for d in dates]
        last = flows[-1]
        flows[-1] = Cashflow(last.t, last.amount + self.face)
        return flows