# Pharmacy Silver v3: source workbook audit / R2
This quality gate does not regenerate original normalizations because raw source datasets were not all uploaded. It reads six provided normalized workbooks and preserves all input columns in CSV.

## Required workbooks
- DAV_Normalized_v2_for_RxNorm_Mapping.xlsx -> DAV_COMPONENT
- DAV_RxNorm_Mapping_11834_Products.xlsx -> DAV_RXNORM_MAPPING
- DAV_RxNorm_Component_Evidence_14844.xlsx -> COMPONENT_EVIDENCE
- rxnorm_output.xlsx -> 00_Clean_Normalized
- ICD10_Vietnam_Normalized.xlsx -> first sheet
- MEDI-2_HPS_Normalized.xlsx -> first sheet

## Run
python -m unittest discover -s tests -v
python -m silver_v3.pipeline --input-dir ./input --output-dir ./output

Artifacts: each dataset has all.csv, accepted.csv, review.csv, rejected.csv; root has quality_summary.csv and manifest.json. No new RxCUI links are invented. Existing VERIFIED_SCD labels remain visible in original fields but are not automatic clinical approval.

## GitHub Actions
PRs execute Python tests. Mondays at 03:15 UTC run in dry-run mode once this workflow is merged into the default branch. Manual workflow_dispatch with publish=true is the only publishing path.

Before triggering R2 processing:
1. Fill silver_v3/bronze_objects.json with six exact verified source object paths beginning bronze/.
2. Configure GitHub Secrets R2_ENDPOINT, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY with least-privilege R2 token scoped to pharmacy-data-lake.
3. Review first dry-run, then approve publication.

Publishes immutable silver/v3/run=HASH/ paths, then latest.json. Does not delete Bronze, replace source rows, claim clinical certainty, or require Google Cloud Run.

Important: the uploaded icd10.xlsx contains English terms, not a substitute for raw Vietnam ICD. The uploaded test.py is a PPT-to-PPTX utility unrelated to Pharmacy.
