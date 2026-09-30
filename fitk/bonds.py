from dataclasses import dataclass
from datetime import date
from typing import Callable

from fitk.cashflows import Cashflow
from fitk.daycount import thirty_360
from fitk.schedule import payment_schedule, previous_quasi_coupon
from fitk.pricing import price, yield_from_price
from fitk import risk

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

    def coupon_amount(self, payment_date: date) -> float:
        """
        The coupon actually paid on payment_date.

        Normally face * coupon / frequency. But a bond issued off-cycle pays
        a short first coupon: it only accrued for part of the period, so it
        only pays for part of the period, scaled by how much of the notional
        period it existed for.

        This was found by real data, not by reasoning. Every test bond in
        this repo is issued on a coupon date, so the full-coupon assumption
        was invisible until the Spanish 3.40% of October 2036 -- issued in
        June, paying in October -- came out 25 basis points wrong.
        """
        full = self.face * self.coupon / self.frequency
        quasi = previous_quasi_coupon(payment_date, self.maturity_date,
                                      self.frequency)
        if quasi >= self.issue_date:
            return full
        return full * (self.daycount(self.issue_date, payment_date)
                       / self.daycount(quasi, payment_date))

    def cashflows(self, valuation_date: date) -> list[Cashflow]:
        """
        Cashflows still outstanding at valuation_date, as (years, amount).

        Time is measured with this bond's day count convention. That is a
        defensible choice and it is not the market's: see icma_cashflows.
        """
        dates = [d for d in self.payment_dates() if d > valuation_date]
        flows = [Cashflow(self.daycount(valuation_date, d),
                          self.coupon_amount(d)) for d in dates]
        last = flows[-1]
        flows[-1] = Cashflow(last.t, last.amount + self.face)
        return flows

    def icma_cashflows(self, settlement: date) -> list[Cashflow]:
        """
        The same cashflows, timed the way the market times them.

        The street convention does not measure time in years at all. It
        measures it in coupon periods: the next coupon is a fraction f of a
        period away, the one after is f+1, then f+2, and the yield is
        compounded once per period. So a bond paying annually on 31 October,
        settling 22 September, has its first cashflow at f = 39/365 and its
        second at f+1 -- never at 1 + 39/365 of a real year, which is what a
        day count would say.

        The two differ because real periods are not all the same length: 365
        days, then 366 in a leap year, then 365. A day count sees that; the
        ICMA measure deliberately does not. The gap is small -- about a
        quarter of a basis point on an eight-year bond -- but it is the
        difference between reproducing the Treasury's published yield and
        merely getting close to it.
        """
        dates = [d for d in self.payment_dates() if d > settlement]
        first = dates[0]
        quasi = previous_quasi_coupon(first, self.maturity_date, self.frequency)
        fraction = ((first - settlement).days / (first - quasi).days)

        flows = [Cashflow(fraction + k, self.coupon_amount(d))
                 for k, d in enumerate(dates)]
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

    def street_yield(self, settlement: date, clean: float) -> float:
        """
        Yield on the ICMA street convention: time in coupon periods.

        This is the number a Treasury, a Bloomberg screen and a trader all
        quote. Reproduces the Spanish Treasury's published "rendimiento
        interno" to within 0.1 basis points on its September 2026 auction --
        see docs/step9-real-data.md. yield_from_clean_price, which measures
        time in years, lands within 0.3bp: close, and not the same number.
        """
        dirty = clean + self.accrued_interest(settlement)
        return yield_from_price(self.icma_cashflows(settlement), dirty,
                                m=self.frequency)

    def modified_duration(self, settlement: date, y: float) -> float:
        """Percentage price fall per unit rise in yield, in years.

        Imported as `risk`, not by function name: a method called
        modified_duration and a module function called modified_duration in
        the same file is a shadowing accident waiting to happen.
        """
        return risk.modified_duration(self.cashflows(settlement), y,
                                      m=self.frequency)

    def convexity(self, settlement: date, y: float) -> float:
        """Curvature of the price-yield relationship."""
        return risk.convexity(self.cashflows(settlement), y, m=self.frequency)

    def dv01(self, settlement: date, y: float) -> float:
        """
        Currency change in value per basis point, on this bond's own face.

        Scale linearly for a real position: a 10m nominal holding has 100,000
        times the DV01 of this 100-face instrument.
        """
        return risk.dv01(self.cashflows(settlement), y, m=self.frequency)

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

        The denominator is the full notional period, not the elapsed one. On
        a seasoned bond those are the same date and this is invisible; on a
        bond issued off-cycle they are not, and using the short period would
        spread a full coupon over fewer days. That inflates accrued by the
        ratio of the periods -- 2.52 instead of 1.03 on the Spanish 2036,
        which the Treasury's own published figure contradicts.
        """
        payment = self.face * self.coupon / self.frequency
        prev = self.previous_coupon_date(settlement)
        nxt = self.next_coupon_date(settlement)
        quasi = previous_quasi_coupon(nxt, self.maturity_date, self.frequency)
        return payment * self.daycount(prev, settlement) / self.daycount(quasi, nxt)
