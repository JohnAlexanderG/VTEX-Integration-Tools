#!/usr/bin/env python3
"""
Delete Product Specifications from VTEX (Concurrent)

Removes all specifications from products using the VTEX Catalog API.
Reads product IDs from a CSV file and processes deletions with concurrent workers.

API Endpoint: DELETE /api/catalog/pvt/product/{productId}/specification

Features:
- Concurrent processing with ThreadPoolExecutor for better performance
- Token bucket rate limiting shared across all workers
- Adaptive handling of 429 (Too Many Requests) with automatic RPS reduction
- Exponential backoff with jitter for transient errors
- Per-worker HTTP sessions to avoid contention

Usage:
    python3 delete_product_specifications.py products.csv
    python3 delete_product_specifications.py products.csv --workers 8 --rps 15
    python3 delete_product_specifications.py products.csv --dry-run

Input CSV Format:
    _ProductId
    123
    456
    789

Output:
    - Timestamped JSON files for successful and failed deletions
    - Markdown report with statistics
"""

import argparse
import csv
import json
import os
import sys
import time
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

import requests
from dotenv import load_dotenv


# --------------- Token Bucket Rate Limiter ---------------

class TokenBucket:
    """Thread-safe token bucket for rate limiting across concurrent workers."""

    def __init__(self, rate_per_sec: float, capacity: int):
        self.rate = float(rate_per_sec)
        self.capacity = int(capacity)
        self.tokens = float(capacity)
        self.timestamp = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.timestamp = now

            if self.tokens < tokens:
                needed = tokens - self.tokens
                sleep_time = needed / self.rate
                self._lock.release()
                time.sleep(sleep_time)
                self._lock.acquire()
                now2 = time.monotonic()
                elapsed2 = now2 - self.timestamp
                self.tokens = min(self.capacity, self.tokens + elapsed2 * self.rate)
                self.timestamp = now2

            self.tokens -= tokens

    def update_rate(self, new_rate: float):
        with self._lock:
            self.rate = max(1.0, float(new_rate))


# --------------- Progress Tracker ---------------

class ProgressTracker:
    """Thread-safe progress tracking for concurrent operations."""

    def __init__(self):
        self.total = 0
        self.success = 0
        self.failures = 0
        self._lock = threading.Lock()

    def increment_success(self):
        with self._lock:
            self.success += 1
            self.total += 1

    def increment_failure(self):
        with self._lock:
            self.failures += 1
            self.total += 1

    def get_stats(self):
        with self._lock:
            return self.total, self.success, self.failures


# --------------- VTEX Client ---------------

class VTEXDeleteClient:
    """VTEX API client for deleting product specifications."""

    def __init__(self, account: str, environment: str, app_key: str, app_token: str,
                 shared_bucket: TokenBucket, base_rps: float = 10.0):
        self.account = account
        self.environment = environment
        self.base_rps = base_rps
        self.current_rps = base_rps
        self.bucket = shared_bucket
        self._rate_lock = threading.Lock()

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-VTEX-API-AppKey": app_key,
            "X-VTEX-API-AppToken": app_token,
        })

        if self.environment.endswith('.com.br'):
            self.base_url = f"https://{self.account}.{self.environment}"
        else:
            self.base_url = f"https://{self.account}.{self.environment}.com.br"

        self.last_429_at: Optional[float] = None

    def _adaptive_on_429(self, reset_after: Optional[float] = None):
        with self._rate_lock:
            self.last_429_at = time.monotonic()
            new_rps = max(1.0, self.current_rps / 2.0)
            self.current_rps = new_rps
            self.bucket.update_rate(new_rps)
            if reset_after is None:
                reset_after = 60.0
            return reset_after

    def _maybe_restore_rate(self):
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

    def delete_specification(self, product_id: str, timeout: int = 30) -> Tuple[int, str]:
        """Delete all specifications from a product. Returns (status_code, response_text)."""
        url = f"{self.base_url}/api/catalog/pvt/product/{product_id}/specification"

        self.bucket.consume(1.0)

        try:
            resp = self.session.delete(url, timeout=timeout)
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
            time.sleep(min(2.0, delay))

        self._maybe_restore_rate()

        return (resp.status_code, resp.text)


# --------------- Utilities ---------------

def exponential_backoff(base: float, factor: float, attempt: int,
                       jitter: float = 0.2, max_sleep: float = 30.0) -> float:
    sleep = min(max_sleep, base * (factor ** attempt))
    return sleep * (1 - jitter/2 + random.random() * jitter)


def load_vtex_credentials():
    """Load VTEX API credentials from .env file."""
    load_dotenv()

    app_key = os.getenv('X-VTEX-API-AppKey')
    app_token = os.getenv('X-VTEX-API-AppToken')
    account_name = os.getenv('VTEX_ACCOUNT_NAME')
    environment = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

    if not all([app_key, app_token, account_name]):
        print("Error: Missing VTEX credentials in .env file")
        print("Required: X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME")
        sys.exit(1)

    return {
        'app_key': app_key,
        'app_token': app_token,
        'account_name': account_name,
        'environment': environment
    }


