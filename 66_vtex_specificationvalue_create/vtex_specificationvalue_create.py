#!/usr/bin/env python3
"""
vtex_specificationvalue_create.py
---------------------------------
Crea valores de especificaciones SKU en VTEX cruzando:

- CSV exitoso del paso 65, que expone Id como FieldId.
- CSV de especificaciones SKU encontradas del paso 61.

El script deduplica por FieldId + Name normalizado, crea payloads para
POST /api/catalog/pvt/specificationvalue, y exporta exitos, fallos, omitidos,
reporte y un state file estable para reanudar cargas interrumpidas.
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

SUCCESS_FIELDNAMES = [
    "FieldValueId",
    "FieldId",
    "Name",
    "IsActive",
    "Position",
    "CategoryId",
    "SpecName",
    "StatusCode",
    "Response",
]

FAILED_FIELDNAMES = [
    "FieldId",
    "Name",
    "Position",
    "CategoryId",
    "SpecName",
    "StatusCode",
    "Error",
    "Payload",
    "SourceRows",
]

SKIPPED_FIELDNAMES = [
    "CategoryId",
    "SpecName",
    "FieldId",
    "ValueName",
    "Reason",
    "SourceRows",
]

STATE_FIELDNAMES = [
    "PayloadKey",
    "FieldId",
    "Name",
    "Position",
    "Status",
    "StatusCode",
    "Response",
    "Error",
    "Timestamp",
]


def load_project_env(env_path: str) -> None:
    """Carga .env con python-dotenv si existe, o con un parser minimo."""
    if load_dotenv:
        load_dotenv(dotenv_path=env_path)
        return

    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_project_env(os.path.join(PROJECT_ROOT, ".env"))

VTEX_APP_KEY = os.getenv("X-VTEX-API-AppKey")
VTEX_APP_TOKEN = os.getenv("X-VTEX-API-AppToken")
VTEX_ACCOUNT = os.getenv("VTEX_ACCOUNT_NAME")
VTEX_ENVIRONMENT = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")


def normalize_integer_id(value: object) -> Optional[str]:
    """Normaliza IDs enteros para comparar CSVs de forma estable."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        number = float(text)
    except ValueError:
        return None

    if not number.is_integer():
        return None

    return str(int(number))


