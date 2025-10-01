#!/usr/bin/env python3
"""
DynamoDB JSON generator from tabular files (.xlsx | .xls | .csv)

Usage examples:
  # Basic: generate batch-write JSON for a table
  python3 dynamojson_from_tabular.py input.xlsx --table-name MyTable -o mytable_items.json

  # Generate NDJSON of Items only (one DynamoDB-JSON item per line)
  python3 dynamojson_from_tabular.py data.csv --ndjson -o items.ndjson

Notes:
  - For Excel files you need pandas and openpyxl installed: pip install pandas openpyxl
  - Column names with parenthetical comments are automatically cleaned (e.g., "_SkuId (Not changeable)" -> "_SkuId")
  - Numbers are inferred and written as DynamoDB N (string), booleans as BOOL, empty as NULL,
    lists/dicts recognized if the cell contains valid JSON (e.g., "[1,2]" or '{"a":1}').
  - Use --all-as-string to force all non-empty values to S (string) type.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

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


# ------------------------------
# Conversion of rows -> DynamoDB JSON items
# ------------------------------

def row_to_item(
    row: Dict[str, Any],
    *,
    all_as_string: bool,
    empty_as_null: bool,
    string_cols: Optional[set] = None
) -> Optional[Dict[str, Any]]:
    item: Dict[str, Any] = {}
    force_cols = string_cols or set()
    for k, v in row.items():
        # Clean header names by removing parenthetical comments
        key = clean_key(str(k))

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
    return item


def rows_to_put_requests(
    rows: Iterable[Dict[str, Any]],
    *,
    all_as_string: bool,
    empty_as_null: bool,
    string_cols: Optional[set] = None
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        item = row_to_item(r, all_as_string=all_as_string, empty_as_null=empty_as_null, string_cols=string_cols)
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
    p.add_argument("--string-cols", default="", help="Comma-separated list of column names to force as String (S). Column names are cleaned like headers (e.g., '_SkuId (Not changeable)' -> '_SkuId').")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    rows = read_rows(args.input)
    empty_as_null = not args.no_empty_as_null

    # Columns to force as String (S)
    string_cols = set()
    if getattr(args, "string_cols", None):
        raw_cols = [c.strip() for c in args.string_cols.split(",") if c.strip()]
        string_cols = {clean_key(c) for c in raw_cols}

    # Compute default output
    if args.output:
        out_path = args.output
    else:
        base, _ = os.path.splitext(args.input)
        out_path = base + (".ndjson" if args.ndjson else ".json")

    # Generate
    if args.ndjson and args.table_name:
        print("[WARN] --ndjson ignores --table-name and writes Items only.", file=sys.stderr)

    if args.ndjson:
        # Write one Item per line
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                item = row_to_item(r, all_as_string=args.all_as_string, empty_as_null=empty_as_null, string_cols=string_cols)
                if item is not None:  # Skip items with NULL _SKUReferenceCode
                    f.write(json.dumps(item, ensure_ascii=False))
                    f.write("\n")
    else:
        # Batch-write format (if table provided) or list of PutRequests
        put_reqs = rows_to_put_requests(rows, all_as_string=args.all_as_string, empty_as_null=empty_as_null, string_cols=string_cols)
        if args.table_name:
            payload = {args.table_name: put_reqs}
        else:
            payload = put_reqs
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote: {out_path}")
    # Tips for AWS CLI usage
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