def read_product_ids(csv_path: str) -> list:
    """Read product IDs from CSV file."""
    product_ids = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        if '_ProductId' not in reader.fieldnames:
            print(f"Error: CSV must contain '_ProductId' column")
            print(f"Found columns: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            product_id = row.get('_ProductId', '').strip()
            if product_id:
                product_ids.append(product_id)

    return product_ids


# --------------- Worker Function ---------------

def worker_delete_specification(product_id: str, client: VTEXDeleteClient,
                                progress: ProgressTracker,
                                results_lock: threading.Lock,
                                successful: list, failed: list,
                                timeout: int = 30) -> None:
    """Worker function to delete specifications for a single product."""
    max_attempts = 5
    attempt = 0
    status, text = 0, ""

    while attempt < max_attempts:
        status, text = client.delete_specification(product_id, timeout)

        if status in (200, 204):
            progress.increment_success()
            with results_lock:
                successful.append({
                    'product_id': product_id,
                    'status_code': status
                })
            return
        elif status in (408, 409, 425, 429, 500, 502, 503, 504, 0):
            sleep_time = exponential_backoff(base=0.5, factor=2.0, attempt=attempt,
                                             jitter=0.3, max_sleep=45.0)
            time.sleep(sleep_time)
            attempt += 1
            continue
        else:
            break

    progress.increment_failure()
    with results_lock:
        failed.append({
            'product_id': product_id,
            'status_code': status,
            'error': text[:500] if text else 'Unknown error'
        })


# --------------- Main Processing ---------------

def process_deletions(product_ids: list, credentials: dict,
                      base_rps: float, num_workers: int,
                      timeout: int, dry_run: bool = False) -> Tuple[list, list, float]:
    """Process all deletions with concurrent workers."""

    shared_bucket = TokenBucket(rate_per_sec=base_rps, capacity=max(5, int(base_rps)))
    progress = ProgressTracker()

    successful = []
    failed = []
    results_lock = threading.Lock()

    total_items = len(product_ids)
    start_time = time.monotonic()
    last_report = start_time
    last_total = 0

    print("\n" + "=" * 60)
    print("VTEX Product Specification Deletion (Concurrent)")
    print("=" * 60)
    print(f"Account: {credentials['account_name']} | Env: {credentials['environment']}")
    print(f"Workers: {num_workers} | RPS: {base_rps} | Products: {total_items}")
    if dry_run:
        print("[DRY RUN MODE - No actual deletions]")
    print("=" * 60 + "\n")

    if dry_run:
        for pid in product_ids:
            successful.append({'product_id': pid, 'status': 'dry_run'})
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    def create_worker_client():
        return VTEXDeleteClient(
            credentials['account_name'],
            credentials['environment'],
            credentials['app_key'],
            credentials['app_token'],
            shared_bucket,
            base_rps
        )

    clients = [create_worker_client() for _ in range(num_workers)]
    max_in_flight = max(32, num_workers * 4)

    def drain_and_report(futures_set, blocking=False):
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
                    progress.increment_failure()
                futures_set.remove(f)
                if not blocking:
                    break
        except:
            if blocking:
                raise

        now = time.monotonic()
        if now - last_report >= 2.0:
            total, success, failures = progress.get_stats()
            processed_since = total - last_total
            elapsed = now - last_report
            rps = processed_since / elapsed if elapsed > 0 else 0.0

            remaining = max(0, total_items - total)
            effective_rps = max(0.1, rps)
            eta_sec = remaining / effective_rps
            eta_str = str(timedelta(seconds=int(eta_sec)))

            current_rate = shared_bucket.rate
            pct = (total / total_items * 100) if total_items > 0 else 0
            print(f"[Progress] {total}/{total_items} ({pct:.1f}%) | OK={success} FAIL={failures} | "
                  f"RPS~{rps:.1f} | ETA={eta_str} | currRPS={current_rate:.1f}")

            last_report = now
            last_total = total

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = set()
        idx = 0

        for product_id in product_ids:
            while len(futures) >= max_in_flight:
                drain_and_report(futures)

            client = clients[idx % num_workers]
            idx += 1

            fut = executor.submit(
                worker_delete_specification,
                product_id, client, progress, results_lock,
                successful, failed, timeout
            )
            futures.add(fut)
            drain_and_report(futures)

        while futures:
            drain_and_report(futures, blocking=True)

    elapsed = time.monotonic() - start_time
    return successful, failed, elapsed


def export_results(successful: list, failed: list, output_dir: str):
    """Export results to JSON and CSV files."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if successful:
        success_path = os.path.join(output_dir, f'{timestamp}_successful.json')
        with open(success_path, 'w', encoding='utf-8') as f:
            json.dump(successful, f, indent=4, ensure_ascii=False)
        print(f"Successful: {success_path}")

    if failed:
        failed_json = os.path.join(output_dir, f'{timestamp}_failed.json')
        with open(failed_json, 'w', encoding='utf-8') as f:
            json.dump(failed, f, indent=4, ensure_ascii=False)

        failed_csv = os.path.join(output_dir, f'{timestamp}_failed.csv')
        with open(failed_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['product_id', 'status_code', 'error'])
            writer.writeheader()
            for item in failed:
                writer.writerow({
                    'product_id': item['product_id'],
                    'status_code': item.get('status_code', ''),
                    'error': item.get('error', '')
                })

        print(f"Failed JSON: {failed_json}")
        print(f"Failed CSV: {failed_csv}")


def generate_report(successful: list, failed: list, total: int,
                   elapsed: float, output_dir: str,
                   workers: int, rps: float, dry_run: bool = False) -> str:
    """Generate markdown report."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(output_dir, f'{timestamp}_deletion_report.md')

    mode = " (DRY RUN)" if dry_run else ""
    avg_rps = len(successful) / elapsed if elapsed > 0 else 0

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Product Specification Deletion Report{mode}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Configuration\n\n")
        f.write(f"| Setting | Value |\n")
        f.write(f"|---------|-------|\n")
        f.write(f"| Workers | {workers} |\n")
        f.write(f"| Target RPS | {rps} |\n")
        f.write(f"| Effective RPS | {avg_rps:.1f} |\n\n")
        f.write("## Results\n\n")
        f.write(f"| Metric | Count |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total Products | {total} |\n")
        f.write(f"| Successful | {len(successful)} |\n")
        f.write(f"| Failed | {len(failed)} |\n")
        f.write(f"| Success Rate | {len(successful)/total*100:.1f}% |\n")

        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = elapsed % 60
        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds:.1f}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds:.1f}s"
        else:
            time_str = f"{seconds:.1f}s"

        f.write(f"| Elapsed Time | {time_str} |\n\n")

        if failed:
            f.write("## Failed Deletions\n\n")
            f.write("| ProductId | Status | Error |\n")
            f.write("|-----------|--------|-------|\n")
            for item in failed[:50]:
                error = item.get('error', 'Unknown')[:80]
                f.write(f"| {item['product_id']} | {item.get('status_code', '')} | {error} |\n")

            if len(failed) > 50:
                f.write(f"\n*...and {len(failed) - 50} more failures*\n")

    return report_path


