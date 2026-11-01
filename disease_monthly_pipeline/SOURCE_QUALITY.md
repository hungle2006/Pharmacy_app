# Source acquisition and custom evaluation

## Evidence reviewed through Firecrawl

| Source | Primary evidence | Decision |
| --- | --- | --- |
| Gretel symptom_to_diagnosis | https://huggingface.co/datasets/gretelai/symptom_to_diagnosis ; Apache-2.0; 853 train / 212 test; 22 labels; source explicitly says LLM-modified descriptions | Limited supplemental synthetic train source. Reviewed exact crosswalk for 8 existing broad labels, capped at 25 examples per label and the 100-train target. Original source test is excluded, and similar source-test examples are rejected. |
| DDXPlus, Mila / NeurIPS | https://github.com/mila-iqia/ddxplus ; CC-BY; synthetic patients, evidence codes, ICD codes and differential diagnoses | Stronger structured research candidate, not imported into free-text train yet. Requires an evidence adapter preserving negation/categorical meanings and a reviewed ICD-to-label mapping. Figshare retrieval returned 403 in this session. |
| Disease and symptoms dataset 2023, Mendeley | https://data.mendeley.com/datasets/2cxccsxydc/1 ; CC BY 4.0; contributor describes artificially generated symptom combinations, 773 diseases | Not automatically admitted. Many rows of symptom combinations do not establish independent patient cases or clinical label quality. |
| ViMedical_Disease | https://github.com/PB3002/ViMedical_Disease | Already part of the current dataset provenance. Downloading it again is not new data; existing deduplication and label-conflict concerns apply. |
| CDC symptom pages | https://www.cdc.gov/other/agencymaterials.html | Knowledge-only excerpts under reviewed page/rights mappings; not patient cases. |

No source is called clinically validated merely because its publisher is reputable or its licence permits reuse. Large row counts are not evidence of independent observations, and no acquisition guarantees a model accuracy target.

## Admission and taxonomy

Published-source versions are pinned and licence metadata is checked. English text remains English: the tool does not invent Vietnamese translations or label synonyms. It checks text length, target-name leakage, original-source train/test proximity, existing exact/near duplicates across all splits, source quota and training deficit before admission. Source labels remain explicitly marked as synthetic source-provided labels. Semantic and cross-language near duplicates remain a limitation.

The reviewed mapping deliberately avoids assigning generic diabetes to type 1/type 2 and avoids mapping broad pneumonia to stage/pathogen-specific classes. Current labels such as `Hen Suyễn`, `Hen suyển` and `Hen phế quản` need taxonomy review; no holdout labels or IDs are silently merged. A canonicalised benchmark requires a new version and a new baseline.

Acquisition targets use TRAIN counts only. Test errors must not choose which test answers or near-identical examples to add to training. The 100-example target is an acquisition goal, not a scientifically validated sufficiency threshold.

## Custom evaluation exported on the next training run

`diagnostics.json` contains, separately for validation and test:

- Accuracy, Macro-F1 and balanced accuracy, with sample counts.
- Vietnamese / English / unknown language slices.
- Source-kind slices when provenance is present; unknown remains unknown. Existing frozen holdouts may lack source-kind metadata, so this is not an independent source-held-out benchmark.
- Performance on labels with fewer than 20, 20–49, and at least 50 TRAIN observations.
- The 50 most frequent true-label → predicted-label errors and labels with zero recall.
- A majority-class baseline selected from TRAIN only.
- Uncalibrated confidence bins and ECE. No probability calibration or automatic treatment decision is implied.

`training_history.json` exports epoch loss and evaluation history. Both are uploaded with the immutable model release. No raw symptom text is included in diagnostic outputs.

Use validation to select models and thresholds, then evaluate test once for a final experiment. Keep the full 1,400-class benchmark when reporting current task accuracy; any reduced-label experiment must have its own scope, label count and baseline. Do not inflate scores by excluding difficult labels after examining test errors.

There is no measured post-enrichment accuracy yet. Do not replace the currently served model merely because data acquisition succeeded. Existing validation-regression protection remains active.

## Training activation and promotion

A successful source refresh with actual new rows submits one background training call; no-change refreshes do not start another GPU run. The existing monthly pipeline remains idempotent by month/config/data signature. The candidate exports custom diagnostics and epoch history. Minimum validation Macro-F1 is now 0.20, an initial research engineering gate (not clinical certification), and regression protection remains active. Candidates below the gate stay archived and do not replace the active model. No accuracy improvement is promised before evaluation.
