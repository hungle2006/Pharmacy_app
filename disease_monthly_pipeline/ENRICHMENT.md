# Monthly source-backed disease enrichment

The existing monthly training pipeline now refreshes the dataset on CPU **before** pinning its training snapshot. A separate `Disease dataset - source enrichment` workflow also supports manual execution and runs after enrichment code/config/source changes on main. The dedicated enrichment workflow waits for the bounded CPU-only Modal job and verifies its publication result; the separate training workflow continues to submit long GPU work in the background. No new ChatGPT automation or external monitor is required.

## Storage and secrets

- Reuses Modal Secret `disease-training` with `HF_TOKEN`, authorized to write `leminhhung0101/disease_data`.
- Optional `FIRECRAWL_API_KEY` in that same secret enables bounded web discovery. The ChatGPT Firecrawl connection does not automatically provision this key in Modal. Without it, reviewed seed URLs still refresh through direct HTTP, subject to robots.txt.
- Keeps exactly one dataset file: `disease_train_ready.parquet`, overwritten atomically at HEAD. Does not create train shards named by month. Hugging Face still retains normal Git/LFS revision history; replacing a filename does not erase historical storage.
- Two small overwritten metadata files accompany it: `enrichment_state.json` (page hashes, ingestion state, bounded review queue) and `enrichment_report.json` (train counts and deficits before/after, accepted/rejected counts). Both are excluded from Parquet scans automatically.
- No schema guessing or destructive shard consolidation: if the repo contains more than one Parquet, refresh stops for explicit review.

## What is automated

`enrichment_config.json` targets 100 **train** observations per label, prioritizes largest deficits, caps discovery at 200 labels / 2 results each and actual source reads at 80 pages, with at most 80 accepted observations per run. These are acquisition budgets, not a promise of balanced data. It retains existing observations and never undersamples, repeats examples, generates paraphrases or fabricates clinical cases to meet quotas.

`crawl_sources.json` binds a verified page title + symptom section to exact existing label aliases, document type, language and reuse conditions. Only one unambiguous existing label is allowed. This is deterministic source-backed classification, not model self-labelling. A discovered title, fuzzy match or LLM guess does not approve a medical label. Discovery results enter the metadata review queue; they are not patient examples and never become training data automatically without a reviewed page/label/rights mapping.

Source seed inspection found a usable severe-symptom list for `Ngộ Độc Thực Phẩm` (11 train observations before refresh). A cholera demonstration source is retained as an example but is skipped when no exact label exists. One eligible excerpt does **not** balance all 178 low-count labels. The remaining deficits are explicitly reported so appropriate, reusable source material can be added rather than manufacturing hundreds of copies.

## Quality checks

- HTTPS hostname allowlist and checked redirects; no arbitrary discovered hosts, embedded URL credentials or custom ports. Direct fetch respects robots.txt, bounded sizes, timeouts and crawl delays.
- Exact title and configured symptom-list section required; excludes navigation, images, captions, treatment sections and diagnostic answers. Preserves wording instead of generating first-person symptom descriptions.
- One independent observation per canonical source page, including when page text changes. Edits are not counted as new clinical cases.
- Exact normalized and conservative trigram-Jaccard near-duplicate checks against **all** existing rows, including validation/test and other labels. Cross-language and semantic duplicates are not exhaustively detected.
- No target disease names/aliases in inputs; explicit source metadata records URL, retrieval time, page hash, label assignment method, content kind and reuse notice.
- Knowledge excerpts remain marked as knowledge, not patient records. Their impact on real patient-text classification needs separate evaluation by source and language.
- Original train rows remain intact. Validation/test values, labels, groups and splits are preserved byte-for-value at the row level. The existing benchmark registry also checks holdout leakage before training.
- Upload uses HF `parent_commit` compare-and-swap: a concurrent dataset update aborts rather than overwriting newer data. Modal training and refresh share a distributed lock. Never retry a conflicting commit blindly.

## Sources and reuse

CDC policy: https://www.cdc.gov/other/agencymaterials.html — most CDC information is public domain but exceptions apply. Only reviewed CDC-authored text is selected, not third-party photographs, captions, logos or other protected content. Preserve the attribution and non-endorsement notice in every new record. Public availability alone is not an unrestricted dataset licence. Other sources require their own explicit policy and page-level review before being added to the allowlist and accepted-source registry.

Seed: https://www.cdc.gov/food-safety/signs-symptoms/index.html — `Food Poisoning Symptoms`, section `Seek help`. Its severe-symptom text is used as a knowledge excerpt, not an observed patient history.

## Operating

1. Deploy the updated Modal app (workflows do this automatically).
2. Inspect Modal `refresh_dataset` call and HF `enrichment_report.json` after completion. No-change runs in the same month/config/master hash are idempotent; failed downloads remain retryable.
3. Review unresolved source URLs and label taxonomy, then add verified mappings to `crawl_sources.json`. Changes on main trigger bounded refresh. Never auto-merge suspected synonyms such as Alzheimer/Azheimer when they are separate current classes; that requires a new benchmark version.
4. Monthly training calls refresh first, then pins the new HF commit. Do not use validation/test to select data acquisition targets or edit test labels to raise accuracy.

Local dry run (no HF write unless `--publish`):

```bash
python enrichment.py --output /tmp/disease-enrichment
python enrichment.py --output /tmp/disease-enrichment --publish
python -m pytest tests/test_enrichment.py
```

Runtime reports must distinguish `accepted` from discovery results and remaining deficits. Neither a successful crawl nor more rows demonstrates better model performance. Only a new held-out evaluation can establish improvement.
