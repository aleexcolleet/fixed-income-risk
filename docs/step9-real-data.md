# Step 9 — the model against the market

Every test before this one checked the code against itself: identities, round
trips, an analytic formula against a numerical one. Those prove
self-consistency. They cannot prove the code is *right*.

This step prices real Spanish government bonds, at a real settlement date,
against the real euro area curve, and compares the answer to figures the
Spanish Treasury and the ECB published and cannot retract.

Reproduce every number here with:

```bash
python3 scripts/step9_report.py
```

## The data

**The bonds.** The auction of Obligaciones del Estado held 17 September 2026,
settled 22 September 2026, published as
[BOE-A-2026-20253](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-20253).
Three bonds, each with its weighted average clean price, its accrued
interest, and — the useful part — the Treasury's own *rendimiento interno*.
That published yield is what the model gets marked against.

**The curve.** The ECB euro area AAA-rated central government bond spot
curve for 22 September 2026, series
`YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_<tenor>`, eighteen tenors from 3 months to
30 years, fitted by the ECB with the Svensson model.
[ECB Data Portal](https://data.ecb.europa.eu/data/datasets/YC/YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y).

Both are in `data/`, with their sources and observation dates in the file
headers.

### The settlement date is not in the resolution

The BOE gives the auction date, not the settlement date. But it prints
accrued interest to two decimals for each bond, and accrued interest is a
function of the settlement date. Solving backwards:

| bond | accrued (BOE) | implied settlement |
|---|---|---|
| 0.70% 30/04/2032 | 0.28 | 0.70 × 145/365 = 0.2781 → 22 Sep |
| 3.45% 31/10/2034 | 3.08 | 3.45 × 326/365 = 3.0814 → 22 Sep |

Two independent bonds agreeing on the same date is enough. 17 September 2026
was a Thursday and 22 September the following Tuesday — T+3 business days,
the Spanish convention.

## Finding 1 — the curve is continuously compounded

The ECB publishes these rates continuously compounded. The engine in
`pricing.py` compounds *m* times a year. They are not interchangeable:

```
ECB ten-year, continuously compounded : 3.45274%
the same rate compounded annually     : 3.51304%
difference                            : 6.03bp
```

Six basis points. Feed the file's numbers into `discount_factor(y, t, m=1)`
as if they were annually compounded and the ten-year prices at 100.746
instead of 100.247: **half a point of price**, every discount factor wrong in
the same direction. Nothing raises an error and nothing looks absurd.

This is why `fitk/curve.py` exists as a separate module with its own
`discount_factor` using `exp(-r*t)`, and why `to_continuous` /
`to_compounded` are explicit functions rather than something done inline.
The convention is a property of the data, so it belongs at the boundary where
the data is loaded.

## Finding 2 — the code paid a full first coupon on a bond that doesn't

The 3.40% of October 2036 was a new issue: it accrues from early June 2026
and pays on 31 October. The model priced it 25 basis points off. The cause
was not the curve or the convention — it was a bug in `bonds.py` that every
test in the repo had missed.

`cashflows()` paid `face * coupon / frequency` on every payment date. A bond
issued off-cycle pays a **short first coupon**: it only accrued for part of
the period, so it only pays for part of it. Here 150 days of a 365-day
period, so 1.3973 rather than 3.40.

Two invariants were wrong together, in the same direction:

- the first coupon, too big by 365/150;
- accrued interest, computed as a full coupon spread over the *short* period
  instead of the notional one, giving 2.516 against the BOE's 1.03.

The fix introduced `schedule.previous_quasi_coupon` — the on-cycle date one
period before the first real payment. No coupon was ever paid on that date;
the bond did not exist. It is a fiction, and it is the fiction the market
measures both the accrual fraction and the ICMA time against.

**Why no test caught it.** Every bond in the suite is issued on a coupon
date, because that is what you write when you invent test data. The
property tests were strong — the par identity across 30 maturities and 4
frequencies — and they were all blind to this, because a bond issued on cycle
has no short first period to get wrong. Real data found in one afternoon what
87 self-consistent tests could not.

## Finding 3 — the market does not measure time in years

With the coupon fixed, the model landed within 0.3bp of the Treasury's
published yield. Close. Not equal, and always on the same side, which means
a convention and not noise.

| bond | ICMA street | BOE | err | by day count | err | ACT/360 | err |
|---|---|---|---|---|---|---|---|
| 0.70% 30/04/2032 | 3.5589 | 3.558 | **+0.09bp** | 3.5553 | −0.27bp | 3.5058 | −5.22bp |
| 3.45% 31/10/2034 | 3.7960 | 3.796 | **−0.00bp** | 3.7933 | −0.27bp | 3.7404 | −5.56bp |
| 3.40% 31/10/2036 | 3.9595 | 3.960 | **−0.05bp** | 3.9563 | −0.37bp | 3.9010 | −5.90bp |

The street convention does not measure time in years at all. It measures it
in **coupon periods**: the next coupon is a fraction *f* of a period away,
the one after is *f*+1, then *f*+2, and the yield compounds once per period.
A bond paying annually on 31 October, settling 22 September, has its first
cashflow at *f* = 39/365 and its second at *f*+1 — never at 1 + 39/365 of a
real year, which is what a day count says.

The two differ because real periods are not the same length: 365 days, then
366 in a leap year, then 365. A day count sees that. The ICMA measure
deliberately does not.

That is `Bond.icma_cashflows` and `Bond.street_yield`, and it reproduces the
BOE figure to within 0.1bp — which is the Treasury's own rounding, so it is
as tight as the comparison can be made.

### And a warning against concluding too much

| convention | yield | error | accrued |
|---|---|---|---|
| ACT/365F | 3.7933 | −0.27bp | 3.0814 |
| ACT/360 | 3.7404 | −5.56bp | 3.0814 |
| 30/360 | 3.7945 | −0.15bp | 3.0858 |
| ICMA street | 3.7960 | −0.00bp | 3.0814 |

30/360 looks nearly as good as ICMA. It is not: these bonds mature on the
30th and 31st, so 30/360 and ACT/ACT almost agree by an accident of the
calendar. A bond maturing on the 1st would separate them. One bond never
validates a convention.

ACT/360 is the instructive one. It is wrong by 5.5bp, which on the 3.45% of
2034 is about 0.04 points of price — €40,000 per €100m of nominal, against an
auction that placed €1.7bn. A convention error is not a rounding error.

## Finding 4 — the AAA curve overvalues every Spanish bond

Now discount the real cashflows off the real curve:

| bond | years | market clean | AAA model | gap | implied flat spread | DV01 |
|---|---|---|---|---|---|---|
| 0.70% 30/04/2032 | 5.60 | 85.704 | 86.918 | +1.214 | 25.5bp | 0.0456 |
| 3.45% 31/10/2034 | 8.11 | 97.618 | 100.344 | +2.726 | 38.2bp | 0.0677 |
| 3.40% 31/10/2036 | 10.11 | 95.415 | 99.213 | +3.798 | 44.9bp | 0.0797 |

The model is too high on all three, by one to four points of price. That is
not an error to fix. Spain is not AAA, and the ECB curve is fitted to
AAA-rated euro area governments — Germany and the Netherlands, not Spain. The
gap is the market's price for Spanish sovereign credit and liquidity, and the
right response is to measure it, not to remove it.

`implied_flat_spread` solves for the parallel shift that reproduces the
market price. The answer rises with maturity — 25.5, 38.2, 44.9 basis points
— so the sovereign spread has a term structure of its own. A single number
per bond is a summary, not a model. Step 12 replaces the parallel shift with
bucket-by-bucket shifts, which is the point at which one duration number
stops being enough.

### Dates matter more than the spread does

The ECB ten-year was 3.4527% on 22 September and 3.6077% on the 29th: 15bp in
five business days. Pricing the 22 September auction off the 29 September
curve moves the implied spread one-for-one, so the five-year spread would
have come out at 10.5bp instead of 25.5bp. Not a small error — a different
conclusion. Hence the observation date in every data file name, and a test
that asserts the size of that mistake.

## What this step actually taught

The gap between a model and the market is never one thing. Here it was four,
and only one of them was a bug:

1. a compounding convention in the published data;
2. a genuine defect in the cashflow generator, found by data and not by
   reasoning;
3. a time measure that is a market convention rather than a calculation;
4. a real economic spread that should be left in and measured.

Knowing which category a discrepancy falls into is the whole skill. Three of
these four are things to model, not to fix, and a model that "matched
perfectly" on the first attempt would have meant the test was too weak to
find them.
