# DAV price history: audit and interpretation

Read-only Gold audit on 2026-11-13 found 51,735 price rows and 50,059 product
rows. There were 1,799 legacy `DAV_PUBLIC_DRUG_PRICE` price rows joined by numeric
DAV ID to current `SILVER_R2` products. These are ambiguous cross-source ID
collisions, not 1,799 independently verified price movements. One observed ID
combined a current tablet product with an old price expressed in mCi.

The API and model input queries now exclude that known cross-source combination.
Original Gold rows remain available for provenance review. This does not recover
the original product identity of those legacy prices; recovery requires their
original source records. Do not relabel them using the current product name.

The existing Gold loader already inserts new price observations without deleting
older ones and deduplicates by DAV ID, source date, price, type, unit and package.
Silver keeps only the latest source-ID version, whereas Bronze retains every
observed version. If several source edits happen between Gold syncs, replay or
review the Bronze event stream; the current-state Silver file alone cannot
reconstruct those intermediate versions. Source fields edited before the first
crawl cannot be recovered by this pipeline.

Model history must compare an exact registration/specification/packaging/price
context. It must not create another temporal observation from another crawl of
the same filing. Multiple source dates for one DAV ID are retained as distinct filing events ONLY when each date is verified from the DAV filing/publication source. Ambiguous legacy revisions and conflicting prices on the same comparable date remain excluded pending source lineage review.
Missing specifications also prevent automatic temporal pairing. The model does
not fill absent dates or use ingestion time as a source price date.

Existing published model reports remain reports of their old training versions.
Their previous counts and error metrics are not validation of the corrected
input logic. Retrain and evaluate both model families before quoting new metrics;
keep experimental/rejected forecasts labeled accordingly. Changes to source
date semantics and the endpoint's historical coverage must be disclosed.

The current classifier is conservative. A new filing at the same price is a new
declaration observation; it is not a new price level. A price edit within an old
source record is a revision observed at crawl time, not proof of when a market
price changed. A missing filing is not evidence of unchanged retail prices.

## Separate source dates

New crawler rows additionally retain `dav_filing_date` (`ngayKK_KKL`),
`dav_publication_date` (`ngayCongBo`, when actually supplied), and
`dav_reception_date` (`ngayTiepNhan`). No date field is synthesized from crawl
 time. The legacy `dav_declaration_date` remains unchanged for compatibility.

Silver chooses a valid, nonfuture filing date, otherwise a valid publication
 date, and records `silver_price_date_basis`. Reception alone yields UNKNOWN.
Gold stores the selected date and its basis. Older rows are LEGACY_UNVERIFIED
until matching source evidence is available; historical dates are never relabeled
by guesswork. Model inputs reject newly classified UNKNOWN-date observations.

The Bronze schema extension is limited to these three date fields. Existing
rows are integrity-checked under their old header, preserved with blank new
fields, then rehashed against the extended header. The checkpoint records the
extension and preserved row count. Arbitrary schema drift still fails closed.

Gold additionally stores `source_observed_at` for newly inserted observations.
Lookup can show a newly recorded revision even when its filing date is unknown.
That timestamp is never substituted for declaration dates in model labels; older
rows retain a null observation timestamp instead of an invented historical one.


## Irregular filing-window model update (13 Nov 2026)

See [market-irregular-filing-training.md](market-irregular-filing-training.md). Calendar 3/6/12-month labels use every genuine observed filing in the window, with time embargo at full window end. Missing filings are censored, NOT synthetic zero-price movements. Conditional test performance is not proof of an unconditional market forecast.
