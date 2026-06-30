#!/usr/bin/env python3
"""
vtex_sku_service_exporter.py

Consulta servicios SKU en VTEX por skuServiceId y exporta las respuestas a JSON:

    GET /api/catalog/pvt/skuservice/{skuServiceId}

Por defecto consulta IDs 1 a 50. El rango puede ajustarse con --start-id y --end-id.

Credenciales requeridas en .env de la raiz del proyecto o variables de entorno:
- X-VTEX-API-AppKey
- X-VTEX-API-AppToken
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

DEFAULT_START_ID = 1
DEFAULT_END_ID = 50
DEFAULT_DELAY = 0.6
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
BACKOFF_FACTOR = 2
ENDPOINT_TEMPLATE = "/api/catalog/pvt/skuservice/{skuServiceId}"


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


def build_result(
    sku_service_id: int,
    status_code: int,
    found: bool,
    response: Optional[Dict[str, Any]],
    error: str,
) -> Dict[str, Any]:
    return {
        "skuServiceId": sku_service_id,
        "statusCode": status_code,
        "found": found,
        "response": response,
        "error": error,
    }


def summarize_response_error(response: requests.Response) -> str:
    text = response.text.strip()
    if not text:
        return f"HTTP {response.status_code} sin cuerpo de respuesta"
    return text[:500]


def fetch_sku_service(
    session: requests.Session,
    config: VtexConfig,
    sku_service_id: int,
    timeout: int,
    retries: int,
) -> Dict[str, Any]:
    url = f"{config.base_url}{ENDPOINT_TEMPLATE.format(skuServiceId=sku_service_id)}"

    for attempt in range(retries + 1):
        try:
            response = session.get(url, headers=build_headers(config), timeout=timeout)

            if response.status_code in (429,) and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(
                    f"Rate limit para skuServiceId={sku_service_id}. "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500 and attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(
                    f"Error {response.status_code} para skuServiceId={sku_service_id}. "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    return build_result(
                        sku_service_id=sku_service_id,
                        status_code=response.status_code,
                        found=False,
                        response=None,
                        error="Respuesta no es JSON valido",
                    )

                if not isinstance(payload, dict):
                    return build_result(
                        sku_service_id=sku_service_id,
                        status_code=response.status_code,
                        found=False,
                        response=None,
                        error="Respuesta JSON no es un objeto",
                    )

                return build_result(
                    sku_service_id=sku_service_id,
                    status_code=response.status_code,
                    found=True,
                    response=payload,
                    error="",
                )

            if response.status_code == 404:
                return build_result(
                    sku_service_id=sku_service_id,
                    status_code=response.status_code,
                    found=False,
                    response=None,
                    error=summarize_response_error(response),
                )

            return build_result(
                sku_service_id=sku_service_id,
                status_code=response.status_code,
                found=False,
                response=None,
                error=summarize_response_error(response),
            )

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(
                    f"Timeout para skuServiceId={sku_service_id}. "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue
            return build_result(
                sku_service_id=sku_service_id,
                status_code=0,
                found=False,
                response=None,
                error=f"Timeout despues de {timeout}s",
            )
        except requests.exceptions.RequestException as exc:
            if attempt < retries:
                wait_seconds = BACKOFF_FACTOR ** (attempt + 1)
                print(
                    f"Error de red para skuServiceId={sku_service_id}. "
                    f"Reintentando en {wait_seconds}s..."
                )
                time.sleep(wait_seconds)
                continue
            return build_result(
                sku_service_id=sku_service_id,
                status_code=0,
                found=False,
                response=None,
                error=str(exc),
            )

    return build_result(
        sku_service_id=sku_service_id,
        status_code=0,
        found=False,
        response=None,
        error="Error desconocido",
    )


def validate_range(start_id: int, end_id: int) -> None:
    if start_id < 1:
        raise ValueError("--start-id debe ser mayor o igual a 1")
    if end_id < start_id:
        raise ValueError("--end-id debe ser mayor o igual a --start-id")


def build_payload(
    config: VtexConfig,
    start_id: int,
    end_id: int,
    results: List[Dict[str, Any]],
    total_requested: int,
    found: int,
    not_found: int,
    failed: int,
) -> Dict[str, Any]:
    return {
        "metadata": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "accountName": config.account,
            "environment": config.environment,
            "endpointTemplate": ENDPOINT_TEMPLATE,
            "startId": start_id,
            "endId": end_id,
        },
        "summary": {
            "totalRequested": total_requested,
            "found": found,
            "notFound": not_found,
            "failed": failed,
        },
        "results": results,
    }


def write_output(output_path: Path, payload: Dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def export_sku_services(
    output_json: Path,
    start_id: int,
    end_id: int,
    delay: float,
    timeout: int,
    retries: int,
    include_not_found: bool,
) -> None:
    validate_range(start_id, end_id)

    config = VtexConfig.load()
    session = requests.Session()
    total_requested = end_id - start_id + 1
    results: List[Dict[str, Any]] = []
    found = 0
    not_found = 0
    failed = 0

    for index, sku_service_id in enumerate(range(start_id, end_id + 1), start=1):
        result = fetch_sku_service(
            session=session,
            config=config,
            sku_service_id=sku_service_id,
            timeout=timeout,
            retries=retries,
        )

        status_code = result["statusCode"]
        is_found = result["found"]
        if is_found:
            found += 1
            results.append(result)
        elif status_code == 404:
            not_found += 1
            if include_not_found:
                results.append(result)
        else:
            failed += 1
            results.append(result)

        print(
            f"[{index}/{total_requested}] skuServiceId={sku_service_id} "
            f"status={status_code or 'N/A'} found={'true' if is_found else 'false'}"
        )

        if delay > 0 and index < total_requested:
            time.sleep(delay)

    payload = build_payload(
        config=config,
        start_id=start_id,
        end_id=end_id,
        results=results,
        total_requested=total_requested,
        found=found,
        not_found=not_found,
        failed=failed,
    )
    write_output(output_json, payload)

    print("\nResumen")
    print(f"- IDs consultados: {total_requested}")
    print(f"- Encontrados: {found}")
    print(f"- No encontrados: {not_found}")
    print(f"- Fallidos: {failed}")
    print(f"- Resultados escritos: {len(results)}")
    print(f"- Salida: {output_json}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta servicios SKU en VTEX por skuServiceId y exporta las respuestas a JSON."
    )
    parser.add_argument("output_json", help="Archivo JSON de salida")
    parser.add_argument(
        "--start-id",
        type=int,
        default=DEFAULT_START_ID,
        help=f"Primer skuServiceId a consultar (default: {DEFAULT_START_ID}).",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=DEFAULT_END_ID,
        help=f"Ultimo skuServiceId a consultar, inclusive (default: {DEFAULT_END_ID}).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Pausa entre consultas en segundos (default: {DEFAULT_DELAY}).",
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
    parser.add_argument(
        "--include-not-found",
        action="store_true",
        help="Incluye respuestas 404 en results; el conteo summary.notFound siempre se conserva.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        export_sku_services(
            output_json=Path(args.output_json),
            start_id=args.start_id,
            end_id=args.end_id,
            delay=args.delay,
            timeout=args.timeout,
            retries=args.retries,
            include_not_found=args.include_not_found,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
