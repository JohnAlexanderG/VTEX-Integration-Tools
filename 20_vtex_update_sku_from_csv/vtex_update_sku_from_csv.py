#!/usr/bin/env python3
"""
Update VTEX SKUs from a CSV file.

Input CSV columns (header names are case-sensitive by default unless --case-insensitive is used):
  ProductId, IsActive, ActivateIfPossible, Name, RefId,
  PackagedHeight, PackagedLength, PackagedWidth, PackagedWeightKg

Only the following are sent to the API (PUT /api/catalog/pvt/stockkeepingunit/{skuId}):
  IsActive (bool), ActivateIfPossible (bool), Name (str),
  PackagedHeight (float), PackagedLength (float),
  PackagedWidth (float), PackagedWeightKg (float)

Notes:
- The script expects API credentials one directory ABOVE this script in a .env file:
    X-VTEX-API-AppKey=...
    X-VTEX-API-AppToken=...
    VTEX_ACCOUNT_NAME=...
    VTEX_ENVIRONMENT=vtexcommercestable
- The script uses RefId from CSV to lookup the actual SkuId from VTEX API for updates.
- Any dimension value equal to '#N/A' (case-insensitive) or empty will be sent as 0.
- Generates multiple output files:
    * _results.csv: Status and response for each row
    * _failed.csv: Original data for failed/skipped records (if any)
    * _summary.md: Detailed summary report with statistics and error breakdown

Usage examples:
  python3 vtex_update_sku_from_csv.py input.csv \
      --sleep 0.6 --retries 3 --dry-run

  python3 vtex_update_sku_from_csv.py input.csv
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
import os

REQUIRED_COLUMNS = [
    "ProductId",
    "IsActive",
    "ActivateIfPossible",
    "Name",
    "RefId",
    "PackagedHeight",
    "PackagedLength",
    "PackagedWidth",
    "PackagedWeightKg",
]

DIMENSION_FIELDS = [
    "PackagedHeight",
    "PackagedLength",
    "PackagedWidth",
    "PackagedWeightKg",
]


@dataclass
class VtexConfig:
    app_key: str
    app_token: str
    account: str
    env: str

    @staticmethod
    def load_from_env() -> "VtexConfig":
        # Try to load .env from parent directory first, then current directory.
        here = Path(__file__).resolve()
        candidates = [here.parent.parent / ".env", here.parent / ".env"]
        for p in candidates:
            if p.exists():
                load_dotenv(p)
                break
        else:
            # Still allow environment variables if user has them exported
            load_dotenv()  # no path

        app_key = os.getenv("X-VTEX-API-AppKey")
        app_token = os.getenv("X-VTEX-API-AppToken")
        account = os.getenv("VTEX_ACCOUNT_NAME")
        env = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")

        missing = [k for k, v in {
            "X-VTEX-API-AppKey": app_key,
            "X-VTEX-API-AppToken": app_token,
            "VTEX_ACCOUNT_NAME": account,
        }.items() if not v]
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. Make sure .env exists one level up or variables are exported.")
        return VtexConfig(app_key, app_token, account, env)


def coerce_numeric(value: str) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if s == "" or s.lower() in {"#n/a", "n/a", "na", "null", "none"}:
        return 0.0
    # Replace comma decimal if present
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def bool_from_str(value: str) -> bool:
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in {"true", "1", "yes", "y"}


def build_headers(cfg: VtexConfig) -> Dict[str, str]:
    return {
        "X-VTEX-API-AppKey": cfg.app_key,
        "X-VTEX-API-AppToken": cfg.app_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_sku_by_refid(cfg: VtexConfig, refid: str, timeout: int = 30) -> Dict[str, Any]:
    """Get SKU information by RefId from VTEX API"""
    url = f"https://{cfg.account}.{cfg.env}.com.br/api/catalog/pvt/stockkeepingunit?refId={refid}"
    resp = requests.get(url, headers=build_headers(cfg), timeout=timeout)
    if resp.status_code == 200:
        data = resp.json()
        if data and 'Id' in data:
            return data  # Return SKU data directly
    return {}

def get_sku_info(cfg: VtexConfig, sku_id: str, timeout: int = 30) -> Dict[str, Any]:
    """Get SKU information from VTEX API to retrieve ProductId"""
    url = f"https://{cfg.account}.{cfg.env}.com.br/api/catalog/pvt/stockkeepingunit/{sku_id}"
    resp = requests.get(url, headers=build_headers(cfg), timeout=timeout)
    if resp.status_code == 200:
        return resp.json()
    return {}

def put_sku(cfg: VtexConfig, sku_id: str, payload: Dict[str, Any], timeout: int = 30) -> requests.Response:
    url = f"https://{cfg.account}.{cfg.env}.com.br/api/catalog/pvt/stockkeepingunit/{sku_id}"
    resp = requests.put(url, headers=build_headers(cfg), data=json.dumps(payload), timeout=timeout)
    return resp


def process_csv(input_path: Path, id_column: str, case_insensitive: bool, sleep: float, retries: int, dry_run: bool) -> tuple[Path, List[Dict[str, Any]], List[Dict[str, Any]]]:
    cfg = VtexConfig.load_from_env()

    # First pass: count total rows for progress tracking
    with input_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        total_rows = sum(1 for _ in reader)
    
    print(f"📁 Processing {total_rows} records from {input_path.name}")
    if dry_run:
        print("🔍 DRY RUN mode - no API calls will be made")
    print()

    with input_path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if case_insensitive:
            # normalize fieldnames
            reader.fieldnames = [fn.strip() if fn else fn for fn in reader.fieldnames]
        # Validate columns exist (loosely if case_insensitive)
        missing_cols = []
        present = {fn.lower(): fn for fn in (reader.fieldnames or [])}
        for col in REQUIRED_COLUMNS:
            key = col.lower() if case_insensitive else col
            if key not in (present.keys() if case_insensitive else reader.fieldnames):
                missing_cols.append(col)
        if missing_cols:
            raise RuntimeError(f"CSV is missing required columns: {', '.join(missing_cols)}")

        out_rows = []
        failed_rows = []
        original_data = []
        line_no = 1
        successful_count = 0
        error_count = 0
        skip_count = 0
        
        for row in reader:
            line_no += 1
            def get(col: str):
                if case_insensitive:
                    return row.get(present[col.lower()])
                return row.get(col)

            original_data.append(row.copy())
            sku_id = (get(id_column) or "").strip()
            if not sku_id:
                result_row = {"row": line_no, "skuId": sku_id, "status": "skip", "code": "", "message": f"Empty {id_column}"}
                out_rows.append(result_row)
                failed_rows.append({**row, **result_row})
                skip_count += 1
                print(f"⚠️  Row {line_no}: Skipped - Empty {id_column}")
                continue

            payload = {
                "IsActive": bool_from_str(get("IsActive")),
                "ActivateIfPossible": bool_from_str(get("ActivateIfPossible")),
                "Name": (get("Name") or "").strip(),
                "RefId": (get("RefId") or "").strip(),  # Include RefId to prevent deletion
                "PackagedHeight": coerce_numeric(get("PackagedHeight")),
                "PackagedLength": coerce_numeric(get("PackagedLength")),
                "PackagedWidth": coerce_numeric(get("PackagedWidth")),
                "PackagedWeightKg": coerce_numeric(get("PackagedWeightKg")),
            }

            # Defensive: Name is required by API; if empty, skip
            if not payload["Name"]:
                result_row = {"row": line_no, "skuId": sku_id, "status": "skip", "code": "", "message": "Empty Name"}
                out_rows.append(result_row)
                failed_rows.append({**row, **result_row})
                skip_count += 1
                print(f"⚠️  Row {line_no}: Skipped - Empty Name (SKU: {sku_id})")
                continue
            
            # Defensive: RefId is important to prevent deletion; warn if empty
            if not payload["RefId"]:
                print(f"⚠️  Row {line_no}: Warning - Empty RefId for SKU {sku_id} (will be set to null)")

            if dry_run:
                out_rows.append({"row": line_no, "skuId": sku_id, "status": "dry-run", "code": "", "message": json.dumps(payload, ensure_ascii=False)})
                successful_count += 1
                print(f"🔍 Row {line_no}: DRY RUN - SKU {sku_id} ({line_no-1}/{total_rows})")
                continue

            # Get SkuId and ProductId using RefId mapping
            refid = payload["RefId"]
            if not refid:
                result_row = {"row": line_no, "skuId": sku_id, "status": "error", "code": "no-refid", "message": "RefId is required for mapping"}
                out_rows.append(result_row)
                failed_rows.append({**row, **result_row})
                error_count += 1
                print(f"❌ Row {line_no}: ERROR - RefId is required for SKU mapping")
                continue
                
            print(f"📥 Row {line_no}: Getting SKU by RefId {refid}...")
            try:
                sku_info = get_sku_by_refid(cfg, refid)
                if not sku_info or 'Id' not in sku_info:
                    result_row = {"row": line_no, "skuId": sku_id, "status": "error", "code": "not-found", "message": f"SKU not found for RefId {refid}"}
                    out_rows.append(result_row)
                    failed_rows.append({**row, **result_row})
                    error_count += 1
                    print(f"❌ Row {line_no}: ERROR - SKU not found for RefId {refid}")
                    continue
                
                actual_sku_id = str(sku_info['Id'])
                product_id = sku_info['ProductId']
                payload["ProductId"] = product_id  # Add required ProductId to payload
                print(f"✅ Row {line_no}: Found SkuId {actual_sku_id} and ProductId {product_id} for RefId {refid}")
                
                # Use the actual SkuId from VTEX API instead of the one from CSV
                sku_id = actual_sku_id
                
            except Exception as e:
                result_row = {"row": line_no, "skuId": sku_id, "status": "error", "code": "lookup-error", "message": str(e)}
                out_rows.append(result_row)
                failed_rows.append({**row, **result_row})
                error_count += 1
                print(f"❌ Row {line_no}: ERROR - Failed to get SKU for RefId {refid}: {e}")
                continue

            attempt = 0
            while True:
                attempt += 1
                try:
                    resp = put_sku(cfg, sku_id, payload)
                    if resp.status_code in (200, 201, 204):
                        out_rows.append({"row": line_no, "skuId": sku_id, "status": "ok", "code": resp.status_code, "message": ""})
                        successful_count += 1
                        print(f"✅ Row {line_no}: SUCCESS - SKU {sku_id} updated ({line_no-1}/{total_rows})")
                        break
                    elif resp.status_code in (429, 500, 502, 503, 504) and attempt <= retries:
                        # exponential backoff
                        wait = min(5.0, sleep * (2 ** (attempt - 1)))
                        print(f"🔄 Row {line_no}: Retry {attempt}/{retries} - HTTP {resp.status_code} for SKU {sku_id} (waiting {wait:.1f}s)")
                        time.sleep(wait)
                        continue
                    else:
                        try:
                            err = resp.json()
                        except Exception:
                            err = resp.text
                        result_row = {"row": line_no, "skuId": sku_id, "status": "error", "code": resp.status_code, "message": json.dumps(err, ensure_ascii=False)}
                        out_rows.append(result_row)
                        failed_rows.append({**row, **result_row})
                        error_count += 1
                        error_msg = err if isinstance(err, str) else str(err)
                        if len(error_msg) > 100:
                            error_msg = error_msg[:100] + "..."
                        print(f"❌ Row {line_no}: ERROR - HTTP {resp.status_code} for SKU {sku_id} - {error_msg}")
                        break
                except requests.RequestException as e:
                    if attempt <= retries:
                        wait = min(5.0, sleep * (2 ** (attempt - 1)))
                        print(f"🔄 Row {line_no}: Retry {attempt}/{retries} - Connection error for SKU {sku_id} (waiting {wait:.1f}s)")
                        time.sleep(wait)
                        continue
                    result_row = {"row": line_no, "skuId": sku_id, "status": "error", "code": "req-exception", "message": str(e)}
                    out_rows.append(result_row)
                    failed_rows.append({**row, **result_row})
                    error_count += 1
                    print(f"❌ Row {line_no}: ERROR - Connection failed for SKU {sku_id}")
                    break
            time.sleep(sleep)

    # Final summary
    print(f"\n📊 Processing completed:")
    print(f"   ✅ Successful: {successful_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   ⚠️  Skipped: {skip_count}")
    print(f"   📝 Total: {total_rows}")
    print()

    # Write results CSV next to input
    out_path = input_path.with_name(input_path.stem + "_results.csv")
    with out_path.open("w", newline='', encoding='utf-8') as fo:
        writer = csv.DictWriter(fo, fieldnames=["row", "skuId", "status", "code", "message"])
        writer.writeheader()
        writer.writerows(out_rows)

    # Write failed CSV with original data
    failed_path = input_path.with_name(input_path.stem + "_failed.csv")
    if failed_rows:
        with failed_path.open("w", newline='', encoding='utf-8') as fo:
            fieldnames = list(failed_rows[0].keys())
            writer = csv.DictWriter(fo, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(failed_rows)

    return out_path, out_rows, original_data


def generate_summary_report(input_path: Path, results: List[Dict[str, Any]], dry_run: bool) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    readme_path = input_path.with_name(input_path.stem + "_summary.md")
    
    # Calculate statistics
    total = len(results)
    successful = len([r for r in results if r["status"] == "ok"])
    errors = len([r for r in results if r["status"] == "error"])
    skipped = len([r for r in results if r["status"] == "skip"])
    dry_runs = len([r for r in results if r["status"] == "dry-run"])
    
    # Group errors by type
    error_types = {}
    for r in results:
        if r["status"] == "error":
            code = str(r["code"])
            if code not in error_types:
                error_types[code] = []
            error_types[code].append(r["skuId"])
    
    with readme_path.open("w", encoding='utf-8') as f:
        f.write(f"# VTEX SKU Update Summary Report\n\n")
        f.write(f"**Generated:** {timestamp}\n\n")
        f.write(f"**Input File:** {input_path.name}\n\n")
        
        if dry_run:
            f.write("**Mode:** DRY RUN (no API calls made)\n\n")
        
        f.write("## 📊 Summary Statistics\n\n")
        f.write(f"- **Total Records:** {total}\n")
        f.write(f"- **✅ Successful Updates:** {successful}\n")
        f.write(f"- **❌ Errors:** {errors}\n")
        f.write(f"- **⚠️ Skipped:** {skipped}\n")
        
        if dry_runs > 0:
            f.write(f"- **🔍 Dry Run Records:** {dry_runs}\n")
        
        success_rate = (successful / total * 100) if total > 0 else 0
        f.write(f"- **Success Rate:** {success_rate:.1f}%\n\n")
        
        if error_types:
            f.write("## ❌ Error Breakdown\n\n")
            for code, skus in error_types.items():
                f.write(f"### HTTP {code}\n")
                f.write(f"- **Count:** {len(skus)}\n")
                f.write(f"- **SKUs:** {', '.join(skus[:10])}")
                if len(skus) > 10:
                    f.write(f" ... and {len(skus) - 10} more")
                f.write("\n\n")
        
        skip_reasons = {}
        for r in results:
            if r["status"] == "skip":
                reason = r["message"]
                if reason not in skip_reasons:
                    skip_reasons[reason] = []
                skip_reasons[reason].append(r["skuId"])
        
        if skip_reasons:
            f.write("## ⚠️ Skip Reasons\n\n")
            for reason, skus in skip_reasons.items():
                f.write(f"### {reason}\n")
                f.write(f"- **Count:** {len(skus)}\n")
                f.write(f"- **SKUs:** {', '.join(skus[:10])}")
                if len(skus) > 10:
                    f.write(f" ... and {len(skus) - 10} more")
                f.write("\n\n")
        
        f.write("## 📁 Generated Files\n\n")
        f.write(f"- **Results CSV:** `{input_path.stem}_results.csv`\n")
        if errors > 0 or skipped > 0:
            f.write(f"- **Failed Records CSV:** `{input_path.stem}_failed.csv`\n")
        f.write(f"- **Summary Report:** `{input_path.stem}_summary.md` (this file)\n\n")
        
        f.write("---\n")
        f.write("*Report generated by vtex_update_sku_from_csv.py*\n")
    
    return readme_path


def main():
    parser = argparse.ArgumentParser(description="Update VTEX SKUs from CSV")
    parser.add_argument("csv", type=Path, help="Path to input CSV")
    parser.add_argument("--id-column", default="ProductId", help="CSV column containing the {skuId} (default: ProductId)")
    parser.add_argument("--case-insensitive", action="store_true", help="Treat CSV headers as case-insensitive")
    parser.add_argument("--sleep", type=float, default=0.6, help="Seconds to sleep between requests (default: 0.6)")
    parser.add_argument("--retries", type=int, default=3, help="Retries for 429/5xx with backoff (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Do not call the API; log payloads instead")

    args = parser.parse_args()

    try:
        out_path, results, _ = process_csv(args.csv, args.id_column, args.case_insensitive, args.sleep, args.retries, args.dry_run)
        
        # Generate summary report
        summary_path = generate_summary_report(args.csv, results, args.dry_run)
        
        print(f"Done. Files generated:")
        print(f"  Results CSV: {out_path}")
        print(f"  Summary Report: {summary_path}")
        
        failed_count = len([r for r in results if r["status"] in ("error", "skip")])
        if failed_count > 0:
            failed_path = args.csv.with_name(args.csv.stem + "_failed.csv")
            print(f"  Failed Records CSV: {failed_path}")
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
