#!/usr/bin/env python3
"""
Add Product Specifications to VTEX (Concurrent)

Reads rows from a CSV and assigns specifications to products using the VTEX Catalog API.

API Endpoint: POST /api/catalog/pvt/product/{productId}/specification

Input CSV columns (required):
    _ProductId,CategoryId,FieldId,Text

Request body (FieldValueId is NOT sent):
    {
      "FieldId": <int>,
      "Text": "<string>"
    }

Features:
- Concurrent processing with ThreadPoolExecutor
- Token bucket rate limiting shared across all workers
- Adaptive handling of 429 (Too Many Requests) with automatic RPS reduction
- Exponential backoff with jitter for transient errors
- Per-worker HTTP sessions
- Timestamped outputs: successful/failed JSON + failed CSV + Markdown report

Env vars (.env supported):
    X-VTEX-API-AppKey
    X-VTEX-API-AppToken
    VTEX_ACCOUNT_NAME
    VTEX_ENVIRONMENT (optional, default: vtexcommercestable)

Usage:
    python3 add_product_specifications.py input.csv
    python3 add_product_specifications.py input.csv --workers 8 --rps 15
    python3 add_product_specifications.py input.csv --dry-run
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv


# ---------------- Rate Limiter ----------------

class TokenBucket:
    """Thread-safe token bucket rate limiter shared across workers."""

    def __init__(self, rate_per_sec: float, capacity: int):
        self.rate = max(1.0, float(rate_per_sec))
        self.capacity = max(1, int(capacity))
        self.tokens = float(self.capacity)
        self.timestamp = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> None:
        """Block until `tokens` are available, then consume them."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.timestamp
                if elapsed > 0:
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                    self.timestamp = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Need to wait
                needed = tokens - self.tokens
                sleep_time = needed / self.rate if self.rate > 0 else 1.0

            # sleep outside lock
            time.sleep(sleep_time)

    def update_rate(self, new_rate: float) -> None:
        with self._lock:
            self.rate = max(1.0, float(new_rate))


# ---------------- Progress ----------------

class ProgressTracker:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failures = 0
        self._lock = threading.Lock()

    def inc_success(self):
        with self._lock:
            self.success += 1
            self.total += 1

    def inc_failure(self):
        with self._lock:
            self.failures += 1
            self.total += 1

    def stats(self) -> Tuple[int, int, int]:
        with self._lock:
            return self.total, self.success, self.failures


# ---------------- Client ----------------

class VTEXSpecClient:
    """VTEX API client to add product specifications."""

    def __init__(
        self,
        account: str,
        environment: str,
        app_key: str,
        app_token: str,
        shared_bucket: TokenBucket,
        base_rps: float = 10.0,
    ):
        self.account = account
        self.environment = environment
        self.base_rps = float(base_rps)
        self.current_rps = float(base_rps)
        self.bucket = shared_bucket

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-VTEX-API-AppKey": app_key,
                "X-VTEX-API-AppToken": app_token,
            }
        )

        # Accept both "vtexcommercestable" and "vtexcommercestable.com.br"
        if self.environment.endswith(".com.br"):
            self.base_url = f"https://{self.account}.{self.environment}"
        else:
            self.base_url = f"https://{self.account}.{self.environment}.com.br"

        self.last_429_at: Optional[float] = None
        self._rate_lock = threading.Lock()

    def _adaptive_on_429(self, reset_after: Optional[float] = None) -> float:
        """Reduce current RPS and return a recommended delay."""
        with self._rate_lock:
            self.last_429_at = time.monotonic()
            self.current_rps = max(1.0, self.current_rps / 2.0)
            self.bucket.update_rate(self.current_rps)
            return float(reset_after) if reset_after is not None else 60.0

    def _maybe_restore_rate(self) -> None:
        with self._rate_lock:
            if self.last_429_at is None:
                return
            elapsed = time.monotonic() - self.last_429_at
            if elapsed > 60:
                target = min(self.base_rps, self.current_rps * 1.25)
                if abs(target - self.current_rps) >= 0.5:
                    self.current_rps = target
                    self.bucket.update_rate(target)
                if math.isclose(self.current_rps, self.base_rps, rel_tol=0.05):
                    self.last_429_at = None

    def post_specification(
        self, product_id: str, field_id: int, text: str, timeout: int = 30
    ) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog/pvt/product/{product_id}/specification"
        payload = {"FieldId": int(field_id), "Text": str(text)}

        self.bucket.consume(1.0)

        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
        except requests.RequestException as e:
            return (0, f"request_exception: {e}")

        if resp.status_code == 429:
            reset_sec = None
            for k in ("x-vtex-ratelimit-reset", "X-VTEX-Ratelimit-Reset"):
                if k in resp.headers:
                    try:
                        reset_sec = float(resp.headers[k])
                    except Exception:
                        reset_sec = None
                    break
            delay = self._adaptive_on_429(reset_sec)
            time.sleep(min(2.0, max(0.2, delay)))

        self._maybe_restore_rate()
        return (resp.status_code, resp.text)


