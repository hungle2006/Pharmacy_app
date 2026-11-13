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
the same filing. Multiple source dates for one filing ID and conflicting prices
on the same comparable date are conservatively excluded pending lineage review.
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
