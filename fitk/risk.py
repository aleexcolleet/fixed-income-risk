"""
Interest rate sensitivity: duration, convexity, DV01.

Every quantity here is a property of a list of cashflows, not of a bond. A
swap, a loan book and a liability schedule all arrive as cashflows, so this
module works on all of them without knowing which is which.

Each measure is implemented twice: analytically, by differentiating the price
function, and numerically, by bumping the yield and re-pricing. The two are
not redundant. The analytic form is exact and fast but easy to get subtly
wrong — the discrete-versus-continuous compounding trap below silently
changes duration by 3-4%. The bumped form is slow and approximate but almost
impossible to misderive. Asserting that they agree is the only way to know
the analytic form is right.
"""

from fitk.cashflows import Cashflow
from fitk.pricing import discount_factor, price, price_derivative


def macaulay_duration(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    The weighted average time to payment, weights being present values.

    Measured in years, and that is the whole intuition: a bond with Macaulay
    duration 7 behaves, to first order, like a single payment 7 years out. It
    is not a sensitivity — it is a time. The sensitivity is below.
    """
    weighted = 0.0
    for cf in cashflows:
        weighted += cf.t * cf.amount * discount_factor(y, cf.t, m)
    return weighted / price(cashflows, y, m)


def modified_duration(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    Percentage price fall per unit rise in yield: -(1/B) dB/dy.

    D_mod = D_mac / (1 + y/m). That divisor is the trap. Under continuous
    compounding the two coincide, so code that mixes conventions produces a
    duration wrong by y/m — roughly 2% at a 4% yield paid semiannually, 4% at
    8%. It never raises an error and it never looks absurd, which is exactly
    why it survives into production.

    Computed here from price_derivative rather than from macaulay_duration,
    because -dB/dy / B is the definition. test_risk asserts that the two
    routes agree, which pins the divisor.
    """
    return -price_derivative(cashflows, y, m) / price(cashflows, y, m)


def convexity(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    (1/B) d2B/dy2. The curvature duration alone misses.

    Differentiating price twice:
        d2B/dy2 = sum_i c_i * t_i * (t_i + 1/m) * (1+y/m)^(-m*t_i - 2)

    Positive for any bond with positive cashflows, and that positivity is
    worth money: a yield fall gains more than the equal yield rise loses. It
    is also what makes duration hedging incomplete — a duration-neutral book
    is not convexity-neutral, and a large move moves it.
    """
    weighted = 0.0
    for cf in cashflows:
        weighted += (cf.amount * cf.t * (cf.t + 1 / m)
                     * discount_factor(y, cf.t, m) / (1 + y / m) ** 2)
    return weighted / price(cashflows, y, m)


def dollar_duration(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    Currency price change per unit change in yield: B * D_mod.

    This is the additive one. Modified duration is a ratio, so it does not add
    across a portfolio — you can only average it, weighted by value. Dollar
    duration is a currency amount, so the portfolio's is the sum of its
    positions'. Every hedge ratio is a ratio of dollar durations.
    """
    return -price_derivative(cashflows, y, m)


def dv01(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    Currency change in value for a one basis point move. Positive.

    Dollar duration divided by 10,000, and confusing the two by that factor
    is the most common unit error in the field. Duration compares bonds of
    different sizes; DV01 tells you how many contracts to sell.
    """
    return dollar_duration(cashflows, y, m) / 10_000


def modified_duration_bumped(cashflows: list[Cashflow], y: float,
                             m: int = 1, bump: float = 1e-5) -> float:
    """
    Modified duration by central difference. The independent check.

    Central rather than one-sided: the first-order error cancels, leaving
    O(bump^2), so a 0.1bp bump is accurate to about ten significant figures.
    A one-sided difference would be contaminated by convexity at first order,
    which is precisely the quantity we are trying to measure separately.
    """
    up = price(cashflows, y + bump, m)
    down = price(cashflows, y - bump, m)
    return -(up - down) / (2 * bump) / price(cashflows, y, m)


def convexity_bumped(cashflows: list[Cashflow], y: float,
                     m: int = 1, bump: float = 1e-4) -> float:
    """
    Convexity by second central difference: (B+ - 2B + B-) / bump^2 / B.

    The bump is ten times larger than for duration, on purpose. A second
    difference divides a near-cancelling sum by bump squared, so floating
    point noise grows as 1/bump^2 while the truncation error only falls as
    bump^2. 1e-4 sits near the minimum of the two. This is the standard
    trade-off of numerical differentiation and the reason the analytic form
    is worth having.
    """
    mid = price(cashflows, y, m)
    up = price(cashflows, y + bump, m)
    down = price(cashflows, y - bump, m)
    return (up - 2 * mid + down) / bump ** 2 / mid


def price_change_estimate(cashflows: list[Cashflow], y: float, dy: float,
                          m: int = 1, second_order: bool = True) -> float:
    """
    Taylor estimate of the price change for a yield move dy.

    dB ~= -B * D_mod * dy + 0.5 * B * C * dy^2

    First order alone always underestimates the gain from a fall and
    overestimates the loss from a rise, because it ignores positive
    curvature. On a 200bp move the second-order term is the difference
    between a usable number and a misleading one.
    """
    b = price(cashflows, y, m)
    change = -b * modified_duration(cashflows, y, m) * dy
    if second_order:
        change += 0.5 * b * convexity(cashflows, y, m) * dy ** 2
    return change
