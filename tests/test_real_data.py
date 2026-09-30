"""
The model against the market.

Everything else in this suite checks the code against itself: identities,
round trips, two implementations of the same formula. These tests check it
against numbers somebody else published and cannot retract -- the Spanish
Treasury's own yields in the BOE, and the ECB's own curve.

That is a different kind of test. A property test proves the code is
self-consistent. Only real data proves it is right.
"""

from datetime import date
from pathlib import Path

import pytest

from fitk.bonds import Bond
from fitk.curve import Curve, implied_flat_spread
from fitk.daycount import act_360, act_365f, thirty_360

DATA = Path(__file__).resolve().parent.parent / "data"

# Auction held 17 September 2026, settled 22 September 2026. BOE-A-2026-20253.
SETTLEMENT = date(2026, 9, 22)

# name, coupon, maturity, clean price, accrued as the BOE prints it,
# the Treasury's own yield, and the date accrual starts from.
TESORO = [
    ("0.70% 30/04/2032", 0.0070, date(2032, 4, 30), 85.704, 0.28, 0.03558,
     date(2022, 4, 30)),
    ("3.45% 31/10/2034", 0.0345, date(2034, 10, 31), 97.618, 3.08, 0.03796,
     date(2024, 10, 31)),
    ("3.40% 31/10/2036", 0.0340, date(2036, 10, 31), 95.415, 1.03, 0.03960,
     date(2026, 6, 3)),
]


def bono(coupon, maturity, accrual_start, daycount=act_365f) -> Bond:
    """A Spanish Obligacion del Estado: annual coupons, actual day counts."""
    return Bond(face=100.0, coupon=coupon, issue_date=accrual_start,
                maturity_date=maturity, frequency=1, daycount=daycount)


# --- against the Treasury's published accrued interest ---------------------

def test_accrued_matches_the_boe_to_the_printed_precision():
    """The BOE prints accrued to two decimals. Match all three, which also
    confirms the settlement date of 22 September -- that date is not in the
    resolution, it is recovered from these figures."""
    for name, coupon, maturity, _, accrued_boe, _, start in TESORO:
        ours = bono(coupon, maturity, start).accrued_interest(SETTLEMENT)
        assert round(ours, 2) == accrued_boe, name


def test_the_short_first_coupon_is_what_makes_the_2036_work():
    """The 2036 was issued in June and pays in October: 150 days of a
    365-day period, so its first coupon is 1.397, not 3.40."""
    b = bono(0.0340, date(2036, 10, 31), date(2026, 6, 3))
    first = b.next_coupon_date(SETTLEMENT)
    assert first == date(2026, 10, 31)
    assert b.coupon_amount(first) == pytest.approx(1.3973, abs=1e-4)
    assert b.coupon_amount(date(2027, 10, 31)) == pytest.approx(3.40)


def test_a_seasoned_bond_pays_full_coupons_throughout():
    b = bono(0.0345, date(2034, 10, 31), date(2024, 10, 31))
    for d in b.payment_dates():
        assert b.coupon_amount(d) == pytest.approx(3.45)


# --- against the Treasury's published yield --------------------------------

def test_street_yield_reproduces_the_treasury_figure():
    """Within 0.1bp of a number published in the Boletin Oficial del Estado.

    The Treasury rounds to three decimals of a percent, i.e. to 0.1bp, so
    0.1bp is the tightest this test can meaningfully be.
    """
    for name, coupon, maturity, clean, _, official, start in TESORO:
        ours = bono(coupon, maturity, start).street_yield(SETTLEMENT, clean)
        assert abs(ours - official) < 1.0e-5, (name, ours, official)


def test_measuring_time_in_years_instead_of_periods_costs_a_third_of_a_bp():
    """yield_from_clean_price is close but not equal, always on one side.

    The ICMA measure ignores that real years differ in length; a day count
    does not. On these three bonds the gap is 0.2 to 0.4bp, and the day
    count answer is always the lower one.
    """
    for name, coupon, maturity, clean, _, official, start in TESORO:
        b = bono(coupon, maturity, start)
        street = b.street_yield(SETTLEMENT, clean)
        by_years = b.yield_from_clean_price(SETTLEMENT, clean)
        gap_bp = abs(street - by_years) * 1e4
        assert 0.1 < gap_bp < 0.6, (name, gap_bp)
        assert by_years < street, name


def test_the_wrong_day_count_costs_five_basis_points():
    """ACT/360 on a bond whose prospectus says ACT/ACT.

    Five basis points is not a rounding difference. On the 3.45% of 2034 it
    is about 0.04 points of price, which is 40,000 euros per 100 million of
    nominal -- and the auction placed 1.7 billion.
    """
    name, coupon, maturity, clean, _, official, start = TESORO[1]
    wrong = bono(coupon, maturity, start, daycount=act_360)
    error_bp = abs(wrong.yield_from_clean_price(SETTLEMENT, clean) - official) * 1e4
    assert error_bp > 4.0


