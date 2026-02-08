#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""update_product_description.py

Actualiza la descripción (Description) de productos en VTEX haciendo match:
- JSON: toma productId desde response.Id y RefId desde ref_id (o response.RefId)
- CSV: si CSV.SKU == JSON.RefId, toma CSV."Descripción" y la envía como "Description"

API:
PUT https://{accountName}.{environment}.com.br/api/catalog/pvt/product/{productId}

Credenciales:
Lee .env en la raíz del proyecto (mismo patrón que tu script de referencia):
- X-VTEX-API-AppKey
- X-VTEX-API-AppToken
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)

Uso:
  python3 update_product_description.py --json productos.json --csv productos.csv --dry-run
  python3 update_product_description.py --json productos.json --csv productos.csv

Opciones:
  --sku-col      Nombre exacto de columna SKU en el CSV (default: SKU)
  --desc-col     Nombre exacto de columna Descripción en el CSV (default: Descripción)
  --limit        Procesa solo N productos (0 = sin límite)
"""

import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple

import requests
from dotenv import load_dotenv


# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Configuración de la API VTEX (MISMA FORMA QUE EL SCRIPT ADJUNTO)
VTEX_APP_KEY = os.getenv('X-VTEX-API-AppKey')
VTEX_APP_TOKEN = os.getenv('X-VTEX-API-AppToken')
VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT_NAME')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')


def die(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sniff_csv_dialect(path: str) -> csv.Dialect:
    # utf-8-sig para manejar BOM
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        except csv.Error:
            # fallback común: coma
            class _D(csv.Dialect):
                delimiter = ","
                quotechar = '"'
                doublequote = True
                skipinitialspace = True
                lineterminator = "\n"
                quoting = csv.QUOTE_MINIMAL

            return _D()


def load_csv_map(path: str, sku_col: str, desc_col: str) -> Dict[str, str]:
    """Devuelve dict: SKU -> Descripción (solo filas con Descripción no vacía)."""
    dialect = sniff_csv_dialect(path)

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            die("El CSV no tiene encabezados.")

        # Normaliza búsqueda de columnas (por si vienen con espacios)
        field_map = {h.strip(): h for h in reader.fieldnames}
        if sku_col not in field_map:
            die(f"No encontré la columna SKU '{sku_col}' en el CSV. Columnas: {list(field_map.keys())}")
        if desc_col not in field_map:
            die(f"No encontré la columna Descripción '{desc_col}' en el CSV. Columnas: {list(field_map.keys())}")

        sku_header = field_map[sku_col]
        desc_header = field_map[desc_col]

        out: Dict[str, str] = {}
        for row in reader:
            sku = (row.get(sku_header) or "").strip()
            desc = (row.get(desc_header) or "").strip()
            if not sku:
                continue
            if desc:
                out[sku] = desc

        return out


def iter_products_from_json(data: Any) -> List[Dict[str, Any]]:
    """Espera que el JSON sea una lista de objetos, o un dict que contenga una lista."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for _, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and ("response" in v[0] or "ref_id" in v[0]):
                return v
    die("No pude interpretar la estructura del JSON: esperaba una lista de productos.")
    return []


def build_put_payload(product_resp: Dict[str, Any], new_description: str) -> Dict[str, Any]:
    """Payload mínimo razonable para PUT /api/catalog/pvt/product/{productId}."""
    return {
        "Name": product_resp.get("Name"),
        "CategoryId": product_resp.get("CategoryId"),
        "BrandId": product_resp.get("BrandId"),
        "LinkId": product_resp.get("LinkId"),
        "Description": new_description,
    }


def vtex_put_product(
    session: requests.Session,
    base_url: str,
    product_id: int,
    payload: Dict[str, Any],
    max_retries: int = 3,
    sleep_base: float = 1.0,
) -> Tuple[bool, int, str]:
    """Retorna (ok, status_code, text). Reintenta en 429/5xx."""
    url = f"{base_url}/api/catalog/pvt/product/{product_id}"

    for attempt in range(1, max_retries + 1):
        try:
            r = session.put(url, json=payload, timeout=60)
            status = r.status_code
            text = (r.text or "")[:1000]

            if status in (200, 201, 204):
                return True, status, text

            if status == 429 or 500 <= status <= 599:
                wait = sleep_base * attempt
                retry_after = r.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = max(wait, float(retry_after))
                    except ValueError:
                        pass
                print(
                    f"[WARN] PUT productId={product_id} status={status}. "
                    f"Reintentando en {wait:.1f}s (intento {attempt}/{max_retries})"
                )
                time.sleep(wait)
                continue

            return False, status, text

        except requests.RequestException as e:
            wait = sleep_base * attempt
            print(
                f"[WARN] Error de red PUT productId={product_id}: {e}. "
                f"Reintentando en {wait:.1f}s (intento {attempt}/{max_retries})"
            )
            time.sleep(wait)

    return False, 0, "Max retries exceeded"


