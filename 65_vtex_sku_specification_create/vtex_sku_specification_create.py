#!/usr/bin/env python3
"""
vtex_sku_specification_create.py
--------------------------------
Crea especificaciones SKU tipo combo en VTEX cruzando:

- CSV de grupos de especificacion validados por categoria.
- CSV de especificaciones SKU encontradas por categoria.

El script deduplica por Category ID + Nombre Especificacion, crea un payload
por especificacion unica, y exporta exitos, fallos, omitidos y reporte.
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

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
DEFAULT_SPECGROUP_CSV = os.path.join(
    SCRIPT_DIR,
    "resultado_20260602_122525_categoryid_tercer_nivel_correctos.csv",
)
DEFAULT_MATCHED_SPECS_CSV = os.path.join(
    SCRIPT_DIR,
    "resultado_20260602_113828_encontrados.csv",
)

SUCCESS_FIELDNAMES = [
    "Id",
    "FieldTypeId",
    "CategoryId",
    "FieldGroupId",
    "Name",
    "Description",
    "Position",
    "IsFilter",
    "IsRequired",
    "IsOnProductDetails",
    "IsStockKeepingUnit",
    "IsWizard",
    "IsActive",
    "IsTopMenuLinkActive",
    "IsSideMenuLinkActive",
    "DefaultValue",
    "StatusCode",
]

FAILED_FIELDNAMES = [
    "CategoryId",
    "FieldGroupId",
    "Name",
    "Position",
    "StatusCode",
    "Error",
]

SKIPPED_FIELDNAMES = [
    "CategoryId",
    "Name",
    "Reason",
    "SourceRows",
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


def make_payload(
    category_id: str,
    group_id: str,
    name: str,
    position: int,
) -> Dict[str, object]:
    return {
        "FieldTypeId": 5,
        "CategoryId": int(category_id),
        "FieldGroupId": int(group_id),
        "Name": name,
        "Position": position,
        "IsFilter": True,
        "IsRequired": False,
        "IsOnProductDetails": True,
        "IsStockKeepingUnit": True,
        "IsActive": True,
        "IsTopMenuLinkActive": False,
        "IsSideMenuLinkActive": False,
        "DefaultValue": "",
    }


def build_group_index(
    specgroup_rows: List[Dict[str, str]],
    category_id_column: str,
    group_id_column: str,
) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, str]], Counter]:
    group_index: Dict[str, Dict[str, str]] = {}
    duplicates: Dict[str, List[int]] = defaultdict(list)
    invalid_groups: List[Dict[str, str]] = []
    skipped_reasons: Counter = Counter()

    for line_number, row in enumerate(specgroup_rows, start=2):
        category_id = normalize_integer_id(row.get(category_id_column))
        group_id = normalize_integer_id(row.get(group_id_column))

        if not category_id:
            invalid_groups.append({
                "CategoryId": str(row.get(category_id_column, "")).strip(),
                "Name": str(row.get("Name", "")).strip(),
                "Reason": "INVALID_GROUP_CATEGORY_ID",
                "SourceRows": str(line_number),
            })
            skipped_reasons["INVALID_GROUP_CATEGORY_ID"] += 1
            continue

        if not group_id:
            invalid_groups.append({
                "CategoryId": category_id,
                "Name": str(row.get("Name", "")).strip(),
                "Reason": "INVALID_GROUP_ID",
                "SourceRows": str(line_number),
            })
            skipped_reasons["INVALID_GROUP_ID"] += 1
            continue

        if category_id in group_index:
            duplicates[category_id].append(line_number)
            continue

        group_index[category_id] = {
            "CategoryId": category_id,
            "GroupId": group_id,
            "SourceRow": str(line_number),
        }

    for category_id, duplicate_lines in duplicates.items():
        first_line = group_index[category_id]["SourceRow"]
        source_rows = ",".join([first_line] + [str(line) for line in duplicate_lines])
        invalid_groups.append({
            "CategoryId": category_id,
            "Name": "",
            "Reason": "DUPLICATE_GROUP_CATEGORY",
            "SourceRows": source_rows,
        })
        skipped_reasons["DUPLICATE_GROUP_CATEGORY"] += 1
        group_index.pop(category_id, None)

    return group_index, invalid_groups, skipped_reasons


def build_payloads(
    matched_spec_rows: List[Dict[str, str]],
    group_index: Dict[str, Dict[str, str]],
    spec_category_id_column: str,
    spec_name_column: str,
    initial_skipped: Optional[List[Dict[str, str]]] = None,
    initial_reason_counts: Optional[Counter] = None,
) -> Tuple[List[Dict[str, object]], List[Dict[str, str]], Counter, Dict[str, int]]:
    payloads: List[Dict[str, object]] = []
    skipped: List[Dict[str, str]] = list(initial_skipped or [])
    reason_counts: Counter = Counter(initial_reason_counts or {})
    seen: Dict[Tuple[str, str], List[int]] = {}
    positions_by_category: Dict[str, int] = defaultdict(int)
    categories_without_group = set()

    for line_number, row in enumerate(matched_spec_rows, start=2):
        category_id = normalize_integer_id(row.get(spec_category_id_column))
        name = str(row.get(spec_name_column, "") or "").strip()

        if not category_id:
            skipped.append({
                "CategoryId": str(row.get(spec_category_id_column, "") or "").strip(),
                "Name": name,
                "Reason": "EMPTY_CATEGORY_ID",
                "SourceRows": str(line_number),
            })
            reason_counts["EMPTY_CATEGORY_ID"] += 1
            continue

        group = group_index.get(category_id)
        if not group:
            key = (category_id, name)
            if key not in seen:
                skipped.append({
                    "CategoryId": category_id,
                    "Name": name,
                    "Reason": "CATEGORY_WITHOUT_GROUP",
                    "SourceRows": str(line_number),
                })
                reason_counts["CATEGORY_WITHOUT_GROUP"] += 1
                categories_without_group.add(category_id)
                seen[key] = [line_number]
            else:
                seen[key].append(line_number)
            continue

        if not name:
            skipped.append({
                "CategoryId": category_id,
                "Name": name,
                "Reason": "EMPTY_SPEC_NAME",
                "SourceRows": str(line_number),
            })
            reason_counts["EMPTY_SPEC_NAME"] += 1
            continue

        key = (category_id, name)
        if key in seen:
            seen[key].append(line_number)
            continue
        seen[key] = [line_number]

        positions_by_category[category_id] += 1
        payloads.append(make_payload(
            category_id=category_id,
            group_id=group["GroupId"],
            name=name,
            position=positions_by_category[category_id],
        ))

    stats = {
        "unique_categories_without_group": len(categories_without_group),
        "processed_categories": len({str(payload["CategoryId"]) for payload in payloads}),
        "duplicate_input_rows": sum(max(0, len(rows) - 1) for rows in seen.values()),
    }
    return payloads, skipped, reason_counts, stats


class VTEXSKUSpecificationCreator:
    """Crea especificaciones SKU tipo combo en VTEX."""

    def __init__(self, delay: float = 1.0, timeout: int = 30, dry_run: bool = False):
        self.delay = delay
        self.timeout = timeout
        self.dry_run = dry_run
        self.successful_specs: List[Dict[str, object]] = []
        self.failed_specs: List[Dict[str, object]] = []
        self.total_attempted = 0

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
        self.endpoint = f"{self.base_url}/api/catalog/pvt/specification"

        print(f"Endpoint: {self.endpoint}")
        print(f"Delay: {self.delay}s entre requests")
        print(f"Timeout: {self.timeout}s por request")
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

    def create_specification(self, payload: Dict[str, object], retry_count: int = 0) -> bool:
        max_retries = 3
        backoff_factor = 2

        if not self.dry_run and self.total_attempted > 0 and retry_count == 0:
            time.sleep(self.delay)

        if self.dry_run:
            simulated_id = f"SIMULATED-{self.total_attempted + 1}"
            response_data = dict(payload)
            response_data.update({
                "Id": simulated_id,
                "Description": "",
                "IsWizard": False,
            })
            self.successful_specs.append({
                "response": response_data,
                "payload": payload,
                "status_code": 200,
            })
            self.total_attempted += 1
            return True

        try:
            if requests is None or self.session is None:
                raise RuntimeError("requests no esta disponible para modo real")

            response = self.session.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code in [200, 201]:
                response_data = response.json() if response.text else {}
                self.successful_specs.append({
                    "response": response_data,
                    "payload": payload,
                    "status_code": response.status_code,
                })
                self.total_attempted += 1
                field_id = response_data.get("Id", "N/A")
                print(
                    f"OK: '{payload['Name']}' "
                    f"(FieldId: {field_id}, CategoryId: {payload['CategoryId']})"
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
                    return self.create_specification(payload, retry_count + 1)

                self.record_failure(
                    payload,
                    429,
                    "Rate limit exceeded - max retries reached",
                )
                print(f"FAIL: '{payload['Name']}' - 429 max retries")
                return False

            error_text = response.text if response.text else "No error message"
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

    def record_failure(self, payload: Dict[str, object], status_code: object, error: str) -> None:
        self.failed_specs.append({
            "CategoryId": payload.get("CategoryId", ""),
            "FieldGroupId": payload.get("FieldGroupId", ""),
            "Name": payload.get("Name", ""),
            "Position": payload.get("Position", ""),
            "StatusCode": status_code,
            "Error": error,
            "Payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        })
        self.total_attempted += 1

    def process_payloads(self, payloads: List[Dict[str, object]]) -> float:
        start_time = time.time()
        total = len(payloads)

        print(f"\nProcesando {total} especificaciones SKU...\n")
        for index, payload in enumerate(payloads, start=1):
            if self.dry_run:
                if index % 1000 == 0 or index == total:
                    print(f"Dry-run payloads: {index}/{total}")
            else:
                print(
                    f"[{index}/{total}] Creando '{payload['Name']}' "
                    f"(CategoryId: {payload['CategoryId']}, "
                    f"GroupId: {payload['FieldGroupId']})"
                )
            self.create_specification(payload)

        duration = time.time() - start_time
        print(f"\nProceso terminado en {duration:.1f}s")
        return duration


def response_to_success_row(item: Dict[str, object]) -> Dict[str, object]:
    response = item.get("response") or {}
    payload = item.get("payload") or {}
    status_code = item.get("status_code", "")

    row = {}
    for fieldname in SUCCESS_FIELDNAMES:
        if fieldname == "StatusCode":
            row[fieldname] = status_code
        else:
            row[fieldname] = response.get(fieldname, payload.get(fieldname, ""))
    return row


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


def generate_markdown_report(
    filepath: str,
    args: argparse.Namespace,
    totals: Dict[str, object],
    skipped_reason_counts: Counter,
    output_files: Dict[str, str],
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "DRY-RUN" if args.dry_run else "REAL"
    reason_lines = "\n".join(
        f"| {reason} | {count} |"
        for reason, count in sorted(skipped_reason_counts.items())
    )
    if not reason_lines:
        reason_lines = "| Sin omitidos | 0 |"

    report = f"""# VTEX SKU Specification Creation Report

