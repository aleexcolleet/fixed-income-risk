"""Day count conventions: how many years are there between two dates?

The answer is contractual, not mathematical. Each convention is specified
in the instrument's prospectus. Using the wrong one does not produce a
rounding error — it prices a different instrument.

ACT/ACT (ICMA) is not here: its denominator is the actual length of the
current coupon period, so it needs the coupon schedule and cannot be a pure
function of two dates. It arrives with the date schedule in the next step.
"""

from datetime import date


def act_360(d1: date, d2: date) -> float:
    """Actual days over 360. Money markets: EUR and USD deposits, most FRNs."""
    return (d2 - d1).days / 360.0


def act_365f(d1: date, d2: date) -> float:
    """Actual days over a fixed 365. GBP money markets."""
    return (d2 - d1).days / 365.0


def thirty_360(d1: date, d2: date) -> float:
    """30/360 US (Bond Basis). US corporate and agency bonds.

    Every month is treated as 30 days and every year as 360, so a year of
    interest divides evenly into months and quarters. It predates computers.

    The end-of-month adjustments must be applied in this order: d2 is only
    pulled back to 30 if d1 has already become 30.
    """
    dd1, dd2 = d1.day, d2.day
    if dd1 == 31:
        dd1 = 30
    if dd2 == 31 and dd1 == 30:
        dd2 = 30
    days = 360 * (d2.year - d1.year) + 30 * (d2.month - d1.month) + (dd2 - dd1)
    return days / 360.0