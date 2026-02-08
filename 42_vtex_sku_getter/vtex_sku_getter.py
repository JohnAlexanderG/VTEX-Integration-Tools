#!/usr/bin/env python3
"""
vtex_sku_getter.py

Script para consultar SKUs en VTEX usando la API privada del catalogo.
Lee un CSV con columna CODIGO SKU (generado por 41_generate_sku_range),
consulta cada SKU por RefId contra GET /api/catalog/pvt/stockkeepingunit?RefId={refId},
descarta los 404 y exporta un JSON con las respuestas de los demas status codes.

Control de Rate Limiting:
- Pausa de 1 segundo entre requests
- Backoff exponencial en caso de rate limiting (429)
- Retry automatico hasta 3 intentos por SKU
- Timeout de 30 segundos por request

Ejecucion:
    python3 vtex_sku_getter.py input.csv output.json
    python3 vtex_sku_getter.py input.csv output.json --delay 2 --timeout 45

Archivos requeridos:
- .env en la raiz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken,
  VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
"""

import json
import csv
import requests
import argparse
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raiz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Configuracion de la API VTEX
VTEX_APP_KEY = os.getenv('X-VTEX-API-AppKey')
VTEX_APP_TOKEN = os.getenv('X-VTEX-API-AppToken')
VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT_NAME')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

# Configuracion de rate limiting
DEFAULT_DELAY = 1.0
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_FACTOR = 2


def validate_credentials():
    """Valida que todas las credenciales VTEX esten configuradas."""
    missing = []
    if not VTEX_APP_KEY:
        missing.append('X-VTEX-API-AppKey')
    if not VTEX_APP_TOKEN:
        missing.append('X-VTEX-API-AppToken')
    if not VTEX_ACCOUNT:
        missing.append('VTEX_ACCOUNT_NAME')
    if missing:
        print(f"❌ Credenciales VTEX faltantes en .env: {', '.join(missing)}")
        sys.exit(1)
    print(f"✅ Credenciales VTEX configuradas para cuenta: {VTEX_ACCOUNT}")


def read_sku_ids(csv_path):
    """Lee SKU IDs desde CSV con columna CODIGO SKU."""
    sku_ids = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if 'CODIGO SKU' not in (reader.fieldnames or []):
            print("❌ Error: El CSV no contiene la columna 'CODIGO SKU'")
            sys.exit(1)
        for row in reader:
            val = row['CODIGO SKU'].strip()
            if val:
                sku_ids.append(val)
    return sku_ids


def fetch_sku(session, base_url, sku_id, delay, timeout, is_first):
    """Consulta un SKU en VTEX con retry y backoff exponencial.

    Returns:
        dict or None: Resultado con sku_id, status_code, response y timestamp.
                      None si el SKU no fue encontrado (404).
    """
    endpoint = f"{base_url}/api/catalog/pvt/stockkeepingunit"

    for attempt in range(MAX_RETRIES + 1):
        try:
            if not is_first or attempt > 0:
                wait = delay if attempt == 0 else delay * (BACKOFF_FACTOR ** attempt)
                time.sleep(wait)

            response = session.get(endpoint, params={'RefId': sku_id}, timeout=timeout)

            if response.status_code == 404:
                return None

            if response.status_code == 429:
                if attempt < MAX_RETRIES:
                    wait_time = delay * (BACKOFF_FACTOR ** (attempt + 1))
                    print(f"⚠️  Rate limit alcanzado para SKU {sku_id}. Esperando {wait_time}s (intento {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ SKU {sku_id} - Rate limit excedido tras {MAX_RETRIES} reintentos")
                    return {
                        'sku_id': sku_id,
                        'status_code': 429,
                        'response': response.text,
                        'timestamp': datetime.now().isoformat()
                    }

            try:
                body = response.json()
            except Exception:
                body = response.text

            return {
                'sku_id': sku_id,
                'status_code': response.status_code,
                'response': body,
                'timestamp': datetime.now().isoformat()
            }

        except requests.exceptions.Timeout:
            print(f"❌ SKU {sku_id} - Timeout ({timeout}s)")
            return {
                'sku_id': sku_id,
                'status_code': None,
                'response': f'Request timeout ({timeout}s)',
                'timestamp': datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            print(f"❌ SKU {sku_id} - Request error: {e}")
            return {
                'sku_id': sku_id,
                'status_code': None,
                'response': f'Request error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"❌ SKU {sku_id} - Error inesperado: {e}")
            return {
                'sku_id': sku_id,
                'status_code': None,
                'response': f'Unexpected error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Consulta SKUs en VTEX y exporta las respuestas (descarta 404s)"
    )
    parser.add_argument("input_csv", help="CSV con columna CODIGO SKU")
    parser.add_argument("output_json", help="Archivo JSON de salida con respuestas")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Delay en segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Timeout en segundos por request (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    print("=" * 70)
    print("  🔍 VTEX SKU Getter")
    print("=" * 70)

    validate_credentials()

    base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"
    print(f"✅ Endpoint base: {base_url}/api/catalog/pvt/stockkeepingunit?RefId=")

    # Leer SKU IDs del CSV
    print(f"\n📂 Leyendo SKU IDs desde: {args.input_csv}")
    sku_ids = read_sku_ids(args.input_csv)
    total = len(sku_ids)

    if total == 0:
        print("❌ No se encontraron SKU IDs en el CSV")
        sys.exit(1)

    print(f"✅ {total} SKU IDs cargados")
    print(f"⏱️  Delay entre requests: {args.delay}s")
    print(f"⏱️  Timeout por request: {args.timeout}s")
    print("=" * 70)

    # Crear session con headers persistentes
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-VTEX-API-AppKey': VTEX_APP_KEY,
        'X-VTEX-API-AppToken': VTEX_APP_TOKEN
    })

    results = []
    found_count = 0
    not_found_count = 0
    error_count = 0
    start_time = datetime.now()

    for i, sku_id in enumerate(sku_ids):
        result = fetch_sku(session, base_url, sku_id, args.delay, args.timeout, is_first=(i == 0))

        if result is None:
            not_found_count += 1
        elif result['status_code'] == 200:
            found_count += 1
            results.append(result)
            print(f"✅ SKU {sku_id} encontrado")
        else:
            error_count += 1
            results.append(result)

        # Progreso cada 10 items
        processed = i + 1
        if processed % 10 == 0 or processed == total:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"📊 Progreso: {processed}/{total} ({processed/total*100:.1f}%) | "
                  f"Encontrados: {found_count} | No encontrados: {not_found_count} | "
                  f"Errores: {error_count} | Tiempo: {elapsed:.0f}s")

    # Exportar resultados
    duration = datetime.now() - start_time
    print("\n" + "=" * 70)
    print("  📋 Resultados")
    print("=" * 70)
    print(f"  Total procesados:  {total}")
    print(f"  ✅ Encontrados:    {found_count}")
    print(f"  ⬜ No encontrados: {not_found_count}")
    print(f"  ❌ Errores:        {error_count}")
    print(f"  ⏱️  Duracion:       {duration}")
    print("=" * 70)

    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(results)} respuestas exportadas a: {args.output_json}")


if __name__ == "__main__":
    main()
