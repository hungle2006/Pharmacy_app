"""Canonical price segment identifiers shared by training, upload and inference."""
import hashlib
import unicodedata

def canonical(value):
    return unicodedata.normalize("NFC", str(value or "")).strip().casefold()

def segment_id(price_type, unit):
    p, u = canonical(price_type), canonical(unit)
    if not p or not u:
        raise ValueError("Price type and unit must be nonempty")
    return hashlib.sha256((p + "\0" + u).encode("utf-8")).hexdigest()[:20]
