from dataclasses import dataclass
from datetime import date
from typing import Callable

from fitk.cashflows import Cashflow
from fitk.daycount import thirty_360
from fitk.schedule import payment_schedule
from fitk.pricing import price, yield_from_price

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

    def dirty_price(self, settlement: date, y: float) -> float:
        """
        What you actually pay: the present value of every remaining cashflow.

        This includes the whole of the next coupon, part of which the seller
        earned. The present value knows nothing about that split — the split
        is a quoting convention, not a valuation concept.
        """
        return price(self.cashflows(settlement), y, m=self.frequency)

    def clean_price(self, settlement: date, y: float) -> float:
        """
        The quoted price: dirty less accrued interest.

        Markets quote this because the dirty price sawtooths — it climbs as
        interest accrues and drops by the coupon on payment day. Removing the
        accrual means a move in the quote reflects a move in the market.
        """
        return self.dirty_price(settlement, y) - self.accrued_interest(settlement)

    def yield_from_clean_price(self, settlement: date, clean: float) -> float:
        """
        Yield to maturity implied by a quoted price.

        The trap: the market quotes clean, but the yield discounts every
        remaining cashflow, accrued interest included. Feeding the clean quote
        straight into the solver understates the price and so overstates the
        yield. Measured on a 5-year 5% semiannual bond mid-period: 41 basis
        points. Small enough to survive a careless review, large enough to
        misvalue a book. Accrued goes back on first.
        """
        dirty = clean + self.accrued_interest(settlement)
        return yield_from_price(self.cashflows(settlement), dirty,
                                m=self.frequency)

    def previous_coupon_date(self, settlement: date) -> date:
        """
        Start of the accrual period containing settlement.

        For a bond settling before its first coupon, interest accrues from
        the issue date. Missing this case is how newly issued bonds break
        pricing systems.
        """
        past = [d for d in self.payment_dates() if d <= settlement]
        return past[-1] if past else self.issue_date

    def next_coupon_date(self, settlement: date) -> date:
        """End of the accrual period containing settlement.

        `next()` over a generator returns the first match and stops there.
        It raises StopIteration if none exists, which is correct: asking for
        the accrual period of a matured bond is a caller error, not a case to
        swallow and propagate as None.
        """
        return next(d for d in self.payment_dates() if d > settlement)

    def accrued_interest(self, settlement: date) -> float:
        """
        Interest earned by the seller, paid to them on top of the quote.

        The ratio form makes any ACT convention agree: the denominator
        cancels, so ACT/360, ACT/365F and ACT/ACT ICMA all give the same
        answer. Only 30/360 differs, because it counts days differently.
        """
        payment = self.face * self.coupon / self.frequency
        prev = self.previous_coupon_date(settlement)
        nxt = self.next_coupon_date(settlement)
        return payment * self.daycount(prev, settlement) / self.daycount(prev, nxt)
