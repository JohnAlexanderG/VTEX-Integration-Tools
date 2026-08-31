#!/usr/bin/env python3
"""
vtex_masterdata_search_exporter.py

Consulta la API de VTEX Master Data (dataentities/scroll) para una entidad dada y exporta
todos los registros a un .csv, paginando automaticamente con token de continuacion:

    GET /api/dataentities/{dataEntityName}/scroll?_fields=...&_size=...   (primer request)
    GET /api/dataentities/{dataEntityName}/scroll?_token=...              (requests siguientes)
    Header de response: X-VTEX-MD-TOKEN (token para pedir la siguiente pagina)

Se usa /scroll en vez de /search porque VTEX limita /search a un maximo de 10.000 documentos;
para colecciones mas grandes (o para traer la coleccion completa) VTEX exige /scroll. El script
sigue pidiendo paginas hasta que la respuesta viene vacia, acumula los resultados y genera:
- Un .csv con los campos solicitados via --fields (o la lista por defecto).
- Un reporte .md con el resumen de la ejecucion.

Nota: segun la documentacion de VTEX, _schema es requerido en /scroll cuando se usa _fields o
_where. Si la cuenta lo exige, pasar --schema con el nombre del schema correspondiente.

Credenciales requeridas en .env de la raiz del proyecto o variables de entorno:
- X-VTEX-API-AppKey
- X-VTEX-API-AppToken
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)

Ejemplos:
    python3 vtex_masterdata_search_exporter.py --data-entity-name CL
    python3 vtex_masterdata_search_exporter.py -e CL -o clientes.csv --page-size 1000 --delay 0.5
    python3 vtex_masterdata_search_exporter.py -e CL --fields id,email,firstName,lastName
    python3 vtex_masterdata_search_exporter.py -e CL --fields _all --schema clientes-v2
    python3 vtex_masterdata_search_exporter.py -e CL --schema clientes-v2
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import os
import requests
from dotenv import load_dotenv

DEFAULT_PAGE_SIZE = 1000
DEFAULT_DELAY = 0.5
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
BACKOFF_FACTOR = 2
ENDPOINT_TEMPLATE = "/api/dataentities/{dataEntityName}/scroll"
TOKEN_HEADER = "X-VTEX-MD-TOKEN"

DEFAULT_FIELDS = [
    "id",
    "accountId",
    "accountName",
    "dataEntityId",
    "isCorporate",
    "tradeName",
    "homePhone",
    "phone",
    "email",
    "userId",
    "firstName",
    "lastName",
    "document",
    "isNewsletterOptIn",
    "localeDefault",
    "birthDate",
    "businessPhone",
    "corporateDocument",
    "corporateName",
    "documentType",
    "gender",
    "birthDateMonth",
    "createdBy",
    "createdIn",
    "updatedBy",
    "updatedIn",
]


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


@dataclass
class PageAttempt:
    page: int
    note: str


@dataclass
class SearchStats:
    data_entity_name: str
    fields: List[str]
    page_size: int
    pages_fetched: int = 0
    records_exported: int = 0
    token_used: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    issues: List[PageAttempt] = field(default_factory=list)


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
    return text[:500]


def fetch_scroll_page(
    session: requests.Session,
    config: VtexConfig,
    data_entity_name: str,
    params: Dict[str, str],
    page_label: str,
    timeout: int,
    retries: int,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    url = f"{config.base_url}{ENDPOINT_TEMPLATE.format(dataEntityName=data_entity_name)}"

    for attempt in range(retries + 1):
        try:
            response = session.get(
                url,
                headers=build_headers(config),
                params=params,
                timeout=timeout,
            )

            if response.status_code in (429,) and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"Rate limit para {page_label}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500 and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"Error {response.status_code} para {page_label}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                raise RuntimeError(
                    f"HTTP {response.status_code} consultando {page_label}: "
                    f"{summarize_response_error(response)}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise RuntimeError(f"Respuesta no es JSON valido para {page_label}") from exc

            if not isinstance(payload, list):
                raise RuntimeError(f"Respuesta JSON no es una lista para {page_label}")

            token = response.headers.get(TOKEN_HEADER)
            return payload, token

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"Timeout para {page_label}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Timeout despues de {timeout}s para {page_label}")
        except requests.exceptions.RequestException as exc:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(f"Error de red para {page_label}. Reintentando en {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Error de red para {page_label}: {exc}") from exc

    raise RuntimeError(f"No se pudo consultar {page_label} tras {retries} reintentos")


def scroll_all_pages(
    config: VtexConfig,
    data_entity_name: str,
    fields: List[str],
    page_size: int,
    schema: Optional[str],
    delay: float,
    timeout: int,
    retries: int,
) -> Tuple[List[Dict[str, Any]], SearchStats]:
    session = requests.Session()
    stats = SearchStats(data_entity_name=data_entity_name, fields=fields, page_size=page_size)
    records: List[Dict[str, Any]] = []

    token: Optional[str] = None
    page = 0
    while True:
        page += 1
        if token is None:
            params: Dict[str, str] = {"_fields": ",".join(fields), "_size": str(page_size)}
            if schema:
                params["_schema"] = schema
        else:
            params = {"_token": token}

        page_records, new_token = fetch_scroll_page(
            session=session,
            config=config,
            data_entity_name=data_entity_name,
            params=params,
            page_label=f"pagina {page}",
            timeout=timeout,
            retries=retries,
        )
        stats.pages_fetched += 1

        if new_token:
            token = new_token
            stats.token_used = True

        if not page_records:
            break

        records.extend(page_records)
        print(f"[pagina {page}] registros: {len(page_records)} (acumulado: {len(records)})")

        if token is None:
            stats.issues.append(
                PageAttempt(
                    page=page,
                    note=f"No se recibio header {TOKEN_HEADER}; no es posible continuar la paginacion",
                )
            )
            break

        if delay > 0:
            time.sleep(delay)

    stats.records_exported = len(records)
    stats.finished_at = datetime.now(timezone.utc)
    return records, stats


def write_csv(output_path: Path, records: List[Dict[str, Any]], fields: List[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(normalize_csv_record(record, fields) for record in records)


def is_all_fields_request(fields: List[str]) -> bool:
    return len(fields) == 1 and fields[0].strip().lower() == "_all"


def resolve_csv_fields(records: List[Dict[str, Any]], requested_fields: List[str]) -> List[str]:
    if not is_all_fields_request(requested_fields):
        return requested_fields

    detected_fields: List[str] = []
    seen = set()
    for record in records:
        for field_name in record.keys():
            if field_name not in seen:
                detected_fields.append(field_name)
                seen.add(field_name)

    return detected_fields or requested_fields


def normalize_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def normalize_csv_record(record: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    return {field_name: normalize_csv_value(record.get(field_name, "")) for field_name in fields}


def build_report(
    config: VtexConfig,
    stats: SearchStats,
    csv_path: Path,
    csv_fields: List[str],
    schema: Optional[str],
    delay: float,
    timeout: int,
    retries: int,
) -> str:
    duration = None
    if stats.finished_at is not None:
        duration = (stats.finished_at - stats.started_at).total_seconds()

    lines: List[str] = []
    lines.append(f"# Reporte de exportacion Master Data - {stats.data_entity_name}")
    lines.append("")
    lines.append(f"- Cuenta VTEX: `{config.account}`")
    lines.append(f"- Ambiente: `{config.environment}`")
    lines.append(f"- Generado: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## 📊 Resumen")
    lines.append("")
    lines.append("- Metodo de paginacion: `/scroll` (VTEX Master Data)")
    lines.append(
        "- `/scroll` no expone un total anticipado; el conteo final se conoce al terminar de "
        "iterar (pagina vacia)."
    )
    lines.append(f"- Registros exportados al CSV: {stats.records_exported}")
    lines.append(f"- Paginas consultadas: {stats.pages_fetched}")
    lines.append(f"- Tamano de pagina (_size): {stats.page_size}")
    lines.append(f"- Duracion: {duration:.2f}s" if duration is not None else "- Duracion: N/A")
    lines.append("")
    lines.append("## ⚙️ Configuracion")
    lines.append("")
    lines.append(f"- `--page-size`: {stats.page_size}")
    lines.append(f"- `--delay`: {delay}s")
    lines.append(f"- `--timeout`: {timeout}s")
    lines.append(f"- `--retries`: {retries}")
    lines.append(f"- `--schema`: {schema if schema else 'N/A'}")
    lines.append(f"- Campos (`_fields`): {', '.join(stats.fields)}")
    if is_all_fields_request(stats.fields):
        lines.append(f"- Columnas CSV detectadas desde `_all`: {len(csv_fields)}")
        lines.append(f"- Campos del CSV: {', '.join(csv_fields)}")
    lines.append(f"- Archivo CSV: `{csv_path}`")
    lines.append("")

    if stats.issues:
        lines.append("## ⚠️ Incidencias durante la paginacion")
        lines.append("")
        for issue in stats.issues:
            lines.append(f"- pagina {issue.page}: {issue.note}")
        lines.append("")
    else:
        lines.append("## ✅ Estado")
        lines.append("")
        lines.append("Paginacion completada sin incidencias.")
        lines.append("")

    lines.append("---")
    lines.append("*Reporte generado automaticamente por vtex_masterdata_search_exporter.py*")

    return "\n".join(lines)


def write_report(report_path: Path, content: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        f.write(content)
        f.write("\n")


def run(
    data_entity_name: str,
    fields: List[str],
    output_csv: Path,
    output_report: Path,
    page_size: int,
    schema: Optional[str],
    delay: float,
    timeout: int,
    retries: int,
) -> None:
    config = VtexConfig.load()

    records, stats = scroll_all_pages(
        config=config,
        data_entity_name=data_entity_name,
        fields=fields,
        page_size=page_size,
        schema=schema,
        delay=delay,
        timeout=timeout,
        retries=retries,
    )

    csv_fields = resolve_csv_fields(records, fields)
    write_csv(output_csv, records, csv_fields)
    report_content = build_report(
        config=config,
        stats=stats,
        csv_path=output_csv,
        csv_fields=csv_fields,
        schema=schema,
        delay=delay,
        timeout=timeout,
        retries=retries,
    )
    write_report(output_report, report_content)

    print("\nResumen")
    print(f"- Entidad: {data_entity_name}")
    print(f"- Paginas consultadas: {stats.pages_fetched}")
    print(f"- Registros exportados: {stats.records_exported}")
    print(f"- CSV: {output_csv}")
    print(f"- Reporte: {output_report}")


def parse_fields(raw: Optional[str]) -> List[str]:
    if not raw:
        return list(DEFAULT_FIELDS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Consulta VTEX Master Data (dataentities/scroll) con autopaginacion via token de "
            "continuacion y exporta los resultados a CSV + reporte Markdown."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python3 vtex_masterdata_search_exporter.py --data-entity-name CL
  python3 vtex_masterdata_search_exporter.py -e CL -o clientes.csv --page-size 1000
  python3 vtex_masterdata_search_exporter.py -e CL --fields id,email,firstName,lastName
  python3 vtex_masterdata_search_exporter.py -e CL --fields _all --schema clientes-v2
  python3 vtex_masterdata_search_exporter.py -e CL --schema clientes-v2
""",
    )
    parser.add_argument(
        "-e",
        "--data-entity-name",
        required=True,
        help="Nombre de la entidad de Master Data a consultar (ej. CL).",
    )
    parser.add_argument("-o", "--output", help="Archivo CSV de salida.")
    parser.add_argument("-r", "--report", help="Archivo de reporte Markdown de salida.")
    parser.add_argument(
        "--fields",
        help=(
            "Lista de campos separada por comas para _fields. "
            "Usa _all para traer todos los campos y detectar columnas del CSV automaticamente. "
            "Por defecto usa el set predefinido de campos de cliente."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Cantidad de registros por pagina, _size (default: {DEFAULT_PAGE_SIZE}, maximo VTEX).",
    )
    parser.add_argument(
        "--schema",
        help=(
            "Nombre del schema (_schema) de la entidad. Algunas cuentas de VTEX lo exigen en "
            "/scroll cuando se usa _fields; dejar sin especificar si la cuenta no lo requiere."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Pausa entre paginas en segundos (default: {DEFAULT_DELAY}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout por request en segundos (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Reintentos para 429, 5xx, timeout o error de red (default: {DEFAULT_RETRIES}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.page_size < 1:
        print("Error: --page-size debe ser mayor o igual a 1", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = Path(args.output) if args.output else Path(f"{args.data_entity_name}_search_{timestamp}.csv")
    output_report = (
        Path(args.report) if args.report else Path(f"{args.data_entity_name}_search_report_{timestamp}.md")
    )

    try:
        run(
            data_entity_name=args.data_entity_name,
            fields=parse_fields(args.fields),
            output_csv=output_csv,
            output_report=output_report,
            page_size=args.page_size,
            schema=args.schema,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
