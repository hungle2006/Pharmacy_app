# Pharmacy Silver automatic R2 (canonical Bronze CSVs)

## Automatic operation
Existing Bronze GitHub workflow: **Pharmacy weekly Bronze ingestion**
Bronze R2 keys:
- bronze/dav.csv
- bronze/icd10.csv
- bronze/rxnorm.csv
- bronze/medi_hps.csv (legacy; skipped until verified newer approved release)

When Bronze workflow completes (including a partial failure where an independent source may have updated), or every Tuesday at 05:00 UTC (12:00 in Vietnam), or on initial merge to main:
1. Reuse the existing Bronze GitHub Actions secrets R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY. No new cloud accounts or Google Cloud required.
2. Download each available canonical Bronze CSV. Skip missing sources, process other sources independently.
3. Verify every Bronze event row against its __row_hash, replay INSERT/UPDATE/REMOVE to current source state.
4. Compute SHA-256 of each input object; skip unchanged versions.
5. Add conservative normalization hints and QC flags. No automated clinical mapping approval.
6. If quality gate succeeds (nonempty, <5% invalid records), upload all.csv/accepted.csv/review.csv/rejected.csv to immutable
   silver/v4/{source}/version={bronzeSha24}/. Upload manifest.json last and only then move silver/v4/{source}/latest.json.
7. If processing fails, leave the source's previous latest.json untouched. GitHub Actions fails with the source name in logs.

The workflow is in .github/workflows/pharmacy-silver-auto.yml, and also supports manual dry-run (Actions > Pharmacy Silver automatic R2 > Run workflow).
Weekly fallback is in addition to automatic workflow_run after Bronze completion.

**MEDI-2**: no 2020 auto-refresh. To enable ingestion from an independently verified newer MEDI-2 HPS file already present in bronze/medi_hps.csv, set GitHub Actions variable MEDI_HPS_APPROVED_RELEASE to its checked release ID. Newer release ingestion itself must be implemented/verified in Bronze first.

**What is NOT automated**: reconstructing official RxNorm SCD/SCDC component relations from the compact five-column Bronze source, mapping DAV to RxNorm with clinical verification, and asserting ICD-10-CM/ICD-10 Việt Nam equivalence. Those need the original evidence/relationship files and manual curation. Legacy raw rebuild scripts are manual-only and not invoked by this automated workflow.

**Storage**: each changed input produces a new version. R2 versions are not auto-deleted. Monitor bucket size/free tier and introduce retention only after backup and review.

## Run locally on R2
pip install 'boto3>=1.35,<2'
export R2_ACCOUNT_ID=...
export R2_ACCESS_KEY_ID=...
export R2_SECRET_ACCESS_KEY=...
python -m silver_auto.r2_runner --dry-run
python -m silver_auto.r2_runner --source dav

Never store secrets in code or commit them.
