from datetime import date

import pytest

from fitk.daycount import act_360, act_365f, thirty_360


def test_known_values_six_months():
    """15 Jan to 15 Jul 2026: 181 actual days, 180 thirty-360 days."""
    d1, d2 = date(2026, 1, 15), date(2026, 7, 15)
    assert act_360(d1, d2) == pytest.approx(181 / 360)
    assert act_365f(d1, d2) == pytest.approx(181 / 365)
    assert thirty_360(d1, d2) == pytest.approx(0.5)


def test_thirty_360_end_of_month_rules():
    """Where the adjustments bite. Values are in 30/360 days."""
    cases = [
        (date(2026, 1, 31), date(2026, 2, 28), 28),  # d1 31->30, d2 untouched
        (date(2026, 1, 31), date(2026, 3, 31), 60),  # both pulled back to 30
        (date(2026, 4, 30), date(2026, 5, 31), 30),  # d1 already 30, d2 ->30
        (date(2026, 2, 28), date(2026, 3, 31), 33),  # d1 != 30, so d2 stays 31
    ]
    for d1, d2, expected_days in cases:
        assert thirty_360(d1, d2) == pytest.approx(expected_days / 360)


def test_leap_year_exceeds_one_under_act_365f():
    """2024 had 366 days. ACT/365F returning >1 is correct, not a bug."""
    d1, d2 = date(2024, 1, 1), date(2025, 1, 1)
    assert act_365f(d1, d2) == pytest.approx(366 / 365)
    assert act_365f(d1, d2) > 1.0
    assert thirty_360(d1, d2) == pytest.approx(1.0)


def test_act_conventions_are_additive():
    """Constant denominator => splitting a period cannot change its length."""
    d1, d2, d3 = date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)
    for f in (act_360, act_365f):
        assert f(d1, d3) == pytest.approx(f(d1, d2) + f(d2, d3))


def test_thirty_360_is_not_additive():
    """Documented, not a defect: end-of-month adjustments break additivity.

    31 Jan -> 31 Mar is 60 days, but going via 28 Feb gives 28 + 33 = 61.
    """
    d1, d2, d3 = date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)
    assert thirty_360(d1, d3) * 360 == pytest.approx(60)
    assert (thirty_360(d1, d2) + thirty_360(d2, d3)) * 360 == pytest.approx(61)


def test_reversed_dates_are_negative():
    d1, d2 = date(2026, 1, 15), date(2026, 7, 15)
    for f in (act_360, act_365f, thirty_360):
        assert f(d2, d1) == pytest.approx(-f(d1, d2))