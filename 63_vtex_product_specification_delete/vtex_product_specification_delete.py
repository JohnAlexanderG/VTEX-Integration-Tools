#!/usr/bin/env python3
"""
Elimina masivamente especificaciones de producto en VTEX desde CSV.

Modo por defecto:
    DELETE /api/catalog/pvt/product/{productId}/specification/{specificationId}

Modo destructivo explicito:
    DELETE /api/catalog/pvt/product/{productId}/specification

El modo listed toma pares Product ID + Specification IDs desde el CSV de
especificaciones y valida que cada producto exista en el CSV de productos.
El modo all ignora Specification IDs y borra todas las especificaciones de
cada producto permitido, solo si se usa --confirm-delete-all.
El modo field usa Product ID + Field ID/Field name desde el CSV, consulta VTEX
para resolver el Id real de la asignacion y borra solo ese field del producto.
El modo rename-field renombra la definicion del field de categoria para liberar
el nombre, sin cambiar IsStockKeepingUnit.
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
import unicodedata
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import asdict, dataclass
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
RETRIABLE_STATUSES = (0, 408, 409, 425, 429, 500, 502, 503, 504)
MAX_ATTEMPTS = 5


@dataclass
class DeleteTask:
    product_id: str
    specification_id: str
    field_id: str
    field_name: str
    product_reference_code: str
    row_number: int
    reason: str = ""


@dataclass
class SkippedRow:
    product_id: str
    specification_id: str
    field_id: str
    field_name: str
    product_reference_code: str
    row_number: int
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


class VTEXProductSpecDeleteClient:
    """VTEX API client for deleting product specifications."""

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

    def _get(self, url: str, timeout: int) -> Tuple[int, str]:
        return self._request("GET", url, timeout)

    def delete_listed_specification(
        self,
        product_id: str,
        specification_id: str,
        timeout: int = 30,
    ) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog/pvt/product/{product_id}/specification/{specification_id}"
        return self._delete(url, timeout)

    def delete_all_product_specifications(self, product_id: str, timeout: int = 30) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog/pvt/product/{product_id}/specification"
        return self._delete(url, timeout)

    def get_specification_field(self, field_id: str, timeout: int = 30) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog_system/pub/specification/fieldGet/{field_id}"
        return self._get(url, timeout)

    def put_specification_field(self, body: Dict[str, Any], timeout: int = 30) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog_system/pvt/specification/field"
        self.bucket.consume(1.0)
        try:
            response = self.session.put(url, json=body, timeout=timeout)
        except requests.RequestException as exc:
            return 0, f"request_exception: {exc}"
        return response.status_code, response.text

    def get_product_specifications(self, product_id: str, timeout: int = 30) -> Tuple[int, str]:
        url = f"{self.base_url}/api/catalog_system/pvt/products/{product_id}/specification"
        return self._get(url, timeout)

    def rename_specification_field(
        self,
        task: DeleteTask,
        timeout: int = 30,
        dry_run: bool = False,
        set_is_stock_keeping_unit: Optional[bool] = None,
    ) -> Tuple[bool, int, str, Dict[str, Any]]:
        field_id = task.field_id or task.specification_id
        status, text = self.get_specification_field(field_id, timeout)
        if status not in SUCCESS_STATUSES:
            return False, status, text, {}

        try:
            current = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as exc:
            return False, status, f"invalid_json_response: {exc}", {}

        if not isinstance(current, dict):
            return False, status, "unexpected_specification_response", {}

        new_name = task.reason
        if not new_name:
            return False, 0, "missing_new_field_name", {}

        payload = dict(current)
        old_name = str(first_present(payload, ("Name", "name")) or task.field_name or "")
        if not old_name:
            old_name = task.field_name
        payload["FieldId"] = int(field_id) if str(field_id).isdigit() else field_id
        payload["Name"] = new_name
        if set_is_stock_keeping_unit is not None:
            payload["IsStockKeepingUnit"] = set_is_stock_keeping_unit
        if "Description" in payload and not str(payload.get("Description") or "").strip():
            payload["Description"] = new_name

        result = {
            "specification_id": field_id,
            "old_field_name": old_name,
            "new_field_name": new_name,
            "is_stock_keeping_unit": payload.get("IsStockKeepingUnit"),
            "requested_is_stock_keeping_unit": set_is_stock_keeping_unit,
            "field_type_id": payload.get("FieldTypeId"),
            "category_id": payload.get("CategoryId"),
            "field_group_id": payload.get("FieldGroupId"),
        }
        if dry_run:
            result["payload_preview"] = payload
            return True, 200, "", result

        put_status, put_text = self.put_specification_field(payload, timeout)
        if put_status in SUCCESS_STATUSES:
            return True, put_status, put_text, result
        return False, put_status, put_text, result

    def delete_live_field_specifications(
        self,
        task: DeleteTask,
        timeout: int = 30,
        dry_run: bool = False,
    ) -> Tuple[bool, int, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        status, text = self.get_product_specifications(task.product_id, timeout)
        if status not in SUCCESS_STATUSES:
            return False, status, text, [], []

        try:
            live_specs = json.loads(text) if text.strip() else []
        except json.JSONDecodeError as exc:
            return False, status, f"invalid_json_response: {exc}", [], []

        matches = [
            spec for spec in iter_live_specs(live_specs)
            if live_spec_matches_task(spec, task)
        ]
        if not matches:
            target = task.field_id or task.field_name
            return False, 404, f"no_live_product_specification_matched_field:{target}", [], []

        successful: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for match in matches:
            resolved_id = live_spec_assignment_id(match)
            if not resolved_id:
                failed.append({
                    "status_code": 0,
                    "error": "missing_live_assignment_id",
                    "live_spec": match,
                })
                continue

            record = {
                "resolved_specification_id": str(resolved_id),
                "live_field_id": live_spec_field_id(match),
                "live_field_name": live_spec_field_name(match),
            }
            if dry_run:
                successful.append({**record, "status_code": "dry_run"})
                continue

            delete_status, delete_text = self.delete_listed_specification(
                task.product_id,
                str(resolved_id),
                timeout,
            )
            if delete_status in SUCCESS_STATUSES:
                successful.append({**record, "status_code": delete_status})
            else:
                failed.append({
                    **record,
                    "status_code": delete_status,
                    "error": delete_text[:500] if delete_text else "Unknown error",
                })

        ok = bool(successful) and not failed
        aggregate_status = 200 if ok else failed[0]["status_code"] if failed else 404
        aggregate_text = "" if ok else json.dumps(failed, ensure_ascii=False)
        return ok, aggregate_status, aggregate_text, successful, failed


def die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def build_base_url(account: str, environment: str) -> str:
    if environment.endswith(".com.br"):
        return f"https://{account}.{environment}"
    return f"https://{account}.{environment}.com.br"


def build_endpoint(credentials: Optional[dict], task: DeleteTask, mode: str) -> str:
    if credentials and credentials.get("account_name"):
        base = build_base_url(credentials["account_name"], credentials["environment"])
    else:
        base = "https://{account}.{environment}.com.br"

    if mode == "listed":
        return f"{base}/api/catalog/pvt/product/{task.product_id}/specification/{task.specification_id}"
    if mode == "field":
        return (
            f"{base}/api/catalog_system/pvt/products/{task.product_id}/specification"
            f" -> DELETE resolved product specification assignment"
        )
    if mode == "rename-field":
        return f"{base}/api/catalog_system/pvt/specification/field"
    return f"{base}/api/catalog/pvt/product/{task.product_id}/specification"


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


def ensure_headers(field_map: Dict[str, str], required: Set[str], path: str) -> None:
    missing = sorted(required - set(field_map.keys()))
    if missing:
        found = ", ".join(field_map.keys()) if field_map else "(sin encabezados)"
        raise ValueError(
            f"CSV '{path}' no contiene columnas requeridas: {', '.join(missing)}. "
            f"Columnas encontradas: {found}"
        )


def normalize_text(value: Any) -> str:
    nfkd = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in nfkd if not unicodedata.combining(char)).lower().strip()


def first_present(record: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def iter_live_specs(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("Specifications", "specifications", "Items", "items", "Data", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def live_spec_assignment_id(spec: Dict[str, Any]) -> Optional[str]:
    value = first_present(spec, ("Id", "id", "SpecificationId", "specificationId"))
    return str(value) if value is not None else None


def live_spec_field_id(spec: Dict[str, Any]) -> Optional[str]:
    value = first_present(spec, ("FieldId", "fieldId", "FieldID", "Field", "field"))
    return str(value) if value is not None else None


def live_spec_field_name(spec: Dict[str, Any]) -> str:
    value = first_present(spec, ("FieldName", "fieldName", "Name", "name", "Field", "field"))
    return str(value or "")


def live_spec_matches_task(spec: Dict[str, Any], task: DeleteTask) -> bool:
    if task.field_id and live_spec_field_id(spec) == str(task.field_id):
        return True
    if task.field_name and normalize_text(live_spec_field_name(spec)) == normalize_text(task.field_name):
        return True
    return False


def apply_field_name_template(template: str, field_name: str, field_id: str) -> str:
    try:
        return template.format(name=field_name, field_id=field_id).strip()
    except KeyError as exc:
        raise ValueError(f"Variable no soportada en --rename-template: {exc}")


def parse_optional_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = normalize_text(value)
    if normalized in {"true", "1", "yes", "y", "si", "sí"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("--set-is-stock-keeping-unit must be true or false")


def split_multi_value_cell(raw) -> List[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if "\n" in text:
        parts = []
        for item in text.splitlines():
            parts.extend(split_multi_value_cell(item))
        return parts
    if ";" in text:
        parts = text.split(";")
    elif "|" in text:
        parts = text.split("|")
    else:
        parts = [text]
    return [part.strip() for part in parts if part and part.strip()]


def load_products_csv(products_csv: str) -> Tuple[Set[str], Dict[str, str], Dict[str, int]]:
    dialect = sniff_csv_dialect(products_csv)
    product_ids: Set[str] = set()
    ref_to_product_id: Dict[str, str] = {}
    rows_read = 0

    with open(products_csv, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj, dialect=dialect)
        field_map = normalize_header_map(reader.fieldnames)
        ensure_headers(field_map, {"Product ID", "SKU reference code"}, products_csv)

        product_id_header = field_map["Product ID"]
        ref_header = field_map["SKU reference code"]

        for row in reader:
            rows_read += 1
            product_id = (row.get(product_id_header) or "").strip()
            ref_code = (row.get(ref_header) or "").strip()

            if product_id:
                product_ids.add(product_id)
            if ref_code and product_id:
                ref_to_product_id[ref_code] = product_id

    stats = {
        "product_rows_read": rows_read,
        "product_ids_loaded": len(product_ids),
        "reference_codes_loaded": len(ref_to_product_id),
    }
    return product_ids, ref_to_product_id, stats


def skipped_from_task(task: DeleteTask, reason: str) -> SkippedRow:
    return SkippedRow(
        product_id=task.product_id,
        specification_id=task.specification_id,
        field_id=task.field_id,
        field_name=task.field_name,
        product_reference_code=task.product_reference_code,
        row_number=task.row_number,
        reason=reason,
    )


def load_specification_delete_tasks(
    specs_csv: str,
    product_ids: Set[str],
    ref_to_product_id: Dict[str, str],
    mode: str,
    limit: Optional[int] = None,
    target_field_id: Optional[str] = None,
    target_field_name: Optional[str] = None,
    rename_template: Optional[str] = None,
) -> Tuple[List[DeleteTask], List[SkippedRow], Dict[str, int]]:
    dialect = sniff_csv_dialect(specs_csv)
    tasks: List[DeleteTask] = []
    skipped: List[SkippedRow] = []
    seen_listed: Set[Tuple[str, str]] = set()
    seen_all: Set[str] = set()
    seen_field: Set[Tuple[str, str, str]] = set()
    seen_rename_field: Set[str] = set()
    field_ids_seen: Set[str] = set()
    field_names_seen: Set[str] = set()
    field_rows_matched = 0
    rows_read = 0

    with open(specs_csv, "r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj, dialect=dialect)
        field_map = normalize_header_map(reader.fieldnames)
        required_headers = {"Product ID", "Product reference code"}
        if mode not in {"field", "rename-field"}:
            required_headers.add("Specification IDs")
        ensure_headers(field_map, required_headers, specs_csv)

        product_id_header = field_map["Product ID"]
        ref_header = field_map["Product reference code"]
        spec_ids_header = field_map.get("Specification IDs")
        field_id_header = field_map.get("Field ID")
        field_name_header = field_map.get("Field name")

        for row_number, row in enumerate(reader, start=2):
            if limit is not None and rows_read >= limit:
                break
            rows_read += 1

            raw_product_id = (row.get(product_id_header) or "").strip()
            product_reference_code = (row.get(ref_header) or "").strip()
            field_id = (row.get(field_id_header) or "").strip() if field_id_header else ""
            field_name = (row.get(field_name_header) or "").strip() if field_name_header else ""
            product_id = raw_product_id or ref_to_product_id.get(product_reference_code, "")
            if field_id:
                field_ids_seen.add(field_id)
            if field_name:
                field_names_seen.add(field_name)

            base_task = DeleteTask(
                product_id=product_id,
                specification_id="",
                field_id=field_id,
                field_name=field_name,
                product_reference_code=product_reference_code,
                row_number=row_number,
            )

            if not product_id:
                skipped.append(skipped_from_task(base_task, "missing_product_id"))
                continue

            if product_id not in product_ids:
                skipped.append(skipped_from_task(base_task, "product_not_in_products_csv"))
                continue

            if mode == "all":
                if product_id in seen_all:
                    skipped.append(skipped_from_task(base_task, "duplicate_product"))
                    continue
                seen_all.add(product_id)
                tasks.append(base_task)
                continue

            if mode in {"field", "rename-field"}:
                field_id_matches = bool(target_field_id and field_id == str(target_field_id))
                field_name_matches = bool(
                    target_field_name and normalize_text(field_name) == normalize_text(target_field_name)
                )
                if not field_id_matches and not field_name_matches:
                    skipped.append(skipped_from_task(base_task, "field_filter_not_matched"))
                    continue

                field_rows_matched += 1
                if mode == "rename-field":
                    if not field_id:
                        skipped.append(skipped_from_task(base_task, "missing_field_id_for_rename"))
                        continue
                    if field_id in seen_rename_field:
                        skipped.append(skipped_from_task(base_task, "duplicate_field_definition_task"))
                        continue
                    seen_rename_field.add(field_id)
                    new_name = apply_field_name_template(rename_template or "Product - {name}", field_name, field_id)
                    if not new_name:
                        skipped.append(skipped_from_task(base_task, "empty_new_field_name"))
                        continue
                    base_task.reason = new_name
                    tasks.append(base_task)
                    continue

                dedupe_key = (product_id, field_id or "", normalize_text(field_name))
                if dedupe_key in seen_field:
                    skipped.append(skipped_from_task(base_task, "duplicate_field_task"))
                    continue
                seen_field.add(dedupe_key)
                tasks.append(base_task)
                continue

            specification_ids = split_multi_value_cell(row.get(spec_ids_header))
            if not specification_ids:
                skipped.append(skipped_from_task(base_task, "missing_specification_ids"))
                continue

            for specification_id in specification_ids:
                task = DeleteTask(
                    product_id=product_id,
                    specification_id=specification_id,
                    field_id=field_id,
                    field_name=field_name,
                    product_reference_code=product_reference_code,
                    row_number=row_number,
                )
                dedupe_key = (product_id, specification_id)
                if dedupe_key in seen_listed:
                    skipped.append(skipped_from_task(task, "duplicate_task"))
                    continue
                seen_listed.add(dedupe_key)
                tasks.append(task)

    stats = {
        "spec_rows_read": rows_read,
        "unique_tasks": len(tasks),
        "skipped_rows": len(skipped),
        "unique_field_ids_seen": len(field_ids_seen),
        "unique_field_names_seen": len(field_names_seen),
        "field_rows_matched": field_rows_matched,
        "category_field_definitions_deleted": 0,
    }
    return tasks, skipped, stats


def worker_delete_task(
    task: DeleteTask,
    client: VTEXProductSpecDeleteClient,
    mode: str,
    progress: ProgressTracker,
    results_lock: threading.Lock,
    successful: list,
    failed: list,
    timeout: int = 30,
    set_is_stock_keeping_unit: Optional[bool] = None,
) -> None:
    attempt = 0
    status, text = 0, ""

    if mode == "rename-field":
        while attempt < MAX_ATTEMPTS:
            ok, status, text, rename_result = client.rename_specification_field(
                task,
                timeout=timeout,
                dry_run=False,
                set_is_stock_keeping_unit=set_is_stock_keeping_unit,
            )
            if ok:
                progress.increment_success()
                with results_lock:
                    successful.append({
                        **asdict(task),
                        "specification_id": task.field_id,
                        "status_code": status,
                        "status": "success",
                        "endpoint_mode": mode,
                        **rename_result,
                    })
                return

            if status in RETRIABLE_STATUSES:
                sleep_time = exponential_backoff(
                    base=0.5,
                    factor=2.0,
                    attempt=attempt,
                    jitter=0.3,
                    max_sleep=45.0,
                )
                time.sleep(sleep_time)
                attempt += 1
                continue
            break

        progress.increment_failure()
        with results_lock:
            failed.append({
                **asdict(task),
                "specification_id": task.field_id,
                "status_code": status,
                "status": "failed",
                "endpoint_mode": mode,
                "error": text[:500] if text else "Unknown error",
            })
        return

    if mode == "field":
        while attempt < MAX_ATTEMPTS:
            ok, status, text, resolved, live_failures = client.delete_live_field_specifications(
                task,
                timeout=timeout,
                dry_run=False,
            )
            if ok:
                progress.increment_success()
                resolved_ids = [item["resolved_specification_id"] for item in resolved]
                with results_lock:
                    successful.append({
                        **asdict(task),
                        "specification_id": ",".join(resolved_ids),
                        "resolved_specification_ids": resolved_ids,
                        "deleted_count": len(resolved_ids),
                        "status_code": ",".join(str(item.get("status_code", "")) for item in resolved),
                        "status": "success",
                        "endpoint_mode": mode,
                    })
                return

            if status in RETRIABLE_STATUSES:
                sleep_time = exponential_backoff(
                    base=0.5,
                    factor=2.0,
                    attempt=attempt,
                    jitter=0.3,
                    max_sleep=45.0,
                )
                time.sleep(sleep_time)
                attempt += 1
                continue
            break

        progress.increment_failure()
        with results_lock:
            failed.append({
                **asdict(task),
                "status_code": status,
                "status": "failed",
                "endpoint_mode": mode,
                "error": text[:500] if text else json.dumps(live_failures, ensure_ascii=False)[:500],
            })
        return

    while attempt < MAX_ATTEMPTS:
        if mode == "listed":
            status, text = client.delete_listed_specification(
                task.product_id,
                task.specification_id,
                timeout,
            )
        else:
            status, text = client.delete_all_product_specifications(task.product_id, timeout)

        if status in SUCCESS_STATUSES:
            progress.increment_success()
            with results_lock:
                successful.append({
                    **asdict(task),
                    "status_code": status,
                    "status": "success",
                    "endpoint_mode": mode,
                })
            return

        if status in RETRIABLE_STATUSES:
            sleep_time = exponential_backoff(
                base=0.5,
                factor=2.0,
                attempt=attempt,
                jitter=0.3,
                max_sleep=45.0,
            )
            time.sleep(sleep_time)
            attempt += 1
            continue

        break

    progress.increment_failure()
    with results_lock:
        failed.append({
            **asdict(task),
            "status_code": status,
            "status": "failed",
            "endpoint_mode": mode,
            "error": text[:500] if text else "Unknown error",
        })


def process_deletions(
    tasks: List[DeleteTask],
    credentials: Optional[dict],
    mode: str,
    base_rps: float,
    num_workers: int,
    timeout: int,
    dry_run: bool = False,
    set_is_stock_keeping_unit: Optional[bool] = None,
) -> Tuple[list, list, float]:
    shared_bucket = TokenBucket(rate_per_sec=base_rps, capacity=max(5, int(base_rps)))
    progress = ProgressTracker()
    successful = []
    failed = []
    results_lock = threading.Lock()

    total_items = len(tasks)
    start_time = time.monotonic()
    last_report = start_time
    last_total = 0

    print("\n" + "=" * 70)
    print("VTEX Product Specification Delete")
    print("=" * 70)
    if credentials:
        print(f"Account: {credentials['account_name']} | Env: {credentials['environment']}")
    else:
        print("Account: not loaded | Env: not loaded")
    print(f"Mode: {mode} | Workers: {num_workers} | RPS: {base_rps} | Tasks: {total_items}")
    if dry_run:
        print("[DRY RUN MODE - No HTTP DELETE requests will be executed]")
    print("=" * 70 + "\n")

    if dry_run and mode == "rename-field" and credentials is not None:
        client = VTEXProductSpecDeleteClient(
            credentials["account_name"],
            credentials["environment"],
            credentials["app_key"],
            credentials["app_token"],
            shared_bucket,
            base_rps,
        )
        for task in tasks:
            ok, status, text, rename_result = client.rename_specification_field(
                task,
                timeout=timeout,
                dry_run=True,
                set_is_stock_keeping_unit=set_is_stock_keeping_unit,
            )
            if ok:
                successful.append({
                    **asdict(task),
                    "specification_id": task.field_id,
                    "status": "dry_run_resolved",
                    "status_code": "dry_run",
                    "endpoint_mode": mode,
                    "endpoint": build_endpoint(credentials, task, mode),
                    **rename_result,
                })
            else:
                failed.append({
                    **asdict(task),
                    "specification_id": task.field_id,
                    "status": "dry_run_resolution_failed",
                    "status_code": status,
                    "endpoint_mode": mode,
                    "endpoint": build_endpoint(credentials, task, mode),
                    "error": text[:500] if text else "Unknown error",
                })
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    if dry_run and not (mode in {"field", "rename-field"} and credentials is not None):
        for task in tasks:
            successful.append({
                **asdict(task),
                "status": "dry_run",
                "endpoint_mode": mode,
                "endpoint": build_endpoint(credentials, task, mode),
            })
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    if dry_run and mode == "field" and credentials is not None:
        client = VTEXProductSpecDeleteClient(
            credentials["account_name"],
            credentials["environment"],
            credentials["app_key"],
            credentials["app_token"],
            shared_bucket,
            base_rps,
        )
        for task in tasks:
            ok, status, text, resolved, live_failures = client.delete_live_field_specifications(
                task,
                timeout=timeout,
                dry_run=True,
            )
            if ok:
                resolved_ids = [item["resolved_specification_id"] for item in resolved]
                successful.append({
                    **asdict(task),
                    "specification_id": ",".join(resolved_ids),
                    "resolved_specification_ids": resolved_ids,
                    "deleted_count": len(resolved_ids),
                    "status": "dry_run_resolved",
                    "status_code": "dry_run",
                    "endpoint_mode": mode,
                    "endpoint": build_endpoint(credentials, task, mode),
                })
            else:
                failed.append({
                    **asdict(task),
                    "status": "dry_run_resolution_failed",
                    "status_code": status,
                    "endpoint_mode": mode,
                    "endpoint": build_endpoint(credentials, task, mode),
                    "error": text[:500] if text else json.dumps(live_failures, ensure_ascii=False)[:500],
                })
        elapsed = time.monotonic() - start_time
        return successful, failed, elapsed

    if credentials is None:
        die("VTEX credentials are required when --dry-run is not enabled")

    def create_worker_client():
        return VTEXProductSpecDeleteClient(
            credentials["account_name"],
            credentials["environment"],
            credentials["app_key"],
            credentials["app_token"],
            shared_bucket,
            base_rps,
        )

    clients = [create_worker_client() for _ in range(num_workers)]
    max_in_flight = max(32, num_workers * 4)

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
                worker_delete_task,
                task,
                client,
                mode,
                progress,
                results_lock,
                successful,
                failed,
                timeout,
                set_is_stock_keeping_unit,
            )
            futures.add(future)
            drain_and_report(futures)

        while futures:
            drain_and_report(futures, blocking=True)

    elapsed = time.monotonic() - start_time
    return successful, failed, elapsed


def write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=4, ensure_ascii=False)


def export_results(
    successful: list,
    failed: list,
    skipped: List[SkippedRow],
    output_dir: str,
    prefix: Optional[str] = None,
) -> Dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = prefix or timestamp
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    success_path = os.path.join(output_dir, f"{file_prefix}_successful.json")
    write_json(success_path, successful)
    paths["successful_json"] = success_path

    failed_json_path = os.path.join(output_dir, f"{file_prefix}_failed.json")
    write_json(failed_json_path, failed)
    paths["failed_json"] = failed_json_path

    failed_csv_path = os.path.join(output_dir, f"{file_prefix}_failed.csv")
    with open(failed_csv_path, "w", encoding="utf-8", newline="") as file_obj:
        fieldnames = [
            "product_id",
            "specification_id",
            "resolved_specification_ids",
            "deleted_count",
            "field_id",
            "field_name",
            "old_field_name",
            "new_field_name",
            "requested_is_stock_keeping_unit",
            "product_reference_code",
            "row_number",
            "status_code",
            "endpoint_mode",
            "error",
        ]
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for item in failed:
            writer.writerow({field: item.get(field, "") for field in fieldnames})
    paths["failed_csv"] = failed_csv_path

    skipped_payload = [asdict(item) for item in skipped]
    skipped_json_path = os.path.join(output_dir, f"{file_prefix}_skipped.json")
    write_json(skipped_json_path, skipped_payload)
    paths["skipped_json"] = skipped_json_path

    skipped_csv_path = os.path.join(output_dir, f"{file_prefix}_skipped.csv")
    with open(skipped_csv_path, "w", encoding="utf-8", newline="") as file_obj:
        fieldnames = [
            "product_id",
            "specification_id",
            "resolved_specification_ids",
            "deleted_count",
            "field_id",
            "field_name",
            "old_field_name",
            "new_field_name",
            "requested_is_stock_keeping_unit",
            "product_reference_code",
            "row_number",
            "reason",
        ]
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for item in skipped_payload:
            writer.writerow(item)
    paths["skipped_csv"] = skipped_csv_path

    print(f"Successful JSON: {success_path}")
    print(f"Failed JSON: {failed_json_path}")
    print(f"Failed CSV: {failed_csv_path}")
    print(f"Skipped JSON: {skipped_json_path}")
    print(f"Skipped CSV: {skipped_csv_path}")
    return paths


def summarize_skipped(skipped: List[SkippedRow]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for item in skipped:
        summary[item.reason] = summary.get(item.reason, 0) + 1
    return summary


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
    successful: list,
    failed: list,
    skipped: List[SkippedRow],
    output_dir: str,
    prefix: Optional[str],
    mode: str,
    dry_run: bool,
    elapsed: float,
    workers: int,
    rps: float,
    product_stats: Dict[str, int],
    spec_stats: Dict[str, int],
) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_prefix = prefix or timestamp
    report_path = os.path.join(output_dir, f"{file_prefix}_deletion_report.md")
    os.makedirs(output_dir, exist_ok=True)

    total_tasks = spec_stats.get("unique_tasks", len(successful) + len(failed))
    attempted = len(successful) + len(failed)
    success_rate = (len(successful) / attempted * 100) if attempted else 0.0
    effective_rps = attempted / elapsed if elapsed > 0 else 0.0
    mode_label = " (DRY RUN)" if dry_run else ""
    skipped_summary = summarize_skipped(skipped)

    with open(report_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(f"# Product Specification Delete Report{mode_label}\n\n")
        file_obj.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        file_obj.write("## Configuration\n\n")
        file_obj.write("| Setting | Value |\n")
        file_obj.write("|---------|-------|\n")
        file_obj.write(f"| Mode | {mode} |\n")
        file_obj.write(f"| Dry run | {dry_run} |\n")
        file_obj.write(f"| Workers | {workers} |\n")
        file_obj.write(f"| Target RPS | {rps} |\n")
        file_obj.write(f"| Effective RPS | {effective_rps:.1f} |\n")
        file_obj.write(f"| Elapsed time | {format_elapsed(elapsed)} |\n\n")

        file_obj.write("## Input Summary\n\n")
        file_obj.write("| Metric | Count |\n")
        file_obj.write("|--------|-------|\n")
        file_obj.write(f"| Product rows read | {product_stats.get('product_rows_read', 0)} |\n")
        file_obj.write(f"| Product IDs loaded | {product_stats.get('product_ids_loaded', 0)} |\n")
        file_obj.write(f"| Reference codes loaded | {product_stats.get('reference_codes_loaded', 0)} |\n")
        file_obj.write(f"| Specification rows read | {spec_stats.get('spec_rows_read', 0)} |\n")
        file_obj.write(f"| Unique delete tasks | {total_tasks} |\n")
        file_obj.write(f"| Distinct Field IDs seen in export | {spec_stats.get('unique_field_ids_seen', 0)} |\n")
        file_obj.write(f"| Distinct Field names seen in export | {spec_stats.get('unique_field_names_seen', 0)} |\n")
        file_obj.write(f"| Field filter rows matched | {spec_stats.get('field_rows_matched', 0)} |\n")
        file_obj.write(f"| Skipped rows/items | {len(skipped)} |\n\n")

        file_obj.write("## Results\n\n")
        file_obj.write("| Metric | Count |\n")
        file_obj.write("|--------|-------|\n")
        file_obj.write(f"| Successful | {len(successful)} |\n")
        file_obj.write(f"| Failed | {len(failed)} |\n")
        file_obj.write(f"| Success rate | {success_rate:.1f}% |\n\n")

        file_obj.write("## Important Distinction\n\n")
        file_obj.write(
            "This script calls product endpoints. In `listed` mode, "
            "`DELETE /api/catalog/pvt/product/{productId}/specification/{specificationId}` "
            "removes a product/specification assignment or value for that product. In `all` mode, "
            "`DELETE /api/catalog/pvt/product/{productId}/specification` removes product "
            "specification assignments for the product. In `field` mode, this script first calls "
            "`GET /api/catalog_system/pvt/products/{productId}/specification` to find the live "
            "assignment Id for the requested Field ID/name, then deletes that assignment. In "
            "`rename-field` mode, it calls the category field endpoint and updates the field name "
            "without changing IsStockKeepingUnit. No mode deletes the category-level product "
            "specification field definition.\n\n"
        )
        file_obj.write("| Outcome | Count |\n")
        file_obj.write("|---------|------:|\n")
        file_obj.write(f"| Deleted product/specification assignments | {len(successful) if not dry_run else 0} |\n")
        file_obj.write(f"| Planned product/specification assignment deletes | {len(successful) if dry_run else total_tasks} |\n")
        file_obj.write(f"| Category field definitions deleted | {spec_stats.get('category_field_definitions_deleted', 0)} |\n\n")

        if skipped_summary:
            file_obj.write("## Skipped By Reason\n\n")
            file_obj.write("| Reason | Count |\n")
            file_obj.write("|--------|-------|\n")
            for reason, count in sorted(skipped_summary.items()):
                file_obj.write(f"| {reason} | {count} |\n")
            file_obj.write("\n")

        if failed:
            file_obj.write("## Failed Deletions\n\n")
            file_obj.write("| Product ID | Specification ID | Status | Error |\n")
            file_obj.write("|------------|------------------|--------|-------|\n")
            for item in failed[:50]:
                error = str(item.get("error", "Unknown")).replace("\n", " ")[:120]
                file_obj.write(
                    f"| {item.get('product_id', '')} | {item.get('specification_id', '')} | "
                    f"{item.get('status_code', '')} | {error} |\n"
                )
            if len(failed) > 50:
                file_obj.write(f"\n*...and {len(failed) - 50} more failures*\n")

    return report_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Elimina especificaciones de producto VTEX desde CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 vtex_product_specification_delete.py products.csv product-specs.csv --dry-run
    python3 vtex_product_specification_delete.py products.csv product-specs.csv --mode field --field-id 2100 --dry-run
    python3 vtex_product_specification_delete.py products.csv product-specs.csv --mode rename-field --field-id 2100 --rename-template 'Product - {name}' --dry-run
    python3 vtex_product_specification_delete.py products.csv product-specs.csv --workers 5 --rps 10
    python3 vtex_product_specification_delete.py products.csv product-specs.csv --mode all --confirm-delete-all --dry-run
        """,
    )
    parser.add_argument("products_csv", help="CSV de productos con Product ID y SKU reference code")
    parser.add_argument("specifications_csv", help="CSV de especificaciones de producto exportado desde VTEX")
    parser.add_argument(
        "--mode",
        choices=("listed", "all", "field", "rename-field"),
        default="listed",
        help=(
            "listed borra Specification IDs del CSV; field resuelve en vivo por Field ID/name; "
            "rename-field renombra la definicion de categoria; "
            "all borra todas las specs por producto (default: listed)"
        ),
    )
    parser.add_argument("--field-id", default=None, help="Field ID a borrar en --mode field, por ejemplo 2100")
    parser.add_argument("--field-name", default=None, help="Field name a borrar en --mode field, por ejemplo Potencia")
    parser.add_argument(
        "--rename-template",
        default="Product - {name}",
        help="Plantilla para --mode rename-field. Variables: {name}, {field_id}.",
    )
    parser.add_argument(
        "--set-is-stock-keeping-unit",
        type=parse_optional_bool,
        default=None,
        metavar="true|false",
        help="En --mode rename-field, fuerza IsStockKeepingUnit en el payload PUT.",
    )
    parser.add_argument(
        "--confirm-delete-all",
        action="store_true",
        help="Confirmacion obligatoria para usar --mode all",
    )
    parser.add_argument("--workers", type=int, default=5, help="Numero de workers concurrentes (default: 5)")
    parser.add_argument("--rps", type=float, default=10.0, help="Limite de requests por segundo (default: 10.0)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout de request en segundos (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Simula borrados sin ejecutar DELETE")
    parser.add_argument("--limit", type=int, default=None, help="Procesa solo las primeras N filas del CSV de specs")
    parser.add_argument("--output-dir", default=".", help="Directorio de salida para reportes (default: actual)")
    parser.add_argument("--output-prefix", default=None, help="Prefijo opcional para archivos de salida")
    return parser.parse_args()


