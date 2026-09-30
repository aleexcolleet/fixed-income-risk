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

def price_derivative(cashflows: list[Cashflow], y: float, m: int = 1) -> float:
    """
    dB/dy: change in present value per unit change in yield.

    Analytic, not a finite difference. Differentiating each term of price()
    gives c_i * (-m*t_i) * (1+y/m)^(-m*t_i - 1) * (1/m); the chain rule's 1/m
    cancels the exponent's m, leaving -t_i * c_i * (1+y/m)^(-m*t_i - 1).

    Factoring out one power of (1+y/m) turns the sum into the price times the
    Macaulay duration, so this whole function equals -B * D_mod. Step 8 reuses
    it rather than deriving duration again.

    Negative for a bond: prices fall when yields rise. Per unit of yield, so
    dividing by 10,000 gives euros per basis point.
    """
    weighted = 0.0
    for cf in cashflows:
        weighted += cf.t * cf.amount * discount_factor(y, cf.t, m)
    return -weighted / (1 + y / m)

def yield_from_price(cashflows: list[Cashflow], target_price: float,
                     m: int = 1, guess: float = 0.05,
                     tol: float = 1e-12, max_iter: int = 100) -> float:
    """
    The single yield at which these cashflows are worth target_price.

    There is no closed form: substituting x = (1+y/m)^-1 turns the price into
    a polynomial in x of degree m*t_n, and polynomials above degree four have
    no root formula. So: Newton-Raphson on f(y) = price(y) - target_price,
    stepping y <- y + (B - P) / (B * D_mod).

    Convergence is global here, not merely local. With all-positive cashflows
    the price is strictly decreasing in y (so the root is unique) and convex
    (so every tangent lies below the curve, and every Newton step lands on the
    same side of the root as the last one). A bad guess costs iterations, not
    correctness.

    That argument fails for a swap, whose cashflows have both signs: the price
    stops being monotone, several roots can exist and the derivative can
    vanish. Step 11 will need a bracketing fallback. Not written yet.

    Raises ValueError if it fails to converge, never a silent wrong answer.
    """
    # (1 + y/m) must stay positive or the discount factors are meaningless.
    floor = -m + 1e-12
    if guess <= floor:
        raise ValueError(f"guess {guess} is outside the domain y > {-m}")

    y = guess
    for _ in range(max_iter):
        error = price(cashflows, y, m) - target_price
        slope = price_derivative(cashflows, y, m)
        if slope == 0.0:
            raise ValueError("zero price sensitivity: Newton cannot step")

        step = -error / slope
        y_next = y + step

        # A wild guess sits where the curve is nearly flat, so the tangent can
        # overshoot past the domain. Bisect toward the boundary instead.
        if y_next <= floor:
            y_next = (y + floor) / 2

        # Stop on the yield, not on the price. The price tolerance would mean
        # different things on face 100 and on face 1bn; the yield is
        # dimensionless, so one tolerance is right for every book.
        if abs(y_next - y) < tol:
            return y_next
        y = y_next
    else:
        raise ValueError(
            f"yield_from_price did not converge in {max_iter} iterations "
            f"(last yield {y}, price error {price(cashflows, y, m) - target_price})"
        )
