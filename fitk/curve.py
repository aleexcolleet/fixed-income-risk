"""
A zero-coupon yield curve, and discounting against it.

Everything so far has priced with a single yield: one rate for every
cashflow, whatever its maturity. That is a quoting convention, not a model.
A real curve gives each maturity its own rate, and the price is the sum of
cashflows discounted at their own rate. The single yield is then a summary
of that price, not an input to it.

The curve published by the ECB is CONTINUOUSLY COMPOUNDED. The engine in
pricing.py compounds m times a year. Mixing them silently misprices a
ten-year bond by a whole point, so the two live in separate modules with
separate discount functions and an explicit converter between them.
"""

from dataclasses import dataclass
from math import exp, log
from pathlib import Path

from fitk.cashflows import Cashflow


@dataclass(frozen=True)
class Curve:
    """
    Continuously compounded zero rates at a set of tenors, in years.

    Tenors must be ascending. Rates are decimals: 0.034 is 3.4%.
    """
    tenors: tuple[float, ...]
    rates: tuple[float, ...]

    def __post_init__(self):
        if len(self.tenors) != len(self.rates):
            raise ValueError("tenors and rates must be the same length")
        if len(self.tenors) < 2:
            raise ValueError("a curve needs at least two points")
        if list(self.tenors) != sorted(self.tenors):
            raise ValueError("tenors must be ascending")

    @classmethod
    def from_csv(cls, path: str | Path) -> "Curve":
        """
        Load tenor_years,zero_rate_percent. Lines starting with # are notes.

        Percent in the file, decimals in the object: the file mirrors what
        the source publishes, the conversion happens once, here.
        """
        tenors, rates = [], []
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("tenor"):
                continue
            tenor, rate = line.split(",")
            tenors.append(float(tenor))
            rates.append(float(rate) / 100.0)
        return cls(tuple(tenors), tuple(rates))

    def zero_rate(self, t: float) -> float:
        """
        Continuously compounded zero rate at t, linear between tenors.

        Linear interpolation on the rate, flat extrapolation beyond the ends.
        Both are choices, and both are wrong in a specific way worth knowing:
        linear-on-rates produces kinked forward rates at every node, and flat
        extrapolation pretends the curve stops moving past 30 years. The
        market interpolates on log discount factors or fits a parametric form
        (Svensson, which is what produced this data). Step 10 does better;
        this is deliberately the simplest thing that is honest about itself.
        """
        if t <= self.tenors[0]:
            return self.rates[0]
        if t >= self.tenors[-1]:
            return self.rates[-1]
        for (t0, r0), (t1, r1) in zip(zip(self.tenors, self.rates),
                                      list(zip(self.tenors, self.rates))[1:]):
            if t0 <= t <= t1:
                return r0 + (r1 - r0) * (t - t0) / (t1 - t0)
        raise AssertionError("unreachable: t is inside the tenor range")

    def discount_factor(self, t: float) -> float:
        """exp(-r*t). Continuous compounding, unlike pricing.discount_factor."""
        return exp(-self.zero_rate(t) * t)

    def present_value(self, cashflows: list[Cashflow]) -> float:
        """Each cashflow at its own maturity's rate. The point of a curve."""
        return sum(cf.amount * self.discount_factor(cf.t) for cf in cashflows)

    def shifted(self, spread: float) -> "Curve":
        """
        The same curve with a flat spread added to every tenor.

        A parallel shift: the crudest scenario there is, and the one every
        risk report starts with. Step 12 replaces it with bucket-by-bucket
        shifts, which is where a duration number stops being enough.
        """
        return Curve(self.tenors, tuple(r + spread for r in self.rates))


def to_continuous(rate: float, m: int) -> float:
    """A rate compounded m times a year, as a continuous rate."""
    return m * log(1 + rate / m)


def to_compounded(rate: float, m: int) -> float:
    """A continuous rate, as one compounded m times a year."""
    return m * (exp(rate / m) - 1)


def implied_flat_spread(curve: Curve, cashflows: list[Cashflow],
                        target_value: float, tol: float = 1e-12,
                        max_iter: int = 200) -> float:
    """
    The flat spread over the curve that reproduces target_value.

    For a government bond priced against a AAA curve this is the market's
    price for that government's credit and liquidity, expressed as one
    number. It is the crudest possible spread measure -- it forces a single
    number onto a term structure that has shape -- and it is the one a trader
    quotes, because one number is what you can compare across bonds.

    Bisection, not Newton, and this one is a considered choice rather than
    laziness: the present value is strictly decreasing in the spread, so a
    bracket cannot fail, and the derivative with respect to a curve shift is
    not something this module has. Newton would need a numerical derivative
    anyway, at which point robustness wins over speed for a function called
    a handful of times.
    """
    lo, hi = -0.05, 0.20
    if curve.shifted(lo).present_value(cashflows) < target_value:
        raise ValueError(f"target {target_value} is above the -500bp bracket")
    if curve.shifted(hi).present_value(cashflows) > target_value:
        raise ValueError(f"target {target_value} is below the +2000bp bracket")

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if curve.shifted(mid).present_value(cashflows) > target_value:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            return (lo + hi) / 2
    return (lo + hi) / 2
