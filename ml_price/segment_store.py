"""Lazy-loading cache for independently quality-gated R2 price models."""
import json
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from tempfile import gettempdir

import boto3
from catboost import CatBoostRegressor

from ml_price.constants import FEATURES
from ml_price.segments import canonical, segment_id
from ml_price.upload_catalog import CATALOG_KEY

class SegmentModelStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.checked_at = 0.0
        self.registry = {}
        self.models = OrderedDict()
        self.max_models = 6

    @staticmethod
    def s3():
        values = [os.getenv(name, "") for name in
                  ("ML_R2_ENDPOINT", "ML_R2_BUCKET", "ML_R2_ACCESS_KEY_ID", "ML_R2_SECRET_ACCESS_KEY")]
        if not all(values):
            return None, None
        endpoint, bucket, access, secret = values
        client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access,
                              aws_secret_access_key=secret, region_name="auto")
        return client, bucket

    def refresh(self):
        if time.monotonic() - self.checked_at < 300:
            return
        with self.lock:
            if time.monotonic() - self.checked_at < 300:
                return
            self.checked_at = time.monotonic()
            s3, bucket = self.s3()
            if s3 is None:
                return
            try:
                raw = s3.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
                manifest = json.loads(raw)
                if manifest.get("schema_version") != 1:
                    raise ValueError("Incompatible segment registry")
                catalog = {}
                for entry in manifest["segments"]:
                    identifier = segment_id(entry["price_type"], entry["unit"])
                    if identifier != entry["id"] or not entry["prefix"].startswith(
                            f"ml/price/catalog/segments/{identifier}/versions/"):
                        raise ValueError("Invalid segment registry entry")
                    catalog[identifier] = entry
                self.registry = catalog
                # Old cached versions may be served until the next request; invalidate
                # immediately if a new version is published to prevent stale responses.
                for key in list(self.models):
                    if key not in catalog or self.models[key][0] != catalog[key]["model_version"]:
                        del self.models[key]
            except Exception as exc:
                print("Catalog refresh unavailable:", type(exc).__name__, flush=True)

    def available(self):
        self.refresh()
        return sorted([
            {key: item[key] for key in
             ("price_type", "unit", "model_version", "n_distinct_products", "mae_vnd", "mae_gain_fraction")}
            for item in self.registry.values()
        ], key=lambda x: (x["price_type"], x["unit"]))

    def get(self, price_type, unit):
        self.refresh()
        try:
            identifier = segment_id(price_type, unit)
        except ValueError:
            return None, None
        with self.lock:
            entry = self.registry.get(identifier)
            if entry is None:
                return None, None
            cache = self.models.get(identifier)
            if cache and cache[0] == entry["model_version"]:
                self.models.move_to_end(identifier)
                return cache[1], cache[2]
            s3, bucket = self.s3()
            if s3 is None:
                return None, None
            try:
                prefix = entry["prefix"]
                metadata = json.loads(s3.get_object(Bucket=bucket, Key=prefix + "/metadata.json")["Body"].read())
                if (metadata.get("status") != "approved" or
                    metadata.get("features") != FEATURES or
                    metadata.get("model_version") != entry["model_version"] or
                    canonical(metadata.get("price_type")) != canonical(price_type) or
                    canonical(metadata.get("unit")) != canonical(unit)):
                    raise ValueError("Segment model metadata rejected")
                path = Path(gettempdir()) / ("pharmabiz_segment_" + identifier + "_" + entry["model_version"] + ".cbm")
                try:
                    path.write_bytes(s3.get_object(Bucket=bucket, Key=prefix + "/price_model.cbm")["Body"].read())
                    model = CatBoostRegressor()
                    model.load_model(str(path))
                finally:
                    path.unlink(missing_ok=True)
                self.models[identifier] = (entry["model_version"], model, metadata)
                self.models.move_to_end(identifier)
                while len(self.models) > self.max_models:
                    self.models.popitem(last=False)
                return model, metadata
            except Exception as exc:
                print("Segment model unavailable:", identifier, type(exc).__name__, flush=True)
                return None, None

catalog_store = SegmentModelStore()
