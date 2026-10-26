# Automated Pharmacy Silver mapping tables

Runs **after** the existing Bronze-to-Silver source job in
.github/workflows/pharmacy-silver-auto.yml. It also runs on the weekly Silver
schedule, on merge into main, and on manual dispatch.

## One CSV per mapping table (no version directories)
- silver/dav_rxnorm_mapping.csv — one row per active DAV product, candidate clinical RxNorm SCD and review rationale.
- silver/dav_rxnorm_component_evidence.csv — one row per extracted DAV ingredient component, exact IN/PIN terminology evidence and review.
- silver/rxnorm_scd_components.csv — SCD-to-SCDC and ingredient/dose-form relationships inferred by **exact parsing of RxNorm source terms**, not official RXNREL.
- silver/medi_icd10_mapping.csv — one row per historical MEDI-2 HPS indication, with textually identical ICD-10 Vietnam code candidates only (not equivalent disease semantics).

All CSVs have a mapping_status/relation_status and clinical_verified=false.
There is intentionally NO auto-VERIFIED_SCD. Even exact strength/form/name
matches do not independently prove product equivalence; a qualified clinical
reviewer must validate official drug formulation and source versions.

The provided MEDI file currently exists as bronze/MEDI-2_HPS.csv (legacy).
Rows are published only as **review candidates**, not as a validated HPS
release. No automatic redownload or upgrade of MEDI-2 2020 takes place.

The compact RxNorm Bronze term CSV includes rxcui/tty/sab/display_name, but
not official RXNREL relationships. The mapping builder reuses the legacy
RxNorm structural parser only to produce transparent **inferences**, with
evidence_method EXACT_RXNORM_TERM_PARSE_NOT_OFFICIAL_RXNREL. For true
official RXNREL mapping, Bronze must be extended to preserve the matching
release's RXNREL.RRF; do not infer a verified edge from text parsing.

This pipeline does not use Google Cloud, external paid compute, or any
credentials beyond the existing R2 GitHub secrets.

## Run on GitHub
Actions > Pharmacy Silver automatic R2 > Run workflow > Source=all.
Leave dry_run enabled for a safe test; uncheck to publish current one-file
tables. Automatic weekly and post-Bronze runs publish when source or code
checksums change.

## Repeatability & safety
The mapping job downloads silver/dav.csv, silver/rxnorm.csv,
silver/icd10.csv and, if available, the legacy MEDI file. Input object
hashes and mapping code revision determine whether rebuild is needed.
The outputs overwrite exactly the four fixed CSV keys. Last step writes
_control/silver/mappings.json with their checksums and counts. A partial
failure of multiple uploads can leave mixed current files, which can be
resolved by retrying the job; R2 does not provide atomic transactions
across several keys. Consumers that require consistency must validate
the control checkpoint hashes and sizes before reading all four tables.
No other Silver CSV or Bronze object is deleted.

## Quality limitations
Ingredient aliases paracetamol → acetaminophen and vitamin C → ascorbic
acid are search candidates marked for review, not clinical equivalence.
Strength comparison is conservative and rejects ambiguous numeric formats.
Combination products and unsupported dosage-form equivalences remain
unmatched. Exactly matching ICD10CM vs ICD10 Vietnam strings is NOT
cross-version equivalence. MEDI 2020 is historical data only.

## RxNorm Report 3 + Report 4 (EDA → Mapping)

`silver_mapping/rxnorm_eda.py` reads current `silver/rxnorm.csv` from R2. It
measures missing values, distinct RxCUI, terminology TTY/SAB distribution,
mapping-readiness, quality status, normalized name changes, duplicate keys,
and name-length distribution. It builds a **temporary** five-column
mapping-ready CSV that `silver_mapping.build_all` uses for DAV↔RxNorm mapping.

The workflow publishes exactly two fixed presentation objects outside Bronze:
- `reports/rxnorm_eda.json` (reviewable aggregates and chart data)
- `reports/rxnorm_eda.html` (standalone Report 3 + Report 4 with mapping samples)

The public app page `/rxnorm-eda.html` is refreshed by the mapping GitHub Action
after a successfully published report, using `assets/rxnorm-eda.json` as its
lightweight static evidence copy. On a blocked GitHub write, the job emits a
warning and the R2 report remains the authoritative version. The report is
linked from the RxNorm lookup tab. The GitHub Actions job also attaches
`rxnorm-eda-report` HTML/JSON files for presentation (30-day retention).

The five RxNorm terms columns are preserved and clinical mapping stays
CANDIDATE_REVIEW / UNMATCHED_REVIEW, never auto-VERIFIED. Exact text matching
is not a licensed official RXNREL relationship.