def validate_env() -> None:
    missing = []
    if not VTEX_APP_KEY:
        missing.append("X-VTEX-API-AppKey")
    if not VTEX_APP_TOKEN:
        missing.append("X-VTEX-API-AppToken")
    if not VTEX_ACCOUNT:
        missing.append("VTEX_ACCOUNT_NAME")

    if missing:
        die(
            "Credenciales VTEX faltantes en .env: " + ", ".join(missing)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Actualiza la descripción de productos en VTEX (match CSV.SKU == JSON.RefId)."
    )
    parser.add_argument("--json", required=True, help="Ruta al archivo JSON (lista de productos).")
    parser.add_argument("--csv", required=True, help="Ruta al archivo CSV (con columnas SKU y Descripción).")
    parser.add_argument("--sku-col", default="SKU", help="Nombre exacto de la columna SKU en el CSV.")
    parser.add_argument("--desc-col", default="Descripción", help="Nombre exacto de la columna Descripción en el CSV.")
    parser.add_argument("--dry-run", action="store_true", help="No hace PUT, solo muestra qué actualizaría.")
    parser.add_argument("--limit", type=int, default=0, help="Procesa solo N productos (0 = sin límite).")
    args = parser.parse_args()

    validate_env()

    base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"

    # Cargar insumos
    json_data = load_json(args.json)
    products = iter_products_from_json(json_data)
    csv_map = load_csv_map(args.csv, args.sku_col, args.desc_col)

    print(f"[INFO] Cuenta: {VTEX_ACCOUNT} / Env: {VTEX_ENVIRONMENT}")
    print(f"[INFO] CSV: {len(csv_map)} SKUs con descripción no vacía.")
    print(f"[INFO] JSON: {len(products)} productos en la lista.")

    # Preparar sesión VTEX
    session = requests.Session()
    session.headers.update(
        {
            "X-VTEX-API-AppKey": VTEX_APP_KEY,
            "X-VTEX-API-AppToken": VTEX_APP_TOKEN,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    updated = 0
    skipped_no_match = 0
    skipped_no_desc = 0
    errors = 0

    for idx, item in enumerate(products, start=1):
        if args.limit and idx > args.limit:
            break

        resp = item.get("response") or {}
        product_id = resp.get("Id")
        ref_id = (item.get("ref_id") or resp.get("RefId") or "").strip()

        if not product_id:
            print(f"[WARN] Item #{idx} sin response.Id, se omite. ref_id={ref_id}")
            errors += 1
            continue

        if not ref_id:
            print(f"[WARN] Item #{idx} sin ref_id/response.RefId, se omite. productId={product_id}")
            errors += 1
            continue

        new_desc = csv_map.get(ref_id)
        if new_desc is None:
            skipped_no_match += 1
            continue

        if not new_desc.strip():
            skipped_no_desc += 1
            continue

        payload = build_put_payload(resp, new_desc)

        # Validación mínima: campos requeridos
        missing_fields = [k for k in ("Name", "CategoryId", "BrandId") if payload.get(k) in (None, "", [])]
        if missing_fields:
            print(
                f"[WARN] productId={product_id} ref_id={ref_id} faltan campos {missing_fields} en response, se omite."
            )
            errors += 1
            continue

        if args.dry_run:
            print(f"[DRY-RUN] productId={product_id} ref_id={ref_id} -> Description = {new_desc[:80]!r}")
            updated += 1
            continue

        ok, status, text = vtex_put_product(session, base_url, int(product_id), payload)
        if ok:
            print(f"[OK] productId={product_id} ref_id={ref_id} status={status}")
            updated += 1
        else:
            print(f"[FAIL] productId={product_id} ref_id={ref_id} status={status} body={text}")
            errors += 1

        # Pequeño sleep para ser amable con rate limits
        time.sleep(0.05)

    print("\n[SUMMARY]")
    print(f"  Actualizados: {updated}")
    print(f"  Sin match SKU==RefId: {skipped_no_match}")
    print(f"  Match pero descripción vacía: {skipped_no_desc}")
    print(f"  Errores: {errors}")


if __name__ == "__main__":
    main()
