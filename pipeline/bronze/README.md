# Pharmacy Bronze: cumulative CSV on Cloudflare R2

Architecture: **one CSV per source**, append-only **record versions**, not a new file every week.

- `bronze/dav.csv`: new/updated drug-price records by `dav_row_id`.
- `bronze/icd10.csv`: new/updated codes by `model,id`.
- `bronze/rxnorm.csv`: new/updated RxNorm terms by `rxcui,tty,sab,display_name`.
- `bronze/medi_hps.csv`: initial legacy HPS records, when the original source becomes available; no automatic re-download of 2020.

Every CSV row includes `__operation` (`INSERT`, `UPDATE`, `REMOVE` where supported), `__ingested_utc`, and `__row_hash`. The latest record version wins. `REMOVE` means absent from a complete RxNorm source release; do not interpret it as a drug recall.

**No direct append on R2:** the Python job downloads the current CSV, adds only new/changed versions, uploads the replacement to the exact same key, and verifies size and SHA-256 metadata. Unchanged data causes no file rewrite. R2 keeps only one canonical CSV per source under Bronze. This reduces object count but cannot avoid full-object transfer for an actual append.

**Initial migration 2026-10-20:** created and verified `bronze/icd10.csv` (16,224 rows) and `bronze/rxnorm.csv` (141,074 rows), then removed the three replaced legacy raw Bronze objects. The original `DAV.xlsx` and `MEDI-2_HPS.xlsx` objects were already missing from R2, so no CSV was fabricated for those. DAV is initialized when a full crawler run succeeds. MEDI remains an official source version watch until a source file is available. The previous Silver objects outside Bronze were NOT deleted.

Weekly GitHub Actions workflow: `.github/workflows/pharmacy-data-lake.yml`, Tuesday 02:19 Asia/Ho_Chi_Minh. For manual run choose a single source or all. Source jobs run independently; a DAV 504 cannot roll back successful RxNorm/ICD rows.

**Safety:** never mark an incomplete crawl as a complete snapshot or emit removals from partial sources. The DAV API may return 504; the job fails and leaves the existing Bronze CSV unchanged. Data columns are preserved verbatim in the CSV export, but file-level raw lineage from NLM ZIP etc. is NOT fully preserved inside Bronze after compaction. For strict immutable raw Bronze use separate raw archival storage.

**Scripts:** `pipeline/bronze/compact_csv.py` (versioned merges), `pipeline/bronze/run_compact.py` (orchestrator), `pipeline/bronze/crawl_dav.py`, `crawl_icd10.py`, `rxnorm_pipeline.py`, `medi_watch.py`.

## DAV: record versions and actual declaration comparisons

`bronze/dav.csv` is the cumulative history. A changed source record appends a
new row with the same `dav_row_id`, `__operation=UPDATE`, the new raw values,
`__row_hash`, and `__ingested_utc`. The old row remains. Identical repeat crawls
append nothing. `silver/dav.csv` and the crawler's local `MASTER.csv` are
current-state catalogs, not substitutes for the Bronze version history.

An UPDATE is **not automatically a price movement**. The DAV audit in
`_control/compact/dav.json` distinguishes:

| Source observation | Storage / interpretation |
| --- | --- |
| Same ID, identical contents | No appended event |
| New ID | Append INSERT; not automatically a price change |
| Same ID, different price | Append UPDATE; source price revision requiring review |
| Same ID, changed date or product identity | Append UPDATE; date/identity revision requiring review |
| Same ID, metadata only | Append UPDATE; not a price movement |
| New ID, later source date, exact comparable attributes and unambiguous prior price | Compare declared prices; distinguish changed and unchanged |
| A record disappears | Retain history; absence is unverified, not a recall or price decrease |

Comparison dates come only from valid filing/publication fields, never reception or crawl time. Comparison requires registration, ingredient, strength, form, manufacturer,
country, packaging, unit, price type, and declaring company. Missing fields or
conflicting prior prices prevent an automatic change classification. Initial
collection does not infer a change solely because a record is new to the app.

The source field currently mapped to `dav_declaration_date` is **`ngayTiepNhan`
(source reception date)**. This legacy column name is retained for schema
compatibility. It is not the crawl date, a verified effective-price date, or a
daily retail quote. `__ingested_utc` records when the app observed the version.

The crawler emits a completion manifest. Full ingestion rejects missing IDs,
conflicting repeated IDs, incomplete row counts, and a changing `totalCount`.
`--max-rows` is a partial sample and cannot update canonical Bronze through
`run_compact.py`. This detects observed paging problems; it does not prove that
the provider's full historical archive is exposed by this active-record endpoint.

See [the audit and model implications](../../docs/dav-price-history.md).

**R2 secrets:** `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`; never commit actual secret values.
