#!/usr/bin/env python3
"""
DynamoDB JSON generator from tabular files (.xlsx | .xls | .csv)

Usage examples:
  # Basic: generate batch-write JSON for a table
  python3 dynamojson_from_tabular.py input.xlsx --table-name MyTable -o mytable_items.json

  # Generate NDJSON of Items only (one DynamoDB-JSON item per line)
  python3 dynamojson_from_tabular.py data.csv --ndjson -o items.ndjson

  # Merge with a seller xlsx, excluding rows whose StockKeepingUnitId matches
  # any _SKUReferenceCode found in the main input (marketplace-owned SKUs).
  python3 dynamojson_from_tabular.py input.xlsx --sellers-xlsx sellers.xlsx -o output.json

Notes:
  - For Excel files you need pandas and openpyxl installed: pip install pandas openpyxl
  - Column names with parenthetical comments are automatically cleaned (e.g., "_SkuId (Not changeable)" -> "_SkuId")
  - Numbers are inferred and written as DynamoDB N (string), booleans as BOOL, empty as NULL,
    lists/dicts recognized if the cell contains valid JSON (e.g., "[1,2]" or '{"a":1}').
  - Use --all-as-string to force all non-empty values to S (string) type.
  - --sellers-xlsx expects columns: StockKeepingUnitId, SellerId, SellerStockKeepingUnitId, IsActive.
    If a StockKeepingUnitId from the sellers file matches a _SkuId from the main input,
    BOTH records are excluded from the output (bidirectional filter). Only IDs that exist
    in one file but not the other are kept.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

# ------------------------------
# VTEX export column name mapping
# ------------------------------

VTEX_COLUMN_MAP = {
    "Product ID": "_ProductId",
    "Product Name": "_ProductName",
    "SKU ID": "_SkuId",
    "SKU name": "_SkuName",
    "SKU reference code": "_SKUReferenceCode",
}

# Columns consumed to compute _IsActive; excluded from the final DynamoDB item.
_ACTIVE_PRODUCT_COL = "Active product"
_ACTIVE_SKU_COL = "Active SKU"


def apply_column_map(rows: List[Dict[str, Any]], column_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Rename column keys in each row according to column_map.

    Keys not present in column_map are kept unchanged.
    """
    mapped = []
    for row in rows:
        new_row = {}
        for k, v in row.items():
            new_key = column_map.get(k, k)
            new_row[new_key] = v
        mapped.append(new_row)
    return mapped


# ------------------------------
# Helpers: key cleaning & type inference & map
# ------------------------------

def clean_key(key: str) -> str:
    """Remove parenthetical comments from a key.

    Examples:
        '_SkuId (Not changeable)' -> '_SkuId'
        '_ProductId (Not changeable)' -> '_ProductId'
        'Name' -> 'Name' (unchanged)
    """
    # Remove everything from the first " (" to the last ")"
    cleaned = re.sub(r'\s+\([^)]*\)$', '', key)
    return cleaned

def _is_truthy_str(s: str) -> Optional[bool]:
    if s is None:
        return None
    t = s.strip().lower()
    if t in {"true", "yes", "y", "1"}:
        return True
    if t in {"false", "no", "n", "0"}:
        return False
    return None


def _try_json_parse(s: str) -> Optional[Any]:
    try:
        return json.loads(s)
    except Exception:
        return None


def _num_from_str(s: str) -> Optional[Decimal]:
    # Reject values with leading zeros that look like ids (to keep as string), unless it's a decimal like 0.5
    if s is None:
        return None
    st = s.strip()
    if st == "":
        return None
    # If it contains letters (except e/E for exponents), treat as string
    letters = any(c.isalpha() for c in st.replace("e", "").replace("E", ""))
    if letters:
        return None
    try:
        d = Decimal(st)
    except InvalidOperation:
        return None
    # If the original starts with 0 and is not '0' or '0.xxx', likely an ID -> keep string
    if st.startswith("0") and not st.startswith("0.") and not all(c == "0" for c in st):
        return None
    # Filter NaN/Infinity
    if d.is_nan() or d == Decimal("Infinity") or d == Decimal("-Infinity"):
        return None
    return d


