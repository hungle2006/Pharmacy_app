# Automatic six-feature price training

The feature estimator predicts a recorded declared price, separately from the
market time-series forecast. It does not learn retail transaction prices.

## Input and latest-price selection

Read the actual Neon Gold join once per run using GOLD_DATABASE_URL first.
Separate price type and unit before constructing the snapshot. Exclude known
cross-source ID collisions, unknown source dates, non-positive/nonfinite prices,
future dates and missing identities. A crawl timestamp never replaces a source
date. Legacy dated rows remain explicitly labelled LEGACY_UNVERIFIED; their
presence does not establish verified filing/publication chronology.

For each registration within each price type/unit select its latest eligible
source date. If that date has conflicting prices or six-feature specifications,
exclude the product instead of picking a random row or reverting to an older
price. Exact duplicate crawls do not add weight. An unknown ingredient on the
latest record excludes that product. Preserve original Gold/Bronze history.

One registration has at most one row per segment. This conservative policy can
exclude registrations with multiple latest packaging variants; do not silently
interpret them as price changes. The report snapshot_audit records exclusions
and date provenance. The private R2 version contains input.csv.gz for replay.

## Evaluation and served model

Keep the existing strict chronological, registration-disjoint 60/15/10/15
train/validation/calibration/test experiment. Only validation selects CatBoost
objective and blend; calibration estimates intervals; test is untouched.
The published model is the exact evaluated model, not a refit on test labels.
Consequently the most recent snapshot rows are used for calibration/testing,
not all for fitting. No claim is made that the model has learned every current
price. All-data refits would require separate evaluation and interval reporting.

The existing approved label means >=1% MAE improvement versus train-only priors
and positive 95% bootstrap lower bound. It is NOT a threshold for absolute price
accuracy. Experimental segments remain visible with that status; new data does
not guarantee improvement. Track MAE, within-20%, supported ingredients and
interval coverage in each version.

## Automatic sequence

1. Weekly DAV Bronze ingestion completes successfully.
2. Silver + mapping + Gold complete. Gold uploads gold-feature-training-ready
   only for a real write attempt with a configured DB, never for a dry run.
3. Feature workflow validates that same-repository main run succeeded and has
   the readiness artifact. Failed Bronze no longer cascades into Silver.
4. Read Gold; hash selected normalized rows and training recipe. If both equal
   the published version, skip fitting and preserve the current pointer.
5. Otherwise archive the input snapshot, run evaluation, validate every model
   and metadata bundle, upload immutable version files, then update latest.json
   last. Failures before the pointer update preserve the previous version.
6. Serving checks the pointer every 120 seconds and retains its previous report
   if refresh fails. Workflow summaries and artifacts expose the evaluation.

A daily 07:30 UTC fallback checks changes, normally skipping unchanged data.
Manual Train Feature Price Estimator supports force=true for deliberate replay.
Training recipe changes on main also trigger evaluation. Successful training can
publish experimental research results; it never changes them to approved merely
because the job succeeded. Credentials and snapshots stay private.
