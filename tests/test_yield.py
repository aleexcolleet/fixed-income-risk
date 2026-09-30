from datetime import date

import pytest

from fitk.bonds import Bond
from fitk.cashflows import Cashflow
from fitk.daycount import act_365f
from fitk.pricing import price, price_derivative, yield_from_price

ISSUE = date(2026, 1, 1)


def bond(years: int, coupon: float = 0.05, **kwargs) -> Bond:
    return Bond(face=100, coupon=coupon, issue_date=ISSUE,
                maturity_date=date(2026 + years, 1, 1), **kwargs)


# --- the round trip: the one test that matters ------------------------------

def test_yield_round_trips_for_every_bond():
    """price -> yield -> price. Catches any sign, exponent or convention error.

    336 cases. A hardcoded number can pass by luck; this cannot.
    """
    for years in (1, 2, 5, 10, 30):
        for freq in (1, 2, 4, 12):
            for coupon in (0.0, 0.02, 0.05, 0.09):
                b = bond(years, coupon, frequency=freq)
                cfs = b.cashflows(ISSUE)
                for y in (-0.005, 0.01, 0.04, 0.12):
                    p = price(cfs, y, m=freq)
                    assert yield_from_price(cfs, p, m=freq) == pytest.approx(y, abs=1e-10)


def test_reference_bond_recovers_four_percent():
    """The anchor from sprint 1, run backwards."""
    cfs = bond(3).cashflows(ISSUE)
    assert yield_from_price(cfs, 102.775091) == pytest.approx(0.04, abs=1e-7)


# --- the economics an interviewer checks in the first two minutes ----------

def test_par_price_gives_the_coupon_rate():
    for coupon in (0.01, 0.04, 0.09):
        for freq in (1, 2):
            b = bond(10, coupon, frequency=freq)
            y = yield_from_price(b.cashflows(ISSUE), 100.0, m=freq)
            assert y == pytest.approx(coupon)


def test_discount_yields_above_coupon_premium_below():
    cfs = bond(10, 0.05).cashflows(ISSUE)
    assert yield_from_price(cfs, 92.0) > 0.05      # bought below par
    assert yield_from_price(cfs, 100.0) == pytest.approx(0.05)
    assert yield_from_price(cfs, 108.0) < 0.05     # bought above par


def test_negative_yield_when_price_exceeds_every_cashflow():
    """The euro area lived here for years; a solver that cannot is useless."""
    cfs = bond(5, 0.01).cashflows(ISSUE)
    total = sum(cf.amount for cf in cfs)
    y = yield_from_price(cfs, total + 1.0)
    assert y < 0.0
    assert price(cfs, y) == pytest.approx(total + 1.0)


def test_zero_coupon_matches_the_closed_form():
    """One cashflow does have a formula, so check the solver against it."""
    cfs = [Cashflow(t=7.0, amount=100.0)]
    y = yield_from_price(cfs, 70.0)
    assert y == pytest.approx((100.0 / 70.0) ** (1 / 7.0) - 1)


# --- convergence is global, so prove it -------------------------------------

def test_converges_from_an_absurd_guess():
    """A 1% bond solved from 50% and from 500%. Convexity says it must."""
    cfs = bond(30, 0.01).cashflows(ISSUE)
    p = price(cfs, 0.01)
    for guess in (0.5, 5.0, 50.0, -0.9):
        assert yield_from_price(cfs, p, guess=guess) == pytest.approx(0.01, abs=1e-9)


def test_guess_outside_the_domain_is_rejected():
    cfs = bond(5).cashflows(ISSUE)
    with pytest.raises(ValueError, match="outside the domain"):
        yield_from_price(cfs, 100.0, m=2, guess=-2.5)


def test_failure_to_converge_raises():
    """One iteration is not enough from a bad start. It must not lie."""
    cfs = bond(30, 0.01).cashflows(ISSUE)
    with pytest.raises(ValueError, match="did not converge"):
        yield_from_price(cfs, 100.0, guess=5.0, max_iter=1)


# --- the derivative is the duration -----------------------------------------

def test_derivative_matches_a_finite_difference():
    """Analytic vs bumped. Step 8 turns this into the duration assertion."""
    for freq in (1, 2, 4):
        cfs = bond(10, 0.05, frequency=freq).cashflows(ISSUE)
        for y in (0.01, 0.04, 0.08):
            h = 1e-7
            bumped = (price(cfs, y + h, freq) - price(cfs, y - h, freq)) / (2 * h)
            assert price_derivative(cfs, y, freq) == pytest.approx(bumped, rel=1e-6)


def test_derivative_is_negative_and_bigger_for_longer_bonds():
    short = bond(2).cashflows(ISSUE)
    long = bond(30).cashflows(ISSUE)
    assert price_derivative(short, 0.04) < 0
    assert abs(price_derivative(long, 0.04)) > abs(price_derivative(short, 0.04))


# --- the accrued interest trap ----------------------------------------------

def semiannual_with_accrual() -> Bond:
    return Bond(face=100, coupon=0.05, issue_date=ISSUE,
                maturity_date=date(2031, 1, 1), frequency=2,
                daycount=act_365f)


def test_yield_from_clean_price_round_trips():
    b = semiannual_with_accrual()
    settle = date(2027, 4, 15)
    quoted = b.clean_price(settle, y=0.037)
    assert b.yield_from_clean_price(settle, quoted) == pytest.approx(0.037, abs=1e-10)


def test_feeding_the_clean_quote_raw_gives_the_wrong_yield():
    """The error is small, one-signed and real. Assert it, do not discover it."""
    b = semiannual_with_accrual()
    settle = date(2027, 4, 15)
    quoted = b.clean_price(settle, y=0.037)

    right = b.yield_from_clean_price(settle, quoted)
    wrong = yield_from_price(b.cashflows(settle), quoted, m=2)

    assert b.accrued_interest(settle) > 0
    assert wrong > right                      # too low a price, too high a yield
    assert wrong - right > 2e-4               # more than two basis points
