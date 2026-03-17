#!/usr/bin/env python3
"""
vtex_price_fetcher.py

Script para consultar precios de SKUs en VTEX usando la API de pricing.
Consulta el endpoint GET https://api.vtex.com/{accountName}/pricing/prices/{itemId}
para cada referenceCode en un CSV de entrada y exporta los resultados encontrados.

Funcionalidad:
- Lee una lista de referenceCodes desde un CSV de entrada
- Consulta la API de precios VTEX para cada referenceCode
- Exporta un CSV de salida con los registros que tienen precio (HTTP 200)
- Genera un reporte Markdown con estadísticas del proceso
- Maneja rate limiting con delay configurable y retry en HTTP 429
- Muestra progreso en terminal con indicadores visuales

Ejecución:
    python3 vtex_price_fetcher.py input.csv
    python3 vtex_price_fetcher.py input.csv -o resultados.csv -r reporte.md
    python3 vtex_price_fetcher.py input.csv --column SKU --delay 0.5
    python3 vtex_price_fetcher.py input.csv --account mi_cuenta --timeout 60

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME
"""

import argparse
import csv
import os
import sys
import time
import requests
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Consultar precios de SKUs en VTEX usando la API de pricing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 vtex_price_fetcher.py reference_codes.csv
  python3 vtex_price_fetcher.py input.csv --delay 0.5 --column SKU
  python3 vtex_price_fetcher.py input.csv -o precios.csv -r reporte.md
        """
    )
    parser.add_argument('input_csv', help='CSV de entrada con columna de referenceCodes')
    parser.add_argument('-o', '--output', default=None,
                        help='CSV de salida (default: price_results_{timestamp}.csv)')
    parser.add_argument('-r', '--report', default=None,
                        help='Reporte Markdown (default: price_report_{timestamp}.md)')
    parser.add_argument('--column', default='referenceCode',
                        help='Nombre de la columna en el CSV de entrada (default: referenceCode)')
    parser.add_argument('--delay', type=float, default=0.2,
                        help='Segundos entre requests (default: 0.2)')
    parser.add_argument('--account', default=None,
                        help='Nombre de cuenta VTEX (sobreescribe VTEX_ACCOUNT_NAME del .env)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout de requests en segundos (default: 30)')
    return parser.parse_args()


def load_credentials(account_override=None):
    app_key = os.getenv('X-VTEX-API-AppKey')
    app_token = os.getenv('X-VTEX-API-AppToken')
    account_name = account_override or os.getenv('VTEX_ACCOUNT_NAME')

    if not app_key:
        print("❌ Error: X-VTEX-API-AppKey no definido en .env")
        sys.exit(1)
    if not app_token:
        print("❌ Error: X-VTEX-API-AppToken no definido en .env")
        sys.exit(1)
    if not account_name:
        print("❌ Error: VTEX_ACCOUNT_NAME no definido en .env ni en --account")
        sys.exit(1)

    return app_key, app_token, account_name


def read_reference_codes(csv_path, column):
    """Lee los referenceCodes del CSV de entrada."""
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo '{csv_path}'")
        sys.exit(1)

    codes = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            available = ', '.join(reader.fieldnames or [])
            print(f"❌ Error: Columna '{column}' no encontrada en el CSV.")
            print(f"   Columnas disponibles: {available}")
            sys.exit(1)
        for row in reader:
            val = row[column].strip()
            if val:
                codes.append(val)

    print(f"📂 {len(codes)} referenceCodes leídos desde '{csv_path}' (columna: '{column}')")
    return codes


def fetch_price(ref_code, account_name, headers, timeout, retry_delay=10):
    """
    Consulta el precio de un itemId en la API de pricing VTEX.
    Retorna (status_code, response_json_or_none, error_message_or_none).
    """
    url = f"https://api.vtex.com/{account_name}/pricing/prices/{ref_code}"
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)

        if resp.status_code == 200:
            return 200, resp.json(), None

        if resp.status_code == 404:
            return 404, None, None

        if resp.status_code == 429:
            print(f"   ⚠️  Rate limit (429) — esperando {retry_delay}s...")
            time.sleep(retry_delay)
            # Retry once
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return 200, resp.json(), None
            return resp.status_code, None, f"HTTP {resp.status_code} después de retry"

        return resp.status_code, None, f"HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        return None, None, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return None, None, f"ConnectionError: {e}"
    except Exception as e:
        return None, None, str(e)


def extract_price_row(ref_code, data):
    """
    Extrae campos de precio del JSON de respuesta VTEX.
    Si hay fixedPrices, genera una fila por cada entrada.
    Si no hay fixedPrices, genera una fila con los campos base.
    """
    base_price = data.get('basePrice')
    cost_price = data.get('costPrice')
    list_price = data.get('listPrice')
    markup = data.get('markup')
    fixed_prices = data.get('fixedPrices', [])

    rows = []
    if fixed_prices:
        for fp in fixed_prices:
            date_range = fp.get('dateRange') or {}
            rows.append({
                'referenceCode': ref_code,
                'basePrice': base_price,
                'costPrice': cost_price,
                'listPrice': list_price,
                'markup': markup,
                'tradePolicyId': fp.get('tradePolicyId'),
                'fixedPrice': fp.get('value'),
                'fixedListPrice': fp.get('listPrice'),
                'minQuantity': fp.get('minQuantity'),
                'dateRange_from': date_range.get('from'),
                'dateRange_to': date_range.get('to'),
            })
    else:
        rows.append({
            'referenceCode': ref_code,
            'basePrice': base_price,
            'costPrice': cost_price,
            'listPrice': list_price,
            'markup': markup,
            'tradePolicyId': None,
            'fixedPrice': None,
            'fixedListPrice': None,
            'minQuantity': None,
            'dateRange_from': None,
            'dateRange_to': None,
        })
    return rows


OUTPUT_FIELDS = [
    'referenceCode', 'basePrice', 'costPrice', 'listPrice', 'markup',
    'tradePolicyId', 'fixedPrice', 'fixedListPrice', 'minQuantity',
    'dateRange_from', 'dateRange_to',
]


def write_output_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"💾 CSV exportado: '{path}' ({len(rows)} filas)")


def write_report(path, stats, args, found_sample, errors):
    now_str = stats['generated_at']
    total = stats['total']
    found = stats['found']
    not_found = stats['not_found']
    failed = stats['failed']
    found_pct = (found / total * 100) if total else 0
    not_found_pct = (not_found / total * 100) if total else 0
    failed_pct = (failed / total * 100) if total else 0

    lines = [
        "# Reporte de Consulta de Precios VTEX",
        "",
        f"**Generado:** {now_str}  ",
        f"**Cuenta VTEX:** {stats['account_name']}",
        "",
        "---",
        "",
        "## 📊 Resumen Ejecutivo",
        "",
        "| Métrica | Cantidad | Porcentaje |",
        "|---------|----------|------------|",
        f"| Total consultados | {total} | 100% |",
        f"| ✅ Con precio (200) | {found} | {found_pct:.1f}% |",
        f"| ❌ Sin precio (404) | {not_found} | {not_found_pct:.1f}% |",
        f"| ⚠️ Errores | {failed} | {failed_pct:.1f}% |",
        "",
        "## ⚙️ Configuración",
        "",
        f"- **Input:** `{args.input_csv}`",
        f"- **Columna:** `{args.column}`",
        f"- **Delay entre requests:** {args.delay}s",
        f"- **Timeout:** {args.timeout}s",
        f"- **Output CSV:** `{stats['output_csv']}`",
        "",
    ]

    if found_sample:
        lines += [
            "## ✅ Muestra de hallazgos (primeros 10)",
            "",
            "| referenceCode | basePrice | costPrice | listPrice | tradePolicyId |",
            "|---------------|-----------|-----------|-----------|---------------|",
        ]
        for row in found_sample[:10]:
            lines.append(
                f"| {row.get('referenceCode')} | {row.get('basePrice')} | "
                f"{row.get('costPrice')} | {row.get('listPrice')} | "
                f"{row.get('tradePolicyId')} |"
            )
        lines.append("")

    if errors:
        lines += [
            "## ⚠️ Errores de API",
            "",
            "| referenceCode | Status | Error |",
            "|---------------|--------|-------|",
        ]
        for err in errors[:50]:
            lines.append(f"| {err['referenceCode']} | {err['status']} | {err['error']} |")
        if len(errors) > 50:
            lines.append(f"| *(y {len(errors) - 50} más...)* | | |")
        lines.append("")

    lines += [
        "---",
        "",
        "*Reporte generado automáticamente por `vtex_price_fetcher.py`*",
    ]

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"📋 Reporte exportado: '{path}'")


def main():
    args = parse_args()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_csv = args.output or f"price_results_{timestamp}.csv"
    output_report = args.report or f"price_report_{timestamp}.md"

    app_key, app_token, account_name = load_credentials(args.account)

    headers = {
        'Content-Type': 'application/json',
        'X-VTEX-API-AppKey': app_key,
        'X-VTEX-API-AppToken': app_token,
    }

    ref_codes = read_reference_codes(args.input_csv, args.column)
    total = len(ref_codes)

    print(f"\n🚀 Iniciando consulta de precios en VTEX")
    print(f"   Cuenta: {account_name}")
    print(f"   Total a consultar: {total}")
    print(f"   Delay: {args.delay}s | Timeout: {args.timeout}s")
    print(f"   Output: {output_csv}\n")

    found_rows = []
    errors = []
    count_found = 0
    count_not_found = 0
    count_failed = 0

    for i, ref_code in enumerate(ref_codes, start=1):
        status, data, error = fetch_price(ref_code, account_name, headers, args.timeout)

        if status == 200:
            count_found += 1
            rows = extract_price_row(ref_code, data)
            found_rows.extend(rows)
            print(f"[{i}/{total}] {ref_code} → ✅ encontrado (basePrice={data.get('basePrice')})")
        elif status == 404:
            count_not_found += 1
            print(f"[{i}/{total}] {ref_code} → ❌ sin precio (404)")
        else:
            count_failed += 1
            errors.append({'referenceCode': ref_code, 'status': status, 'error': error or ''})
            print(f"[{i}/{total}] {ref_code} → ⚠️  error ({status}: {error})")

        if i < total:
            time.sleep(args.delay)

    print(f"\n✅ Consulta completada.")
    print(f"   Con precio:  {count_found}/{total}")
    print(f"   Sin precio:  {count_not_found}/{total}")
    print(f"   Errores:     {count_failed}/{total}")

    if found_rows:
        write_output_csv(output_csv, found_rows)
    else:
        print("ℹ️  No se encontraron precios — CSV de salida no generado.")

    stats = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'account_name': account_name,
        'total': total,
        'found': count_found,
        'not_found': count_not_found,
        'failed': count_failed,
        'output_csv': output_csv,
    }
    write_report(output_report, stats, args, found_rows, errors)


if __name__ == '__main__':
    main()
