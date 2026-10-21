# Incremental Gold sync: in-place, minimal tables

Keep the eight existing PharmaBiz PostgreSQL tables. Add only one missing table, **dav_rxnorm_evidence**, to store component-level review evidence. Do not create persistent staging snapshots, shadow copies, duplicate Gold data or per-run versions.

The inputs are the seven stable CSVs in Cloudflare R2 Silver: dav, icd10, rxnorm, dav_rxnorm_mapping, dav_rxnorm_component_evidence, rxnorm_scd_components, medi_icd10_mapping.

## What changes

- dav_product: UPSERT by dav_row_id, adding QC fields.
- price_record: add genuinely new observations only; natural-key dedup across old price IDs.
- rxnorm_concept: consolidate multiple TTY records under one RxCUI.
- rxnorm_scd and rxnorm_scd_component: UPSERT by SCD ID and component order; preserve formally verified old edges.
- disease: UPSERT by ICD code; preserve curated columns.
- dav_rxnorm_mapping: UPSERT by dav_row_id; preserve selected_scd_rxcui, mapping_status and accepted_for_serving on existing rows. Incoming Silver candidate fields stay separately labeled.
- medi_relation: insert missing indication relationships only, never assert ICD10CM/ICD10 Vietnam equivalence.
- dav_rxnorm_evidence (NEW): unique by (dav_row_id, component_order).

Temporary PostgreSQL COPY stages are dropped at COMMIT; no TRUNCATE or DELETE. Unique indexes prevent duplicates. One transaction ensures rollback on error. A small R2 control JSON at _control/gold/latest.json stores source checksums and code revision after the database COMMIT. Unchanged runs are skipped.

## One-time activation

Production Vercel has a server-side DATABASE_URL; it is *not* automatically transferred to GitHub. Add the separate secret **GOLD_DATABASE_URL** in GitHub repository Settings > Secrets and variables > Actions. Use a dedicated Neon ETL database role with only the permissions needed for the target schema. Do not paste any connection string into chat or commit it to GitHub.

After reviewing the PostgreSQL integration tests, set GitHub Actions variable **GOLD_SYNC_ENABLED=true**. This enables the Gold job after Silver source and mapping jobs. Until then Gold is intentionally skipped and the existing dashboard is unaffected.

GitHub Actions > Pharmacy Silver automatic R2 > Run workflow, choose source=all. Manual dry_run avoids DB writes; turning it off enables writing only when GOLD_SYNC_ENABLED is true. All three existing R2 secrets are reused.

## Quality safeguards

The job refuses preexisting duplicate Gold identities rather than deleting arbitrary rows. It verifies Silver mapping checkpoint consistency and declines clinical_verified=true from unreviewed sources. Clinical reviews and accepted mapping choices in existing Gold are never overwritten with guessed Silver candidates. It keeps legitimate price observation history without duplicating identical observations.

A separate GitHub workflow runs PostgreSQL 16 integration tests, including two consecutive Gold syncs, and validates the original eight tables plus a single new evidence table.


## Gold NULL and duplicate-DAV quality policy (2026-10-21 audit)

A null **RxCUI candidate is not a database fault**. Never backfill
`selected_scd_rxcui`, `suggested_scd_rxcui` or `ingredient_candidate_rxcui`
with guessed medical relationships. Those are evidence-bearing identifiers.

At initial audit, `dav_rxnorm_mapping` had 49,830 rows, including
44,492 missing selected SCD and 45,414 missing suggested SCD. Of 53,754
`dav_rxnorm_evidence` rows, 41,341 had no ingredient RxCUI candidate;
281 had no DAV source ingredient to begin with. The extra cause was
10,692 pre-existing mapping rows without newer Silver provenance/status.
695 legacy suggested SCD identifiers had an exact local RxNorm SCD name
available.

Fixes are **additive and idempotent**:
- `candidate_evidence_status` always states missing source ingredient,
  no RxNorm ingredient, partial evidence, missing SCD, candidate awaiting
  review, or legacy provenance. `ingredient_component_total` and
  `ingredient_component_matched` are source-derived counts, not guesses.
- Fill legacy `candidate_scd_name` **only** when a local SCD row
  matches the pre-existing suggested RxCUI exactly. Preserve any human-
  reviewed `selected_scd_*`, `mapping_status`, `accepted_for_serving`.
- Populate `silver_mapping_status` and `review_reason` for older
  mappings without inventing a clinical match.
- `dav_product` gains `catalog_equivalent_to` and
  `catalog_duplicate_status`. One-to-one exact matches between older
  and Silver DAV data are labeled **POSSIBLE_SAME_PRODUCT_REVIEW**;
  one-to-many matches are labeled **AMBIGUOUS_MULTIPLE_SILVER_ROWS_REVIEW**.
  These are *review flags*, not deduplication or automatic suppression.
- When a DAV ID already exists but has a legacy source label, refresh
  the source to `SILVER_R2` upon current Silver import.
- The transaction checks for unexplained null status/review reason,
  inconsistent component counts, and still refuses duplicate stable IDs.
  No legacy product, price history, clinical mapping, or row is deleted.

DAV ingredients often contain Vietnamese/localized orthography and
ingredient form/salt descriptions not in US RxNorm terminology.
A limited review-only exact-name alias list makes *search candidates* for
some spelling variants; never sets `clinical_verified=true`.

Full clinical RxNorm mapping needs the matching release's official RXNREL
and validated cross-language ingredient/form equivalence. Do not treat
an exact string as official evidence. Gold records remain safe for
candidate research and business analytics, **not treatment advice**.
