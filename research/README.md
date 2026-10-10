# EDA — Nine Vietnamese Patient Symptom Datasets

This folder contains a **complete reproducible EDA workflow** for the exact nine filenames supplied in ChatGPT. No content has been fabricated.

## Status
- The ChatGPT container runtime failed while mounting the large attached binary Parquet/ZIP files. The notebook and script have been created, but **results for the 8 binary files have NOT been executed or verified** in this session.
- `ViMedical_Disease.csv` is readable by the ChatGPT file service and was summarized earlier; its metrics should be reproduced and verified again by the program.
- The script inventories ZIP members and captures processing errors instead of silently claiming coverage.

## Inputs (exact names)
- train-00000-of-00001.parquet
- train.parquet
- train (1).parquet
- train (2).parquet
- train (3).parquet
- ViMedical_Disease.csv
- Corpus_Redone.zip
- Question_for_dataset.zip
- Corpus.zip

## Run in Colab
1. Place all nine uploaded files in **one** Google Drive folder, e.g. `MyDrive/PatientSymptomDatasets`. Retain the exact names, including `(1)`, `(2)`, `(3)`.
2. Open `research/Patient_Symptom_9Datasets_EDA.ipynb` from GitHub in Colab.
3. Run the cells, mount Drive and set `INPUT_DIR`.
4. The notebook downloads this repo's script from the research branch, executes it over the whole folder and displays the resulting CSV/PNG/Markdown reports.
5. It packages all published aggregates into `Patient_Symptom_9Datasets_EDA_Results.zip`.

## Run on a local machine
```bash
pip install pandas pyarrow matplotlib numpy openpyxl
python research/eda_all_datasets.py --input-dir "./all_uploaded_files" --output-dir "./eda_output"
```

The script reads Parquet in 2,500-row batches and uses an on-disk SQLite database of **hashes**, not verbatim text, to measure exact duplicates and cross-source overlap.

## Outputs
- `overall_report.md`: complete auto-generated EDA summary
- `source_metrics.csv`: per-file row counts, unique texts, missing texts, PII flags and boilerplate rates
- `zip_members.csv`: all ZIP members, supported/unsupported/failed status and record count
- `column_completeness.csv`: detected schemas and null rates
- `disease_labels.csv`: labels and frequency
- `symptom_keyword_heuristics.csv`: keyword mentions (NOT clinically labeled symptoms)
- `cross_source_overlap.csv`: exact normalized-text overlaps between sources
- `errors.csv`: parser issues
- `source_record_counts.png`, `duplicate_rates.png`, `top_symptom_keyword_mentions.png`
- `text_presence.sqlite3`: intermediate database containing only 128-bit text hashes and labels

## Important scientific limitations
- A repeated narrative under multiple diseases can be genuinely ambiguous; it is not automatically a wrong label.
- Train/validation/test splits must group exact or near-duplicate narratives.
- Synthetic and authentic patient narratives must be separated using **provenance**, never inferred merely from text style.
- Raw patient texts may include personal health information. Do not upload raw texts into the public PharmaBiz dashboard.
- This EDA is **not** a classifier, clinical diagnosis, medical prescription tool or epidemiological estimate.
- For unsupported ZIP members, consult `zip_members.csv` and add an explicitly approved parser instead of pretending those entries were processed.