def print_final_summary(total_tasks: int, successful: list, failed: list, skipped: List[SkippedRow], elapsed: float) -> None:
    print("\n" + "=" * 70)
    print("DELETE PROCESS COMPLETE")
    print("=" * 70)
    print(f"Tasks: {total_tasks}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Time: {format_elapsed(elapsed)}")
    avg_rps = (len(successful) + len(failed)) / elapsed if elapsed > 0 else 0.0
    print(f"Effective RPS: {avg_rps:.1f}")
    print("=" * 70 + "\n")


def main():
    args = parse_args()

    if args.mode == "all" and not args.confirm_delete_all:
        die(
            "--mode all uses DELETE /api/catalog/pvt/product/{productId}/specification "
            "and removes all product specifications. Add --confirm-delete-all to continue.",
            code=2,
        )
    if args.mode in {"field", "rename-field"} and not args.field_id and not args.field_name:
        die(f"--mode {args.mode} requires --field-id or --field-name so it can target one product spec.", code=2)

    if args.workers < 1:
        die("--workers must be >= 1", code=2)
    if args.rps <= 0:
        die("--rps must be > 0", code=2)
    if args.timeout <= 0:
        die("--timeout must be > 0", code=2)
    if args.limit is not None and args.limit < 1:
        die("--limit must be >= 1 when provided", code=2)

    if not os.path.exists(args.products_csv):
        die(f"Products CSV not found: {args.products_csv}")
    if not os.path.exists(args.specifications_csv):
        die(f"Specifications CSV not found: {args.specifications_csv}")

    try:
        print(f"Loading products CSV: {args.products_csv}")
        product_ids, ref_to_product_id, product_stats = load_products_csv(args.products_csv)
        print(f"Loaded {len(product_ids)} allowed Product IDs and {len(ref_to_product_id)} reference codes")

        print(f"Loading specification tasks: {args.specifications_csv}")
        tasks, skipped, spec_stats = load_specification_delete_tasks(
            args.specifications_csv,
            product_ids,
            ref_to_product_id,
            args.mode,
            args.limit,
            target_field_id=args.field_id,
            target_field_name=args.field_name,
            rename_template=args.rename_template,
        )
        print(f"Prepared {len(tasks)} unique delete tasks; skipped {len(skipped)} rows/items")
        print(
            "Note: these tasks delete product/specification assignments; "
            "category field definitions are not deleted by this script."
        )
    except ValueError as exc:
        die(str(exc))

    credentials = load_vtex_credentials(required=not args.dry_run)

    if not tasks:
        print("No valid delete tasks were found.")
        if skipped:
            print("Skipped summary:")
            for reason, count in sorted(summarize_skipped(skipped).items()):
                print(f"  {reason}: {count}")
        export_results([], [], skipped, args.output_dir, args.output_prefix)
        report_path = generate_report(
            [],
            [],
            skipped,
            args.output_dir,
            args.output_prefix,
            args.mode,
            args.dry_run,
            0.0,
            args.workers,
            args.rps,
            product_stats,
            spec_stats,
        )
        print(f"Report: {report_path}")
        sys.exit(1)

    try:
        successful, failed, elapsed = process_deletions(
            tasks,
            credentials,
            args.mode,
            args.rps,
            args.workers,
            args.timeout,
            args.dry_run,
            args.set_is_stock_keeping_unit,
        )
    except KeyboardInterrupt:
        print("\n[WARN] Process interrupted by user")
        sys.exit(130)

    print_final_summary(len(tasks), successful, failed, skipped, elapsed)

    export_results(successful, failed, skipped, args.output_dir, args.output_prefix)
    report_path = generate_report(
        successful,
        failed,
        skipped,
        args.output_dir,
        args.output_prefix,
        args.mode,
        args.dry_run,
        elapsed,
        args.workers,
        args.rps,
        product_stats,
        spec_stats,
    )
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
