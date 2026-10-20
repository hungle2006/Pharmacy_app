from __future__ import annotations
import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

BASE_URL = "https://ccs.whiteneuron.com/api/ICD10_TT06"

# API is hierarchical. The endpoint name is the CURRENT node's model.
# Examples:
# root
# childs/chapter?id=I
# childs/section?id=A00
# childs/type?id=A00
# Chapter XX can expose deeper models such as subsection/subsubsection.
SUPPORTED_MODELS = {
    "chapter", "section", "type", "subsection", "subsubsection", "disease"
}

def get_json(session: requests.Session, url: str, retries: int = 5) -> dict[str, Any]:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=90)
            r.raise_for_status()
            obj = r.json()
            if obj.get("status") != "success":
                raise ValueError(f"API status is not success: {obj}")
            return obj
        except Exception as e:
            last_err = e
            if attempt == retries:
                break
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}\n{last_err}")

def children_url(model: str, node_id: str, lang: str) -> str:
    return f"{BASE_URL}/childs/{quote(model)}?id={quote(str(node_id))}&lang={quote(lang)}"

def root_url(lang: str) -> str:
    return f"{BASE_URL}/root?lang={quote(lang)}"

def crawl_lang(lang: str, delay: float = 0.05) -> list[dict[str, Any]]:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; PharmacyResearchCrawler/1.0)",
        "Accept": "application/json, text/plain, */*",
    })

    root = get_json(s, root_url(lang))
    queue: list[tuple[dict[str, Any], str | None, int]] = [
        (node, None, 0) for node in (root.get("data") or [])
    ]
    out: list[dict[str, Any]] = []
    visited: set[tuple[str, str]] = set()

    while queue:
        node, parent_id, depth = queue.pop(0)
        model = str(node.get("model") or "")
        node_id = str(node.get("id") or "")
        is_leaf = bool(node.get("is_leaf"))
        data = node.get("data") or {}

        key = (model, node_id)
        if key in visited:
            continue
        visited.add(key)

        rec = {
            "lang": lang,
            "model": model,
            "id": node_id,
            "code": data.get("code"),
            "name": data.get("name"),
            "is_leaf": is_leaf,
            "parent_id": parent_id,
            "depth": depth,
        }
        out.append(rec)

        if is_leaf:
            continue

        if not model:
            print(f"[WARN] Non-leaf node has no model: {rec}")
            continue

        # Future-proof: allow any model returned by server, but log unfamiliar ones.
        if model not in SUPPORTED_MODELS:
            print(f"[WARN] New model from server: {model!r}; trying childs/{model}")

        url = children_url(model, node_id, lang)
        obj = get_json(s, url)
        children = obj.get("data") or []
        for child in children:
            queue.append((child, node_id, depth + 1))

        if len(out) % 500 == 0:
            print(f"[ICD-{lang}] nodes={len(out):,}, queue={len(queue):,}")
        time.sleep(delay)

    return out

def key_of(r: dict[str, Any]) -> tuple[str, str]:
    return (str(r.get("model") or ""), str(r.get("id") or ""))

def merge_bilingual(vi: list[dict[str, Any]], en: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vi_map = {key_of(r): r for r in vi}
    en_map = {key_of(r): r for r in en}
    keys = list(dict.fromkeys([*vi_map.keys(), *en_map.keys()]))

    rows = []
    for k in keys:
        rv = vi_map.get(k, {})
        re = en_map.get(k, {})
        base = rv or re
        rows.append({
            "model": k[0],
            "id": k[1],
            "code": rv.get("code") or re.get("code"),
            "name_vi": rv.get("name"),
            "name_en": re.get("name"),
            "is_leaf": base.get("is_leaf"),
            "parent_id": base.get("parent_id"),
            "depth": base.get("depth"),
            "source": "CCS ICD10_TT06",
        })
    return rows

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def crawl(output_dir: Path, only_lang: str | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    if only_lang:
        rows = crawl_lang(only_lang)
        write_csv(output_dir / f"icd10_tt06_{only_lang}_all_nodes.csv", rows)
        diseases = [r for r in rows if r["model"] == "disease" or r["is_leaf"]]
        write_csv(output_dir / f"icd10_tt06_{only_lang}_diseases.csv", diseases)
        return

    print("Crawling Vietnamese tree...")
    vi = crawl_lang("vi")
    print("Crawling English tree...")
    en = crawl_lang("en")

    merged = merge_bilingual(vi, en)
    write_csv(output_dir / "ICD10_Vietnam_TT06_2026_FULL.csv", merged)

    diseases = [r for r in merged if r["model"] == "disease" or r["is_leaf"]]
    write_csv(output_dir / "ICD10_Vietnam_TT06_2026_DISEASES.csv", diseases)

    # audit snapshots
    with (output_dir / "icd10_tt06_vi_raw_nodes.json").open("w", encoding="utf-8") as f:
        json.dump(vi, f, ensure_ascii=False, indent=2)
    with (output_dir / "icd10_tt06_en_raw_nodes.json").open("w", encoding="utf-8") as f:
        json.dump(en, f, ensure_ascii=False, indent=2)

    print(f"VI nodes: {len(vi):,}")
    print(f"EN nodes: {len(en):,}")
    print(f"Merged nodes: {len(merged):,}")
    print(f"Disease/leaf rows: {len(diseases):,}")
    print(f"Saved to: {output_dir}")

def main():
    ap = argparse.ArgumentParser(description="Crawl Vietnam ICD-10 TT06/2026 hierarchical API.")
    ap.add_argument("--output-dir", default="output_icd10")
    ap.add_argument("--only-lang", choices=["vi", "en"], default=None)
    args = ap.parse_args()
    crawl(Path(args.output_dir), args.only_lang)

if __name__ == "__main__":
    main()