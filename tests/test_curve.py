from math import exp, log

import pytest

from fitk.cashflows import Cashflow
from fitk.curve import (Curve, implied_flat_spread, to_compounded,
                        to_continuous)

FLAT = Curve(tenors=(1.0, 30.0), rates=(0.03, 0.03))
SLOPED = Curve(tenors=(1.0, 2.0, 5.0, 10.0),
               rates=(0.020, 0.025, 0.030, 0.035))


# --- construction refuses nonsense -----------------------------------------

def test_mismatched_lengths_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        Curve(tenors=(1.0, 2.0), rates=(0.03,))


def test_unsorted_tenors_are_rejected():
    """A silently unsorted curve interpolates to garbage. Fail loudly."""
    with pytest.raises(ValueError, match="ascending"):
        Curve(tenors=(5.0, 1.0), rates=(0.03, 0.02))


def test_a_single_point_is_not_a_curve():
    with pytest.raises(ValueError, match="at least two"):
        Curve(tenors=(1.0,), rates=(0.03,))


# --- interpolation ----------------------------------------------------------

def test_rate_is_exact_at_every_node():
    """Interpolation must not move the data it was given."""
    for t, r in zip(SLOPED.tenors, SLOPED.rates):
        assert SLOPED.zero_rate(t) == pytest.approx(r)


def test_interpolation_is_linear_between_nodes():
    assert SLOPED.zero_rate(1.5) == pytest.approx(0.0225)
    assert SLOPED.zero_rate(3.5) == pytest.approx(0.030 - 0.005 * 1.5 / 3)
    assert SLOPED.zero_rate(7.5) == pytest.approx(0.0325)


def test_extrapolation_is_flat_at_both_ends():
    assert SLOPED.zero_rate(0.01) == pytest.approx(0.020)
    assert SLOPED.zero_rate(0.0) == pytest.approx(0.020)
    assert SLOPED.zero_rate(50.0) == pytest.approx(0.035)


def test_rate_is_monotone_on_a_monotone_curve():
    ts = [i / 4 for i in range(1, 200)]
    rs = [SLOPED.zero_rate(t) for t in ts]
    assert rs == sorted(rs)


# --- discounting ------------------------------------------------------------

def test_discount_factor_is_one_at_zero_and_falls_thereafter():
    assert FLAT.discount_factor(0.0) == pytest.approx(1.0)
    dfs = [FLAT.discount_factor(t) for t in (0.5, 1, 5, 10, 30)]
    assert dfs == sorted(dfs, reverse=True)
    assert all(0 < df < 1 for df in dfs)


def test_discount_factor_is_continuously_compounded():
    """Not (1+r)^-t. The difference is the whole reason this module exists."""
    assert FLAT.discount_factor(10.0) == pytest.approx(exp(-0.03 * 10))
    assert FLAT.discount_factor(10.0) != pytest.approx((1.03) ** -10)


def test_present_value_uses_each_cashflow_own_rate():
    cfs = [Cashflow(t=1.0, amount=100.0), Cashflow(t=10.0, amount=100.0)]
    expected = (100 * exp(-0.020 * 1.0) + 100 * exp(-0.035 * 10.0))
    assert SLOPED.present_value(cfs) == pytest.approx(expected)


def test_a_flat_curve_agrees_with_a_single_yield():
    """Sanity bridge between the two discounting worlds.

    A flat continuous curve at r discounts exactly like a single yield of
    exp(r)-1 compounded annually. If this fails, one of the two is wrong.
    """
    from fitk.pricing import price
    cfs = [Cashflow(t=float(k), amount=5.0) for k in range(1, 11)]
    cfs[-1] = Cashflow(t=10.0, amount=105.0)
    annual = to_compounded(0.03, 1)
    assert FLAT.present_value(cfs) == pytest.approx(price(cfs, annual, m=1))


# --- compounding conversion -------------------------------------------------

def test_conversions_are_inverses():
    for m in (1, 2, 4, 12):
        for r in (0.001, 0.02, 0.05, 0.10):
            assert to_compounded(to_continuous(r, m), m) == pytest.approx(r)
            assert to_continuous(to_compounded(r, m), m) == pytest.approx(r)


def test_continuous_is_below_the_compounded_equivalent():
    """Continuous compounding works harder, so it needs a lower rate."""
    for m in (1, 2, 12):
        assert to_continuous(0.05, m) < 0.05
        assert to_continuous(0.05, m) == pytest.approx(m * log(1 + 0.05 / m))


def test_the_ecb_ten_year_translated_to_annual_compounding():
    """3.45274% continuous is 3.51304% annually compounded.

    Six basis points, on the actual published ECB ten-year of 22 September
    2026. Treat the file's number as an annually compounded rate and every
    discount factor is wrong in the same direction.
    """
    annual = to_compounded(0.0345274, 1)
    assert annual == pytest.approx(0.0351304, abs=1e-7)
    assert (annual - 0.0345274) * 1e4 == pytest.approx(6.03, abs=0.01)


# --- shifting and the implied spread ---------------------------------------

def test_shifting_moves_every_tenor_and_lowers_the_value():
    up = SLOPED.shifted(0.0050)
    assert all(up.zero_rate(t) == pytest.approx(SLOPED.zero_rate(t) + 0.005)
               for t in (0.5, 1, 3, 7, 20))
    cfs = [Cashflow(t=10.0, amount=100.0)]
    assert up.present_value(cfs) < SLOPED.present_value(cfs)


def test_implied_spread_round_trips():
    cfs = [Cashflow(t=float(k), amount=3.0) for k in range(1, 9)]
    cfs[-1] = Cashflow(t=8.0, amount=103.0)
    for spread in (-0.002, 0.0, 0.0035, 0.015):
        target = SLOPED.shifted(spread).present_value(cfs)
        assert implied_flat_spread(SLOPED, cfs, target) == pytest.approx(
            spread, abs=1e-9)


def test_implied_spread_rejects_an_unreachable_target():
    cfs = [Cashflow(t=5.0, amount=100.0)]
    with pytest.raises(ValueError, match="bracket"):
        implied_flat_spread(SLOPED, cfs, 200.0)
    with pytest.raises(ValueError, match="bracket"):
        implied_flat_spread(SLOPED, cfs, 1.0)
