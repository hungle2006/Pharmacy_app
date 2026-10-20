# Full Pharmacy Silver v3 rebuild and QA

## Source -> tool -> desired output
| Tool | Raw input | Main output |
|---|---|---|
| DAV guarded normalizer | DAV raw CSV, optionally split-component CSV | dav_product_normalized_v2.csv, dav_component_normalized_v2.csv, DAV_Normalized_v2_for_RxNorm_Mapping.xlsx |
| RxNorm terminology normalizer | RxNorm raw XLSX | rxnorm_output.xlsx, rxnorm_scd_mapping_ready.csv |
| DAV to RxNorm guarded mapper | DAV normalized CSV + RxNorm terminology CSV | DAV_RxNorm_Mapping_Products.xlsx, DAV_RxNorm_Component_Evidence.xlsx |
| ICD-10 Vietnam normalizer | Official Vietnam ICD10 raw XLSX | ICD10_Vietnam_Normalized.xlsx |
| MEDI-2 HPS guarded normalizer | Current MEDI2 raw XLSX, not the 2020 release | MEDI-2_HPS_Normalized.xlsx |
| Silver quality audit | Six normalized workbooks | 4 CSV partitions per source, quality_summary.csv, manifest.json |

## Commands
- Raw rebuild: python -m silver_v3.rebuild_raw --dav-csv input/dav.csv --rxnorm-raw-xlsx input/rxnorm.xlsx --icd10-vietnam-raw-xlsx input/icd10_vietnam.xlsx --medi2-raw-xlsx input/medi2_new.xlsx --output-dir rebuilt
- Existing workbook QA: python -m silver_v3.pipeline --input-dir input --output-dir output
- Tests: python -m unittest discover -s tests -v

## GitHub integration
- Pharmacy Silver v3 Quality: Pull Requests automatically run tests; schedule defaults to dry-run.
- Pharmacy Rebuild Raw Sources: Disabled until repository variable PHARMACY_RAW_PIPELINE_ENABLED=true.
- R2 credentials in GitHub Secrets: R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY.
- Object keys in silver_v3/raw_keys.json and silver_v3/bronze_objects.json need to be replaced with verified values.
- Publishing requires manual workflow_dispatch publish=true. No Bronze deletion or clinical auto-verification.

## Limits
Not all raw source files were uploaded. These tools are provided and tested by unit tests; a true raw-to-rebuilt end-to-end execution on the production Bronze sources has not yet been run. The existing workbook QA was tested offline on six user-provided normalized XLSX files (234,004 rows). MEDI2 mapping from ICD10CM to ICD10 Vietnam is not presumed valid by numeric/text code equality alone; 2020 release is blocked from unattended refresh.
