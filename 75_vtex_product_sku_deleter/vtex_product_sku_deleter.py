#!/usr/bin/env python3
"""
Elimina masivamente SKUs y Productos completos en VTEX (borrado en dos fases).

Fase 1:
    DELETE /api/catalog/pvt/stockkeepingunit/{skuId}
    Se ejecuta para todos los SkuId del CSV de entrada.

Fase 2:
    DELETE /api/catalog/pvt/product/{productId}
    Se ejecuta unicamente para los productos cuyos SKUs (todos los listados en el
    CSV para ese ProductId) terminaron en exito o ya no existian (HTTP 404) en la
    Fase 1. Si algun SKU de un producto no pudo eliminarse, ese producto se omite
    (no se llama a la API) y se reporta para revision manual.

Estos endpoints no aparecen en la referencia publica de la Catalog API de VTEX
(https://developers.vtex.com/docs/api-reference/catalog-api), pero forman parte
de la API privada/legacy de catalogo (prefijo /pvt/) y son los que VTEX Soporte
recomienda para este tipo de limpieza masiva por lotes.

Uso:
    python3 vtex_product_sku_deleter.py <input_csv> --dry-run
    python3 vtex_product_sku_deleter.py <input_csv> --confirm-delete

Ejemplo:
    python3 vtex_product_sku_deleter.py ids.csv --dry-run
    python3 vtex_product_sku_deleter.py ids.csv --confirm-delete --workers 3 --rps 3

Formato del CSV de entrada (una fila por SKU; varios SKUs pueden compartir el
mismo ProductId):
    SkuId,ProductId
    123456,987
    123457,987
    123458,988

Variables de entorno requeridas (.env en raiz, no necesarias con --dry-run):
    - VTEX_ACCOUNT_NAME: Nombre de la cuenta VTEX
    - VTEX_ENVIRONMENT: Entorno VTEX (ej: vtexcommercestable)
    - X-VTEX-API-AppKey: Clave de aplicacion VTEX
    - X-VTEX-API-AppToken: Token de aplicacion VTEX
"""

import argparse
import csv
import json
import math
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


SUCCESS_STATUSES = (200, 202, 204)
ALREADY_GONE_STATUS = 404
RETRIABLE_STATUSES = (0, 408, 409, 425, 429, 500, 502, 503, 504)
MAX_ATTEMPTS = 5


@dataclass
class SkuTask:
    sku_id: str
    product_id: str
    row_number: int


@dataclass
class ProductTask:
    product_id: str
    sku_ids: List[str] = field(default_factory=list)


@dataclass
class SkippedRow:
    sku_id: str
    product_id: str
    row_number: int
    reason: str


@dataclass
class SkippedProduct:
    product_id: str
    sku_ids: List[str]
    failed_sku_ids: List[str]
    reason: str


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


class VTEXCatalogDeleteClient:
    """VTEX Catalog API client for deleting SKUs and Products (private/legacy pvt API)."""

    def __init__(
        self,
        account: str,
        environment: str,
        app_key: str,
        app_token: str,
        shared_bucket: TokenBucket,
        base_rps: float = 5.0,
    ):
        self.account = account
        self.environment = environment
        self.base_rps = base_rps
        self.current_rps = base_rps
        self.bucket = shared_bucket
        self._rate_lock = threading.Lock()

        if requests is None:
            die("Missing dependency 'requests'. Install it before running real VTEX deletes.")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-VTEX-API-AppKey": app_key,
            "X-VTEX-API-AppToken": app_token,
        })

        self.base_url = build_base_url(account, environment)
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

    def _request(self, method: str, url: str, timeout: int) -> Tuple[int, str]:
        self.bucket.consume(1.0)

        try:
            response = self.session.request(method, url, timeout=timeout)
        except requests.RequestException as exc:
            return 0, f"request_exception: {exc}"

        if response.status_code == 429:
            reset_sec = None
            for header in ("x-vtex-ratelimit-reset", "X-VTEX-Ratelimit-Reset"):
                if header in response.headers:
                    try:
                        reset_sec = float(response.headers[header])
                    except Exception:
                        reset_sec = None
                    break
            delay = self._adaptive_on_429(reset_sec)
            time.sleep(min(2.0, delay))

        self._maybe_restore_rate()
        return response.status_code, response.text

    def _delete(self, url: str, timeout: int) -> Tuple[int, str]:
        return self._request("DELETE", url, timeout)

    def delete_entity(self, entity_type: str, entity_id: str, timeout: int = 30) -> Tuple[int, str]:
        if entity_type == "sku":
            url = f"{self.base_url}/api/catalog/pvt/stockkeepingunit/{entity_id}"
        else:
            url = f"{self.base_url}/api/catalog/pvt/product/{entity_id}"
        return self._delete(url, timeout)


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def build_base_url(account: str, environment: str) -> str:
    if environment.endswith(".com.br"):
        return f"https://{account}.{environment}"
    return f"https://{account}.{environment}.com.br"