def normalize_spaces(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_text_key(value: object) -> str:
    return normalize_spaces(value).casefold()


def make_payload_key(field_id: object, name: object) -> str:
    return f"{str(field_id).strip()}::{normalize_text_key(name)}"


def read_csv_rows(filepath: str, encoding: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Lee un CSV y devuelve (rows, fieldnames) preservando encabezados."""
    with open(filepath, encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def validate_required_columns(
    fieldnames: Sequence[str],
    required_columns: Sequence[str],
    csv_label: str,
) -> bool:
    missing = [column for column in required_columns if column not in fieldnames]
    if not missing:
        return True

    print(f"ERROR: Faltan columnas requeridas en {csv_label}: {missing}", file=sys.stderr)
    print(f"Columnas disponibles: {list(fieldnames)}", file=sys.stderr)
    return False


def validate_input_files(paths: Sequence[Tuple[str, str]]) -> bool:
    ok = True
    for path, label in paths:
        if not os.path.isfile(path):
            print(f"ERROR: No se encontro el archivo de {label}: {path}", file=sys.stderr)
            ok = False
    return ok


def skipped_row(
    category_id: object,
    spec_name: object,
    field_id: object,
    value_name: object,
    reason: str,
    source_rows: Iterable[object],
) -> Dict[str, str]:
    return {
        "CategoryId": str(category_id or ""),
        "SpecName": str(spec_name or ""),
        "FieldId": str(field_id or ""),
        "ValueName": str(value_name or ""),
        "Reason": reason,
        "SourceRows": ";".join(str(row) for row in source_rows),
    }


def build_field_index(
    fields_rows: List[Dict[str, str]],
    field_id_column: str,
    field_category_id_column: str,
    field_name_column: str,
    dry_run: bool,
) -> Tuple[Dict[Tuple[str, str], Dict[str, object]], List[Dict[str, str]], Counter, Dict[str, object]]:
    raw_mappings: Dict[Tuple[str, str], Dict[str, object]] = {}
    skipped: List[Dict[str, str]] = []
    reason_counts: Counter = Counter()

    for index, row in enumerate(fields_rows, start=2):
        raw_category_id = row.get(field_category_id_column, "")
        raw_field_id = row.get(field_id_column, "")
        raw_name = row.get(field_name_column, "")
        category_id = normalize_integer_id(raw_category_id)
        name = normalize_spaces(raw_name)

        if not category_id:
            reason_counts["INVALID_FIELD_CATEGORY_ID"] += 1
            skipped.append(skipped_row(raw_category_id, raw_name, raw_field_id, "", "INVALID_FIELD_CATEGORY_ID", [index]))
            continue

        if not name:
            reason_counts["EMPTY_FIELD_NAME"] += 1
            skipped.append(skipped_row(category_id, raw_name, raw_field_id, "", "EMPTY_FIELD_NAME", [index]))
            continue

        field_id = normalize_integer_id(raw_field_id)
        if field_id is None and dry_run and str(raw_field_id).strip().startswith("SIMULATED-"):
            field_id = str(raw_field_id).strip()

        if field_id is None:
            reason_counts["INVALID_FIELD_ID"] += 1
            skipped.append(skipped_row(category_id, name, raw_field_id, "", "INVALID_FIELD_ID", [index]))
            continue

        key = (category_id, normalize_text_key(name))
        mapping = raw_mappings.setdefault(
            key,
            {
                "CategoryId": category_id,
                "SpecName": name,
                "FieldIds": set(),
                "SourceRows": [],
            },
        )
        mapping["FieldIds"].add(str(field_id))
        mapping["SourceRows"].append(index)

    field_index: Dict[Tuple[str, str], Dict[str, object]] = {}
    duplicate_conflicts = 0
    duplicate_same_id = 0

    for key, mapping in raw_mappings.items():
        field_ids = sorted(mapping["FieldIds"])
        if len(field_ids) > 1:
            duplicate_conflicts += 1
            reason_counts["DUPLICATE_FIELD_MAPPING"] += 1
            skipped.append(skipped_row(
                mapping["CategoryId"],
                mapping["SpecName"],
                ",".join(field_ids),
                "",
                "DUPLICATE_FIELD_MAPPING",
                mapping["SourceRows"],
            ))
            continue

        if len(mapping["SourceRows"]) > 1:
            duplicate_same_id += len(mapping["SourceRows"]) - 1

        field_id_text = field_ids[0]
        field_id_value: object = field_id_text
        if field_id_text.isdigit():
            field_id_value = int(field_id_text)

        field_index[key] = {
            "FieldId": field_id_value,
            "FieldIdText": field_id_text,
            "CategoryId": mapping["CategoryId"],
            "SpecName": mapping["SpecName"],
            "SourceRows": list(mapping["SourceRows"]),
        }

    stats = {
        "valid_field_mappings": len(field_index),
        "field_rows_skipped": len(skipped),
        "duplicate_field_mapping_conflicts": duplicate_conflicts,
        "duplicate_field_rows_same_id": duplicate_same_id,
    }
    return field_index, skipped, reason_counts, stats


def build_value_name(
    spec_name: object,
    specification_value: object,
    quantity: object,
) -> Tuple[Optional[str], str]:
    spec_name_text = normalize_spaces(spec_name)
    specification_text = normalize_spaces(specification_value)
    quantity_text = normalize_spaces(quantity)

    if quantity_text and specification_text:
        if normalize_text_key(specification_text) == normalize_text_key(spec_name_text):
            return quantity_text, "QUANTITY_ONLY_SPEC_EQUALS_NAME"
        return f"{quantity_text} {specification_text}", "QUANTITY_PLUS_SPECIFICATION"

    if specification_text:
        return specification_text, "SPECIFICATION_ONLY"

    if quantity_text:
        return quantity_text, "QUANTITY_ONLY"

    return None, "EMPTY_VALUE"


def make_vtex_payload(field_id: object, name: str, position: int, is_active: bool = False) -> Dict[str, object]:
    return {
        "FieldId": field_id,
        "Name": name,
        "IsActive": is_active,
        "Position": position,
    }


def add_internal_metadata(
    payload: Dict[str, object],
    category_id: str,
    spec_name: str,
    source_rows: List[object],
    normalization_rule: str,
    payload_key: str,
) -> Dict[str, object]:
    enriched = dict(payload)
    enriched.update({
        "_CategoryId": category_id,
        "_SpecName": spec_name,
        "_SourceRows": list(source_rows),
        "_NormalizationRule": normalization_rule,
        "_PayloadKey": payload_key,
    })
    return enriched


def build_payloads(
    matched_rows: List[Dict[str, str]],
    field_index: Dict[Tuple[str, str], Dict[str, object]],
    spec_category_id_column: str,
    spec_name_column: str,
    spec_value_column: str,
    quantity_column: str,
    is_active: bool = False,
    initial_skipped: Optional[List[Dict[str, str]]] = None,
    initial_reason_counts: Optional[Counter] = None,
) -> Tuple[List[Dict[str, object]], List[Dict[str, str]], Counter, Dict[str, object]]:
    skipped = list(initial_skipped or [])
    reason_counts: Counter = Counter(initial_reason_counts or {})
    rule_counts: Counter = Counter()
    deduped: Dict[str, Dict[str, object]] = {}
    field_order: List[str] = []
    duplicate_input_rows = 0

    for index, row in enumerate(matched_rows, start=2):
        raw_category_id = row.get(spec_category_id_column, "")
        raw_spec_name = row.get(spec_name_column, "")
        category_id = normalize_integer_id(raw_category_id)
        spec_name = normalize_spaces(raw_spec_name)

        if not category_id:
            reason_counts["EMPTY_CATEGORY_ID"] += 1
            skipped.append(skipped_row(raw_category_id, raw_spec_name, "", "", "EMPTY_CATEGORY_ID", [index]))
            continue

        if not spec_name:
            reason_counts["EMPTY_SPEC_NAME"] += 1
            skipped.append(skipped_row(category_id, raw_spec_name, "", "", "EMPTY_SPEC_NAME", [index]))
            continue

        field = field_index.get((category_id, normalize_text_key(spec_name)))
        if not field:
            reason_counts["MISSING_FIELD_ID"] += 1
            value_name, _rule = build_value_name(
                spec_name,
                row.get(spec_value_column, ""),
                row.get(quantity_column, ""),
            )
            skipped.append(skipped_row(category_id, spec_name, "", value_name or "", "MISSING_FIELD_ID", [index]))
            continue

        value_name, rule = build_value_name(
            spec_name,
            row.get(spec_value_column, ""),
            row.get(quantity_column, ""),
        )
        if not value_name:
            reason_counts["EMPTY_VALUE"] += 1
            skipped.append(skipped_row(category_id, spec_name, field["FieldId"], "", "EMPTY_VALUE", [index]))
            continue

        payload_key = make_payload_key(field["FieldId"], value_name)
        if payload_key in deduped:
            deduped[payload_key]["_SourceRows"].append(index)
            duplicate_input_rows += 1
            continue

        if field["FieldIdText"] not in field_order:
            field_order.append(field["FieldIdText"])

        rule_counts[rule] += 1
        deduped[payload_key] = add_internal_metadata(
            make_vtex_payload(field["FieldId"], value_name, 0, is_active=is_active),
            category_id=category_id,
            spec_name=spec_name,
            source_rows=[index],
            normalization_rule=rule,
            payload_key=payload_key,
        )

    positions_by_field: Dict[str, int] = defaultdict(int)
    payloads = list(deduped.values())
    for payload in payloads:
        field_id_text = str(payload["FieldId"])
        positions_by_field[field_id_text] += 1
        payload["Position"] = positions_by_field[field_id_text]

    stats = {
        "unique_payloads": len(payloads),
        "processed_fields": len(positions_by_field),
        "duplicate_input_rows": duplicate_input_rows,
        "normalization_rule_counts": rule_counts,
    }
    return payloads, skipped, reason_counts, stats


def request_payload(payload: Dict[str, object]) -> Dict[str, object]:
    return {
        "FieldId": payload["FieldId"],
        "Name": payload["Name"],
        "IsActive": payload["IsActive"],
        "Position": payload["Position"],
    }


def response_text(response: object) -> str:
    text = getattr(response, "text", "")
    return text if text else ""


class VTEXSpecificationValueCreator:
    """Crea valores de especificaciones SKU en VTEX."""

    def __init__(
        self,
        delay: float = 1.0,
        timeout: int = 30,
        dry_run: bool = False,
        state_file: Optional[str] = None,
        resume_keys: Optional[Set[str]] = None,
        encoding: str = "utf-8-sig",
    ):
        self.delay = delay
        self.timeout = timeout
        self.dry_run = dry_run
        self.state_file = state_file
        self.resume_keys = set(resume_keys or set())
        self.encoding = encoding
        self.successful_values: List[Dict[str, object]] = []
        self.failed_values: List[Dict[str, object]] = []
        self.skipped_rows: List[Dict[str, str]] = []
        self.total_attempted = 0
        self.resume_skipped = 0

        if not self.dry_run:
            self.validate_credentials()
            if requests is None:
                raise ValueError(
                    "Falta instalar requests. Ejecute: pip install requests python-dotenv"
                )

            self.session = requests.Session()
            self.session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-VTEX-API-AppKey": VTEX_APP_KEY,
                "X-VTEX-API-AppToken": VTEX_APP_TOKEN,
            })
        else:
            self.session = None

        account = VTEX_ACCOUNT or "VTEX_ACCOUNT_NAME"
        self.base_url = f"https://{account}.{VTEX_ENVIRONMENT}.com.br"
        self.endpoint = f"{self.base_url}/api/catalog/pvt/specificationvalue"

        print(f"Endpoint: {self.endpoint}")
        print(f"Delay: {self.delay}s entre requests")
        print(f"Timeout: {self.timeout}s por request")
        if self.state_file:
            print(f"State file: {self.state_file}")
        if self.dry_run:
            print("DRY-RUN: no se haran requests a VTEX")

    def validate_credentials(self) -> None:
        missing = []
        if not VTEX_APP_KEY:
            missing.append("X-VTEX-API-AppKey")
        if not VTEX_APP_TOKEN:
            missing.append("X-VTEX-API-AppToken")
        if not VTEX_ACCOUNT:
            missing.append("VTEX_ACCOUNT_NAME")

        if missing:
            raise ValueError(f"Faltan credenciales VTEX en .env: {', '.join(missing)}")

        print(f"Credenciales VTEX configuradas para cuenta: {VTEX_ACCOUNT}")

    def append_state_row(
        self,
        payload: Dict[str, object],
        status: str,
        status_code: object,
        response: object = "",
        error: object = "",
    ) -> None:
        if not self.state_file:
            return

        os.makedirs(os.path.dirname(os.path.abspath(self.state_file)), exist_ok=True)
        should_write_header = not os.path.isfile(self.state_file) or os.path.getsize(self.state_file) == 0
        row = {
            "PayloadKey": payload.get("_PayloadKey", make_payload_key(payload.get("FieldId", ""), payload.get("Name", ""))),
            "FieldId": payload.get("FieldId", ""),
            "Name": payload.get("Name", ""),
            "Position": payload.get("Position", ""),
            "Status": status,
            "StatusCode": status_code,
            "Response": response if isinstance(response, str) else json.dumps(response, ensure_ascii=False, sort_keys=True),
            "Error": error,
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self.state_file, "a", encoding=self.encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=STATE_FIELDNAMES, extrasaction="ignore")
            if should_write_header:
                writer.writeheader()
            writer.writerow(row)

    def record_success(self, payload: Dict[str, object], response_data: Dict[str, object], status_code: object) -> None:
        self.successful_values.append({
            "response": response_data,
            "payload": payload,
            "status_code": status_code,
        })
        self.total_attempted += 1
        self.append_state_row(payload, "SUCCESS", status_code, response_data, "")

    def record_failure(self, payload: Dict[str, object], status_code: object, error: str) -> None:
        self.failed_values.append({
            "FieldId": payload.get("FieldId", ""),
            "Name": payload.get("Name", ""),
            "Position": payload.get("Position", ""),
            "CategoryId": payload.get("_CategoryId", ""),
            "SpecName": payload.get("_SpecName", ""),
            "StatusCode": status_code,
            "Error": error,
            "Payload": json.dumps(request_payload(payload), ensure_ascii=False, sort_keys=True),
            "SourceRows": ";".join(str(row) for row in payload.get("_SourceRows", [])),
        })
        self.total_attempted += 1
        self.append_state_row(payload, "FAILED", status_code, "", error)

    def create_specification_value(self, payload: Dict[str, object], retry_count: int = 0) -> bool:
        max_retries = 3
        backoff_factor = 2

        if not self.dry_run and self.total_attempted > 0 and retry_count == 0:
            time.sleep(self.delay)

        if self.dry_run:
            simulated_id = f"SIMULATED-{self.total_attempted + 1}"
            response_data = request_payload(payload)
            response_data.update({"FieldValueId": simulated_id, "Id": simulated_id})
            self.record_success(payload, response_data, 200)
            return True

        try:
            if requests is None or self.session is None:
                raise RuntimeError("requests no esta disponible para modo real")

            response = self.session.post(
                self.endpoint,
                json=request_payload(payload),
                timeout=self.timeout,
            )

            if response.status_code in [200, 201]:
                try:
                    response_data = response.json() if response.text else {}
                except ValueError:
                    response_data = {"raw_response": response.text}
                self.record_success(payload, response_data, response.status_code)
                field_value_id = response_data.get("FieldValueId", response_data.get("Id", "N/A"))
                print(
                    f"OK: '{payload['Name']}' "
                    f"(FieldValueId: {field_value_id}, FieldId: {payload['FieldId']})"
                )
                return True

            if response.status_code == 429:
                if retry_count < max_retries:
                    wait_time = self.delay * (backoff_factor ** retry_count)
                    print(
                        "Rate limit 429. "
                        f"Esperando {wait_time}s (retry {retry_count + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    return self.create_specification_value(payload, retry_count + 1)

                self.record_failure(
                    payload,
                    429,
                    "Rate limit exceeded - max retries reached",
                )
                print(f"FAIL: '{payload['Name']}' - 429 max retries")
                return False

            error_text = response_text(response) or "No error message"
            self.record_failure(payload, response.status_code, error_text)
            print(f"FAIL: '{payload['Name']}' - Status {response.status_code}")
            return False

        except requests.exceptions.Timeout:
            self.record_failure(payload, "", f"Request timeout after {self.timeout}s")
            print(f"FAIL: '{payload['Name']}' - Timeout")
            return False
        except requests.exceptions.RequestException as exc:
            self.record_failure(payload, "", f"Request error: {exc}")
            print(f"FAIL: '{payload['Name']}' - {exc}")
            return False

    def process_payloads(self, payloads: List[Dict[str, object]], max_requests: Optional[int] = None) -> float:
        start_time = time.time()
        total = len(payloads)
        pending_processed = 0

        print(f"\nProcesando {total} valores de especificaciones SKU...\n")
        for index, payload in enumerate(payloads, start=1):
            payload_key = str(payload.get("_PayloadKey", ""))
            if payload_key in self.resume_keys:
                self.resume_skipped += 1
                self.skipped_rows.append(skipped_row(
                    payload.get("_CategoryId", ""),
                    payload.get("_SpecName", ""),
                    payload.get("FieldId", ""),
                    payload.get("Name", ""),
                    "RESUME_ALREADY_SUCCESSFUL",
                    payload.get("_SourceRows", []),
                ))
                continue

            if max_requests is not None and pending_processed >= max_requests:
                break

            pending_processed += 1
            if self.dry_run:
                if pending_processed % 1000 == 0 or pending_processed == max_requests:
                    print(f"Dry-run payloads pendientes: {pending_processed}")
            else:
                print(
                    f"[{index}/{total}] Creando valor '{payload['Name']}' "
                    f"(FieldId: {payload['FieldId']}, Position: {payload['Position']})"
                )
            self.create_specification_value(payload)

        duration = time.time() - start_time
        print(f"\nProceso terminado en {duration:.1f}s")
        return duration


def load_success_keys_from_csv(filepath: str, encoding: str) -> Set[str]:
    keys: Set[str] = set()
    rows, fieldnames = read_csv_rows(filepath, encoding)
    has_payload_key = "PayloadKey" in fieldnames
    for row in rows:
        if has_payload_key and row.get("PayloadKey"):
            keys.add(str(row["PayloadKey"]).strip())
            continue
        field_id = row.get("FieldId", "")
        name = row.get("Name", "")
        if field_id and name:
            keys.add(make_payload_key(field_id, name))
    return keys


def load_resume_keys(
    state_file: Optional[str],
    success_csvs: Sequence[str],
    encoding: str,
    no_resume: bool,
) -> Set[str]:
    if no_resume:
        return set()

    keys: Set[str] = set()
    if state_file and os.path.isfile(state_file):
        rows, _fieldnames = read_csv_rows(state_file, encoding)
        for row in rows:
            if str(row.get("Status", "")).strip().upper() == "SUCCESS":
                payload_key = str(row.get("PayloadKey", "")).strip()
                if payload_key:
                    keys.add(payload_key)
                elif row.get("FieldId") and row.get("Name"):
                    keys.add(make_payload_key(row.get("FieldId"), row.get("Name")))

    for filepath in success_csvs:
        if not os.path.isfile(filepath):
            print(f"ADVERTENCIA: No se encontro resume CSV: {filepath}", file=sys.stderr)
            continue
        keys.update(load_success_keys_from_csv(filepath, encoding))

    return keys


def response_to_success_row(item: Dict[str, object]) -> Dict[str, object]:
    response = item.get("response") or {}
    payload = item.get("payload") or {}
    status_code = item.get("status_code", "")

    field_value_id = ""
    if isinstance(response, dict):
        field_value_id = response.get("FieldValueId", response.get("Id", ""))

    return {
        "FieldValueId": field_value_id,
        "FieldId": payload.get("FieldId", ""),
        "Name": payload.get("Name", ""),
        "IsActive": payload.get("IsActive", ""),
        "Position": payload.get("Position", ""),
        "CategoryId": payload.get("_CategoryId", ""),
        "SpecName": payload.get("_SpecName", ""),
        "StatusCode": status_code,
        "Response": json.dumps(response, ensure_ascii=False, sort_keys=True),
    }


def write_csv(
    filepath: str,
    rows: List[Dict[str, object]],
    fieldnames: List[str],
    encoding: str,
) -> None:
    with open(filepath, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def counter_table(counter: Counter, empty_label: str) -> str:
    if not counter:
        return f"| {empty_label} | 0 |"
    return "\n".join(f"| {key} | {value} |" for key, value in sorted(counter.items()))


def generate_markdown_report(
    filepath: str,
    args: argparse.Namespace,
    totals: Dict[str, object],
    skipped_reason_counts: Counter,
    normalization_rule_counts: Counter,
    output_files: Dict[str, str],
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "DRY-RUN" if args.dry_run else "REAL"
    is_active_text = str(args.active).lower()

    report = f"""# VTEX SKU Specification Value Creation Report

**Generated:** {timestamp}
**Mode:** {mode}
**VTEX Account:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}

## Summary

| Metric | Value |
|--------|-------|
| Field rows read | {totals['field_rows_read']} |
| Matched spec rows read | {totals['matched_spec_rows_read']} |
| Valid FieldId mappings | {totals['valid_field_mappings']} |
| Field mappings skipped | {totals['field_rows_skipped']} |
| Unique payloads | {totals['unique_payloads']} |
| Requests performed | {totals['requests_performed']} |
| Successful | {totals['successful']} |
| Failed | {totals['failed']} |
| Skipped rows | {totals['skipped']} |
| Duplicate input rows ignored | {totals['duplicate_input_rows']} |
| Resume already successful | {totals['resume_skipped']} |
| Processed FieldIds | {totals['processed_fields']} |
| Duration seconds | {totals['duration_seconds']:.1f} |

## Skipped Reasons

| Reason | Count |
|--------|-------|
{counter_table(skipped_reason_counts, "Sin omitidos")}

## Normalization Rules

| Rule | Count |
|------|-------|
{counter_table(normalization_rule_counts, "Sin payloads")}

## Output Files

| Type | File |
|------|------|
| Successful | {output_files.get('successful', '')} |
| Failed | {output_files.get('failed', '')} |
| Skipped | {output_files.get('skipped', '')} |
| State | {args.state_file or ''} |

## Notes

- Payloads use `FieldId`, `Name`, `IsActive={is_active_text}` and `Position`.
- Positions are consecutive per `FieldId` over the complete deduplicated batch before resume skips.
- Existing VTEX values are not queried before POST. Use `--resume-from-success-csv` for previous local successes.
"""

    with open(filepath, "w", encoding=args.encoding) as f:
        f.write(report)


def export_results(
    creator: VTEXSpecificationValueCreator,
    skipped_rows: List[Dict[str, str]],
    skipped_reason_counts: Counter,
    normalization_rule_counts: Counter,
    args: argparse.Namespace,
    totals: Dict[str, object],
) -> Dict[str, str]:
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_files: Dict[str, str] = {}

    success_rows = [response_to_success_row(item) for item in creator.successful_values]
    success_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_successful.csv")
    write_csv(success_csv, success_rows, SUCCESS_FIELDNAMES, args.encoding)
    output_files["successful"] = success_csv
    print(f"Exitos exportados: {success_csv}")

    failed_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_failed.csv")
    write_csv(failed_csv, creator.failed_values, FAILED_FIELDNAMES, args.encoding)
    output_files["failed"] = failed_csv
    print(f"Fallos exportados: {failed_csv}")

    skipped_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_skipped.csv")
    write_csv(skipped_csv, skipped_rows + creator.skipped_rows, SKIPPED_FIELDNAMES, args.encoding)
    output_files["skipped"] = skipped_csv
    print(f"Omitidos exportados: {skipped_csv}")

    report_file = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_REPORT.md")
    generate_markdown_report(
        report_file,
        args,
        totals,
        skipped_reason_counts,
        normalization_rule_counts,
        output_files,
    )
    output_files["report"] = report_file
    print(f"Reporte generado: {report_file}")

    return output_files


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea valores de especificaciones SKU en VTEX desde CSVs de pasos 65 y 61.",
    )
    parser.add_argument(
        "fields_csv",
        help="CSV exitoso del paso 65 con Id, CategoryId y Name para usar Id como FieldId.",
    )
    parser.add_argument(
        "matched_specs_csv",
        help="CSV del paso 61 con Category ID, Nombre Especificacion, Especificacion y cantidad.",
    )
    parser.add_argument(
        "--output-prefix",
        default="sku_specificationvalue_creation",
        help="Prefijo para archivos de salida (default: sku_specificationvalue_creation)",
    )
    parser.add_argument(
        "--output-dir",
        default=SCRIPT_DIR,
        help="Directorio de salida (default: directorio del script)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding de entrada y salida (default: utf-8-sig)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay entre requests en segundos (default: 1.0)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout de request en segundos (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No llama a VTEX; simula respuestas exitosas.",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="Crea valores activos en VTEX; por defecto se crean inactivos.",
    )
    parser.add_argument(
        "--field-id-column",
        default="Id",
        help='Columna Id en CSV exitoso del paso 65 (default: "Id")',
    )
    parser.add_argument(
        "--field-category-id-column",
        default="CategoryId",
        help='Columna CategoryId en CSV exitoso del paso 65 (default: "CategoryId")',
    )
    parser.add_argument(
        "--field-name-column",
        default="Name",
        help='Columna Name en CSV exitoso del paso 65 (default: "Name")',
    )
    parser.add_argument(
        "--spec-category-id-column",
        default="Category ID",
        help='Columna Category ID en CSV de specs (default: "Category ID")',
    )
    parser.add_argument(
        "--spec-name-column",
        default="Nombre Especificacion",
        help='Columna de nombre de especificacion (default: "Nombre Especificacion")',
    )
    parser.add_argument(
        "--spec-value-column",
        default="Especificacion",
        help='Columna de valor textual de especificacion (default: "Especificacion")',
    )
    parser.add_argument(
        "--quantity-column",
        default="cantidad",
        help='Columna de cantidad para componer valores (default: "cantidad")',
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="CSV journal para reanudacion (default: <output-dir>/<output-prefix>_state.csv)",
    )
    parser.add_argument(
        "--resume-from-success-csv",
        action="append",
        default=[],
        help="CSV exitoso previo para sembrar skips de reanudacion. Puede repetirse.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignora state file y CSVs exitosos previos.",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="Procesa como maximo esta cantidad de payloads pendientes.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    start_time = time.time()
    process_duration = 0.0
    interrupted = False

    if args.max_requests is not None and args.max_requests < 0:
        print("ERROR: --max-requests debe ser mayor o igual a 0", file=sys.stderr)
        return 1

    if args.state_file is None:
        args.state_file = os.path.join(args.output_dir, f"{args.output_prefix}_state.csv")

    if not validate_input_files([
        (args.fields_csv, "CSV exitoso de fields paso 65"),
        (args.matched_specs_csv, "especificaciones encontradas paso 61"),
    ]):
        return 1

    try:
        print(f"Leyendo fields: {args.fields_csv}")
        fields_rows, fields_fieldnames = read_csv_rows(args.fields_csv, args.encoding)
        print(f"  Filas fields: {len(fields_rows)}")

        print(f"Leyendo specs: {args.matched_specs_csv}")
        matched_rows, matched_fieldnames = read_csv_rows(args.matched_specs_csv, args.encoding)
        print(f"  Filas specs: {len(matched_rows)}")
    except OSError as exc:
        print(f"ERROR: No se pudo leer un CSV: {exc}", file=sys.stderr)
        return 1

    columns_ok = True
    columns_ok = validate_required_columns(
        fields_fieldnames,
        [args.field_id_column, args.field_category_id_column, args.field_name_column],
        "CSV exitoso de fields",
    ) and columns_ok
    columns_ok = validate_required_columns(
        matched_fieldnames,
        [
            args.spec_category_id_column,
            args.spec_name_column,
            args.spec_value_column,
            args.quantity_column,
        ],
        "CSV de specs",
    ) and columns_ok
    if not columns_ok:
        return 1

    field_index, field_skipped, field_reason_counts, field_stats = build_field_index(
        fields_rows,
        args.field_id_column,
        args.field_category_id_column,
        args.field_name_column,
        args.dry_run,
    )
    payloads, skipped_rows, skipped_reason_counts, payload_stats = build_payloads(
        matched_rows,
        field_index,
        args.spec_category_id_column,
        args.spec_name_column,
        args.spec_value_column,
        args.quantity_column,
        is_active=args.active,
        initial_skipped=field_skipped,
        initial_reason_counts=field_reason_counts,
    )

    print("\nResumen de preparacion:")
    print(f"  Fields leidos: {len(fields_rows)}")
    print(f"  FieldId validos indexados: {len(field_index)}")
    print(f"  Specs leidas: {len(matched_rows)}")
    print(f"  Payloads unicos: {len(payloads)}")
    print(f"  Omitidos previos: {len(skipped_rows)}")
    print(f"  Duplicados ignorados: {payload_stats['duplicate_input_rows']}")

    if not payloads:
        print("ERROR: No hay payloads validos para procesar.", file=sys.stderr)
        return 1

    try:
        resume_keys = load_resume_keys(
            args.state_file,
            args.resume_from_success_csv,
            args.encoding,
            args.no_resume,
        )
        if resume_keys:
            print(f"Claves de reanudacion cargadas: {len(resume_keys)}")

        creator = VTEXSpecificationValueCreator(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run,
            state_file=None if args.no_resume else args.state_file,
            resume_keys=resume_keys,
            encoding=args.encoding,
        )
        try:
            process_duration = creator.process_payloads(payloads, args.max_requests)
        except KeyboardInterrupt:
            interrupted = True
            print("\nProceso interrumpido por el usuario; exportando resultados parciales.", file=sys.stderr)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    skipped_reason_counts.update(row["Reason"] for row in creator.skipped_rows)
    duration = time.time() - start_time
    totals = {
        "field_rows_read": len(fields_rows),
        "matched_spec_rows_read": len(matched_rows),
        "valid_field_mappings": field_stats["valid_field_mappings"],
        "field_rows_skipped": field_stats["field_rows_skipped"],
        "unique_payloads": len(payloads),
        "requests_performed": creator.total_attempted,
        "successful": len(creator.successful_values),
        "failed": len(creator.failed_values),
        "skipped": len(skipped_rows) + len(creator.skipped_rows),
        "duplicate_input_rows": payload_stats["duplicate_input_rows"],
        "resume_skipped": creator.resume_skipped,
        "processed_fields": payload_stats["processed_fields"],
        "duration_seconds": duration,
        "process_duration_seconds": process_duration,
    }

    export_results(
        creator=creator,
        skipped_rows=skipped_rows,
        skipped_reason_counts=skipped_reason_counts,
        normalization_rule_counts=payload_stats["normalization_rule_counts"],
        args=args,
        totals=totals,
    )

    print("\nEstadisticas finales:")
    print(f"  Payloads procesados: {creator.total_attempted}")
    print(f"  Exitosos: {len(creator.successful_values)}")
    print(f"  Fallidos: {len(creator.failed_values)}")
    print(f"  Omitidos: {totals['skipped']}")
    print(f"  Saltados por reanudacion: {creator.resume_skipped}")

    if interrupted:
        return 1
    return 1 if creator.failed_values else 0


if __name__ == "__main__":
    sys.exit(main())
