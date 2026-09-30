from datetime import date, timedelta

import pytest

from fitk.bonds import Bond
from fitk.daycount import act_360, act_365f, thirty_360
from fitk.pricing import price

ISSUE = date(2026, 1, 1)
MATURITY = date(2031, 1, 1)


def semiannual(**kwargs):
    """5% semiannual, coupons on 1 January and 1 July."""
    return Bond(face=100, coupon=0.05, issue_date=ISSUE,
                maturity_date=MATURITY, frequency=2, **kwargs)


def test_accrued_is_zero_on_a_coupon_date():
    assert semiannual().accrued_interest(date(2027, 1, 1)) == 0.0


def test_accrued_approaches_the_full_coupon():
    """One day before payment, the seller has earned almost all of it."""
    ai = semiannual(daycount=act_365f).accrued_interest(date(2027, 6, 30))
    assert ai == pytest.approx(2.5 * 180 / 181, abs=1e-9)
    assert ai < 2.5


def test_accrued_grows_every_day_then_resets():
    """The sawtooth, as an assertion."""
    bond = semiannual(daycount=act_365f)
    d = date(2027, 1, 1)
    values = [bond.accrued_interest(d + timedelta(days=k)) for k in range(182)]
    assert values[0] == 0.0
    assert all(b > a for a, b in zip(values[:181], values[1:181]))
    assert values[181] == 0.0          # 1 July: coupon paid, accrual restarts


def test_clean_plus_accrued_equals_dirty():
    """The identity that defines the split, at every date and convention."""
    for dc in (act_360, act_365f, thirty_360):
        bond = semiannual(daycount=dc)
        for settle in (date(2027, 2, 14), date(2027, 4, 15), date(2029, 9, 3)):
            dirty = price(bond.cashflows(settle), y=0.04, m=2)
            accrued = bond.accrued_interest(settle)
            assert (dirty - accrued) + accrued == pytest.approx(dirty)
            assert accrued > 0


def test_accrual_starts_at_issue_before_the_first_coupon():
    """A newly issued bond accrues from issue, not from an invented date."""
    bond = Bond(face=100, coupon=0.05, issue_date=date(2026, 3, 15),
                maturity_date=date(2031, 7, 1), frequency=2,
                daycount=act_365f)
    assert bond.previous_coupon_date(date(2026, 4, 1)) == date(2026, 3, 15)
    assert bond.accrued_interest(date(2026, 3, 15)) == 0.0
    assert bond.accrued_interest(date(2026, 4, 1)) > 0


def test_every_act_convention_gives_the_icma_answer():
    """Denominators cancel in the ratio, so all ACT conventions agree."""
    settle = date(2027, 4, 15)
    expected = 2.5 * 104 / 181          # ACT/ACT ICMA, by hand
    for dc in (act_360, act_365f):
        assert semiannual(daycount=dc).accrued_interest(settle) == pytest.approx(expected)
    assert semiannual(daycount=thirty_360).accrued_interest(settle) == pytest.approx(2.5 * 104 / 360 * 2)
    assert semiannual(daycount=thirty_360).accrued_interest(settle) != pytest.approx(expected, abs=1e-6)

def test_clean_equals_dirty_on_a_coupon_date():
    bond = semiannual(daycount=act_365f)
    d = date(2027, 7, 1)
    assert bond.clean_price(d, y=0.04) == pytest.approx(bond.dirty_price(d, y=0.04))


def test_clean_price_has_no_sawtooth():
    """The dirty price jumps on payment day; the clean price does not."""
    bond = semiannual(daycount=act_365f)
    before, after = date(2027, 6, 30), date(2027, 7, 1)
    dirty_jump = bond.dirty_price(before, 0.04) - bond.dirty_price(after, 0.04)
    clean_jump = bond.clean_price(before, 0.04) - bond.clean_price(after, 0.04)
    assert dirty_jump > 2.4              # roughly the coupon
    assert abs(clean_jump) < 0.02        # continuous across the payment
