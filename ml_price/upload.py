"""Publish approved ML models to R2; switch latest only after complete uploads."""
import json
import os
from pathlib import Path
import boto3

def upload(directory="models/price"):
    root = Path(directory)
    info = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    if info["status"] != "approved":
        raise RuntimeError("Model failed evaluation: publication denied")
    client = boto3.client("s3", endpoint_url=os.environ["ML_R2_ENDPOINT"].rstrip("/"),
                          aws_access_key_id=os.environ["ML_R2_ACCESS_KEY_ID"],
                          aws_secret_access_key=os.environ["ML_R2_SECRET_ACCESS_KEY"],
                          region_name="auto")
    bucket = os.environ["ML_R2_BUCKET"]
    prefix = f"ml/price/versions/{info['model_version']}"
    client.upload_file(str(root / "price_model.cbm"), bucket, prefix + "/price_model.cbm")
    client.upload_file(str(root / "metadata.json"), bucket, prefix + "/metadata.json")
    pointer = json.dumps({"model_version": info["model_version"], "prefix": prefix},
                         ensure_ascii=False).encode("utf-8")
    client.put_object(Bucket=bucket, Key="ml/price/latest.json", Body=pointer,
                      ContentType="application/json", CacheControl="no-cache")
    print("Published approved model version:", info["model_version"])

if __name__ == "__main__":
    upload()
