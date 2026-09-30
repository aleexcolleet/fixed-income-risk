from datetime import date

import pytest

from fitk.bonds import Bond
from fitk.cashflows import Cashflow
from fitk.pricing import price
from fitk.risk import (convexity, convexity_bumped, dollar_duration, dv01,
                       macaulay_duration, modified_duration,
                       modified_duration_bumped, price_change_estimate)

ISSUE = date(2026, 1, 1)


def bond(years: int, coupon: float = 0.05, **kwargs) -> Bond:
    return Bond(face=100, coupon=coupon, issue_date=ISSUE,
                maturity_date=date(2026 + years, 1, 1), **kwargs)


def flows(years: int, coupon: float = 0.05, **kwargs) -> list[Cashflow]:
    return bond(years, coupon, **kwargs).cashflows(ISSUE)


GRID = [(years, freq, coupon, y)
        for years in (1, 2, 5, 10, 30)
        for freq in (1, 2, 4)
        for coupon in (0.0, 0.03, 0.07)
        for y in (0.005, 0.02, 0.05, 0.10)]


# --- the assertion the whole sprint exists for ------------------------------

def test_analytic_and_bumped_duration_agree():
    """The independent-implementation check. 180 cases.

    An analytic duration that forgot the (1+y/m) divisor passes every
    sanity test and fails only this one.

    Tolerance 1e-7, and worst observed across the grid is 1.6e-8 (a 30-year
    zero at 50bp, where the derivative is largest and the cancellation in the
    central difference worst). The convention error this test exists to catch
    is 2-4% — six orders of magnitude above the noise floor, so the tolerance
    is loose enough to be stable and tight enough to be worth running.
    """
    for years, freq, coupon, y in GRID:
        cfs = flows(years, coupon, frequency=freq)
        assert modified_duration(cfs, y, freq) == pytest.approx(
            modified_duration_bumped(cfs, y, freq), rel=1e-7)


def test_analytic_and_bumped_convexity_agree():
    """Looser tolerance, and the reason is numerical, not a defect.

    A second central difference divides a near-cancelling sum by bump^2, so
    rounding noise enters at 1/bump^2. Worst observed is 8.7e-7 relative,
    against 1.6e-8 for duration: two orders of magnitude worse for the same
    data, which is the price of the second derivative.
    """
    for years, freq, coupon, y in GRID:
        cfs = flows(years, coupon, frequency=freq)
        assert convexity(cfs, y, freq) == pytest.approx(
            convexity_bumped(cfs, y, freq), rel=1e-5)


# --- the two analytic routes to modified duration must meet -----------------

def test_modified_is_macaulay_over_one_plus_y_over_m():
    """This is the compounding-convention divisor, pinned down."""
    for years, freq, coupon, y in GRID:
        cfs = flows(years, coupon, frequency=freq)
        assert modified_duration(cfs, y, freq) == pytest.approx(
            macaulay_duration(cfs, y, freq) / (1 + y / freq))


def test_continuous_and_discrete_duration_differ_by_the_known_factor():
    """The trap, quantified: mixing conventions costs y/m in relative terms."""
    cfs = flows(10, 0.05, frequency=2)
    y = 0.08
    relative_error = macaulay_duration(cfs, y, 2) / modified_duration(cfs, y, 2) - 1
    assert relative_error == pytest.approx(0.04)          # y/m = 8%/2
    assert relative_error > 0.03                          # 3-4%, silent, real


# --- closed forms for a zero coupon bond ------------------------------------

def test_zero_coupon_duration_equals_maturity():
    """A single payment is its own weighted average time. Any yield, any m."""
    cfs = [Cashflow(t=7.0, amount=100.0)]
    for m in (1, 2, 4):
        for y in (0.01, 0.06):
            assert macaulay_duration(cfs, y, m) == pytest.approx(7.0)
            assert modified_duration(cfs, y, m) == pytest.approx(7.0 / (1 + y / m))
            assert convexity(cfs, y, m) == pytest.approx(
                7.0 * (7.0 + 1 / m) / (1 + y / m) ** 2)


def test_coupon_bond_duration_is_below_its_maturity():
    """Strictly below, because some money arrives early. Equality only at
    zero coupon, which is the previous test."""
    for years in (2, 5, 10, 30):
        for coupon in (0.02, 0.05, 0.09):
            d = macaulay_duration(flows(years, coupon), 0.04)
            assert 0 < d < years
    assert macaulay_duration(flows(10, 0.0), 0.04) == pytest.approx(10.0)


# --- comparative statics: the direction each input moves duration ----------

def test_duration_falls_as_the_coupon_rises():
    """More money early pulls the average payment time in."""
    ds = [macaulay_duration(flows(20, c), 0.04)
          for c in (0.0, 0.02, 0.04, 0.06, 0.10)]
    assert ds == sorted(ds, reverse=True)


def test_duration_rises_with_maturity():
    ds = [macaulay_duration(flows(n), 0.04) for n in (1, 2, 5, 10, 20, 30)]
    assert ds == sorted(ds)


def test_duration_falls_as_the_yield_rises():
    """A higher yield discounts the distant cashflows harder, so their
    weight in the average falls."""
    ds = [modified_duration(flows(30), y) for y in (0.01, 0.03, 0.06, 0.10)]
    assert ds == sorted(ds, reverse=True)


def test_convexity_is_positive_and_grows_with_maturity():
    cs = [convexity(flows(n), 0.04) for n in (1, 5, 10, 30)]
    assert all(c > 0 for c in cs)
    assert cs == sorted(cs)


