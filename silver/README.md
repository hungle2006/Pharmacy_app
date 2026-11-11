# Pharmacy Silver (R2 + Cloud Run Jobs)
This module is isolated from the existing app and **does not modify Bronze**.
It produces immutable `silver/{source}/version={sha16}/part-00000.parquet` and
a manifest committed last. It deliberately does **not** infer clinical mappings.

## Setup
1. Confirm actual Bronze keys and formats, then edit `silver/sources.json`.
   Four entries are **templates**, not verified Bronze object locations.
   Unzip or convert source archives during Bronze ingestion, before this job.
2. Create Google Cloud project and enable Cloud Run, Artifact Registry,
   Cloud Build, IAM Credentials and STS APIs.
3. Create GCP service account with Cloud Run Job deployment/execution roles,
   an Artifact Registry writer identity for CI, and GitHub OIDC Workload Identity Federation.
4. Create R2 S3 API token scoped to this bucket; store keys in **Google Secret Manager**
   (not GitHub repository files). Grant the Cloud Run runtime service account
   access to the secrets.
5. Configure the GitHub Actions vars `GCP_PROJECT_ID`, `GCP_REGION`,
   `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `GCP_RUN_SA`, `R2_ENDPOINT`
   and configure Cloud Run Job secrets `AWS_ACCESS_KEY_ID` and
   `AWS_SECRET_ACCESS_KEY` with Secret Manager references.
6. Trigger workflow manually after Bronze completes; schedule is every Monday
   03:00 UTC. The workflow is off until required vars and GCP setup exist.

**Safety**: `DRY_RUN=true` by default. Never set it false before confirming
schemas, acceptable source versions, manifests and sampling records.
This initial job only supports uncompressed CSV and RXNCONSO.RRF. Larger
datasets may require streaming/chunking rather than whole-file Polars.
No PII should be ingested into this pipeline without additional controls.