def test_thirty_360_happens_to_be_close_and_that_is_luck():
    """30/360 lands within 0.2bp here, which does not make it right.

    These bonds mature on the 30th and 31st, so 30/360 and ACT/ACT nearly
    agree by coincidence of the calendar. A bond maturing on the 1st would
    separate them. Never conclude a convention is correct from one bond.
    """
    name, coupon, maturity, clean, _, official, start = TESORO[1]
    b = bono(coupon, maturity, start, daycount=thirty_360)
    assert abs(b.yield_from_clean_price(SETTLEMENT, clean) - official) * 1e4 < 0.3


# --- against the ECB curve -------------------------------------------------

@pytest.fixture(scope="module")
def ecb() -> Curve:
    return Curve.from_csv(DATA / "ecb_aaa_spot_2026-09-22.csv")


def test_the_curve_file_loads_as_published(ecb):
    assert ecb.tenors[0] == 0.25
    assert ecb.tenors[-1] == 30.0
    assert ecb.zero_rate(10.0) == pytest.approx(0.0345274)
    assert ecb.zero_rate(2.0) == pytest.approx(0.0313556, abs=1e-7)


def test_the_curve_is_upward_sloping_then_inverts_at_the_long_end(ecb):
    """Real curves are not textbook shapes. This one peaks at 25 years and
    falls into 30 -- pension and insurance demand at the very long end, and
    a reminder that a model assuming monotonicity would be wrong on the day
    it was fitted."""
    short = [ecb.zero_rate(t) for t in (0.25, 1, 2, 5, 10, 20)]
    assert short == sorted(short)
    assert ecb.zero_rate(30.0) < ecb.zero_rate(25.0)


def test_the_aaa_curve_overvalues_every_spanish_bond(ecb):
    """Spain is not AAA, so discounting it at AAA rates prices it too high.

    The sign is the test. A model that priced a Spanish bond *below* the
    market off a AAA curve would be broken, not interesting.
    """
    for name, coupon, maturity, clean, _, _, start in TESORO:
        b = bono(coupon, maturity, start)
        model_dirty = ecb.present_value(b.cashflows(SETTLEMENT))
        model_clean = model_dirty - b.accrued_interest(SETTLEMENT)
        assert model_clean > clean, name


def test_the_implied_spread_is_positive_and_rises_with_maturity(ecb):
    """The sovereign spread has a term structure, which is why one number
    per bond is a summary and not a model."""
    spreads = []
    for name, coupon, maturity, clean, _, _, start in TESORO:
        b = bono(coupon, maturity, start)
        cfs = b.cashflows(SETTLEMENT)
        target = clean + b.accrued_interest(SETTLEMENT)
        spreads.append(implied_flat_spread(ecb, cfs, target))

    assert all(s > 0 for s in spreads)
    assert spreads == sorted(spreads)
    assert 0.0015 < spreads[0] < 0.0035      # 5.6 years: 25.5bp
    assert 0.0030 < spreads[1] < 0.0048      # 8.1 years: 38.2bp
    assert 0.0035 < spreads[-1] < 0.0060     # 10.1 years: 44.9bp


def test_the_implied_spread_reprices_the_bond_exactly(ecb):
    """Closing the loop: shift the curve by the solved spread and the model
    price is the market price. If this fails the spread means nothing."""
    for name, coupon, maturity, clean, _, _, start in TESORO:
        b = bono(coupon, maturity, start)
        cfs = b.cashflows(SETTLEMENT)
        target = clean + b.accrued_interest(SETTLEMENT)
        spread = implied_flat_spread(ecb, cfs, target)
        assert ecb.shifted(spread).present_value(cfs) == pytest.approx(
            target, abs=1e-8), name


def test_using_the_wrong_days_curve_moves_the_spread_by_more_than_it_is(ecb):
    """Why the data files are named by date.

    The ECB ten-year went from 3.4527% on 22 September to 3.6077% on the
    29th -- 15bp in five business days. Pricing the 22 September auction off
    the 29 September curve moves the implied spread one-for-one with that,
    so the five-year spread of 25.5bp would have come out at 10.5bp: not a
    small error, a different conclusion.
    """
    name, coupon, maturity, clean, _, _, start = TESORO[0]
    b = bono(coupon, maturity, start)
    cfs = b.cashflows(SETTLEMENT)
    target = clean + b.accrued_interest(SETTLEMENT)

    right = implied_flat_spread(ecb, cfs, target)
    stale = implied_flat_spread(ecb.shifted(0.0015), cfs, target)

    assert right - stale == pytest.approx(0.0015, abs=1e-9)
    assert (right - stale) / right > 0.5
