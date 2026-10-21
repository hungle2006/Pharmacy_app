"""Publish only independently approved price segment models to private R2.

Every model uploads before the global registry pointer is replaced. The legacy
single-unit latest.json is not touched, preserving the known-good model.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from ml_price.segments import segment_id

CATALOG_KEY = "ml/price/catalog/latest.json"

def upload_catalog(directory="models/price"):
    root = Path(directory)
    report = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    approved = [x for x in report["segments"] if x["status"] == "approved"]
    if not approved:
        print("NO_APPROVED_SEGMENTS: R2 registry remains unchanged")
        return 0
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["ML_R2_ENDPOINT"].rstrip("/"),
        aws_access_key_id=os.environ["ML_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["ML_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    bucket = os.environ["ML_R2_BUCKET"]
    published = []
    for item in approved:
        identifier = item["id"]
        if identifier != segment_id(item["price_type"], item["unit"]):
            raise RuntimeError("Catalog segment identifier mismatch")
        folder = root / "segments" / identifier
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        if (metadata["status"] != "approved" or
            metadata["model_version"] != item["model_version"] or
            metadata["price_type"] != item["price_type"] or metadata["unit"] != item["unit"]):
            raise RuntimeError("Unapproved or inconsistent segment metadata: " + identifier)
        prefix = f"ml/price/catalog/segments/{identifier}/versions/{metadata['model_version']}"
        client.upload_file(str(folder / "price_model.cbm"), bucket, prefix + "/price_model.cbm")
        client.upload_file(str(folder / "metadata.json"), bucket, prefix + "/metadata.json")
        published.append({
            "id": identifier, "price_type": item["price_type"], "unit": item["unit"],
            "model_version": metadata["model_version"], "prefix": prefix,
            "n_distinct_products": metadata["n_distinct_products"], "n_test": metadata["n_test"],
            "mae_vnd": metadata["metrics"]["mae_vnd"],
            "mae_gain_fraction": metadata["mae_gain_fraction"],
        })
        print("R2 segment uploaded:", item["price_type"], "/", item["unit"], flush=True)
    registry = {
        "schema_version": 1,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "segments": published,
        "approved_segments": len(published),
        "evaluated_segments": report["evaluated_segments"],
        "insufficient_segments": report["insufficient_segments"],
        "rejected_segments": report["rejected_segments"],
    }
    # Switch to the complete new catalog only after all approved artifacts exist.
    client.put_object(Bucket=bucket, Key=CATALOG_KEY,
                      Body=json.dumps(registry, ensure_ascii=False).encode("utf-8"),
                      ContentType="application/json", CacheControl="no-cache")
    print("Published price model catalog", len(published), "approved segments")
    return len(published)

if __name__ == "__main__":
    upload_catalog()
