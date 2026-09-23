import pytest

from fitk.bonds import Bond
from fitk.pricing import price, discount_factor, effective_annual_rate



def test_reference_value():
    bond = Bond(face=100, coupon=0.05, maturity=3)
    assert price(bond.cashflows(), y=0.04) == pytest.approx(102.775091, abs=1e-6)


def test_par_identity():
    for n in range(1, 31):
        for rate in (0.01, 0.04, 0.09):
            bond = Bond(face=100, coupon=rate, maturity=n)
            assert price(bond.cashflows(), y=rate) == pytest.approx(100.0)


def test_price_falls_as_yield_rises():
    cfs = Bond(face=100, coupon=0.05, maturity=10).cashflows()
    yields = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08]
    prices = [price(cfs, y) for y in yields]
    assert prices == sorted(prices, reverse=True)


def test_last_cashflow_includes_redemption():
    cfs = Bond(face=100, coupon=0.05, maturity=3).cashflows()
    assert [cf.amount for cf in cfs] == [5.0, 5.0, 105.0]

def test_annual_is_unchanged_by_frequency_default():
    """Regression: frequency=1 must reproduce sprint 1 exactly."""
    bond = Bond(face=100, coupon=0.05, maturity=3)
    assert price(bond.cashflows(), y=0.04) == pytest.approx(102.775091, abs=1e-6)

def test_semiannual_cashflow_schedule():
    cfs = Bond(face=100, coupon=0.05, maturity=3, frequency=2).cashflows()
    assert [cf.t for cf in cfs] == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    assert [cf.amount for cf in cfs] == [2.5, 2.5, 2.5, 2.5, 2.5, 102.5]


def test_par_identity_holds_for_any_frequency():
    """Coupon == yield => price == face, whatever the frequency."""
    for freq in (1, 2, 4, 12):
        for rate in (0.01, 0.04, 0.09):
            for n in (1, 5, 30):
                bond = Bond(face=100, coupon=rate, maturity=n, frequency=freq)
                assert price(bond.cashflows(), y=rate, m=freq) == pytest.approx(100.0)


def test_compounding_conventions_are_equivalent():
    """4% semiannual and its effective annual rate must discount identically."""
    ear = effective_annual_rate(0.04, 2)
    assert ear == pytest.approx(0.0404, abs=1e-12)
    assert discount_factor(0.04, 1.0, m=2) == pytest.approx(discount_factor(ear, 1.0, m=1))