def to_dynamo_attr(value: Any, *, all_as_string: bool = False, empty_as_null: bool = True) -> Dict[str, Any]:
    """Convert a Python value into DynamoDB AttributeValue JSON.
    Returns a one-key dict like {"S":"abc"} or {"N":"123"} etc.
    """
    # Handle None or empties
    if value is None:
        return {"NULL": True}

    # If explicitly force strings
    if all_as_string:
        s = str(value)
        if s == "":
            return {"NULL": True} if empty_as_null else {"S": s}
        return {"S": s}

    # Type-based handling
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float, Decimal)):
        # DynamoDB numbers are strings
        # Convert float via Decimal to avoid scientific notation issues
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return {"NULL": True}
            value = Decimal(str(value))
        return {"N": str(value)}
    if isinstance(value, str):
        v = value.strip()
        if v == "":
            return {"NULL": True} if empty_as_null else {"S": v}
        # Try boolean strings
        tb = _is_truthy_str(v)
        if tb is not None:
            return {"BOOL": tb}
        # Try JSON parse (list/dict/number/bool/null)
        parsed = _try_json_parse(v) if (v.startswith("[") or v.startswith("{")) else None
        if parsed is not None:
            return to_dynamo_attr(parsed, all_as_string=all_as_string, empty_as_null=empty_as_null)
        # Try number
        d = _num_from_str(v)
        if d is not None:
            return {"N": str(d)}
        # Fallback to string
        return {"S": value}
    if isinstance(value, list):
        return {"L": [to_dynamo_attr(x, all_as_string=all_as_string, empty_as_null=empty_as_null) for x in value]}
    if isinstance(value, dict):
        return {"M": {str(k): to_dynamo_attr(v, all_as_string=all_as_string, empty_as_null=empty_as_null) for k, v in value.items()}}

    # Unknown types -> string
    return {"S": str(value)}


# ------------------------------
# Input readers
# ------------------------------

# Columns expected in the sellers xlsx (case-insensitive match)
_SELLER_COLS = {"stockkeepingunitid", "sellerid", "sellerstockkeepingunitid", "isactive"}


def read_rows(input_path: str) -> List[Dict[str, Any]]:
    ext = os.path.splitext(input_path)[1].lower()
    if ext in {".csv"}:
        with open(input_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(r) for r in reader]
    elif ext in {".xlsx", ".xls"}:
        try:
            import pandas as pd  # type: ignore
        except Exception as e:
            print("[ERROR] Reading Excel requires pandas (and openpyxl). Install with: pip install pandas openpyxl", file=sys.stderr)
            raise
        df = pd.read_excel(input_path, dtype=object)  # keep as object to preserve strings
        # Replace NaN with None
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
    else:
        raise ValueError(f"Unsupported input extension: {ext}. Use .csv, .xlsx, or .xls")


def _extract_sku_ids(rows: List[Dict[str, Any]]) -> set:
    """Return the set of _SkuId values present in the main input rows.

    Handles both pre- and post-column-map states: looks for the key
    '_SkuId' (after mapping) as well as the original VTEX export
    header 'SKU ID' (before mapping), whichever is present.
    Values are stored as stripped strings for comparison.
    """
    ids: set = set()
    for row in rows:
        for key in ("_SkuId", "SKU ID"):
            val = row.get(key)
            if val is not None:
                s = str(val).strip()
                if s:
                    ids.add(s)
                break
    return ids


