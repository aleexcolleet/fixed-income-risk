from fitk.cashflows import Cashflow

def discount_factor(y: float, t: float, m: int = 1) -> float:
    """Value today of 1 unit received at time t,
        y is a nominal annual rate compounded m times per year."""
    return (1 + y / m) ** (-m * t)

def price(cashflows: list[Cashflow], y:float, m: int = 1) -> float:
    """Present value of a list of cashflows at a single yield y
        compounded m times per year."""
    total = 0.0
    for cf in cashflows:
        total += cf.amount * discount_factor(y, cf.t, m)
    return total

def effective_annual_rate(y: float, m: int) -> float:
    """Annual rate giving the same growth as y compounded m times per year."""
    return (1 + y / m) ** m - 1
