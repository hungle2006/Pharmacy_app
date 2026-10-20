# Pharmacy automatic Bronze ingestion

This branch adds DAV, ICD-10, RxNorm and MEDI monitoring to Pharmacy_app without changing the deployed frontend.

- Tuesday 02:19 Asia/Ho_Chi_Minh: DAV and ICD-10 crawl, immutable compressed raw, normalized CSV snapshots and delta; MEDI official page version check only.
- Day 8 02:31 monthly: NLM RxNorm Current Prescribable Content (no-license subset) ZIP, RXNCONSO.RRF -> five-column rxnorm CSV and added/removed terms.
- MEDI 2020 is **not** auto-downloaded. New release candidates cause a GitHub Actions warning/failure for review.
- R2 bucket: pharmacy-data-lake. Requires three repository Actions secrets: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY. Scope credentials to this R2 bucket and do not put them in source.
- Uses latest pointers under _control/, immutable raw under bronze/, derived CSV under silver/, audit reports under _audit/.
- Manually trigger via Actions -> Pharmacy four source bronze -> Run workflow.
- Scrapers depend on third-party public endpoints and may fail when the providers change schemas or reject requests.
- The files initially provided in ChatGPT have not been published as raw files to GitHub or R2.
- End-to-end runs and cloud writes require configured GitHub secrets and must be verified before treating ingestion as live.
