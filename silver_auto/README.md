# Pharmacy Silver: exactly one current CSV per source

## Cloudflare R2 output keys
- silver/dav.csv (only when bronze/dav.csv exists and validates)
- silver/icd10.csv
- silver/rxnorm.csv
- silver/medi_hps.csv (only after a verified new MEDI release is approved)

Each file contains the current effective Bronze rows, original fields, the normalized search fields and columns silver_qc_status, silver_qc_flags, and silver_mapping_verified. Review rows stay inside the same file: filter by silver_qc_status == REVIEW_REQUIRED. Clinical mapping is never auto-approved.

No silver/v4/ or per-version directories, no separate all/accepted/review/rejected copies. Each update overwrites the exact same CSV key in R2. Small JSON status records reside outside the Silver layer in _control/silver/{source}.json for SHA-256/checkpoint tracking. A rerun with unchanged Bronze SHA and unchanged pipeline code skips upload.

## Automatic triggers
GitHub Actions workflow .github/workflows/pharmacy-silver-auto.yml:
- Immediately after the existing "Pharmacy weekly Bronze ingestion" workflow finishes;
- Every Tuesday at 05:00 UTC (12:00 Vietnam) as a catch-up;
- After a Silver code/workflow change is merged to main;
- Manually on GitHub Actions with a source selector and dry_run option.

Reuses the existing R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY secrets. No Google Cloud. Missing DAV Bronze is reported as skipped, not invented; MEDI-2 2020 and unverified releases remain skipped.

## Integrity and retention
1. Verify per-event __row_hash and replay INSERT/UPDATE/REMOVE to reconstruct current rows.
2. Refuse to publish empty output or when >5% of rows are invalid by the current syntactic rules.
3. Upload silver/{source}.csv with SHA256 metadata, verify object length and SHA256 metadata, then commit the tiny _control/silver/{source}.json checkpoint.
4. After successful verification, --cleanup-legacy deletes only that source's legacy silver/{source}/..., silver/v3/{source}/..., and silver/v4/{source}/... prefixes; **never touches Bronze** or other data sources.
5. If a source cannot be published, its previous Silver CSV is not deliberately deleted. Uploads overwrite the same R2 object; retaining historical copies is not a feature of this compact storage policy. Keep external backup if historical recovery is required.

The workflow automatically uses --cleanup-legacy. One CSV per source means per-run history is not retained; for reproducibility check the Bronze cumulative history and GitHub commit SHA. Existing legacy version folders will be deleted irreversibly after compact replacements are verified.

## Manual use
python -m unittest discover -s tests -p 'test_silver_auto.py' -v
python -m unittest discover -s tests -p 'test_silver_r2_runner.py' -v
python -m silver_auto.r2_runner --dry-run --cleanup-legacy
python -m silver_auto.r2_runner --source rxnorm --cleanup-legacy

## Deliberately not done here
This pipeline does not fabricate full RxNorm SCD/SCDC semantic relationships from Bronze's five-column terminology CSV, or auto-certify mappings DAV to RxNorm and ICD10CM to WHO ICD10 Vietnam. Original evidence files are required to rebuild those products. 
