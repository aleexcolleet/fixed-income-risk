# fixed-income-risk

A fixed income valuation and interest rate risk engine in Python, built from first principles: bonds, then the yield curve, then swaps, then a bucketed DV01 report for a portfolio.

The goal is understanding, not a library to import. Every formula is derived, implemented, and tested two ways (analytic and numerical bumping).

## Design

**The instrument generates cashflows. The pricing engine discounts them. The engine does not know which instrument produced them.**

A bond emits a list of `Cashflow(t, amount)`. `price(cashflows, y)` discounts whatever it is given. A swap will be two cashflow streams with opposite signs, so adding swaps requires no change to the engine.

## Conventions

- Rates are decimals: `0.04` means 4%.
- Discrete annual compounding (until stated otherwise).
- Time is in years, as a float. No calendar dates yet.
- Amounts are per the instrument's face value.

## Roadmap

1. Bond pricing from cashflows
2. Annual coupons + redemption
3. Tests: par identity, monotonicity
4. Coupon frequency (semiannual)
5. Day count conventions
6. Clean vs dirty price, accrued interest
7. Yield solving (Newton-Raphson)
8. Duration, convexity, DV01
9. Real data: ECB curve + a Spanish Tesoro bond
10. Curve bootstrapping, forward rates
11. Vanilla interest rate swap, swap DV01
12. Bucketed DV01 (key rate durations) for a portfolio

## Not implemented

Calendar dates, holiday calendars, floating-rate notes, options, inflation-linked bonds, credit spreads, multi-curve (OIS/IBOR) discounting.

## Running tests

```bash
python3 -m pytest
```

## License

MIT
