#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RXNORM XLSX CLEAN -> NORMALIZE -> SPLIT TOOL
===========================================

Mục tiêu
--------
Đọc trực tiếp file .xlsx RxNorm, sau đó:
1. Clean text.
2. Chuẩn hóa RxCUI, TTY, SAB.
3. Giữ nguyên các RxCUI trùng hợp lệ.
4. Đánh dấu exact duplicate thay vì xóa.
5. Tách dữ liệu theo vai trò TTY.
6. Tạo quan hệ:
      SCD -> SCDC -> IN/PIN
      SCD -> DF
   bằng EXACT matching, KHÔNG fuzzy-auto-verify.
7. Xuất tất cả kết quả vào 1 file Excel nhiều sheet.

Yêu cầu cột đầu vào tối thiểu
-----------------------------
normalized_name
rxcui
display_name
tty
sab

Cách chạy
---------
python rxnorm_xlsx_clean_normalize_split.py rxnorm.xlsx rxnorm_output.xlsx

Chọn sheet nguồn:
python rxnorm_xlsx_clean_normalize_split.py rxnorm.xlsx rxnorm_output.xlsx --sheet Sheet1

Nếu không truyền --sheet, tool dùng sheet đầu tiên.

Cài thư viện
------------
pip install openpyxl
"""

from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


# =============================================================================
# CONFIG
# =============================================================================

REQUIRED_COLUMNS = {"normalized_name", "rxcui", "display_name", "tty", "sab"}

INGREDIENT_TTYS = {"IN", "PIN", "MIN"}
CLINICAL_TTYS = {"SCD"}
COMPONENT_TTYS = {"SCDC"}
DOSE_FORM_TTYS = {"DF", "DFG", "SCDF", "SCDFP", "SCDG", "SCDGP"}
BRAND_TTYS = {"BN", "SBD", "SBDC", "SBDF", "SBDFP", "SBDG", "SBDGP"}
PACK_TTYS = {"GPCK", "BPCK"}
ALIAS_TTYS = {"PSN", "SY", "TMSY", "DP", "MTH_RXN_DP", "SU", "PT"}

SHEET_NAMES = {
    "clean": "00_Clean_Normalized",
    "ingredient": "01_Ingredient",
    "scdc": "02_Component_SCDC",
    "scd": "03_Clinical_Drug_SCD",
    "dose_form": "04_Dose_Form",
    "scd_component": "05_SCD_Component_Rel",
    "scd_df": "06_SCD_Dose_Form_Rel",
    "brand": "07_Brand",
    "pack": "08_Pack",
    "alias": "09_Alias",
    "other": "10_Other_TTY",
    "tty_dist": "11_TTY_Distribution",
    "quality": "12_Quality_Summary",
    "review": "13_Review_Queue",
}


# =============================================================================
# CLEAN / NORMALIZE
# =============================================================================

def clean_text(value) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFC", str(value))
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060"):
        s = s.replace(ch, "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_rxcui(value) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def search_norm(value: str) -> str:
    """
    Chuẩn hóa phục vụ search/candidate generation.
    Không thay thế tên gốc.
    """
    s = clean_text(value).casefold()
    s = s.replace("µ", "u").replace("μ", "u")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z0-9%/+.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def exact_key(value: str) -> str:
    return clean_text(value).casefold()


def row_hash(parts) -> str:
    payload = "\x1f".join(clean_text(x) for x in parts).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=12).hexdigest()


def normalize_header(value: str) -> str:
    s = clean_text(value).casefold()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    aliases = {
        "rx_cui": "rxcui",
        "rxnorm_rxcui": "rxcui",
        "displayname": "display_name",
        "display_name": "display_name",
        "str": "display_name",
        "term": "display_name",
        "normalizedname": "normalized_name",
        "normalized_name": "normalized_name",
        "name_normalized": "normalized_name",
        "source_abbreviation": "sab",
        "source": "sab",
        "term_type": "tty",
    }
    return aliases.get(s, s)


def dedupe_exact(rows: list[dict], keys: list[str]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = tuple(row.get(k, "") for k in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


# =============================================================================
# EXACT STRUCTURAL PARSING
# =============================================================================

def longest_suffix_match(text: str, names: list[str]) -> str:
    t = exact_key(text)
    for name in names:
        n = exact_key(name)
        if t == n or t.endswith(" " + n):
            return name
    return ""


def build_ingredient_prefix_index(records: list[dict]):
    index = defaultdict(list)
    for rec in records:
        key = exact_key(rec["ingredient_name"])
        first = key.split(" ", 1)[0] if key else ""
        index[first].append(rec)

    for first in index:
        index[first].sort(
            key=lambda x: len(x["ingredient_name"]),
            reverse=True
        )
    return index


def longest_prefix_record(text: str, index) -> dict | None:
    t = exact_key(text)
    first = t.split(" ", 1)[0] if t else ""

    for rec in index.get(first, []):
        n = exact_key(rec["ingredient_name"])
        if t == n or t.startswith(n + " "):
            return rec
    return None


def strip_quantity_prefix(text: str) -> str:
    """
    Chỉ bỏ quantity factor rất rõ.
    Không chắc -> giữ nguyên -> REVIEW.
    """
    s = clean_text(text)
    patterns = [
        r"^\d+(?:\.\d+)?\s+(?:ML|L|MG|G|GM|MCG|UG|IU|UNIT|UNITS)\s+",
        r"^\d+(?:\.\d+)?\s+(?:TABLET|TABLETS|CAPSULE|CAPSULES|ACTUATION|ACTUATIONS)\s+",
    ]
    for pattern in patterns:
        new = re.sub(pattern, "", s, flags=re.I).strip()
        if new != s:
            return new
    return s


# =============================================================================
# XLSX INPUT
# =============================================================================

def read_xlsx_rows(input_xlsx: Path, sheet_name: str | None):
    wb = load_workbook(input_xlsx, read_only=True, data_only=True)

    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"Không tìm thấy sheet '{sheet_name}'. "
                f"Các sheet hiện có: {wb.sheetnames}"
            )
        ws = wb[sheet_name]
    else:
        ws = wb[wb.sheetnames[0]]

    iterator = ws.iter_rows(values_only=True)

    try:
        raw_headers = next(iterator)
    except StopIteration:
        raise ValueError("Sheet Excel không có dữ liệu.")

    headers = [normalize_header(x) for x in raw_headers]

    if len(headers) != len(set(headers)):
        dup = [h for h in headers if headers.count(h) > 1]
        raise ValueError(f"Header bị trùng sau chuẩn hóa: {sorted(set(dup))}")

    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValueError(
            f"Thiếu cột bắt buộc: {sorted(missing)}. "
            f"Header hiện có: {headers}"
        )

    idx = {h: i for i, h in enumerate(headers)}

    cleaned_rows = []
    quality = Counter()
    exact_seen = Counter()

    for source_row_id, values in enumerate(iterator, start=2):
        quality["input_rows"] += 1

        rxcui = normalize_rxcui(
            values[idx["rxcui"]] if idx["rxcui"] < len(values) else ""
        )
        tty = clean_text(
            values[idx["tty"]] if idx["tty"] < len(values) else ""
        ).upper()
        sab = clean_text(
            values[idx["sab"]] if idx["sab"] < len(values) else ""
        ).upper()
        display_name = clean_text(
            values[idx["display_name"]] if idx["display_name"] < len(values) else ""
        )
        normalized_name = clean_text(
            values[idx["normalized_name"]] if idx["normalized_name"] < len(values) else ""
        )

        if not any((rxcui, tty, sab, display_name, normalized_name)):
            quality["empty_rows_removed"] += 1
            continue

        if not rxcui:
            quality["missing_rxcui"] += 1
        elif not rxcui.isdigit():
            quality["non_numeric_rxcui"] += 1

        if not tty:
            quality["missing_tty"] += 1
        if not sab:
            quality["missing_sab"] += 1
        if not display_name:
            quality["missing_display_name"] += 1

        semantic_hash = row_hash(
            [rxcui, tty, sab, display_name, normalized_name]
        )
        exact_seen[semantic_hash] += 1

        is_exact_duplicate = exact_seen[semantic_hash] > 1
        if is_exact_duplicate:
            quality["exact_duplicate_rows_preserved"] += 1

        cleaned_rows.append({
            "source_row_id": source_row_id,
            "rxcui": rxcui,
            "tty": tty,
            "sab": sab,
            "display_name": display_name,
            "normalized_name_source": normalized_name,
            "display_name_norm": search_norm(display_name),
            "normalized_name_norm": search_norm(
                normalized_name or display_name
            ),
            "row_hash": semantic_hash,
            "exact_duplicate_flag": "1" if is_exact_duplicate else "0",
        })

    quality["clean_rows"] = len(cleaned_rows)
    quality["unique_rxcui"] = len(
        {r["rxcui"] for r in cleaned_rows if r["rxcui"]}
    )
    quality["unique_tty"] = len(
        {r["tty"] for r in cleaned_rows if r["tty"]}
    )
    quality["unique_sab"] = len(
        {r["sab"] for r in cleaned_rows if r["sab"]}
    )

    wb.close()
    return cleaned_rows, quality, ws.title


# =============================================================================
# SPLIT PIPELINE
# =============================================================================

def build_outputs(rows: list[dict], quality: Counter):
    canonical = [r for r in rows if r["sab"] == "RXNORM"]

    # -------------------------------------------------------------------------
    # 1. INGREDIENT
    # -------------------------------------------------------------------------
    ingredient = []

    for r in canonical:
        if r["tty"] in INGREDIENT_TTYS:
            ingredient.append({
                "ingredient_rxcui": r["rxcui"],
                "ingredient_name": r["display_name"],
                "ingredient_name_norm": r["display_name_norm"],
                "ingredient_tty": r["tty"],
                "sab": r["sab"],
            })

    ingredient = dedupe_exact(
        ingredient,
        ["ingredient_rxcui", "ingredient_name", "ingredient_tty", "sab"],
    )

    ingredient_match = [
        r for r in ingredient
        if r["ingredient_tty"] in {"IN", "PIN"}
    ]
    ingredient_match.sort(
        key=lambda x: len(x["ingredient_name"]),
        reverse=True,
    )
    ingredient_prefix_index = build_ingredient_prefix_index(
        ingredient_match
    )

    # -------------------------------------------------------------------------
    # 2. SCDC
    # -------------------------------------------------------------------------
    scdc = []

    for r in canonical:
        if r["tty"] != "SCDC":
            continue

        rec = longest_prefix_record(
            r["display_name"],
            ingredient_prefix_index,
        )

        if rec:
            strength = clean_text(
                r["display_name"][len(rec["ingredient_name"]):]
            )
            parse_status = "EXACT_INGREDIENT_PREFIX"
            ing_rxcui = rec["ingredient_rxcui"]
            ing_name = rec["ingredient_name"]
            ing_tty = rec["ingredient_tty"]
        else:
            strength = ""
            parse_status = "REVIEW"
            ing_rxcui = ""
            ing_name = ""
            ing_tty = ""

        scdc.append({
            "scdc_rxcui": r["rxcui"],
            "scdc_name": r["display_name"],
            "ingredient_rxcui": ing_rxcui,
            "ingredient_name": ing_name,
            "ingredient_tty": ing_tty,
            "strength_text": strength,
            "parse_status": parse_status,
            "sab": r["sab"],
        })

    scdc = dedupe_exact(
        scdc,
        ["scdc_rxcui", "scdc_name"],
    )

    scdc_lookup = {
        exact_key(r["scdc_name"]): r["scdc_rxcui"]
        for r in scdc
    }

    # -------------------------------------------------------------------------
    # 3. DOSE FORM
    # -------------------------------------------------------------------------
    dose_form = []
    canonical_df_names = []
    df_rxcui_by_name = {}

    for r in canonical:
        if r["tty"] in DOSE_FORM_TTYS:
            role = (
                "CANONICAL_DOSE_FORM"
                if r["tty"] in {"DF", "DFG"}
                else "DOSE_FORM_SUPPORT"
            )

            dose_form.append({
                "rxcui": r["rxcui"],
                "display_name": r["display_name"],
                "display_name_norm": r["display_name_norm"],
                "tty": r["tty"],
                "sab": r["sab"],
                "role": role,
            })

            if r["tty"] == "DF":
                canonical_df_names.append(r["display_name"])
                df_rxcui_by_name[r["display_name"]] = r["rxcui"]

    dose_form = dedupe_exact(
        dose_form,
        ["rxcui", "display_name", "tty", "sab"],
    )

    canonical_df_names = sorted(
        set(canonical_df_names),
        key=len,
        reverse=True,
    )

    # -------------------------------------------------------------------------
    # 4. SCD + RELATIONS
    # -------------------------------------------------------------------------
    clinical = []
    scd_component_rel = []
    scd_df_rel = []

    for r in canonical:
        if r["tty"] != "SCD":
            continue

        scd_rxcui = r["rxcui"]
        scd_name = r["display_name"]

        df_name = longest_suffix_match(
            scd_name,
            canonical_df_names,
        )

        df_rxcui = df_rxcui_by_name.get(df_name, "")
        df_status = (
            "EXACT_DF_SUFFIX"
            if df_name
            else "REVIEW"
        )

        body = scd_name

        if df_name:
            body = clean_text(
                scd_name[:-len(df_name)]
            )

        components_raw = [
            clean_text(x)
            for x in body.split(" / ")
            if clean_text(x)
        ]

        exact_component_count = 0

        for component_order, raw_component in enumerate(
            components_raw,
            start=1,
        ):
            component_clean = strip_quantity_prefix(
                raw_component
            )

            scdc_rxcui = scdc_lookup.get(
                exact_key(component_clean),
                "",
            )

            relation_status = (
                "EXACT_SCDC_NAME"
                if scdc_rxcui
                else "REVIEW"
            )

            if scdc_rxcui:
                exact_component_count += 1

            scd_component_rel.append({
                "scd_rxcui": scd_rxcui,
                "scd_name": scd_name,
                "component_order": component_order,
                "component_raw": raw_component,
                "component_clean": component_clean,
                "scdc_rxcui": scdc_rxcui,
                "relation_status": relation_status,
            })

        component_status = (
            "ALL_COMPONENTS_EXACT"
            if components_raw
            and exact_component_count == len(components_raw)
            else "REVIEW"
        )

        clinical.append({
            "scd_rxcui": scd_rxcui,
            "scd_name": scd_name,
            "scd_name_norm": r["display_name_norm"],
            "dose_form_rxcui": df_rxcui,
            "dose_form_name": df_name,
            "dose_form_status": df_status,
            "component_count": len(components_raw),
            "matched_component_count": exact_component_count,
            "component_status": component_status,
            "sab": r["sab"],
        })

        scd_df_rel.append({
            "scd_rxcui": scd_rxcui,
            "dose_form_rxcui": df_rxcui,
            "dose_form_name": df_name,
            "relation_status": df_status,
        })

    clinical = dedupe_exact(
        clinical,
        ["scd_rxcui", "scd_name"],
    )

    # -------------------------------------------------------------------------
    # 5. BRAND
    # -------------------------------------------------------------------------
    brand = []

    for r in canonical:
        if r["tty"] in BRAND_TTYS:
            brand.append({
                "brand_rxcui": r["rxcui"],
                "brand_name": r["display_name"],
                "brand_name_norm": r["display_name_norm"],
                "brand_tty": r["tty"],
                "sab": r["sab"],
                "generic_scd_rxcui": "",
                "relation_status": "NEEDS_OFFICIAL_RXNORM_RELATION",
            })

    brand = dedupe_exact(
        brand,
        ["brand_rxcui", "brand_name", "brand_tty", "sab"],
    )

    # -------------------------------------------------------------------------
    # 6. PACK
    # -------------------------------------------------------------------------
    pack = []

    for r in canonical:
        if r["tty"] in PACK_TTYS:
            pack.append({                "pack_rxcui": r["rxcui"],
                "pack_name": r["display_name"],
                "pack_name_norm": r["display_name_norm"],
                "pack_tty": r["tty"],
                "sab": r["sab"],
                "related_scd_rxcui": "",
                "relation_status": "NEEDS_OFFICIAL_RXNORM_RELATION",
            })

    pack = dedupe_exact(
        pack,
        ["pack_rxcui", "pack_name", "pack_tty", "sab"],
    )

    # -------------------------------------------------------------------------
    # 7. ALIAS
    # -------------------------------------------------------------------------
    alias = []

    for r in rows:
        if r["tty"] in ALIAS_TTYS:
            alias.append({
                "rxcui": r["rxcui"],
                "alias_text": r["display_name"],
                "alias_norm": r["display_name_norm"],
                "tty": r["tty"],
                "sab": r["sab"],
                "usage": "SEARCH_CANDIDATE_ONLY",
            })

    alias = dedupe_exact(
        alias,
        ["rxcui", "alias_text", "tty", "sab"],
    )

    # -------------------------------------------------------------------------
    # 8. OTHER TTY
    # -------------------------------------------------------------------------
    handled = (
        INGREDIENT_TTYS
        | CLINICAL_TTYS
        | COMPONENT_TTYS
        | DOSE_FORM_TTYS
        | BRAND_TTYS
        | PACK_TTYS
        | ALIAS_TTYS
    )

    other = []

    for r in rows:
        if r["tty"] not in handled:
            other.append({
                "rxcui": r["rxcui"],
                "display_name": r["display_name"],
                "display_name_norm": r["display_name_norm"],
                "tty": r["tty"],
                "sab": r["sab"],
                "usage": "PRESERVED_NOT_USED_FOR_DAV_FINAL_MAPPING",
            })

    # -------------------------------------------------------------------------
    # 9. TTY DISTRIBUTION
    # -------------------------------------------------------------------------
    tty_counter = Counter(
        (r["tty"], r["sab"])
        for r in rows
    )

    tty_distribution = [
        {
            "tty": tty,
            "sab": sab,
            "row_count": count,
        }
        for (tty, sab), count in sorted(
            tty_counter.items(),
            key=lambda x: (-x[1], x[0][0], x[0][1]),
        )
    ]

    # -------------------------------------------------------------------------
    # 10. REVIEW QUEUE
    # -------------------------------------------------------------------------
    review = []

    for r in scdc:
        if r["parse_status"] != "EXACT_INGREDIENT_PREFIX":
            review.append({
                "review_type": "SCDC_PARSE",
                "rxcui": r["scdc_rxcui"],
                "name": r["scdc_name"],
                "reason": "Ingredient prefix not resolved exactly",
            })

    for r in scd_component_rel:
        if r["relation_status"] != "EXACT_SCDC_NAME":
            review.append({
                "review_type": "SCD_COMPONENT_RELATION",
                "rxcui": r["scd_rxcui"],
                "name": r["scd_name"],
                "reason": (
                    "SCD component not matched exactly to SCDC: "
                    + r["component_clean"]
                ),
            })

    for r in scd_df_rel:
        if r["relation_status"] != "EXACT_DF_SUFFIX":
            review.append({
                "review_type": "SCD_DOSE_FORM_RELATION",
                "rxcui": r["scd_rxcui"],
                "name": "",
                "reason": "Dose form DF suffix not resolved exactly",
            })

    # -------------------------------------------------------------------------
    # 11. QUALITY SUMMARY
    # -------------------------------------------------------------------------
    summary = []

    def add(metric, value):
        summary.append({
            "metric": metric,
            "value": value,
        })

    for metric in [
        "input_rows",
        "clean_rows",
        "empty_rows_removed",
        "missing_rxcui",
        "non_numeric_rxcui",
        "missing_tty",
        "missing_sab",
        "missing_display_name",
        "exact_duplicate_rows_preserved",
        "unique_rxcui",
        "unique_tty",
        "unique_sab",
    ]:
        add(metric, quality.get(metric, 0))

    add("sab_rxnorm_rows", len(canonical))
    add("ingredient_rows", len(ingredient))
    add("scdc_rows", len(scdc))
    add(
        "scdc_exact_ingredient_parse",
        sum(
            r["parse_status"] == "EXACT_INGREDIENT_PREFIX"
            for r in scdc
        ),
    )
    add(
        "scdc_review",
        sum(
            r["parse_status"] != "EXACT_INGREDIENT_PREFIX"
            for r in scdc
        ),
    )
    add("scd_rows", len(clinical))
    add("scd_component_relation_rows", len(scd_component_rel))
    add(
        "scd_component_exact",
        sum(
            r["relation_status"] == "EXACT_SCDC_NAME"
            for r in scd_component_rel
        ),
    )
    add(
        "scd_component_review",
        sum(
            r["relation_status"] != "EXACT_SCDC_NAME"
            for r in scd_component_rel
        ),
    )
    add(
        "scd_dose_form_exact",
        sum(
            r["relation_status"] == "EXACT_DF_SUFFIX"
            for r in scd_df_rel
        ),
    )
    add(
        "scd_dose_form_review",
        sum(
            r["relation_status"] != "EXACT_DF_SUFFIX"
            for r in scd_df_rel
        ),
    )
    add("dose_form_rows", len(dose_form))
    add("brand_rows", len(brand))
    add("pack_rows", len(pack))
    add("alias_rows", len(alias))
    add("other_tty_rows", len(other))
    add("review_queue_rows", len(review))

    return {
        SHEET_NAMES["clean"]: rows,
        SHEET_NAMES["ingredient"]: ingredient,
        SHEET_NAMES["scdc"]: scdc,
        SHEET_NAMES["scd"]: clinical,
        SHEET_NAMES["dose_form"]: dose_form,
        SHEET_NAMES["scd_component"]: scd_component_rel,
        SHEET_NAMES["scd_df"]: scd_df_rel,
        SHEET_NAMES["brand"]: brand,
        SHEET_NAMES["pack"]: pack,
        SHEET_NAMES["alias"]: alias,
        SHEET_NAMES["other"]: other,
        SHEET_NAMES["tty_dist"]: tty_distribution,
        SHEET_NAMES["quality"]: summary,
        SHEET_NAMES["review"]: review,
    }


# =============================================================================
# XLSX OUTPUT
# =============================================================================

def write_sheet(ws, rows: list[dict]):
    if not rows:
        ws.append(["NO_DATA"])
        return

    headers = list(rows[0].keys())
    ws.append(headers)

    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    # Header style
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    for cell in ws[1]:
        cell.font = Font(
            bold=True,
            color="FFFFFF",
        )
        cell.fill = header_fill
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Conservative widths: tránh Excel quá rộng.
    sample_limit = min(ws.max_row, 300)
    for col_idx in range(1, ws.max_column + 1):
        max_len = 8
        for row_idx in range(1, sample_limit + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value is not None:
                max_len = max(
                    max_len,
                    min(len(str(value)), 45),
                )
        ws.column_dimensions[
            get_column_letter(col_idx)
        ].width = min(max_len + 2, 45)


def save_output_xlsx(output_xlsx: Path, outputs: dict):
    wb = Workbook()

    # Remove default sheet
    default = wb.active
    wb.remove(default)

    for sheet_name, rows in outputs.items():
        ws = wb.create_sheet(title=sheet_name[:31])
        write_sheet(ws, rows)

    wb.save(output_xlsx)

def run_pipeline(
    input_xlsx: str,
    output_xlsx: str,
    sheet_name: str | None = None,
):
    input_path = Path(input_xlsx)
    output_path = Path(output_xlsx)

    if input_path.suffix.lower() != ".xlsx":
        raise ValueError(
            "Tool này nhận input .xlsx. "
            "Ví dụ: rxnorm.xlsx"
        )

    if output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")

    rows, quality, actual_sheet = read_xlsx_rows(
        input_path,
        sheet_name,
    )

    outputs = build_outputs(
        rows,
        quality,
    )

    save_output_xlsx(
        output_path,
        outputs,
    )

    q = {
        r["metric"]: r["value"]
        for r in outputs[SHEET_NAMES["quality"]]
    }

    print("=" * 70)
    print("RXNORM XLSX PIPELINE COMPLETED")
    print("=" * 70)
    print(f"Input file             : {input_path}")
    print(f"Input sheet            : {actual_sheet}")
    print(f"Output file            : {output_path}")
    print(f"Clean rows             : {q.get('clean_rows', 0)}")
    print(f"Unique RxCUI           : {q.get('unique_rxcui', 0)}")
    print(f"SAB=RXNORM rows        : {q.get('sab_rxnorm_rows', 0)}")
    print(f"Ingredient rows        : {q.get('ingredient_rows', 0)}")
    print(f"SCDC rows              : {q.get('scdc_rows', 0)}")
    print(f"SCD rows               : {q.get('scd_rows', 0)}")
    print(
        f"SCD component exact    : "
        f"{q.get('scd_component_exact', 0)}/"
        f"{q.get('scd_component_relation_rows', 0)}"
    )
    print(
        f"SCD dose-form exact    : "
        f"{q.get('scd_dose_form_exact', 0)}"
    )
    print(f"Review queue           : {q.get('review_queue_rows', 0)}")
    print("No fuzzy relation was auto-verified.")
    print("=" * 70)


# =============================================================================
# MAIN
# =============================================================================
# =============================================================================
# DIRECT PATH CONFIG
# =============================================================================

# CHỈ CẦN SỬA 3 DÒNG DƯỚI ĐÂY
INPUT_PATH = r"D:\Downloads\pharmacy data\rxnorm.xlsx"
OUTPUT_PATH = r"D:\Downloads\pharmacy data\rxnorm_output.xlsx"

# Nếu muốn dùng sheet đầu tiên, để None.
# Nếu muốn chọn sheet cụ thể, ví dụ "RxNorm":
# SHEET_NAME = "RxNorm"
SHEET_NAME = None


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    run_pipeline(
        input_xlsx=INPUT_PATH,
        output_xlsx=OUTPUT_PATH,
        sheet_name=SHEET_NAME,
    )