def _extract_seller_sku_ids(rows: List[Dict[str, Any]]) -> set:
    """Return the set of StockKeepingUnitId values from sellers xlsx rows.

    Searches for the column name case-insensitively.
    Values are stored as stripped strings for comparison.
    """
    ids: set = set()
    if not rows:
        return ids
    # Find the actual column name (case-insensitive)
    sku_col = None
    for col in rows[0].keys():
        if col.strip().lower() == "stockkeepingunitid":
            sku_col = col
            break
    if sku_col is None:
        return ids
    for row in rows:
        val = row.get(sku_col)
        if val is not None:
            s = str(val).strip()
            if s:
                ids.add(s)
    return ids


def read_sellers_xlsx(sellers_path: str, exclude_ids: set) -> List[Dict[str, Any]]:
    """Read the sellers xlsx and return rows whose StockKeepingUnitId is NOT
    in *exclude_ids* (the intersection computed by the caller).

    Expected columns: StockKeepingUnitId, SellerId, SellerStockKeepingUnitId, IsActive
    """
    try:
        import pandas as pd  # type: ignore
    except Exception:
        print("[ERROR] Reading sellers xlsx requires pandas (and openpyxl). Install with: pip install pandas openpyxl", file=sys.stderr)
        raise

    df = pd.read_excel(sellers_path, dtype=object)
    df = df.where(pd.notnull(df), None)
    rows = df.to_dict(orient="records")

    # Locate the StockKeepingUnitId column (case-insensitive)
    col_map: Dict[str, str] = {}
    if rows:
        for col in rows[0].keys():
            col_map[col.strip().lower()] = col

    sku_col = col_map.get("stockkeepingunitid")
    if sku_col is None:
        print(
            "[WARN] --sellers-xlsx: 'StockKeepingUnitId' column not found. "
            "No filtering applied. Columns found: " + str(list(col_map.values())),
            file=sys.stderr,
        )
        return rows

    kept: List[Dict[str, Any]] = []
    skipped = 0
    for row in rows:
        val = row.get(sku_col)
        val_str = str(val).strip() if val is not None else ""
        if val_str in exclude_ids:
            skipped += 1
        else:
            kept.append(row)

    print(
        f"[sellers-xlsx] Read {len(rows)} rows, excluded {skipped} marketplace-owned SKUs "
        f"(StockKeepingUnitId matched _SkuId), kept {len(kept)}.",
        file=sys.stderr,
    )
    return kept


# ------------------------------
# Conversion of rows -> DynamoDB JSON items
# ------------------------------

def _resolve_is_active(row: Dict[str, Any]) -> bool:
    """Return True only if both 'Active product' and 'Active SKU' columns are truthy."""
    def _col_is_true(val: Any) -> bool:
        if val is None:
            return False
        b = _is_truthy_str(str(val))
        return b is True

    return _col_is_true(row.get(_ACTIVE_PRODUCT_COL)) and _col_is_true(row.get(_ACTIVE_SKU_COL))


def row_to_item(
    row: Dict[str, Any],
    *,
    all_as_string: bool,
    empty_as_null: bool,
    string_cols: Optional[set] = None,
    exclude_cols: Optional[set] = None
) -> Optional[Dict[str, Any]]:
    item: Dict[str, Any] = {}
    force_cols = string_cols or set()
    skip_cols = exclude_cols or set()

    # Compute _IsActive from the source row before iterating (columns are excluded below)
    is_active = _resolve_is_active(row)

    # Columns consumed by computed fields; always excluded from pass-through
    computed_source_cols = {_ACTIVE_PRODUCT_COL, _ACTIVE_SKU_COL}

    for k, v in row.items():
        # Clean header names by removing parenthetical comments
        key = clean_key(str(k))

        # Skip columns consumed to compute derived fields
        if key in computed_source_cols:
            continue

        # Skip excluded columns
        if key in skip_cols:
            continue

        # Skip items that have NULL _SKUReferenceCode to avoid errors
        if key == "_SKUReferenceCode":
            if v is None or (isinstance(v, str) and v.strip() == ""):
                return None

        if key in force_cols:
            # Force String type for these columns (respect empty_as_null)
            if v is None:
                item[key] = {"NULL": True}
            else:
                s = str(v)
                if s == "":
                    item[key] = {"NULL": True} if empty_as_null else {"S": s}
                else:
                    item[key] = {"S": s}
        else:
            item[key] = to_dynamo_attr(v, all_as_string=all_as_string, empty_as_null=empty_as_null)

    # Computed fields
    item["_IsActive"] = {"BOOL": is_active}
    item["_validated_at"] = {"S": datetime.now(timezone.utc).isoformat()}
    item["_product_validated"] = {"BOOL": is_active}

    return item