**Generated:** {timestamp}
**Mode:** {mode}
**VTEX Account:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}

## Summary

| Metric | Value |
|--------|-------|
| Spec group rows read | {totals['specgroup_rows_read']} |
| Matched spec rows read | {totals['matched_spec_rows_read']} |
| Unique payloads | {totals['unique_payloads']} |
| Successful | {totals['successful']} |
| Failed | {totals['failed']} |
| Skipped rows | {totals['skipped']} |
| Categories processed | {totals['processed_categories']} |
| Categories without validated group | {totals['unique_categories_without_group']} |
| Duplicate input rows ignored | {totals['duplicate_input_rows']} |
| Duration seconds | {totals['duration_seconds']:.1f} |

## Skipped Reasons

| Reason | Count |
|--------|-------|
{reason_lines}

## Output Files

| Type | File |
|------|------|
| Successful | {output_files.get('successful', '')} |
| Failed | {output_files.get('failed', '')} |
| Skipped | {output_files.get('skipped', '')} |

## Notes

- Payloads use `FieldTypeId=5` for VTEX combo specifications.
- Positions are consecutive per category within this input batch.
- Existing VTEX specifications are not queried before POST.
"""

    with open(filepath, "w", encoding=args.encoding) as f:
        f.write(report)


def export_results(
    creator: VTEXSKUSpecificationCreator,
    skipped_rows: List[Dict[str, str]],
    skipped_reason_counts: Counter,
    args: argparse.Namespace,
    totals: Dict[str, object],
) -> Dict[str, str]:
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_files: Dict[str, str] = {}

    success_rows = [response_to_success_row(item) for item in creator.successful_specs]
    success_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_successful.csv")
    write_csv(success_csv, success_rows, SUCCESS_FIELDNAMES, args.encoding)
    output_files["successful"] = success_csv
    print(f"Exitos exportados: {success_csv}")

    failed_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_failed.csv")
    failed_rows = [
        {
            "CategoryId": item.get("CategoryId", ""),
            "FieldGroupId": item.get("FieldGroupId", ""),
            "Name": item.get("Name", ""),
            "Position": item.get("Position", ""),
            "StatusCode": item.get("StatusCode", ""),
            "Error": item.get("Error", ""),
        }
        for item in creator.failed_specs
    ]
    write_csv(failed_csv, failed_rows, FAILED_FIELDNAMES, args.encoding)
    output_files["failed"] = failed_csv
    print(f"Fallos exportados: {failed_csv}")

    if skipped_rows:
        skipped_csv = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_skipped.csv")
        write_csv(skipped_csv, skipped_rows, SKIPPED_FIELDNAMES, args.encoding)
        output_files["skipped"] = skipped_csv
        print(f"Omitidos exportados: {skipped_csv}")

    report_file = os.path.join(args.output_dir, f"{timestamp}_{args.output_prefix}_REPORT.md")
    generate_markdown_report(report_file, args, totals, skipped_reason_counts, output_files)
    output_files["report"] = report_file
    print(f"Reporte generado: {report_file}")

    return output_files


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea especificaciones SKU tipo combo en VTEX desde dos CSV.",
    )
    parser.add_argument(
        "specgroup_csv",
        nargs="?",
        default=DEFAULT_SPECGROUP_CSV,
        help=(
            "CSV de grupos validados por categoria "
            f"(default: {DEFAULT_SPECGROUP_CSV})"
        ),
    )
    parser.add_argument(
        "matched_specs_csv",
        nargs="?",
        default=DEFAULT_MATCHED_SPECS_CSV,
        help=(
            "CSV de especificaciones SKU encontradas "
            f"(default: {DEFAULT_MATCHED_SPECS_CSV})"
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="sku_specification_creation",
        help="Prefijo para archivos de salida (default: sku_specification_creation)",
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
        "--category-id-column",
        default="CategoryId",
        help='Columna CategoryId en CSV de grupos (default: "CategoryId")',
    )
    parser.add_argument(
        "--group-id-column",
        default="GroupId",
        help='Columna GroupId en CSV de grupos (default: "GroupId")',
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
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    start_time = time.time()

    if not validate_input_files([
        (args.specgroup_csv, "grupos de especificacion"),
        (args.matched_specs_csv, "especificaciones encontradas"),
    ]):
        return 1

    try:
        print(f"Leyendo grupos: {args.specgroup_csv}")
        specgroup_rows, specgroup_fieldnames = read_csv_rows(args.specgroup_csv, args.encoding)
        print(f"  Filas grupos: {len(specgroup_rows)}")

        print(f"Leyendo specs: {args.matched_specs_csv}")
        matched_spec_rows, matched_spec_fieldnames = read_csv_rows(args.matched_specs_csv, args.encoding)
        print(f"  Filas specs: {len(matched_spec_rows)}")
    except OSError as exc:
        print(f"ERROR: No se pudo leer un CSV: {exc}", file=sys.stderr)
        return 1

    columns_ok = True
    columns_ok = validate_required_columns(
        specgroup_fieldnames,
        [args.category_id_column, args.group_id_column],
        "CSV de grupos",
    ) and columns_ok
    columns_ok = validate_required_columns(
        matched_spec_fieldnames,
        [args.spec_category_id_column, args.spec_name_column],
        "CSV de specs",
    ) and columns_ok
    if not columns_ok:
        return 1

    group_index, invalid_group_rows, group_reason_counts = build_group_index(
        specgroup_rows,
        args.category_id_column,
        args.group_id_column,
    )
    payloads, skipped_rows, skipped_reason_counts, payload_stats = build_payloads(
        matched_spec_rows,
        group_index,
        args.spec_category_id_column,
        args.spec_name_column,
        initial_skipped=invalid_group_rows,
        initial_reason_counts=group_reason_counts,
    )

    print("\nResumen de preparacion:")
    print(f"  Grupos leidos: {len(specgroup_rows)}")
    print(f"  Grupos validos indexados: {len(group_index)}")
    print(f"  Specs leidas: {len(matched_spec_rows)}")
    print(f"  Payloads unicos: {len(payloads)}")
    print(f"  Omitidos: {len(skipped_rows)}")
    print(f"  Categorias sin grupo validado: {payload_stats['unique_categories_without_group']}")

    if not payloads:
        print("ERROR: No hay payloads validos para procesar.", file=sys.stderr)
        return 1

    try:
        creator = VTEXSKUSpecificationCreator(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        process_duration = creator.process_payloads(payloads)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario", file=sys.stderr)
        return 1

    duration = time.time() - start_time
    totals = {
        "specgroup_rows_read": len(specgroup_rows),
        "matched_spec_rows_read": len(matched_spec_rows),
        "unique_payloads": len(payloads),
        "successful": len(creator.successful_specs),
        "failed": len(creator.failed_specs),
        "skipped": len(skipped_rows),
        "processed_categories": payload_stats["processed_categories"],
        "unique_categories_without_group": payload_stats["unique_categories_without_group"],
        "duplicate_input_rows": payload_stats["duplicate_input_rows"],
        "duration_seconds": duration,
        "process_duration_seconds": process_duration,
    }

    export_results(
        creator=creator,
        skipped_rows=skipped_rows,
        skipped_reason_counts=skipped_reason_counts,
        args=args,
        totals=totals,
    )

    print("\nEstadisticas finales:")
    print(f"  Payloads procesados: {creator.total_attempted}")
    print(f"  Exitosos: {len(creator.successful_specs)}")
    print(f"  Fallidos: {len(creator.failed_specs)}")
    print(f"  Omitidos: {len(skipped_rows)}")

    return 1 if creator.failed_specs else 0


if __name__ == "__main__":
    sys.exit(main())
