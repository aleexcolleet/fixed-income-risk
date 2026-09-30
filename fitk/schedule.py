import calendar
from datetime import date

"""Calendar arithmetic for coupon schedules.

Schedules are generated backwards from the maturity date, because maturity
is contractual and fixed. Any irregularity lands on the first period as a
short or long first coupon, which is how bonds are actually issued.
"""
def add_months(d: date, n: int) -> date:
    """
    Shift d by n months, clamping the day to the target month's length.

    Month arithmetic is not well defined: 31 August minus six months could
    be 28 February or 3 March. This clamps, which is the market convention.
    """
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def is_month_end(d: date) -> bool:
    return d.day == calendar.monthrange(d.year, d.month)[1]

def to_month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])

def payment_schedule(issue_date: date, maturity_date: date,
                     frequency: int) -> list[date]:
    """
    Coupon payment dates, ascending, generated backwards from maturity.

    If maturity falls on a month end, every coupon rolls to month end too:
    a bond maturing 30 November pays on 31 May, not 30 May.
    """
    step = 12 // frequency
    eom = is_month_end(maturity_date)
    dates, k = [], 0
    while True:
        d = add_months(maturity_date, -step * k)
        if eom:
            d = to_month_end(d)
        if d <= issue_date:
            break
        dates.append(d)
        k += 1
    return sorted(dates)

def previous_quasi_coupon(payment_date: date, maturity_date: date,
                          frequency: int) -> date:
    """
    The on-cycle date one coupon period before payment_date.

    "Quasi" because for a bond with a short first period this date is before
    the bond existed: no coupon was ever paid on it. It is a fiction, and it
    is the fiction the market uses. Both the accrued interest fraction and
    the ICMA time measure are expressed against this full notional period,
    not against the shorter real one, which is why a short first coupon is
    smaller than a normal one in exactly the ratio of the two.

    Takes maturity_date only to inherit its month-end convention, so this
    date lands on the same cycle payment_schedule produces.
    """
    d = add_months(payment_date, -12 // frequency)
    return to_month_end(d) if is_month_end(maturity_date) else d