def rows_to_put_requests(
    rows: Iterable[Dict[str, Any]],
    *,
    all_as_string: bool,
    empty_as_null: bool,
    string_cols: Optional[set] = None,
    exclude_cols: Optional[set] = None
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        item = row_to_item(r, all_as_string=all_as_string, empty_as_null=empty_as_null, string_cols=string_cols, exclude_cols=exclude_cols)
        if item is not None:  # Skip items with NULL _SKUReferenceCode
            out.append({"PutRequest": {"Item": item}})
    return out


# ------------------------------
# CLI
# ------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert .xlsx/.xls/.csv to DynamoDB JSON")
    p.add_argument("input", help="Path to input file (.xlsx/.xls/.csv)")
    p.add_argument("-o", "--output", help="Output file path. Defaults to <input_basename>.json or .ndjson if --ndjson.")
    p.add_argument("--table-name", help="If provided, produce a batch-write JSON object keyed by the table name.")
    p.add_argument("--ndjson", action="store_true", help="Write Items as newline-delimited JSON (one Item per line), without PutRequest wrapper.")
    p.add_argument("--all-as-string", action="store_true", help="Force all non-empty values to DynamoDB S (string) type.")
    p.add_argument("--no-empty-as-null", action="store_true", help="Do not convert empty strings to NULL; keep them as empty S.")
    p.add_argument("--no-column-map", action="store_true", help="Disable automatic VTEX column name mapping (e.g., 'Product ID' -> '_ProductId').")
    p.add_argument("--exclude-cols", default="", help="Comma-separated list of column names to exclude from the output (e.g., '_ProductName,_SkuName').")
    p.add_argument("--string-cols", default="", help="Comma-separated list of column names to force as String (S). Column names are cleaned like headers (e.g., '_SkuId (Not changeable)' -> '_SkuId').")
    p.add_argument(
        "--sellers-xlsx",
        default="",
        metavar="PATH",
        help=(
            "Optional path to a seller xlsx file with columns: "
            "StockKeepingUnitId, SellerId, SellerStockKeepingUnitId, IsActive. "
            "When a StockKeepingUnitId from this file matches a _SkuId from the "
            "main input, BOTH records are excluded from the output. "
            "The remaining sellers rows are converted to DynamoDB items and "
            "merged into the output alongside the remaining main input rows."
        ),
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # ── Main input ──────────────────────────────────────────────────────────
    rows = read_rows(args.input)

    # Extract _SkuId values BEFORE applying the column map so we capture both
    # the original header name ('SKU ID') and the mapped name ('_SkuId').
    sku_ids = _extract_sku_ids(rows)

    if not args.no_column_map:
        rows = apply_column_map(rows, VTEX_COLUMN_MAP)
        # Re-collect after mapping to catch the renamed key as well
        sku_ids |= _extract_sku_ids(rows)

    empty_as_null = not args.no_empty_as_null

    # Columns to force as String (S)
    string_cols = set()
    if getattr(args, "string_cols", None):
        raw_cols = [c.strip() for c in args.string_cols.split(",") if c.strip()]
        string_cols = {clean_key(c) for c in raw_cols}

    # Columns to exclude from output
    exclude_cols = set()
    if getattr(args, "exclude_cols", None):
        raw_excl = [c.strip() for c in args.exclude_cols.split(",") if c.strip()]
        exclude_cols = {clean_key(c) for c in raw_excl}

    # ── Optional sellers xlsx ────────────────────────────────────────────────
    seller_rows: List[Dict[str, Any]] = []
    sellers_path = getattr(args, "sellers_xlsx", "") or ""
    if sellers_path:
        if not os.path.isfile(sellers_path):
            print(f"[ERROR] --sellers-xlsx path not found: {sellers_path}", file=sys.stderr)
            return 1
        print(f"[sellers-xlsx] Loading '{sellers_path}' ...", file=sys.stderr)

        # Read sellers file once to (a) extract its IDs and (b) filter it
        try:
            import pandas as pd  # type: ignore
            _df = pd.read_excel(sellers_path, dtype=object)
            _df = _df.where(pd.notnull(_df), None)
            _seller_raw = _df.to_dict(orient="records")
        except Exception as exc:
            print(f"[ERROR] Could not read sellers xlsx: {exc}", file=sys.stderr)
            return 1

        seller_ids = _extract_seller_sku_ids(_seller_raw)

        # IDs present in BOTH files → excluded from both outputs
        matched_ids = sku_ids & seller_ids
        print(
            f"[sellers-xlsx] Main _SkuId count: {len(sku_ids)}, "
            f"Seller StockKeepingUnitId count: {len(seller_ids)}, "
            f"Matched (excluded from both outputs): {len(matched_ids)}.",
            file=sys.stderr,
        )

        # Filter sellers xlsx: keep only rows NOT in the matched set
        seller_rows = read_sellers_xlsx(sellers_path, matched_ids)

        # Filter main input: exclude rows whose _SkuId appears in sellers file
        if matched_ids:
            before = len(rows)
            rows = [r for r in rows if str(r.get("_SkuId", r.get("SKU ID", "")) or "").strip() not in matched_ids]
            excluded_main = before - len(rows)
            if excluded_main:
                print(
                    f"[main-input] Excluded {excluded_main} row(s) whose _SkuId "
                    f"matched a StockKeepingUnitId in the sellers file.",
                    file=sys.stderr,
                )

    # ── Compute default output path ──────────────────────────────────────────
    if args.output:
        out_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        out_path = base + (".ndjson" if args.ndjson else ".json")

    # ── Generate output ──────────────────────────────────────────────────────
    if args.ndjson and args.table_name:
        print("[WARN] --ndjson ignores --table-name and writes Items only.", file=sys.stderr)

    conv_kw = dict(all_as_string=args.all_as_string, empty_as_null=empty_as_null,
                   string_cols=string_cols, exclude_cols=exclude_cols)

    if args.ndjson:
        # Write one Item per line (main rows + seller rows)
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                item = row_to_item(r, **conv_kw)
                if item is not None:
                    f.write(json.dumps(item, ensure_ascii=False))
                    f.write("\n")
            for r in seller_rows:
                item = row_to_item(r, **conv_kw)
                if item is not None:
                    f.write(json.dumps(item, ensure_ascii=False))
                    f.write("\n")
    else:
        # Batch-write format (if table provided) or list of PutRequests
        put_reqs = rows_to_put_requests(rows, **conv_kw)
        if seller_rows:
            put_reqs += rows_to_put_requests(seller_rows, **conv_kw)
        if args.table_name:
            payload = {args.table_name: put_reqs}
        else:
            payload = put_reqs
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"Wrote: {out_path}")
    if sellers_path:
        print(f"  Main input rows : {len(rows)}")
        print(f"  Seller rows kept: {len(seller_rows)}")
    if not args.ndjson:
        if string_cols:
            print(f"  (Forced as String) Columns: {', '.join(sorted(string_cols))}")
        if args.table_name:
            print("\nUse with AWS CLI:")
            print("  aws dynamodb batch-write-item --request-items file://" + out_path)
        else:
            print("\nNOTE: Output is a list of PutRequests. Wrap under a table key or use --table-name next time.")
    else:
        print("\nNDJSON written: each line is a DynamoDB Item in AttributeValue JSON. Convert/wrap as needed for your import path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