def main():
    parser = argparse.ArgumentParser(
        description='Delete product specifications from VTEX catalog (concurrent)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 delete_product_specifications.py products.csv
    python3 delete_product_specifications.py products.csv --workers 8 --rps 15
    python3 delete_product_specifications.py products.csv --dry-run
        """
    )

    parser.add_argument('input_csv', help='CSV file with _ProductId column')
    parser.add_argument('--workers', type=int, default=5,
                        help='Number of concurrent workers (default: 5)')
    parser.add_argument('--rps', type=float, default=10.0,
                        help='Requests per second limit (default: 10)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Request timeout in seconds (default: 30)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simulate deletions without making API calls')
    parser.add_argument('--output-dir', '-o', default='.',
                        help='Output directory for reports (default: current directory)')

    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: Input file not found: {args.input_csv}")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    print("Loading VTEX credentials...")
    credentials = load_vtex_credentials()

    print(f"Reading product IDs from: {args.input_csv}")
    product_ids = read_product_ids(args.input_csv)

    if not product_ids:
        print("Error: No product IDs found in CSV")
        sys.exit(1)

    print(f"Found {len(product_ids)} products to process")

    try:
        successful, failed, elapsed = process_deletions(
            product_ids, credentials,
            args.rps, args.workers,
            args.timeout, args.dry_run
        )
    except KeyboardInterrupt:
        print("\n[WARN] Process interrupted by user")
        sys.exit(130)

    print("\n" + "=" * 60)
    print("DELETION COMPLETE")
    print("=" * 60)
    print(f"Total: {len(product_ids)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60
    if hours > 0:
        print(f"Time: {hours}h {minutes}m {seconds:.1f}s")
    elif minutes > 0:
        print(f"Time: {minutes}m {seconds:.1f}s")
    else:
        print(f"Time: {seconds:.1f}s")

    avg_rps = len(successful) / elapsed if elapsed > 0 else 0
    print(f"Effective RPS: {avg_rps:.1f}")
    print("=" * 60 + "\n")

    export_results(successful, failed, args.output_dir)
    report_path = generate_report(
        successful, failed, len(product_ids), elapsed,
        args.output_dir, args.workers, args.rps, args.dry_run
    )
    print(f"Report: {report_path}")


if __name__ == '__main__':
    main()