# ---------------- Utilities ----------------

def exponential_backoff(
    base: float, factor: float, attempt: int, jitter: float = 0.25, max_sleep: float = 45.0
) -> float:
    sleep = min(max_sleep, base * (factor ** attempt))
    return sleep * (1 - jitter / 2 + random.random() * jitter)


def load_vtex_credentials() -> Dict[str, str]:
    load_dotenv()

    app_key = os.getenv("X-VTEX-API-AppKey")
    app_token = os.getenv("X-VTEX-API-AppToken")
    account_name = os.getenv("VTEX_ACCOUNT_NAME")
    environment = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")

    if not all([app_key, app_token, account_name]):
        print("Error: Missing VTEX credentials in .env")
        print("Required: X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME")
        sys.exit(1)

    return {
        "app_key": app_key,
        "app_token": app_token,
        "account_name": account_name,
        "environment": environment,
    }


@dataclass
class SpecRow:
    product_id: str
    category_id: str
    field_id: int
    text: str


def read_input_rows(csv_path: str) -> List[SpecRow]:
    required = {"_ProductId", "CategoryId", "FieldId", "Text"}
    rows: List[SpecRow] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        missing = required - headers
        if missing:
            print(f"Error: CSV missing required columns: {sorted(missing)}")
            print(f"Found columns: {reader.fieldnames}")
            sys.exit(1)

        for i, r in enumerate(reader, start=2):
            pid = (r.get("_ProductId") or "").strip()
            cat = (r.get("CategoryId") or "").strip()
            fid_raw = (r.get("FieldId") or "").strip()
            text = (r.get("Text") or "").strip()

            if not pid or not fid_raw or text == "":
                # Skip blank / invalid lines but keep it strict-ish
                continue

            try:
                fid = int(fid_raw)
            except ValueError:
                print(f"[WARN] Line {i}: FieldId is not int: {fid_raw!r}. Skipping.")
                continue

            rows.append(SpecRow(product_id=pid, category_id=cat, field_id=fid, text=text))

    return rows


# ---------------- Worker ----------------

def worker_post_spec(
    row: SpecRow,
    client: VTEXSpecClient,
    progress: ProgressTracker,
    results_lock: threading.Lock,
    successful: List[Dict[str, Any]],
    failed: List[Dict[str, Any]],
    timeout: int = 30,
) -> None:
    max_attempts = 5
    attempt = 0
    status, text = 0, ""

    while attempt < max_attempts:
        status, text = client.post_specification(row.product_id, row.field_id, row.text, timeout=timeout)

        if 200 <= status < 300:
            progress.inc_success()
            with results_lock:
                successful.append(
                    {
                        "product_id": row.product_id,
                        "category_id": row.category_id,
                        "field_id": row.field_id,
                        "text": row.text,
                        "status_code": status,
                    }
                )
            return

        if status in (408, 409, 425, 429, 500, 502, 503, 504, 0):
            time.sleep(exponential_backoff(base=0.5, factor=2.0, attempt=attempt))
            attempt += 1
            continue

        break  # non-retriable

    progress.inc_failure()
    with results_lock:
        failed.append(
            {
                "product_id": row.product_id,
                "category_id": row.category_id,
                "field_id": row.field_id,
                "text": row.text,
                "status_code": status,
                "error": (text[:500] if text else "Unknown error"),
            }
        )


