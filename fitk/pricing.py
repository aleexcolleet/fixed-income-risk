from fitk.cashflows import Cashflow

def discount_factor(y: float, t: float) -> float:
    """Value today of 1 unit received at time t, discounted at yield y."""
    return (1 + y) ** (-t)

def price(cashflows: list[Cashflow], y:float) -> float:
    """Present value of a list of cashflows at a single yield y"""
    total = 0.0
    for cf in cashflows:
        total += cf.amount * discount_factor(y, cf.t)
    return total


