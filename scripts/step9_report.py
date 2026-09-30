"""
Reproduce every number in docs/step9-real-data.md.

Run from the repository root:

    python3 scripts/step9_report.py

The note is written prose; this is where its figures come from. If the two
ever disagree, the script is right and the note is stale.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitk.bonds import Bond                                    # noqa: E402
from fitk.curve import (Curve, implied_flat_spread,            # noqa: E402
                        to_compounded)
from fitk.daycount import act_360, act_365f, thirty_360        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SETTLEMENT = date(2026, 9, 22)

TESORO = [
    ("0.70% 30/04/2032", 0.0070, date(2032, 4, 30), 85.704, 0.28, 0.03558,
     date(2022, 4, 30)),
    ("3.45% 31/10/2034", 0.0345, date(2034, 10, 31), 97.618, 3.08, 0.03796,
     date(2024, 10, 31)),
    ("3.40% 31/10/2036", 0.0340, date(2036, 10, 31), 95.415, 1.03, 0.03960,
     date(2026, 6, 3)),
]


def bono(coupon, maturity, accrual_start, daycount=act_365f) -> Bond:
    return Bond(face=100.0, coupon=coupon, issue_date=accrual_start,
                maturity_date=maturity, frequency=1, daycount=daycount)


def yields_table() -> None:
    print("Yield against the Treasury's published figure")
    print(f"{'bond':18s} {'accrued':>8s} {'street':>8s} {'BOE':>7s} "
          f"{'err bp':>7s} {'by years':>9s} {'err bp':>7s} "
          f"{'ACT/360':>8s} {'err bp':>7s}")
    for name, coupon, maturity, clean, _, official, start in TESORO:
        b = bono(coupon, maturity, start)
        street = b.street_yield(SETTLEMENT, clean)
        by_years = b.yield_from_clean_price(SETTLEMENT, clean)
        wrong = bono(coupon, maturity, start,
                     act_360).yield_from_clean_price(SETTLEMENT, clean)
        print(f"{name:18s} {b.accrued_interest(SETTLEMENT):8.4f} "
              f"{street * 100:8.4f} {official * 100:7.3f} "
              f"{(street - official) * 1e4:+7.2f} "
              f"{by_years * 100:9.4f} {(by_years - official) * 1e4:+7.2f} "
              f"{wrong * 100:8.4f} {(wrong - official) * 1e4:+7.2f}")


def convention_table() -> None:
    print("\nThe same bond under four day count conventions (3.45% 2034)")
    name, coupon, maturity, clean, _, official, start = TESORO[1]
    print(f"{'convention':12s} {'yield':>9s} {'err bp':>8s} {'accrued':>9s}")
    for daycount, label in ((act_365f, "ACT/365F"), (act_360, "ACT/360"),
                            (thirty_360, "30/360")):
        b = bono(coupon, maturity, start, daycount)
        y = b.yield_from_clean_price(SETTLEMENT, clean)
        print(f"{label:12s} {y * 100:9.4f} {(y - official) * 1e4:+8.2f} "
              f"{b.accrued_interest(SETTLEMENT):9.4f}")
    b = bono(coupon, maturity, start)
    y = b.street_yield(SETTLEMENT, clean)
    print(f"{'ICMA street':12s} {y * 100:9.4f} {(y - official) * 1e4:+8.2f} "
          f"{b.accrued_interest(SETTLEMENT):9.4f}")


def curve_table(ecb: Curve) -> None:
    print("\nAgainst the ECB AAA curve of the same date")
    print(f"{'bond':18s} {'years':>6s} {'market':>8s} {'AAA model':>10s} "
          f"{'gap':>7s} {'spread bp':>10s} {'DV01':>8s}")
    for name, coupon, maturity, clean, _, official, start in TESORO:
        b = bono(coupon, maturity, start)
        cfs = b.cashflows(SETTLEMENT)
        accrued = b.accrued_interest(SETTLEMENT)
        model_clean = ecb.present_value(cfs) - accrued
        spread = implied_flat_spread(ecb, cfs, clean + accrued)
        print(f"{name:18s} {(maturity - SETTLEMENT).days / 365.25:6.2f} "
              f"{clean:8.3f} {model_clean:10.3f} {model_clean - clean:+7.3f} "
              f"{spread * 1e4:10.1f} {b.dv01(SETTLEMENT, official):8.5f}")


def compounding_note(ecb: Curve) -> None:
    ten = ecb.zero_rate(10.0)
    print("\nCompounding convention on the curve")
    print(f"  ECB ten-year, continuously compounded : {ten * 100:.5f}%")
    print(f"  the same rate compounded annually     : "
          f"{to_compounded(ten, 1) * 100:.5f}%")
    print(f"  difference                            : "
          f"{(to_compounded(ten, 1) - ten) * 1e4:.2f}bp")


if __name__ == "__main__":
    ecb = Curve.from_csv(ROOT / "data" / "ecb_aaa_spot_2026-09-22.csv")
    yields_table()
    convention_table()
    curve_table(ecb)
    compounding_note(ecb)
