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
