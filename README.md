# fixed-income-risk

A fixed income valuation and interest rate risk engine in Python, built from
first principles: bonds, then the yield curve, then swaps, then a bucketed
DV01 report for a portfolio.

The goal is understanding, not a library to import. Every formula is derived,
implemented, and tested two ways — analytically and by numerical bumping —
with an assertion that the two agree.

No dependencies beyond `pytest`. Standard library only.

## Validated against published market data

The engine reproduces the Spanish Treasury's own published yields for its
auction of 17 September 2026 ([BOE-A-2026-20253](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-20253))
to within **0.1 basis points**, which is the precision the Treasury prints:

| bond | model | Treasury | error |
|---|---|---|---|
| Obligación 0.70% 30/04/2032 | 3.5589% | 3.558% | +0.09bp |
| Obligación 3.45% 31/10/2034 | 3.7960% | 3.796% | −0.00bp |
| Obligación 3.40% 31/10/2036 | 3.9595% | 3.960% | −0.05bp |

Discounting the same cashflows off the ECB euro area AAA curve of the same
date gives an implied Spanish sovereign spread of 25.5bp at 5.6 years, 38.2bp
at 8.1 and 44.9bp at 10.1.

Getting there required finding a compounding convention in the published data,
a real bug in the cashflow generator that 87 self-consistent tests had missed,
and a market time convention that is not a day count.
**[docs/step9-real-data.md](docs/step9-real-data.md)** is the write-up.

```bash
python3 scripts/step9_report.py     # reproduces every number above
```

## Design

**The instrument generates cashflows. The pricing engine discounts them. The
engine does not know which instrument produced them.**

A bond emits a list of `Cashflow(t, amount)`. `price(cashflows, y)` discounts
whatever it is given. A swap will be two cashflow streams with opposite signs,
so adding swaps requires no change to the engine.

`pricing.py` has not changed since step 2, through every sprint that added
coupon frequency, calendar schedules, day count conventions, accrued interest,
yield solving and duration. That is the split paying for itself.

## Conventions

- Rates are decimals: `0.04` means 4%.
- The single-yield engine compounds discretely, `m` periods per year
  (`m=1` by default). **The curve in `curve.py` compounds continuously**,
  because that is how the ECB publishes it — the two have separate discount
  functions and an explicit converter, and mixing them costs 6bp.
- The engine works in years as a float. Calendar dates live on the
  instrument: a `Bond` holds `issue_date`, `maturity_date` and its own day
  count convention, and converts dates to year fractions before handing
  cashflows over.
- The day count convention is a property of the instrument, not of the engine
  — it is written in the prospectus, like the coupon.
- Coupon schedules are generated **backwards from maturity**, so an off-cycle
  issue date produces a short first coupon, as in the market.
- Amounts are per the instrument's face value.

## Roadmap

1. ~~Bond pricing from cashflows~~
2. ~~Annual coupons + redemption~~
3. ~~Tests: par identity, monotonicity~~
4. ~~Coupon frequency + calendar schedules~~
5. ~~Day count conventions: ACT/360, ACT/365F, 30/360~~
6. ~~Clean vs dirty price, accrued interest~~
7. ~~Yield solving (Newton-Raphson)~~
8. ~~Duration, modified duration, convexity, DV01~~
9. ~~Real data: ECB curve + Spanish Tesoro bonds~~
10. Curve bootstrapping, forward rates
11. Vanilla interest rate swap, swap DV01
12. Bucketed DV01 (key rate durations) for a portfolio

## Layout

```
fitk/
  cashflows.py  Cashflow(t, amount)
  pricing.py    discount factors, price, dB/dy, yield by Newton-Raphson
  risk.py       duration, convexity, DV01 — analytic and bumped
  curve.py      zero curve, interpolation, continuous discounting, spreads
  bonds.py      Bond: schedule, cashflows, clean/dirty, accrued, street yield
  daycount.py   ACT/360, ACT/365F, 30/360
  schedule.py   month arithmetic, backward schedules, quasi-coupon dates
data/           the ECB curve and the BOE auction, with sources and dates
docs/           what the real data taught
scripts/        reproduces the figures in docs/
```

## Not implemented

Holiday calendars and business day adjustment, curve bootstrapping, forward
rates, swaps, floating-rate notes, options, inflation-linked bonds,
multi-curve (OIS/IBOR) discounting.

Interpolation on the curve is linear on zero rates with flat extrapolation.
That is the simplest thing that is honest about itself: it produces kinked
forwards at every node and pretends the curve stops moving past 30 years.
Step 10 does better.

`ACT/ACT ICMA` is deliberately absent as a day count function. Accrued
interest is a ratio of two day count fractions, and any ACT convention's
denominator cancels in that ratio, so ACT/360, ACT/365F and ACT/ACT ICMA all
return the same accrued figure. The function would be dead code. The ICMA
*time measure* is a different thing and does exist, as
`Bond.icma_cashflows` — see step 9.

## Running tests

```bash
python3 -m pytest
```

## License

MIT
