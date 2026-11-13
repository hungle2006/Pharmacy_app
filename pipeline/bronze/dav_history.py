"""Classify source revisions separately from comparable declaration changes.

An UPDATE is a new *version of a source record*, not evidence of a new dated
declaration. Ingestion time must never be substituted for the source date.
"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata

IDENTITY = (
    "dav_registration_number", "dav_active_ingredient_raw", "dav_strength",
    "dav_dosage_form", "dav_manufacturer", "dav_country", "dav_package",
    "dav_unit", "dav_price_type", "dav_declaring_unit",
)
PRICE_FIELDS = ("dav_price_vnd", "dav_retail_price_vnd")


def normalized(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value or ""))).strip().casefold()


def source_date(row):
    value = str(row.get("dav_filing_date") or row.get("dav_publication_date") or "").strip()
    try:
        return date.fromisoformat(value[:10]) if re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value) else None
    except ValueError:
        return None


def money(value):
    try:
        result = Decimal(str(value).strip())
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, ValueError):
        return None


def comparison_key(row):
    values = tuple(normalized(row.get(k)) for k in IDENTITY)
    # Missing identity is not a license to merge unrelated products.
    return values if all(v and v not in ("n/a", "#n/a", "null", "-") for v in values) else None


def classify_snapshot(before, current):
    """Return audit counts only; preserve the original append-only Bronze schema.

Only a NEW source ID, a strictly later source date, exact comparable attributes,
and an unambiguous prior wholesale price can establish a declaration comparison.
"""
    counts = Counter()
    grouped = defaultdict(list)
    for row in before.values():
        key = comparison_key(row)
        if key and source_date(row) and money(row.get("dav_price_vnd")) is not None:
            grouped[key].append(row)
    for rid, row in current.items():
        old = before.get(rid)
        if old is not None:
            if old == row:
                counts["unchanged"] += 1
                continue
            identity_changed = any(normalized(old.get(k)) != normalized(row.get(k)) for k in IDENTITY)
            date_changed = any(str(old.get(k) or "") != str(row.get(k) or "")
                               for k in ("dav_declaration_date", "dav_filing_date", "dav_publication_date"))
            price_changed = any(
                (money(old.get(k)) != money(row.get(k))) or
                (money(old.get(k)) is None and normalized(old.get(k)) != normalized(row.get(k)))
                for k in PRICE_FIELDS
            )
            counts["source_record_revisions"] += 1
            if identity_changed: counts["identity_revision_review"] += 1
            if date_changed: counts["source_date_revision_review"] += 1
            if price_changed: counts["price_revision_review"] += 1
            if not (identity_changed or date_changed or price_changed):
                counts["metadata_only_revisions"] += 1
            continue
        counts["new_source_records"] += 1
        key, day, price = comparison_key(row), source_date(row), money(row.get("dav_price_vnd"))
        candidates = [r for r in grouped.get(key, []) if day and source_date(r) < day]
        if not candidates or price is None:
            counts["new_record_without_comparable_prior"] += 1
            continue
        latest_day = max(source_date(r) for r in candidates)
        prices = {money(r.get("dav_price_vnd")) for r in candidates if source_date(r) == latest_day}
        # A different ID at the same source date can be a duplicate/correction.
        same_day = any(source_date(r) == day for r in grouped.get(key, []))
        if len(prices) != 1 or same_day:
            counts["ambiguous_declaration_review"] += 1
        else:
            previous = next(iter(prices))
            counts["new_declaration_price_unchanged" if price == previous else
                   "new_declaration_price_changed"] += 1
    counts["missing_unverified"] = len(set(before) - set(current))
    return dict(sorted(counts.items()))
