from datetime import date

import pytest

from fitk.bonds import Bond
from fitk.daycount import act_365f
from fitk.pricing import price, discount_factor, effective_annual_rate
from fitk.schedule import add_months

VAL = date(2026, 1, 1)


def three_year_5pc(**kwargs):
    """The reference bond: 3 years, 5% annual coupon, face 100."""
    return Bond(face=100, coupon=0.05, issue_date=VAL,
                maturity_date=date(2029, 1, 1), **kwargs)


# --- regression: the sprint 1 number must survive calendar dates -------------

def test_reference_value_survives_calendar_dates():
    """30/360 makes every year exactly 1.0, so the original number holds."""
    cfs = three_year_5pc().cashflows(VAL)
    assert [cf.t for cf in cfs] == [1.0, 2.0, 3.0]
    assert price(cfs, y=0.04) == pytest.approx(102.775091, abs=1e-6)


def test_last_cashflow_includes_redemption():
    cfs = three_year_5pc().cashflows(VAL)
    assert [cf.amount for cf in cfs] == [5.0, 5.0, 105.0]


def test_price_falls_as_yield_rises():
    cfs = Bond(face=100, coupon=0.05, issue_date=VAL,
               maturity_date=date(2036, 1, 1)).cashflows(VAL)
    prices = [price(cfs, y) for y in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08)]
    assert prices == sorted(prices, reverse=True)


def test_par_identity():
    """Coupon == yield => price == face. Exact under 30/360."""
    for n in range(1, 31):
        for rate in (0.01, 0.04, 0.09):
            bond = Bond(face=100, coupon=rate, issue_date=VAL,
                        maturity_date=date(2026 + n, 1, 1))
            assert price(bond.cashflows(VAL), y=rate) == pytest.approx(100.0)


def test_par_identity_holds_for_any_frequency():
    for freq in (1, 2, 4, 12):
        for rate in (0.01, 0.04, 0.09):
            for n in (1, 5, 30):
                bond = Bond(face=100, coupon=rate, issue_date=VAL,
                            maturity_date=date(2026 + n, 1, 1), frequency=freq)
                assert price(bond.cashflows(VAL), y=rate, m=freq) == pytest.approx(100.0)


def test_semiannual_cashflow_schedule():
    cfs = three_year_5pc(frequency=2).cashflows(VAL)
    assert [cf.t for cf in cfs] == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    assert [cf.amount for cf in cfs] == [2.5, 2.5, 2.5, 2.5, 2.5, 102.5]


def test_compounding_conventions_are_equivalent():
    ear = effective_annual_rate(0.04, 2)
    assert ear == pytest.approx(0.0404, abs=1e-12)
    assert discount_factor(0.04, 1.0, m=2) == pytest.approx(discount_factor(ear, 1.0, m=1))


# --- the calendar itself ----------------------------------------------------

def test_add_months_clamps_to_month_length():
    assert add_months(date(2026, 8, 31), -6) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert add_months(date(2024, 8, 31), -6) == date(2024, 2, 29)  # leap year


def test_schedule_runs_backwards_from_maturity():
    """Issue 15 Mar 2024, mature 30 Jun 2029, semiannual: short first period."""
    bond = Bond(face=100, coupon=0.05, issue_date=date(2024, 3, 15),
                maturity_date=date(2029, 6, 30), frequency=2)
    dates = bond.payment_dates()
    assert len(dates) == 11
    assert dates[0] == date(2024, 6, 30)    # not 15 Sep 2024
    assert dates[-1] == date(2029, 6, 30)   # maturity is always a payment date


def test_month_end_convention():
    """Maturing on a month end drags every coupon to month end."""
    bond = Bond(face=100, coupon=0.05, issue_date=date(2026, 11, 30),
                maturity_date=date(2029, 11, 30), frequency=2)
    assert bond.payment_dates()[0] == date(2027, 5, 31)   # 31st, not 30th


def test_schedule_does_not_drift():
    """Anchoring on maturity, not on the previous date, prevents day drift."""
    bond = Bond(face=100, coupon=0.05, issue_date=date(2024, 8, 31),
                maturity_date=date(2027, 8, 31), frequency=2)
    assert {d.day for d in bond.payment_dates()} <= {28, 29, 31}


def test_past_coupons_are_dropped():
    bond = Bond(face=100, coupon=0.05, issue_date=date(2024, 1, 1),
                maturity_date=date(2029, 1, 1))
    assert len(bond.cashflows(date(2026, 6, 1))) == 3   # 2027, 2028, 2029


# --- the day count convention is part of the contract -----------------------

def test_day_count_convention_changes_the_price():
    """Same contract, different conventions, different price. Not a bug.

    30/360 forces every year to 1.0. ACT/365F counts real days, so 2028 being
    a leap year makes that period 366/365 and the price moves.
    """
    thirty = three_year_5pc()
    actual = three_year_5pc(daycount=act_365f)

    assert [cf.t for cf in thirty.cashflows(VAL)] == [1.0, 2.0, 3.0]
    assert [cf.t for cf in actual.cashflows(VAL)] != [1.0, 2.0, 3.0]

    p_thirty = price(thirty.cashflows(VAL), y=0.04)
    p_actual = price(actual.cashflows(VAL), y=0.04)
    assert p_thirty != pytest.approx(p_actual, abs=1e-9)