def exponential_backoff(
    base: float,
    factor: float,
    attempt: int,
    jitter: float = 0.2,
    max_sleep: float = 30.0,
) -> float:
    sleep = min(max_sleep, base * (factor ** attempt))
    return sleep * (1 - jitter / 2 + random.random() * jitter)


def load_vtex_credentials(required: bool = True) -> Optional[dict]:
    """Load VTEX API credentials from .env at the project root."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(project_root, ".env")
    if load_dotenv:
        load_dotenv(dotenv_path=env_path)
    elif required:
        print("Warning: missing dependency 'python-dotenv'; reading credentials from current environment only")

    if requests is None and required:
        die("Missing dependency 'requests'. Install it before running real VTEX deletes.")

    app_key = os.getenv("X-VTEX-API-AppKey")
    app_token = os.getenv("X-VTEX-API-AppToken")
    account_name = os.getenv("VTEX_ACCOUNT_NAME")
    environment = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")

    missing = []
    if not app_key:
        missing.append("X-VTEX-API-AppKey")
    if not app_token:
        missing.append("X-VTEX-API-AppToken")
    if not account_name:
        missing.append("VTEX_ACCOUNT_NAME")

    if missing and required:
        print(f"Error: Missing VTEX credentials in {env_path}")
        print(f"Required: {', '.join(missing)}")
        sys.exit(1)

    if missing:
        return None

    return {
        "app_key": app_key,
        "app_token": app_token,
        "account_name": account_name,
        "environment": environment,
    }


def sniff_csv_dialect(path: str) -> csv.Dialect:
    with open(path, "r", encoding="utf-8-sig", newline="") as file_obj:
        sample = file_obj.read(8192)
        try:
            return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        except csv.Error:
            class DefaultDialect(csv.Dialect):
                delimiter = ","
                quotechar = '"'
                doublequote = True
                skipinitialspace = True
                lineterminator = "\n"
                quoting = csv.QUOTE_MINIMAL

            return DefaultDialect()


def normalize_header_map(fieldnames) -> Dict[str, str]:
    return {header.strip(): header for header in (fieldnames or []) if header and header.strip()}


def normalize_header_name(header: str) -> str:
    return re.sub(r"[\s_-]+", "", header or "").lower()


def find_header(field_map: Dict[str, str], canonical: str) -> Optional[str]:
    for header, original in field_map.items():
        if normalize_header_name(header) == canonical:
            return original
    return None


def load_delete_tasks(
    path: str,
    limit: Optional[int] = None,
) -> Tuple[List[SkuTask], "Dict[str, List[str]]", List[SkippedRow], Dict[str, int]]:
    dialect = sniff_csv_dialect(path)
    sku_tasks: List[SkuTask] = []
    skipped: List[SkippedRow] = []
    product_to_skus: Dict[str, List[str]] = {}
    seen_sku_ids: Set[str] = set()
    rows_read = 0

    with open(path, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj, dialect=dialect)
        field_map = normalize_header_map(reader.fieldnames)
        sku_header = find_header(field_map, "skuid")
        product_header = find_header(field_map, "productid")
        if not sku_header or not product_header:
            found = ", ".join(field_map.keys()) if field_map else "(sin encabezados)"
            raise ValueError(
                f"CSV '{path}' debe tener columnas SkuId y ProductId. Columnas encontradas: {found}"
            )

        for row_number, row in enumerate(reader, start=2):
            if limit is not None and rows_read >= limit:
                break
            rows_read += 1

            sku_id = (row.get(sku_header) or "").strip()
            product_id = (row.get(product_header) or "").strip()

            if not sku_id or not product_id:
                skipped.append(SkippedRow(
                    sku_id=sku_id,
                    product_id=product_id,
                    row_number=row_number,
                    reason="missing_sku_id_or_product_id",
                ))
                continue

            if sku_id in seen_sku_ids:
                skipped.append(SkippedRow(
                    sku_id=sku_id,
                    product_id=product_id,
                    row_number=row_number,
                    reason="duplicate_sku_id",
                ))
                continue

            seen_sku_ids.add(sku_id)
            sku_tasks.append(SkuTask(sku_id=sku_id, product_id=product_id, row_number=row_number))
            product_to_skus.setdefault(product_id, []).append(sku_id)

    stats = {
        "rows_read": rows_read,
        "unique_skus": len(sku_tasks),
        "unique_products": len(product_to_skus),
        "skipped_rows": len(skipped),
    }
    return sku_tasks, product_to_skus, skipped, stats


def attempt_delete_with_retry(
    client: VTEXCatalogDeleteClient,
    entity_type: str,
    entity_id: str,
    timeout: int,
) -> Tuple[str, int, str]:
    attempt = 0
    status, text = 0, ""

    while attempt < MAX_ATTEMPTS:
        status, text = client.delete_entity(entity_type, entity_id, timeout)

        if status in SUCCESS_STATUSES:
            return "success", status, text
        if status == ALREADY_GONE_STATUS:
            return "already_gone", status, text
        if status in RETRIABLE_STATUSES:
            time.sleep(exponential_backoff(base=0.5, factor=2.0, attempt=attempt, jitter=0.3, max_sleep=45.0))
            attempt += 1
            continue
        break

    return "failed", status, text


def worker_delete_sku(
    task: SkuTask,
    client: VTEXCatalogDeleteClient,
    progress: ProgressTracker,
    results_lock: threading.Lock,
    successful: list,
    failed: list,
    timeout: int,
) -> None:
    outcome, status, text = attempt_delete_with_retry(client, "sku", task.sku_id, timeout)
    record = {
        "sku_id": task.sku_id,
        "product_id": task.product_id,
        "row_number": task.row_number,
        "status_code": status,
        "status": outcome,
    }
    if outcome in ("success", "already_gone"):
        progress.increment_success()
        with results_lock:
            successful.append(record)
    else:
        progress.increment_failure()
        record["error"] = text[:500] if text else "Unknown error"
        with results_lock:
            failed.append(record)


def worker_delete_product(
    task: ProductTask,
    client: VTEXCatalogDeleteClient,
    progress: ProgressTracker,
    results_lock: threading.Lock,
    successful: list,
    failed: list,
    timeout: int,
) -> None:
    outcome, status, text = attempt_delete_with_retry(client, "product", task.product_id, timeout)
    record = {
        "product_id": task.product_id,
        "sku_ids": ",".join(task.sku_ids),
        "status_code": status,
        "status": outcome,
    }
    if outcome in ("success", "already_gone"):
        progress.increment_success()
        with results_lock:
            successful.append(record)
    else:
        progress.increment_failure()
        record["error"] = text[:500] if text else "Unknown error"
        with results_lock:
            failed.append(record)


def process_phase(
    tasks: List[Any],
    credentials: Optional[dict],
    entity_type: str,
    phase_label: str,
    base_rps: float,
    num_workers: int,
    timeout: int,
    dry_run: bool,
) -> Tuple[list, list, float]:
    shared_bucket = TokenBucket(rate_per_sec=base_rps, capacity=max(5, int(base_rps)))
    progress = ProgressTracker()
    successful: list = []
    failed: list = []
    results_lock = threading.Lock()

    total_items = len(tasks)
    start_time = time.monotonic()
    last_report = start_time
    last_total = 0

    print("\n" + "=" * 70)
    print(f"VTEX {phase_label} Delete")
    print("=" * 70)
    if credentials:
        print(f"Account: {credentials['account_name']} | Env: {credentials['environment']}")
    else:
        print("Account: not loaded | Env: not loaded")
    print(f"Workers: {num_workers} | RPS: {base_rps} | Tasks: {total_items}")
    if dry_run:
        print("[DRY RUN MODE - No HTTP DELETE requests will be executed]")
    print("=" * 70 + "\n")

    if dry_run:
        for task in tasks:
            if entity_type == "sku":
                successful.append({
                    "sku_id": task.sku_id,
                    "product_id": task.product_id,
                    "row_number": task.row_number,
                    "status_code": "dry_run",
                    "status": "dry_run",
                })
            else:
                successful.append({
                    "product_id": task.product_id,
                    "sku_ids": ",".join(task.sku_ids),
                    "status_code": "dry_run",
                    "status": "dry_run",
                })
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    if not tasks:
        return successful, failed, 0.0

    if credentials is None:
        die("VTEX credentials are required when --dry-run is not enabled")

    def create_worker_client():
        return VTEXCatalogDeleteClient(
            credentials["account_name"],
            credentials["environment"],
            credentials["app_key"],
            credentials["app_token"],
            shared_bucket,
            base_rps,
        )

    clients = [create_worker_client() for _ in range(num_workers)]
    max_in_flight = max(32, num_workers * 4)
    worker_fn = worker_delete_sku if entity_type == "sku" else worker_delete_product

    def drain_and_report(futures_set, blocking=False):
        nonlocal last_report, last_total

        if not futures_set:
            return

        try:
            timeout_val = None if blocking else 0.1
            for future in as_completed(list(futures_set), timeout=timeout_val):
                try:
                    future.result()
                except Exception as exc:
                    print(f"[WARN] Worker exception: {exc}")
                    progress.increment_failure()
                futures_set.remove(future)
                if not blocking:
                    break
        except FuturesTimeoutError:
            pass

        now = time.monotonic()
        if now - last_report >= 2.0:
            total, success, failures = progress.get_stats()
            processed_since = total - last_total
            elapsed_since = now - last_report
            current_rps = processed_since / elapsed_since if elapsed_since > 0 else 0.0
            remaining = max(0, total_items - total)
            eta_sec = remaining / max(0.1, current_rps)
            eta_str = str(timedelta(seconds=int(eta_sec)))
            pct = (total / total_items * 100) if total_items else 0
            print(
                f"[Progress] {total}/{total_items} ({pct:.1f}%) | "
                f"OK={success} FAIL={failures} | RPS~{current_rps:.1f} | "
                f"ETA={eta_str} | currRPS={shared_bucket.rate:.1f}"
            )
            last_report = now
            last_total = total

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = set()
        index = 0

        for task in tasks:
            while len(futures) >= max_in_flight:
                drain_and_report(futures)

            client = clients[index % num_workers]
            index += 1
            future = executor.submit(
                worker_fn,
                task,
                client,
                progress,
                results_lock,
                successful,
                failed,
                timeout,
            )
            futures.add(future)
            drain_and_report(futures)

        while futures:
            drain_and_report(futures, blocking=True)

    elapsed = time.monotonic() - start_time
    return successful, failed, elapsed


def compute_product_eligibility(
    product_to_skus: Dict[str, List[str]],
    sku_failed: list,
) -> Tuple[List[ProductTask], List[SkippedProduct]]:
    failed_sku_ids = {item["sku_id"] for item in sku_failed}
    eligible: List[ProductTask] = []
    skipped: List[SkippedProduct] = []

    for product_id, sku_ids in product_to_skus.items():
        failing = [sku_id for sku_id in sku_ids if sku_id in failed_sku_ids]
        if failing:
            skipped.append(SkippedProduct(
                product_id=product_id,
                sku_ids=list(sku_ids),
                failed_sku_ids=failing,
                reason=f"{len(failing)} de {len(sku_ids)} SKUs no se pudieron eliminar",
            ))
        else:
            eligible.append(ProductTask(product_id=product_id, sku_ids=list(sku_ids)))

    return eligible, skipped


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=4, ensure_ascii=False)


def export_results(
    sku_successful: list,
    sku_failed: list,
    product_successful: list,
    product_failed: list,
    skipped_rows: List[SkippedRow],
    skipped_products: List[SkippedProduct],
    output_dir: str,
    prefix: Optional[str] = None,
) -> Dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = prefix or timestamp
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    def dump_json(name: str, payload: Any) -> None:
        path = os.path.join(output_dir, f"{file_prefix}_{name}.json")
        write_json(path, payload)
        paths[f"{name}_json"] = path

    dump_json("skus_successful", sku_successful)
    dump_json("skus_failed", sku_failed)
    dump_json("products_successful", product_successful)
    dump_json("products_failed", product_failed)
    dump_json("rows_skipped", [asdict(item) for item in skipped_rows])
    dump_json("products_skipped", [asdict(item) for item in skipped_products])

    def write_csv(name: str, items: List[Dict[str, Any]], fieldnames: List[str]) -> None:
        path = os.path.join(output_dir, f"{file_prefix}_{name}.csv")
        with open(path, "w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                writer.writerow({key: item.get(key, "") for key in fieldnames})
        paths[f"{name}_csv"] = path

    write_csv("skus_failed", sku_failed, ["sku_id", "product_id", "row_number", "status_code", "status", "error"])
    write_csv("products_failed", product_failed, ["product_id", "sku_ids", "status_code", "status", "error"])
    write_csv(
        "products_skipped",
        [
            {
                "product_id": item.product_id,
                "sku_ids": ",".join(item.sku_ids),
                "failed_sku_ids": ",".join(item.failed_sku_ids),
                "reason": item.reason,
            }
            for item in skipped_products
        ],
        ["product_id", "sku_ids", "failed_sku_ids", "reason"],
    )
    write_csv(
        "rows_skipped",
        [asdict(item) for item in skipped_rows],
        ["sku_id", "product_id", "row_number", "reason"],
    )

    for name, path in paths.items():
        print(f"{name}: {path}")
    return paths


def format_elapsed(elapsed: float) -> str:
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds:.1f}s"
    if minutes > 0:
        return f"{minutes}m {seconds:.1f}s"
    return f"{seconds:.1f}s"


def generate_report(
    input_stats: Dict[str, int],
    sku_successful: list,
    sku_failed: list,
    skipped_rows: List[SkippedRow],
    product_successful: list,
    product_failed: list,
    skipped_products: List[SkippedProduct],
    output_dir: str,
    prefix: Optional[str],
    dry_run: bool,
    elapsed_sku: float,
    elapsed_product: float,
    workers: int,
    rps: float,
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = prefix or timestamp
    report_path = os.path.join(output_dir, f"{file_prefix}_deletion_report.md")
    os.makedirs(output_dir, exist_ok=True)

    sku_attempted = len(sku_successful) + len(sku_failed)
    sku_rate = (len(sku_successful) / sku_attempted * 100) if sku_attempted else 0.0
    product_attempted = len(product_successful) + len(product_failed)
    product_rate = (len(product_successful) / product_attempted * 100) if product_attempted else 0.0
    mode_label = " (DRY RUN)" if dry_run else ""

    with open(report_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(f"# VTEX SKU & Product Delete Report{mode_label}\n\n")
        file_obj.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        file_obj.write("## Configuration\n\n")
        file_obj.write("| Setting | Value |\n")
        file_obj.write("|---------|-------|\n")
        file_obj.write(f"| Dry run | {dry_run} |\n")
        file_obj.write(f"| Workers | {workers} |\n")
        file_obj.write(f"| Target RPS | {rps} |\n")
        file_obj.write(f"| Elapsed (Phase 1 - SKUs) | {format_elapsed(elapsed_sku)} |\n")
        file_obj.write(f"| Elapsed (Phase 2 - Products) | {format_elapsed(elapsed_product)} |\n\n")

        file_obj.write("## Input Summary\n\n")
        file_obj.write("| Metric | Count |\n")
        file_obj.write("|--------|-------|\n")
        file_obj.write(f"| Rows read | {input_stats.get('rows_read', 0)} |\n")
        file_obj.write(f"| Unique SKU IDs | {input_stats.get('unique_skus', 0)} |\n")
        file_obj.write(f"| Unique Product IDs | {input_stats.get('unique_products', 0)} |\n")
        file_obj.write(f"| Skipped rows (malformed CSV) | {len(skipped_rows)} |\n\n")

        file_obj.write("## Phase 1 - SKU Deletion Results\n\n")
        file_obj.write("| Metric | Count |\n")
        file_obj.write("|--------|-------|\n")
        file_obj.write(f"| Successful (incl. already gone / HTTP 404) | {len(sku_successful)} |\n")
        file_obj.write(f"| Failed | {len(sku_failed)} |\n")
        file_obj.write(f"| Success rate | {sku_rate:.1f}% |\n\n")

        file_obj.write("## Phase 2 - Product Deletion Results\n\n")
        file_obj.write("| Metric | Count |\n")
        file_obj.write("|--------|-------|\n")
        file_obj.write(f"| Eligible for deletion | {product_attempted} |\n")
        file_obj.write(f"| Successful (incl. already gone / HTTP 404) | {len(product_successful)} |\n")
        file_obj.write(f"| Failed | {len(product_failed)} |\n")
        file_obj.write(f"| Skipped (blocked by a failed SKU) | {len(skipped_products)} |\n")
        file_obj.write(f"| Success rate (of attempted) | {product_rate:.1f}% |\n\n")

        if skipped_products:
            file_obj.write("## Products Skipped (Blocked by a Failed SKU)\n\n")
            file_obj.write("| Product ID | Reason |\n")
            file_obj.write("|------------|--------|\n")
            for item in skipped_products[:50]:
                file_obj.write(f"| {item.product_id} | {item.reason} |\n")
            if len(skipped_products) > 50:
                file_obj.write(f"\n*...and {len(skipped_products) - 50} more*\n")
            file_obj.write("\n")

        if sku_failed:
            file_obj.write("## Failed SKU Deletions\n\n")
            file_obj.write("| SKU ID | Product ID | Status | Error |\n")
            file_obj.write("|--------|------------|--------|-------|\n")
            for item in sku_failed[:50]:
                error = str(item.get("error", "Unknown")).replace("\n", " ")[:120]
                file_obj.write(
                    f"| {item.get('sku_id', '')} | {item.get('product_id', '')} | "
                    f"{item.get('status_code', '')} | {error} |\n"
                )
            if len(sku_failed) > 50:
                file_obj.write(f"\n*...and {len(sku_failed) - 50} more failures*\n")
            file_obj.write("\n")

        if product_failed:
            file_obj.write("## Failed Product Deletions\n\n")
            file_obj.write("| Product ID | Status | Error |\n")
            file_obj.write("|------------|--------|-------|\n")
            for item in product_failed[:50]:
                error = str(item.get("error", "Unknown")).replace("\n", " ")[:120]
                file_obj.write(f"| {item.get('product_id', '')} | {item.get('status_code', '')} | {error} |\n")
            if len(product_failed) > 50:
                file_obj.write(f"\n*...and {len(product_failed) - 50} more failures*\n")
            file_obj.write("\n")

        file_obj.write("## Notas Importantes\n\n")
        file_obj.write(
            "- La eliminacion dispara reindexacion automatica en VTEX; puede tomar algunos minutos "
            "en reflejarse en storefront y busqueda.\n"
        )
        file_obj.write(
            "- Un error persistente en el DELETE de un producto normalmente indica que aun existen "
            "dependencias (por ejemplo, SKUs no incluidos en este CSV). Revise el mensaje de error "
            "exacto en la tabla de arriba y comparta con VTEX Soporte si es necesario.\n"
        )
        file_obj.write(
            "- Como mitigacion inmediata y reversible mientras se confirma el borrado definitivo, "
            "puede desactivar los SKUs (`IsActive=false`) con "
            "`20_vtex_update_sku_from_csv/vtex_update_sku_from_csv.py`.\n"
        )

    return report_path


def print_final_summary(
    sku_tasks: list,
    sku_successful: list,
    sku_failed: list,
    product_tasks: list,
    product_successful: list,
    product_failed: list,
    skipped_products: list,
    elapsed_total: float,
) -> None:
    print("\n" + "=" * 70)
    print("DELETE PROCESS COMPLETE")
    print("=" * 70)
    print(f"SKUs: {len(sku_tasks)} | OK={len(sku_successful)} FAIL={len(sku_failed)}")
    print(
        f"Products eligible: {len(product_tasks)} | OK={len(product_successful)} "
        f"FAIL={len(product_failed)} | Skipped={len(skipped_products)}"
    )
    print(f"Total time: {format_elapsed(elapsed_total)}")
    print("=" * 70 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Elimina masivamente SKUs y Productos en VTEX (borrado en dos fases)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Secuencia:
    1) DELETE /api/catalog/pvt/stockkeepingunit/{skuId} para cada SkuId del CSV
    2) DELETE /api/catalog/pvt/product/{productId} solo para los productos cuyos
       SKUs se eliminaron correctamente (o ya no existian, HTTP 404)

Ejemplos:
    python3 vtex_product_sku_deleter.py ids.csv --dry-run
    python3 vtex_product_sku_deleter.py ids.csv --confirm-delete
    python3 vtex_product_sku_deleter.py ids.csv --confirm-delete --workers 3 --rps 3
    python3 vtex_product_sku_deleter.py ids.csv --dry-run --limit 5
        """,
    )
    parser.add_argument("input_csv", help="CSV con columnas SkuId y ProductId")
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help="Confirmacion obligatoria para ejecutar el borrado real (no requerida con --dry-run)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simula el borrado sin ejecutar DELETE")
    parser.add_argument("--workers", type=int, default=5, help="Numero de workers concurrentes (default: 5)")
    parser.add_argument("--rps", type=float, default=5.0, help="Limite de requests por segundo (default: 5.0)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout de request en segundos (default: 30)")
    parser.add_argument("--limit", type=int, default=None, help="Procesa solo las primeras N filas del CSV")
    parser.add_argument("--output-dir", default=".", help="Directorio de salida para reportes (default: actual)")
    parser.add_argument("--output-prefix", default=None, help="Prefijo opcional para archivos de salida")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.dry_run and not args.confirm_delete:
        die(
            "Esta operacion ejecuta DELETE /api/catalog/pvt/stockkeepingunit/{skuId} y "
            "DELETE /api/catalog/pvt/product/{productId} de forma IRREVERSIBLE sobre el catalogo real. "
            "Agregue --confirm-delete para continuar, o use --dry-run para simular sin ejecutar deletes.",
            code=2,
        )

    if args.workers < 1:
        die("--workers must be >= 1", code=2)
    if args.rps <= 0:
        die("--rps must be > 0", code=2)
    if args.timeout <= 0:
        die("--timeout must be > 0", code=2)
    if args.limit is not None and args.limit < 1:
        die("--limit must be >= 1 when provided", code=2)

    if not os.path.exists(args.input_csv):
        die(f"Input CSV not found: {args.input_csv}")

    try:
        print(f"Loading input CSV: {args.input_csv}")
        sku_tasks, product_to_skus, skipped_rows, input_stats = load_delete_tasks(args.input_csv, args.limit)
        print(
            f"Prepared {len(sku_tasks)} SKU delete tasks across {len(product_to_skus)} unique products; "
            f"skipped {len(skipped_rows)} malformed rows"
        )
    except ValueError as exc:
        die(str(exc))

    credentials = load_vtex_credentials(required=not args.dry_run)

    if not sku_tasks:
        print("No valid SkuId/ProductId pairs were found in the input CSV.")
        export_results([], [], [], [], skipped_rows, [], args.output_dir, args.output_prefix)
        report_path = generate_report(
            input_stats, [], [], skipped_rows, [], [], [],
            args.output_dir, args.output_prefix, args.dry_run, 0.0, 0.0, args.workers, args.rps,
        )
        print(f"Report: {report_path}")
        sys.exit(1)

    try:
        print("\n>>> FASE 1: Eliminando SKUs <<<")
        sku_successful, sku_failed, elapsed_sku = process_phase(
            sku_tasks, credentials, "sku", "SKU", args.rps, args.workers, args.timeout, args.dry_run,
        )
    except KeyboardInterrupt:
        print("\n[WARN] Process interrupted by user during SKU phase")
        sys.exit(130)

    product_tasks, skipped_products = compute_product_eligibility(product_to_skus, sku_failed)
    print(
        f"\n{len(product_tasks)} productos elegibles para Fase 2; "
        f"{len(skipped_products)} omitidos por SKUs pendientes de eliminar"
    )

    try:
        print("\n>>> FASE 2: Eliminando Productos <<<")
        product_successful, product_failed, elapsed_product = process_phase(
            product_tasks, credentials, "product", "Product", args.rps, args.workers, args.timeout, args.dry_run,
        )
    except KeyboardInterrupt:
        print("\n[WARN] Process interrupted by user during Product phase")
        sys.exit(130)

    print_final_summary(
        sku_tasks, sku_successful, sku_failed,
        product_tasks, product_successful, product_failed,
        skipped_products, elapsed_sku + elapsed_product,
    )

    export_results(
        sku_successful, sku_failed, product_successful, product_failed,
        skipped_rows, skipped_products, args.output_dir, args.output_prefix,
    )
    report_path = generate_report(
        input_stats, sku_successful, sku_failed, skipped_rows,
        product_successful, product_failed, skipped_products,
        args.output_dir, args.output_prefix, args.dry_run,
        elapsed_sku, elapsed_product, args.workers, args.rps,
    )
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
