"""
Draw the ECB AAA curve against the three Spanish bonds, as an SVG.

    python3 scripts/plot_curve.py        # writes docs/curve.svg

Pure standard library. The project takes no dependencies beyond pytest, and
a chart is not a good enough reason to break that -- an SVG is text, and
writing the text is fifty lines.

What the chart shows, and what it deliberately does not:

The line is the ECB AAA-rated euro area government curve, converted from the
continuously compounded rates the ECB publishes to annually compounded ones,
because that is the basis the bond yields are quoted on. Comparing them
without converting would draw a picture that is 6bp wrong everywhere.

Each bond appears twice. The hollow marker is the yield it *would* have if it
were AAA: price it off the curve, then solve that price back to a yield, so
the coupon and the exact cashflow dates are handled identically to the real
one. The filled marker is the yield the market actually paid. The gap between
them is the sovereign spread, and it is an honest gap -- both ends come from
the same bond, the same convention and the same settlement date.

Plotting the market yields straight against a zero curve would be the easy
version and a slightly dishonest one: a coupon bond's yield is a weighted
average over the curve, so part of the apparent gap would be the shape of the
curve rather than Spain's credit.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fitk.bonds import Bond                              # noqa: E402
from fitk.curve import Curve, to_compounded              # noqa: E402
from fitk.daycount import act_365f                       # noqa: E402
from fitk.pricing import yield_from_price                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SETTLEMENT = date(2026, 9, 22)

BONDS = [
    ("0.70% 2032", 0.0070, date(2032, 4, 30), 85.704, date(2022, 4, 30)),
    ("3.45% 2034", 0.0345, date(2034, 10, 31), 97.618, date(2024, 10, 31)),
    ("3.40% 2036", 0.0340, date(2036, 10, 31), 95.415, date(2026, 6, 3)),
]

W, H = 840, 470
L, R, T, B = 74, 210, 46, 58          # margins; the right one holds the legend
INK = "#1b1b1b"
GRID = "#d8d8d8"
AAA = "#8a8f98"
SPAIN = "#b3242b"


def x_px(years: float, xmax: float) -> float:
    return L + (years / xmax) * (W - L - R)


def y_px(rate: float, lo: float, hi: float) -> float:
    return T + (hi - rate) / (hi - lo) * (H - T - B)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build() -> str:
    curve = Curve.from_csv(ROOT / "data" / "ecb_aaa_spot_2026-09-22.csv")

    points = []
    for name, coupon, maturity, clean, start in BONDS:
        bond = Bond(face=100.0, coupon=coupon, issue_date=start,
                    maturity_date=maturity, frequency=1, daycount=act_365f)
        cfs = bond.cashflows(SETTLEMENT)
        years = (maturity - SETTLEMENT).days / 365.0

        market = bond.street_yield(SETTLEMENT, clean)
        # The same bond priced off the AAA curve, expressed as a yield so the
        # two numbers are on one axis.
        aaa = yield_from_price(cfs, curve.present_value(cfs), m=1)
        points.append((name, years, market, aaa))

    xmax = 31.0
    samples = [(t / 4, to_compounded(curve.zero_rate(t / 4), 1))
               for t in range(1, int(xmax * 4) + 1)]

    values = ([r for _, r in samples]
              + [p[2] for p in points] + [p[3] for p in points])
    lo = min(values) - 0.0020
    hi = max(values) + 0.0020

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
    ]

    # Horizontal gridlines every 25bp, labelled.
    step = 0.0025
    tick = (int(lo / step) + 1) * step
    while tick < hi:
        y = y_px(tick, lo, hi)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{L - 10}" y="{y + 4:.1f}" text-anchor="end" '
                   f'font-size="12" fill="{INK}">{tick * 100:.2f}%</text>')
        tick += step

    # X axis.
    y0 = H - B
    out.append(f'<line x1="{L}" y1="{y0}" x2="{W - R}" y2="{y0}" '
               f'stroke="{INK}" stroke-width="1.2"/>')
    for years in (0, 5, 10, 15, 20, 25, 30):
        x = x_px(years, xmax)
        out.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + 5}" '
                   f'stroke="{INK}" stroke-width="1.2"/>')
        out.append(f'<text x="{x:.1f}" y="{y0 + 20}" text-anchor="middle" '
                   f'font-size="12" fill="{INK}">{years}y</text>')
    out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 12}" '
               f'text-anchor="middle" font-size="12" fill="#555">'
               f'years to maturity</text>')

    # The curve itself.
    path = " ".join(f"{x_px(t, xmax):.1f},{y_px(r, lo, hi):.1f}"
                    for t, r in samples)
    out.append(f'<polyline points="{path}" fill="none" stroke="{AAA}" '
               f'stroke-width="2.4"/>')

    # The bonds. All three mature within five years of each other, so their
    # markers sit close together and per-marker labels would cross each
    # other's connectors. Labels go in one column to the right of the last
    # marker instead, each joined to its own by a leader.
    label_x = max(x_px(p[1], xmax) for p in points) + 46

    for name, years, market, aaa in points:
        x = x_px(years, xmax)
        y_mkt, y_aaa = y_px(market, lo, hi), y_px(aaa, lo, hi)
        spread_bp = (market - aaa) * 1e4

        out.append(f'<line x1="{x:.1f}" y1="{y_aaa:.1f}" x2="{x:.1f}" '
                   f'y2="{y_mkt:.1f}" stroke="{SPAIN}" stroke-width="1.4" '
                   f'stroke-dasharray="3 3"/>')
        out.append(f'<line x1="{x + 9:.1f}" y1="{y_mkt:.1f}" '
                   f'x2="{label_x - 7:.1f}" y2="{y_mkt:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y_aaa:.1f}" r="5" '
                   f'fill="#ffffff" stroke="{AAA}" stroke-width="2"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y_mkt:.1f}" r="5.5" '
                   f'fill="{SPAIN}"/>')
        out.append(f'<text x="{label_x:.1f}" y="{y_mkt + 4.5:.1f}" '
                   f'font-size="12.5" fill="{INK}">'
                   f'{esc(name)}  <tspan fill="{SPAIN}" font-weight="bold">'
                   f'+{spread_bp:.1f}bp</tspan></text>')

    # Title and legend.
    out.append(f'<text x="{L}" y="24" font-size="15" font-weight="bold" '
               f'fill="{INK}">Spanish sovereign spread over the euro area '
               f'AAA curve</text>')
    out.append(f'<text x="{L}" y="39" font-size="11.5" fill="#555">'
               f'settlement 22 September 2026 &#183; ECB AAA spot curve, '
               f'annually compounded &#183; Tesoro auction of 17 September '
               f'(BOE-A-2026-20253)</text>')

    lx, ly = W - R + 14, T + 22
    out.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 22}" y2="{ly - 4}" '
               f'stroke="{AAA}" stroke-width="2.4"/>')
    out.append(f'<text x="{lx + 29}" y="{ly}" font-size="11.5" fill="{INK}">'
               f'ECB AAA curve</text>')
    out.append(f'<circle cx="{lx + 11}" cy="{ly + 20}" r="5" fill="#ffffff" '
               f'stroke="{AAA}" stroke-width="2"/>')
    out.append(f'<text x="{lx + 29}" y="{ly + 24}" font-size="11.5" '
               f'fill="{INK}">bond priced off it</text>')
    out.append(f'<circle cx="{lx + 11}" cy="{ly + 44}" r="5.5" '
               f'fill="{SPAIN}"/>')
    out.append(f'<text x="{lx + 29}" y="{ly + 48}" font-size="11.5" '
               f'fill="{INK}">yield actually paid</text>')

    out.append('</svg>')
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    target = ROOT / "docs" / "curve.svg"
    target.write_text(build())
    print(f"wrote {target.relative_to(ROOT)}")
