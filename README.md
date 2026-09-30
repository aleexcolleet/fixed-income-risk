# fixed-income-risk

A fixed income valuation and interest rate risk engine in Python, built from first principles: bonds, then the yield curve, then swaps, then a bucketed DV01 report for a portfolio.

The goal is understanding, not a library to import. Every formula is derived, implemented, and tested two ways (analytic and numerical bumping).

## Design

**The instrument generates cashflows. The pricing engine discounts them. The engine does not know which instrument produced them.**

A bond emits a list of `Cashflow(t, amount)`. `price(cashflows, y)` discounts whatever it is given. A swap will be two cashflow streams with opposite signs, so adding swaps requires no change to the engine.

`pricing.py` has not changed since step 2, through the sprints that added coupon frequency, calendar schedules, day count conventions and accrued interest. That is the split paying for itself.

## Conventions

- Rates are decimals: `0.04` means 4%.
- Discrete compounding, `m` periods per year (`m=1` by default).
- The engine works in years as a float. Calendar dates live on the instrument: a `Bond` holds `issue_date`, `maturity_date` and its own day count convention, and converts dates to year fractions before handing cashflows over.
- The day count convention is a property of the instrument, not of the engine — it is written in the prospectus, like the coupon.
- Coupon schedules are generated **backwards from maturity**, so an off-cycle issue date produces a short first coupon, as in the market.
- Amounts are per the instrument's face value.

## Roadmap

1. ~~Bond pricing from cashflows~~
2. ~~Annual coupons + redemption~~
3. ~~Tests: par identity, monotonicity~~
4. ~~Coupon frequency + calendar schedules~~
5. ~~Day count conventions: ACT/360, ACT/365F, 30/360~~
6. ~~Clean vs dirty price, accrued interest~~
7. Yield solving (Newton-Raphson)
8. Duration, convexity, DV01
9. Real data: ECB curve + a Spanish Tesoro bond
10. Curve bootstrapping, forward rates
11. Vanilla interest rate swap, swap DV01
12. Bucketed DV01 (key rate durations) for a portfolio

## Not implemented

Holiday calendars and business day adjustment, yield solving, duration and DV01, floating-rate notes, options, inflation-linked bonds, credit spreads, multi-curve (OIS/IBOR) discounting.

`ACT/ACT ICMA` is deliberately absent. Accrued interest is a ratio of two day count fractions, and any ACT convention's denominator cancels in that ratio, so ACT/360, ACT/365F and ACT/ACT ICMA all return the same accrued figure. The function would be dead code.

## Running tests

```bash
python3 -m pytest
```

## License

MIT