# ---------------- Orchestration ----------------

def process_posts(
    rows: List[SpecRow],
    credentials: Dict[str, str],
    base_rps: float,
    num_workers: int,
    timeout: int,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    shared_bucket = TokenBucket(rate_per_sec=base_rps, capacity=max(5, int(base_rps)))
    progress = ProgressTracker()
    results_lock = threading.Lock()

    successful: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    total_items = len(rows)
    start_time = time.monotonic()
    last_report = start_time
    last_total = 0

    print("\n" + "=" * 60)
    print("VTEX Product Specification Add (Concurrent)")
    print("=" * 60)
    print(f"Account: {credentials['account_name']} | Env: {credentials['environment']}")
    print(f"Workers: {num_workers} | RPS: {base_rps} | Rows: {total_items}")
    if dry_run:
        print("[DRY RUN MODE - No API calls]")
    print("=" * 60 + "\n")

    if dry_run:
        for r in rows:
            successful.append(
                {
                    "product_id": r.product_id,
                    "category_id": r.category_id,
                    "field_id": r.field_id,
                    "text": r.text,
                    "status": "dry_run",
                }
            )
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    def mk_client() -> VTEXSpecClient:
        return VTEXSpecClient(
            credentials["account_name"],
            credentials["environment"],
            credentials["app_key"],
            credentials["app_token"],
            shared_bucket,
            base_rps,
        )

    clients = [mk_client() for _ in range(num_workers)]
    max_in_flight = max(32, num_workers * 4)

    def drain_and_report(futures_set, blocking: bool = False):
        nonlocal last_report, last_total

        if not futures_set:
            return

        try:
            timeout_val = None if blocking else 0.1
            for f in as_completed(list(futures_set), timeout=timeout_val):
                try:
                    f.result()
                except Exception as e:
                    print(f"[WARN] Worker exception: {e}")
                    progress.inc_failure()
                futures_set.remove(f)
                if not blocking:
                    break
        except Exception:
            if blocking:
                raise

        now = time.monotonic()
        if now - last_report >= 2.0:
            total, ok, fail = progress.stats()
            processed_since = total - last_total
            elapsed_window = now - last_report
            rps_est = processed_since / elapsed_window if elapsed_window > 0 else 0.0

            remaining = max(0, total_items - total)
            effective = max(0.1, rps_est)
            eta_sec = remaining / effective
            eta_str = str(timedelta(seconds=int(eta_sec)))

            pct = (total / total_items * 100) if total_items else 0
            print(
                f"[Progress] {total}/{total_items} ({pct:.1f}%) | OK={ok} FAIL={fail} | "
                f"RPS~{rps_est:.1f} | ETA={eta_str} | currRPS={shared_bucket.rate:.1f}"
            )
            last_report = now
            last_total = total

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = set()
        idx = 0

        for row in rows:
            while len(futures) >= max_in_flight:
                drain_and_report(futures)

            client = clients[idx % num_workers]
            idx += 1

            fut = executor.submit(
                worker_post_spec,
                row,
                client,
                progress,
                results_lock,
                successful,
                failed,
                timeout,
            )
            futures.add(fut)
            drain_and_report(futures)

        while futures:
            drain_and_report(futures, blocking=True)

    elapsed = time.monotonic() - start_time
    return successful, failed, elapsed


def export_results(successful: List[Dict[str, Any]], failed: List[Dict[str, Any]], output_dir: str) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if successful:
        p = os.path.join(output_dir, f"{ts}_successful.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(successful, f, indent=2, ensure_ascii=False)
        print(f"Successful: {p}")

    if failed:
        pj = os.path.join(output_dir, f"{ts}_failed.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(failed, f, indent=2, ensure_ascii=False)

        pc = os.path.join(output_dir, f"{ts}_failed.csv")
        with open(pc, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["product_id", "category_id", "field_id", "text", "status_code", "error"],
            )
            writer.writeheader()
            for item in failed:
                writer.writerow(item)

        print(f"Failed JSON: {pj}")
        print(f"Failed CSV: {pc}")


def generate_report(
    successful: List[Dict[str, Any]],
    failed: List[Dict[str, Any]],
    total: int,
    elapsed: float,
    output_dir: str,
    workers: int,
    rps: float,
    dry_run: bool,
) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{ts}_spec_add_report.md")

    mode = " (DRY RUN)" if dry_run else ""
    eff_rps = (len(successful) / elapsed) if elapsed > 0 else 0.0

    def fmt_time(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        if h > 0:
            return f"{h}h {m}m {s:.1f}s"
        if m > 0:
            return f"{m}m {s:.1f}s"
        return f"{s:.1f}s"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Product Specification Add Report{mode}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Configuration\n\n")
        f.write("| Setting | Value |\n|---|---|\n")
        f.write(f"| Workers | {workers} |\n")
        f.write(f"| Target RPS | {rps} |\n")
        f.write(f"| Effective RPS | {eff_rps:.1f} |\n\n")

        f.write("## Results\n\n")
        f.write("| Metric | Count |\n|---|---|\n")
        f.write(f"| Total Rows | {total} |\n")
        f.write(f"| Successful | {len(successful)} |\n")
        f.write(f"| Failed | {len(failed)} |\n")
        f.write(f"| Success Rate | {(len(successful)/total*100):.1f}% |\n")
        f.write(f"| Elapsed Time | {fmt_time(elapsed)} |\n\n")

        if failed:
            f.write("## Sample Failures (first 50)\n\n")
            f.write("| ProductId | CategoryId | FieldId | Status | Error |\n")
            f.write("|---|---|---:|---:|---|\n")
            for item in failed[:50]:
                err = (item.get("error") or "Unknown")[:120].replace("\n", " ")
                f.write(
                    f"| {item.get('product_id','')} | {item.get('category_id','')} | "
                    f"{item.get('field_id','')} | {item.get('status_code','')} | {err} |\n"
                )
            if len(failed) > 50:
                f.write(f"\n*...and {len(failed) - 50} more failures*\n")

    return path


def main():
    parser = argparse.ArgumentParser(
        description="Add product specifications in VTEX catalog (concurrent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 add_product_specifications.py input.csv
  python3 add_product_specifications.py input.csv --workers 8 --rps 15
  python3 add_product_specifications.py input.csv --dry-run
""",
    )

    parser.add_argument("input_csv", help="CSV with _ProductId,CategoryId,FieldId,Text")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers (default: 5)")
    parser.add_argument("--rps", type=float, default=10.0, help="Requests per second (default: 10)")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="No API calls, just simulate")
    parser.add_argument("--output-dir", "-o", default=".", help="Output dir for reports (default: .)")

    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: Input file not found: {args.input_csv}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    print("Loading VTEX credentials...")
    creds = load_vtex_credentials()

    print(f"Reading input rows from: {args.input_csv}")
    rows = read_input_rows(args.input_csv)
    if not rows:
        print("Error: No valid rows found in CSV (check required columns and values).")
        sys.exit(1)

    print(f"Found {len(rows)} rows to process")

    try:
        successful, failed, elapsed = process_posts(
            rows, creds, args.rps, args.workers, args.timeout, args.dry_run
        )
    except KeyboardInterrupt:
        print("\n[WARN] Interrupted by user")
        sys.exit(130)

    print("\n" + "=" * 60)
    print("SPEC ADD COMPLETE")
    print("=" * 60)
    print(f"Total rows: {len(rows)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Time: {elapsed:.1f}s")
    eff = (len(successful) / elapsed) if elapsed > 0 else 0.0
    print(f"Effective RPS: {eff:.1f}")
    print("=" * 60 + "\n")

    export_results(successful, failed, args.output_dir)
    report_path = generate_report(
        successful, failed, len(rows), elapsed, args.output_dir, args.workers, args.rps, args.dry_run
    )
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()