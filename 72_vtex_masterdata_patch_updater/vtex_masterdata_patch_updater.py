#!/usr/bin/env python3
"""
vtex_masterdata_patch_updater.py

Ejecuta PATCH real contra la API de VTEX Master Data v2 para actualizar
parcialmente documentos existentes, a partir de un CSV con columnas `id` y
`patch_payload` (JSON string por fila) — el formato exacto que genera
`71_email_masterdata_diff/email_masterdata_diff.py` en `_coincidencias_actualizar.csv`.

    PATCH https://{accountName}.{environment}.com.br/api/dataentities/{dataEntityName}/documents/{id}

Documentación: https://developers.vtex.com/docs/api-reference/master-data-api-v2#patch-/api/dataentities/-dataEntityName-/documents/-id-

Funcionalidad:
- Lee cada fila del CSV, parsea `patch_payload` como JSON y ejecuta PATCH contra
  el documento `id` de la entidad indicada por --data-entity-name (default: CL).
- Soporta --dry-run para simular sin llamar a la API.
- Reintenta con backoff exponencial en HTTP 429, 5xx, timeout o error de red.
- Filas con `id` vacío o `patch_payload` inválido se registran como error de
  validación (sin llamar a la API) y no detienen el procesamiento del resto.
- Genera CSV de errores (si hay) y reporte Markdown con estadísticas.

Credenciales requeridas en .env de la raíz del proyecto o variables de entorno:
- X-VTEX-API-AppKey
- X-VTEX-API-AppToken
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)

Ejecución:
    python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv
    python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv --dry-run
    python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv -e CL --delay 1.0
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

DEFAULT_DATA_ENTITY_NAME = "CL"
DEFAULT_DELAY = 0.5
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
BACKOFF_FACTOR = 2
ENDPOINT_TEMPLATE = "/api/dataentities/{dataEntityName}/documents/{id}"


@dataclass
class VtexConfig:
    app_key: str
    app_token: str
    account: str
    environment: str

    @property
    def base_url(self) -> str:
        return f"https://{self.account}.{self.environment}.com.br"

    @staticmethod
    def load() -> "VtexConfig":
        here = Path(__file__).resolve()
        candidates = [here.parent.parent / ".env", here.parent / ".env"]
        for env_path in candidates:
            if env_path.exists():
                load_dotenv(env_path)
                break
        else:
            load_dotenv()

        app_key = os.getenv("X-VTEX-API-AppKey")
        app_token = os.getenv("X-VTEX-API-AppToken")
        account = os.getenv("VTEX_ACCOUNT_NAME")
        environment = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")

        missing = [
            name
            for name, value in {
                "X-VTEX-API-AppKey": app_key,
                "X-VTEX-API-AppToken": app_token,
                "VTEX_ACCOUNT_NAME": account,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Credenciales VTEX faltantes: "
                f"{', '.join(missing)}. Configuralas en .env o como variables de entorno."
            )

        return VtexConfig(
            app_key=app_key or "",
            app_token=app_token or "",
            account=account or "",
            environment=environment,
        )


def build_headers(config: VtexConfig) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-VTEX-API-AppKey": config.app_key,
        "X-VTEX-API-AppToken": config.app_token,
    }


def summarize_response_error(response: requests.Response) -> str:
    text = response.text.strip()
    if not text:
        return f"HTTP {response.status_code} sin cuerpo de respuesta"
    return f"HTTP {response.status_code}: {text[:500]}"


def patch_document(
    session: requests.Session,
    config: VtexConfig,
    data_entity_name: str,
    doc_id: str,
    payload: Dict[str, Any],
    timeout: int,
    retries: int,
) -> Tuple[bool, Optional[str]]:
    """
    Ejecuta el PATCH para un documento. Retorna (exito, error_o_none).
    """
    url = f"{config.base_url}{ENDPOINT_TEMPLATE.format(dataEntityName=data_entity_name, id=doc_id)}"

    for attempt in range(retries + 1):
        try:
            response = session.patch(
                url,
                headers=build_headers(config),
                json=payload,
                timeout=timeout,
            )

            if response.status_code == 429 and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Rate limit (429) para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500 and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Error {response.status_code} para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                return False, summarize_response_error(response)

            return True, None

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Timeout para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            return False, f"Timeout después de {timeout}s"
        except requests.exceptions.RequestException as exc:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Error de red para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            return False, f"Error de red: {exc}"

    return False, f"No se pudo actualizar tras {retries} reintentos"


def read_rows(csv_path: str, id_col: str, payload_col: str, encoding: str) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo '{csv_path}'")
        sys.exit(1)

    with open(csv_path, "r", newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in (id_col, payload_col) if c not in fieldnames]
        if missing:
            available = ", ".join(fieldnames)
            print(f"❌ Error: Columna(s) {missing} no encontrada(s) en el CSV.")
            print(f"   Columnas disponibles: {available}")
            sys.exit(1)
        return list(reader)


def open_progress_log(path: str) -> Tuple[Any, "csv._writer"]:
    """
    Abre el log incremental de progreso y escribe el encabezado. Cada fila se
    escribe (y se fuerza a disco con flush+fsync) apenas se resuelve, para que
    una interrupción abrupta del proceso no pierda el rastro de qué se procesó.
    """
    f = open(path, "w", newline="", encoding="utf-8")
    writer = csv.writer(f)
    writer.writerow(["fila", "id", "estado", "motivo"])
    f.flush()
    os.fsync(f.fileno())
    return f, writer


def log_progress(f: Any, writer: "csv._writer", fila: int, doc_id: str, estado: str, motivo: str = "") -> None:
    writer.writerow([fila, doc_id, estado, motivo])
    f.flush()
    os.fsync(f.fileno())


def write_errors_csv(path: str, errors: List[Dict[str, str]]) -> None:
    fields = ["id", "patch_payload", "motivo"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(errors)
    print(f"💾 CSV de errores exportado: '{path}' ({len(errors)} filas)")


def write_report(path: str, stats: Dict[str, Any], args: argparse.Namespace, errors: List[Dict[str, str]]) -> None:
    total = stats["total"]
    updated = stats["updated"]
    failed = stats["failed"]
    simulated = stats["simulated"]
    is_dry_run = args.dry_run

    updated_pct = (updated / total * 100) if total else 0
    failed_pct = (failed / total * 100) if total else 0
    simulated_pct = (simulated / total * 100) if total else 0

    mode_label = "DRY-RUN" if is_dry_run else "REAL"

    lines = [
        "# Reporte de Actualización PATCH — VTEX Master Data",
        "",
        f"**Generado:** {stats['generated_at']}  ",
        f"**Cuenta VTEX:** {stats['account_name']}  ",
        f"**Data Entity:** {args.data_entity_name}  ",
        f"**Modo:** {mode_label}",
        "",
        "---",
        "",
        "## 📊 Resumen Ejecutivo",
        "",
        "| Métrica | Cantidad | Porcentaje |",
        "|---------|----------|------------|",
        f"| Total filas | {total} | 100% |",
    ]

    if is_dry_run:
        lines.append(f"| 🔍 Simuladas (dry-run) | {simulated} | {simulated_pct:.1f}% |")
    else:
        lines += [
            f"| ✅ Actualizadas exitosamente | {updated} | {updated_pct:.1f}% |",
            f"| ⚠️ Errores | {failed} | {failed_pct:.1f}% |",
        ]

    lines += [
        "",
        "## ⚙️ Configuración",
        "",
        f"- **Input:** `{args.input_csv}`",
        f"- **Data Entity:** `{args.data_entity_name}`",
        f"- **Columna id:** `{args.id_col}`",
        f"- **Columna payload:** `{args.payload_col}`",
        f"- **Delay entre requests:** {args.delay}s",
        f"- **Timeout:** {args.timeout}s",
        f"- **Retries:** {args.retries}",
        f"- **Modo dry-run:** {'Sí' if is_dry_run else 'No'}",
        "",
    ]

    if errors:
        errors_csv = stats.get("errors_csv", "")
        lines += [
            "## ⚠️ Errores",
            "",
            "| id | motivo |",
            "|----|--------|",
        ]
        for err in errors[:50]:
            lines.append(f"| {err['id']} | {err['motivo']} |")
        if len(errors) > 50:
            lines.append(f"| *(y {len(errors) - 50} más...)* | |")
        if errors_csv:
            lines += ["", f"CSV de errores exportado: `{errors_csv}`"]
        lines.append("")

    lines += [
        "---",
        "",
        "*Reporte generado automáticamente por `vtex_masterdata_patch_updater.py`*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📋 Reporte exportado: '{path}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta PATCH real contra VTEX Master Data v2 para actualizar documentos "
            "a partir de un CSV con columnas id y patch_payload."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv
  python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv --dry-run
  python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv -e CL --delay 1.0
  python3 vtex_masterdata_patch_updater.py input.csv --id-col id --payload-col patch_payload
""",
    )
    parser.add_argument("input_csv", help="CSV con columnas id y patch_payload (ej. salida de 71_email_masterdata_diff)")
    parser.add_argument(
        "-e", "--data-entity-name", default=DEFAULT_DATA_ENTITY_NAME,
        help=f"Nombre de la entidad de Master Data a actualizar (default: {DEFAULT_DATA_ENTITY_NAME}).",
    )
    parser.add_argument("--id-col", default="id", help="Columna con el id del documento (default: id)")
    parser.add_argument("--payload-col", default="patch_payload", help="Columna con el JSON del patch (default: patch_payload)")
    parser.add_argument("-o", "--output", help="CSV de errores (default: {data_entity_name}_patch_errors_{timestamp}.csv)")
    parser.add_argument("-r", "--report", help="Reporte Markdown (default: {data_entity_name}_patch_report_{timestamp}.md)")
    parser.add_argument("--log", help="Log incremental CSV, una fila por documento procesado (default: {data_entity_name}_patch_log_{timestamp}.csv)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout de requests en segundos (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Reintentos para 429/5xx/timeout/error de red (default: {DEFAULT_RETRIES})")
    parser.add_argument("--encoding", default="utf-8", help="Encoding del CSV de entrada (default: utf-8)")
    parser.add_argument("--dry-run", action="store_true", help="Simula las operaciones sin hacer PATCH reales")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_errors = args.output or f"{args.data_entity_name}_patch_errors_{timestamp}.csv"
    output_report = args.report or f"{args.data_entity_name}_patch_report_{timestamp}.md"
    output_log = args.log or f"{args.data_entity_name}_patch_log_{timestamp}.csv"

    try:
        config = VtexConfig.load()
    except RuntimeError as exc:
        print(f"❌ Error: {exc}")
        return 1

    rows = read_rows(args.input_csv, args.id_col, args.payload_col, args.encoding)
    total = len(rows)

    mode_label = "DRY-RUN" if args.dry_run else "REAL"
    print(f"\n🚀 Iniciando actualización PATCH en VTEX Master Data")
    print(f"   Cuenta: {config.account}")
    print(f"   Data Entity: {args.data_entity_name}")
    print(f"   Modo: {mode_label}")
    print(f"   Total a procesar: {total}")
    print(f"   Delay: {args.delay}s | Timeout: {args.timeout}s | Retries: {args.retries}")
    print(f"   Reporte: {output_report}")
    print(f"   Log incremental: {output_log}\n")

    session = requests.Session()
    errors: List[Dict[str, str]] = []
    count_updated = 0
    count_failed = 0
    count_simulated = 0

    log_file, log_writer = open_progress_log(output_log)
    try:
        for i, row in enumerate(rows, start=1):
            doc_id = (row.get(args.id_col) or "").strip()
            raw_payload = row.get(args.payload_col) or ""

            if not doc_id:
                count_failed += 1
                errors.append({"id": "", "patch_payload": raw_payload, "motivo": "id vacío"})
                print(f"[{i}/{total}] (sin id) → ⚠️  id vacío, se omite")
                log_progress(log_file, log_writer, i, "", "id_vacio", "id vacío")
                continue

            try:
                payload = json.loads(raw_payload)
            except (ValueError, TypeError) as exc:
                count_failed += 1
                errors.append({"id": doc_id, "patch_payload": raw_payload, "motivo": f"patch_payload inválido: {exc}"})
                print(f"[{i}/{total}] {doc_id} → ⚠️  patch_payload inválido: {exc}")
                log_progress(log_file, log_writer, i, doc_id, "payload_invalido", f"patch_payload inválido: {exc}")
                continue

            if args.dry_run:
                count_simulated += 1
                print(f"[{i}/{total}] {doc_id} → 🔍 dry-run ({len(payload)} campos)")
                log_progress(log_file, log_writer, i, doc_id, "simulado")
            else:
                success, error = patch_document(
                    session=session,
                    config=config,
                    data_entity_name=args.data_entity_name,
                    doc_id=doc_id,
                    payload=payload,
                    timeout=args.timeout,
                    retries=args.retries,
                )
                if success:
                    count_updated += 1
                    print(f"[{i}/{total}] {doc_id} → ✅ actualizado")
                    log_progress(log_file, log_writer, i, doc_id, "actualizado")
                else:
                    count_failed += 1
                    errors.append({"id": doc_id, "patch_payload": raw_payload, "motivo": error or ""})
                    print(f"[{i}/{total}] {doc_id} → ❌ error: {error}")
                    log_progress(log_file, log_writer, i, doc_id, "error", error or "")

                if i < total:
                    time.sleep(args.delay)
    finally:
        log_file.close()

    print(f"\n✅ Proceso completado.")
    if args.dry_run:
        print(f"   Simuladas:  {count_simulated}/{total}")
    else:
        print(f"   Actualizadas: {count_updated}/{total}")
        print(f"   Errores:      {count_failed}/{total}")

    errors_csv_written = None
    if errors:
        errors_csv_written = output_errors
        write_errors_csv(output_errors, errors)

    stats = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account_name": config.account,
        "total": total,
        "updated": count_updated,
        "failed": count_failed,
        "simulated": count_simulated,
        "errors_csv": errors_csv_written or "",
    }
    write_report(output_report, stats, args, errors)

    return 0


if __name__ == "__main__":
    sys.exit(main())