# --- units: the factor of 10,000 -------------------------------------------

def test_dv01_is_dollar_duration_over_ten_thousand():
    for years, freq, coupon, y in GRID:
        cfs = flows(years, coupon, frequency=freq)
        assert dv01(cfs, y, freq) == pytest.approx(
            dollar_duration(cfs, y, freq) / 10_000)


def test_dv01_approximates_the_price_move_for_one_basis_point():
    """What DV01 means, checked by actually repricing one basis point away.

    It does not match exactly, and the residual is not error — it is
    convexity. DV01 is the tangent; the reprice follows the curve. The gap
    grows with duration: 1.2e-4 relative at 2 years, 1.2e-3 at 30. So the
    second assertion is the real one: put the curvature term back and the
    residual falls by five orders of magnitude, from 1.2e-3 to 1.2e-8 at 2
    years and from 1.2e-3 to 1.1e-6 at 30. What is left still scales with
    maturity, because it is the third derivative, not arithmetic noise.
    """
    for years in (2, 10, 30):
        cfs = flows(years, frequency=2)
        y, bp = 0.04, 0.0001
        actual = price(cfs, y + bp, 2) - price(cfs, y, 2)

        assert -dv01(cfs, y, 2) == pytest.approx(actual, rel=2e-3)
        assert price_change_estimate(cfs, y, bp, 2) == pytest.approx(
            actual, rel=1e-5)


def test_dollar_duration_adds_but_modified_duration_does_not():
    """Why a risk report is in DV01 and a fund fact sheet is in duration.

    Dollar duration is currency, so it sums. Modified duration is a ratio, so
    the portfolio's is the value-weighted average — never the plain average,
    and the plain average is wrong by enough to matter.
    """
    y = 0.04
    short, long = flows(2, 0.05), flows(30, 0.05)
    book = short + long

    assert dollar_duration(book, y) == pytest.approx(
        dollar_duration(short, y) + dollar_duration(long, y))

    b_short, b_long = price(short, y), price(long, y)
    weighted = (modified_duration(short, y) * b_short
                + modified_duration(long, y) * b_long) / (b_short + b_long)
    assert modified_duration(book, y) == pytest.approx(weighted)

    plain = (modified_duration(short, y) + modified_duration(long, y)) / 2
    assert modified_duration(book, y) != pytest.approx(plain, rel=1e-3)


# --- where duration alone stops working ------------------------------------

def test_second_order_beats_first_order_on_a_large_move():
    """A 30-year bond, measured at three sizes of move.

        move    actual    duration only      + convexity
         50bp   -8.19     -8.69  (0.50)      -8.16  (0.02)
        100bp  -15.45    -17.38  (1.93)     -15.28  (0.18)
        200bp  -27.68    -34.76  (7.09)     -26.34  (1.33)

    Two things to read off it. Duration alone is useless for a stress
    scenario: at 200bp it overstates the loss by 7 points of price, 26%.
    And convexity does not rescue it either — 1.33 points of residual is
    still real money, because the third derivative is now in play. This is
    why a market risk unit reprices its book for a stress test instead of
    extrapolating from sensitivities, and only uses DV01 for small moves.
    """
    cfs = flows(30, 0.04, frequency=2)
    y = 0.04
    for dy, first_floor, second_cap in ((0.005, 0.4, 0.05),
                                        (0.01, 1.5, 0.3),
                                        (0.02, 6.0, 1.5)):
        actual = price(cfs, y + dy, 2) - price(cfs, y, 2)
        first = price_change_estimate(cfs, y, dy, 2, second_order=False)
        second = price_change_estimate(cfs, y, dy, 2, second_order=True)

        assert abs(first - actual) > first_floor
        assert abs(second - actual) < second_cap
        assert abs(second - actual) < abs(first - actual) / 4


def test_first_order_always_overstates_the_loss_and_understates_the_gain():
    """Positive convexity, stated as an inequality on both sides."""
    cfs = flows(20, 0.03, frequency=2)
    y = 0.05
    for dy in (0.01, 0.02, 0.03):
        rise = price(cfs, y + dy, 2) - price(cfs, y, 2)
        fall = price(cfs, y - dy, 2) - price(cfs, y, 2)
        linear_rise = price_change_estimate(cfs, y, dy, 2, second_order=False)
        linear_fall = price_change_estimate(cfs, y, -dy, 2, second_order=False)
        assert rise > linear_rise      # loses less than the line says
        assert fall > linear_fall      # gains more than the line says


# --- the Bond convenience layer --------------------------------------------

def test_bond_methods_match_the_engine():
    b = bond(10, 0.05, frequency=2)
    cfs = b.cashflows(ISSUE)
    assert b.modified_duration(ISSUE, 0.04) == pytest.approx(
        modified_duration(cfs, 0.04, 2))
    assert b.convexity(ISSUE, 0.04) == pytest.approx(convexity(cfs, 0.04, 2))
    assert b.dv01(ISSUE, 0.04) == pytest.approx(dv01(cfs, 0.04, 2))


def test_dv01_scales_linearly_with_face():
    """A 10m position has 100,000 times the DV01 of a 100-face bond."""
    small = Bond(face=100, coupon=0.05, issue_date=ISSUE,
                 maturity_date=date(2036, 1, 1), frequency=2)
    big = Bond(face=10_000_000, coupon=0.05, issue_date=ISSUE,
               maturity_date=date(2036, 1, 1), frequency=2)
    assert big.dv01(ISSUE, 0.04) == pytest.approx(
        small.dv01(ISSUE, 0.04) * 100_000)
