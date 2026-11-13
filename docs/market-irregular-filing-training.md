# PharmaBiz — Irregular DAV price-filing model

## Purpose

Prices do not change at fixed 91/183/365-day intervals. One DAV drug
may have multiple independently recorded filings within the same quarter.
Model input must preserve ALL real events, not select a single filing near
day 91/183/365.

## Source integrity

Read real dated DAV records from Neon Gold, grouped by registration and
exact drug specification, package, price type and unit. Exclude missing
identifiers, conflicting same-day prices, inconsistent units and the known
cross-source numeric-ID collisions.

Use verified DAV filing/publication dates before unverified reception dates
for one source ID. Multiple dates for the same source ID may be treated as
different events only if all retained dates have verified filing/publication
provenance. Unverified duplicate revisions remain excluded. A crawl timestamp
is never a price-event date; an identical recrawl never adds a sample.

## Irregular calendar windows

For every real event at origin t, create separate calendar 3/6/12-month windows
ending at t+3, t+6 and t+12 calendar months. Only complete windows are eligible
for labels. Within a completed window, inspect EVERY real subsequent filing,
not only the entry closest to an arbitrary fixed-day target.

Use the price of the final actual filing in that window as a CONDITIONAL
observed-window target; preserve its actual source date, number of filings,
number of price changes, cumulative movement, observed minimum and maximum,
and gap between last filing and the calendar end.

CRITICAL: If there is no new filing inside the window, the price outcome is
UNOBSERVED rather than a synthetic 0% change. This conditional observed price
is NOT an official quote at the exact horizon end and cannot represent the
full market without independently verified uninterrupted source coverage.

For chronological splitting, target_date is the full calendar WINDOW END,
not the date of the last intermediate filing. A model cannot use a window
until that window is entirely in the past.

## Leakage prevention and evaluation

Features are computed ONLY using events known at the origin, including
previous observed change, days since previous filing and historical 90/365-day
filing counts/volatility. All statistics from the future evaluation window
remain targets or report-only diagnostics.

Use >=2 valid expanding walk-forward folds (each >=50 historical training
observations, >=20 later validation observations), then a final chronological
holdout of >=20 rows and >=15 distinct product registrations. Compare
time-weighted, hierarchical and temporal Ridge models with the no-change
baseline on the same conditional target. Candidate selection is validation
only. Calculate errors by registration rather than by row; cluster bootstrap
resamples registration IDs.

Passing this conditional backtest does NOT approve a 3/6/12-month unconditional
market forecast: prices for non-filing products are unobserved. If conditional
evaluation passes, mark experimental_conditional, keep forecast_change_pct null
and publish any conditional diagnostics separately. No quality gate is
lowered to force a percentage into the production dashboard.

## Automatic pipeline

Weekly DAV Bronze -> Silver/mapping -> Neon Gold. On a real completed Gold
run, the market-training GitHub Actions workflow is triggered by the Silver
workflow completion and checks the Gold readiness artifact. It also runs
weekly or on relevant code pushes. A dry run is skipped. The tests precede
a read-only Gold evaluation. Store versioned JSON in private Cloudflare R2,
switch the latest pointer last, and serve a public aggregate report via Render
and Vercel. Training success does not imply model approval.

## What remains necessary

Obtain a verified continuous coverage audit for each drug across the full
horizon, distinguishing a true absence of re-filing from missing collection.
Only then can prices at the exact end of 3/6/12 months be defined reliably
for all eligible products, including products without a new declaration.

Code: ml_price/forecast.py, market_models.py, market_forecast.py; tests:
ml_price/tests/test_forecast.py and test_market_models.py.
