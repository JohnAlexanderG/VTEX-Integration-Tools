#!/usr/bin/env python3
"""
vtex_masterdata_document_deleter.py

Ejecuta DELETE real contra la API de VTEX Master Data para eliminar documentos,
a partir de un CSV con columna `id` — el formato que genera
`69_vtex_masterdata_search_exporter/vtex_masterdata_search_exporter.py`.

    DELETE https://{accountName}.{environment}.com.br/api/dataentities/{dataEntityName}/documents/{id}

Documentación: https://developers.vtex.com/docs/api-reference/master-data-api-v2#delete-/api/dataentities/-dataEntityName-/documents/-id-

Flujo recomendado (la eliminación es IRREVERSIBLE):
    1. Exportar la entidad completa con 69 usando --fields _all (sirve como respaldo).
    2. Ejecutar este script con --dry-run sobre ese CSV.
    3. Ejecutar en real pasando --confirm-account con el nombre exacto de la cuenta.

Funcionalidad:
- Lee los ids del CSV (columna --id-col, default `id`), descarta vacíos y
  deduplica, y ejecuta DELETE por cada id contra la entidad --data-entity-name.
- En modo real exige --confirm-account igual a VTEX_ACCOUNT_NAME, para evitar
  borrar por error en una cuenta distinta a la esperada.
- --env-file permite usar un .env alternativo (ej. credenciales de otra cuenta)
  sin tocar el .env de la raíz.
- HTTP 404 se considera "ya eliminado" (re-ejecuciones idempotentes).
- Reintenta con backoff exponencial en HTTP 429, 5xx, timeout o error de red.
- Genera log incremental, CSV de errores (si hay) y reporte Markdown.

Credenciales requeridas en .env de la raíz del proyecto (o --env-file):
- X-VTEX-API-AppKey
- X-VTEX-API-AppToken
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)

Ejecución:
    python3 vtex_masterdata_document_deleter.py CL_search.csv -e CL --dry-run
    python3 vtex_masterdata_document_deleter.py CL_search.csv -e CL --confirm-account micuenta
    python3 vtex_masterdata_document_deleter.py export.csv -e XX --env-file .env.otra --confirm-account otra
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

DEFAULT_DELAY = 0.2
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
    source: str

    @property
    def base_url(self) -> str:
        return f"https://{self.account}.{self.environment}.com.br"

    @staticmethod
    def load(env_file: Optional[str] = None) -> "VtexConfig":
        # Si VTEX_ACCOUNT_NAME ya viene en el entorno (ej. la WebOps inyecta las
        # credenciales del tenant), load_dotenv sin override no la pisa.
        preset = bool(os.getenv("VTEX_ACCOUNT_NAME"))
        if env_file:
            if not os.path.exists(env_file):
                raise RuntimeError(f"No se encontró el archivo de entorno '{env_file}'")
            load_dotenv(env_file, override=True)
            source = f"archivo --env-file ({env_file})"
        elif preset:
            source = "variables de entorno del proceso (credenciales del tenant en la WebOps)"
        else:
            source = ".env de la raíz del proyecto"
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
            source=source,
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


def delete_document(
    session: requests.Session,
    config: VtexConfig,
    data_entity_name: str,
    doc_id: str,
    timeout: int,
    retries: int,
) -> Tuple[str, Optional[str]]:
    """
    Ejecuta el DELETE para un documento.
    Retorna (estado, error_o_none) con estado en: eliminado, no_existe, error.
    """
    url = f"{config.base_url}{ENDPOINT_TEMPLATE.format(dataEntityName=data_entity_name, id=doc_id)}"

    for attempt in range(retries + 1):
        try:
            response = session.delete(url, headers=build_headers(config), timeout=timeout)

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

            if response.status_code == 404:
                return "no_existe", None

            if response.status_code >= 400:
                return "error", summarize_response_error(response)

            return "eliminado", None

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Timeout para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            return "error", f"Timeout después de {timeout}s"
        except requests.exceptions.RequestException as exc:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"   ⚠️  Error de red para {doc_id}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            return "error", f"Error de red: {exc}"

    return "error", f"No se pudo eliminar tras {retries} reintentos"


def read_ids(csv_path: str, id_col: str, encoding: str) -> Tuple[List[str], int, int]:
    """Retorna (ids_unicos_en_orden, filas_totales, filas_sin_id)."""
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo '{csv_path}'")
        sys.exit(1)

    with open(csv_path, "r", newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if id_col not in fieldnames:
            print(f"❌ Error: Columna '{id_col}' no encontrada en el CSV.")
            print(f"   Columnas disponibles: {', '.join(fieldnames)}")
            sys.exit(1)

        ids: List[str] = []
        seen = set()
        total_rows = 0
        empty = 0
        for row in reader:
            total_rows += 1
            doc_id = (row.get(id_col) or "").strip()
            if not doc_id:
                empty += 1
                continue
            if doc_id in seen:
                continue
            seen.add(doc_id)
            ids.append(doc_id)
    return ids, total_rows, empty


def open_progress_log(path: str) -> Tuple[Any, "csv._writer"]:
    """
    Abre el log incremental de progreso y escribe el encabezado. Cada fila se
    escribe (y se fuerza a disco con flush+fsync) apenas se resuelve, para que
    una interrupción abrupta del proceso no pierda el rastro de qué se procesó.
    """
    f = open(path, "w", newline="", encoding="utf-8")
    writer = csv.writer(f)
    writer.writerow(["n", "id", "estado", "motivo"])
    f.flush()
    os.fsync(f.fileno())
    return f, writer


def log_progress(f: Any, writer: "csv._writer", n: int, doc_id: str, estado: str, motivo: str = "") -> None:
    writer.writerow([n, doc_id, estado, motivo])
    f.flush()
    os.fsync(f.fileno())


def write_errors_csv(path: str, errors: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "motivo"])
        writer.writeheader()
        writer.writerows(errors)
    print(f"💾 CSV de errores exportado: '{path}' ({len(errors)} filas)")


def write_report(path: str, stats: Dict[str, Any], args: argparse.Namespace, errors: List[Dict[str, str]]) -> None:
    total = stats["total"]

    def pct(n: int) -> str:
        return f"{(n / total * 100) if total else 0:.1f}%"

    is_dry_run = args.dry_run
    lines = [
        "# Reporte de Eliminación — VTEX Master Data",
        "",
        f"**Generado:** {stats['generated_at']}  ",
        f"**Cuenta VTEX:** {stats['account_name']}  ",
        f"**Data Entity:** {args.data_entity_name}  ",
        f"**Modo:** {'DRY-RUN' if is_dry_run else 'REAL'}",
        "",
        "---",
        "",
        "## 📊 Resumen Ejecutivo",
        "",
        f"- Filas en el CSV: {stats['total_rows']}",
        f"- Filas sin id (omitidas): {stats['empty']}",
        f"- Ids únicos a procesar: {total}",
        "",
        "| Métrica | Cantidad | Porcentaje |",
        "|---------|----------|------------|",
    ]
    if is_dry_run:
        lines.append(f"| 🔍 Simulados (dry-run) | {stats['simulated']} | {pct(stats['simulated'])} |")
    else:
        lines += [
            f"| ✅ Eliminados | {stats['deleted']} | {pct(stats['deleted'])} |",
            f"| ➖ No existían (404) | {stats['not_found']} | {pct(stats['not_found'])} |",
            f"| ⚠️ Errores | {stats['failed']} | {pct(stats['failed'])} |",
        ]

    lines += [
        "",
        "## ⚙️ Configuración",
        "",
        f"- **Input:** `{args.input_csv}`",
        f"- **Data Entity:** `{args.data_entity_name}`",
        f"- **Columna id:** `{args.id_col}`",
        f"- **Delay entre requests:** {args.delay}s",
        f"- **Timeout:** {args.timeout}s",
        f"- **Retries:** {args.retries}",
        "",
    ]

    if errors:
        lines += ["## ⚠️ Errores", "", "| id | motivo |", "|----|--------|"]
        for err in errors[:50]:
            lines.append(f"| {err['id']} | {err['motivo']} |")
        if len(errors) > 50:
            lines.append(f"| *(y {len(errors) - 50} más...)* | |")
        if stats.get("errors_csv"):
            lines += ["", f"CSV de errores exportado: `{stats['errors_csv']}`"]
        lines.append("")

    lines += ["---", "", "*Reporte generado automáticamente por `vtex_masterdata_document_deleter.py`*"]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📋 Reporte exportado: '{path}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta DELETE real contra VTEX Master Data para eliminar documentos "
            "a partir de un CSV con columna id (ej. export de 69_vtex_masterdata_search_exporter)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python3 vtex_masterdata_document_deleter.py CL_search.csv -e CL --dry-run
  python3 vtex_masterdata_document_deleter.py CL_search.csv -e CL --confirm-account micuenta
  python3 vtex_masterdata_document_deleter.py export.csv -e XX --env-file .env.otra --confirm-account otra
""",
    )
    parser.add_argument("input_csv", help="CSV con columna id (ej. salida de 69_vtex_masterdata_search_exporter)")
    parser.add_argument(
        "-e", "--data-entity-name", required=True,
        help="Nombre (sigla) de la entidad de Master Data (ej. CL). Obligatorio para evitar borrar en la entidad equivocada.",
    )
    parser.add_argument("--id-col", default="id", help="Columna con el id del documento (default: id)")
    parser.add_argument("--env-file", help="Archivo .env alternativo con credenciales (default: .env de la raíz)")
    parser.add_argument(
        "--confirm-account",
        help="Obligatorio en modo real: debe coincidir exactamente con VTEX_ACCOUNT_NAME.",
    )
    parser.add_argument("-o", "--output", help="CSV de errores (default: {data_entity_name}_delete_errors_{timestamp}.csv)")
    parser.add_argument("-r", "--report", help="Reporte Markdown (default: {data_entity_name}_delete_report_{timestamp}.md)")
    parser.add_argument("--log", help="Log incremental CSV (default: {data_entity_name}_delete_log_{timestamp}.csv)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout de requests en segundos (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Reintentos para 429/5xx/timeout/error de red (default: {DEFAULT_RETRIES})")
    parser.add_argument("--encoding", default="utf-8", help="Encoding del CSV de entrada (default: utf-8)")
    parser.add_argument("--dry-run", action="store_true", help="Simula las operaciones sin hacer DELETE reales")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_errors = args.output or f"{args.data_entity_name}_delete_errors_{timestamp}.csv"
    output_report = args.report or f"{args.data_entity_name}_delete_report_{timestamp}.md"
    output_log = args.log or f"{args.data_entity_name}_delete_log_{timestamp}.csv"

    try:
        config = VtexConfig.load(args.env_file)
    except RuntimeError as exc:
        print(f"❌ Error: {exc}")
        return 1

    if not args.dry_run and args.confirm_account != config.account:
        print("❌ Error: la eliminación es IRREVERSIBLE.")
        print(f"   Para ejecutar en real pasa --confirm-account {config.account}")
        print("   (o usa --dry-run para simular).")
        return 1

    ids, total_rows, empty = read_ids(args.input_csv, args.id_col, args.encoding)
    total = len(ids)

    print("\n" + "=" * 64)
    print(f"🗑️  ELIMINACIÓN EN VTEX MASTER DATA — modo {'DRY-RUN (simulación)' if args.dry_run else 'REAL (IRREVERSIBLE)'}")
    print(f"   Cuenta VTEX destino: {config.account}")
    print(f"   Ambiente:            {config.environment}")
    print(f"   URL base:            {config.base_url}")
    print(f"   Data Entity:         {args.data_entity_name}")
    print(f"   Credenciales desde:  {config.source}")
    print("=" * 64)
    print(f"   Filas en CSV: {total_rows} | sin id: {empty} | ids únicos: {total}")
    print(f"   Delay: {args.delay}s | Timeout: {args.timeout}s | Retries: {args.retries}")
    print(f"   Reporte: {output_report}")
    print(f"   Log incremental: {output_log}\n")

    session = requests.Session()
    errors: List[Dict[str, str]] = []
    counts = {"eliminado": 0, "no_existe": 0, "error": 0, "simulado": 0}

    log_file, log_writer = open_progress_log(output_log)
    try:
        for i, doc_id in enumerate(ids, start=1):
            if args.dry_run:
                counts["simulado"] += 1
                print(f"[{i}/{total}] {doc_id} → 🔍 dry-run")
                log_progress(log_file, log_writer, i, doc_id, "simulado")
                continue

            estado, error = delete_document(
                session=session,
                config=config,
                data_entity_name=args.data_entity_name,
                doc_id=doc_id,
                timeout=args.timeout,
                retries=args.retries,
            )
            counts[estado] += 1
            if estado == "eliminado":
                print(f"[{i}/{total}] {doc_id} → ✅ eliminado")
            elif estado == "no_existe":
                print(f"[{i}/{total}] {doc_id} → ➖ no existe (404)")
            else:
                errors.append({"id": doc_id, "motivo": error or ""})
                print(f"[{i}/{total}] {doc_id} → ❌ error: {error}")
            log_progress(log_file, log_writer, i, doc_id, estado, error or "")

            if i < total:
                time.sleep(args.delay)
    finally:
        log_file.close()

    print(f"\n✅ Proceso completado.")
    if args.dry_run:
        print(f"   Simulados:   {counts['simulado']}/{total}")
    else:
        print(f"   Eliminados:  {counts['eliminado']}/{total}")
        print(f"   No existían: {counts['no_existe']}/{total}")
        print(f"   Errores:     {counts['error']}/{total}")

    errors_csv_written = ""
    if errors:
        errors_csv_written = output_errors
        write_errors_csv(output_errors, errors)

    stats = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account_name": config.account,
        "total_rows": total_rows,
        "empty": empty,
        "total": total,
        "deleted": counts["eliminado"],
        "not_found": counts["no_existe"],
        "failed": counts["error"],
        "simulated": counts["simulado"],
        "errors_csv": errors_csv_written,
    }
    write_report(output_report, stats, args, errors)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
