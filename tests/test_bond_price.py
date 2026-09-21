import pytest

from fitk.bonds import Bond
from fitk.pricing import price


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