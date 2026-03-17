#!/usr/bin/env python3
"""
vtex_inventory_resetter.py

Script para resetear el inventario a 0 en las 18 bodegas por defecto de VTEX.
Lee los referenceCodes del CSV generado por vtex_price_fetcher.py y ejecuta
PATCH https://{accountName}.{environment}.com.br/api/logistics/pvt/inventory/skus/{skuId}/warehouses/{warehouseId}/quantity
para cada combinación SKU × bodega.

Funcionalidad:
- Lee y deduplica referenceCodes desde el CSV de entrada
- Ejecuta PATCH quantity=0 en 18 bodegas por cada referenceCode único
- Soporta modo --dry-run para simular sin modificar inventario
- Maneja rate limiting con delay configurable y retry en HTTP 429
- Genera reporte Markdown con estadísticas del proceso
- Exporta CSV de errores si hay fallos

Ejecución:
    python3 vtex_inventory_resetter.py price_results_20260304_125357.csv
    python3 vtex_inventory_resetter.py input.csv --dry-run
    python3 vtex_inventory_resetter.py input.csv --delay 1.0 --column referenceCode
    python3 vtex_inventory_resetter.py input.csv --account mi_cuenta --timeout 60

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken,
  VTEX_ACCOUNT_NAME, VTEX_ENVIRONMENT
"""

import argparse
import csv
import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

WAREHOUSE_IDS = [
    "021", "001", "140", "084", "180", "160", "280", "320", "340",
    "300", "032", "200", "100", "095", "003", "053", "068", "220"
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Resetear inventario a 0 en 18 bodegas VTEX para SKUs listados en un CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 vtex_inventory_resetter.py price_results_20260304_125357.csv
  python3 vtex_inventory_resetter.py input.csv --dry-run
  python3 vtex_inventory_resetter.py input.csv --delay 1.0 --column referenceCode
  python3 vtex_inventory_resetter.py input.csv --account mi_cuenta --timeout 60
        """
    )
    parser.add_argument('input_csv', help='CSV con columna de referenceCodes (output de vtex_price_fetcher.py)')
    parser.add_argument('-r', '--report', default=None,
                        help='Reporte Markdown (default: inventory_reset_report_{timestamp}.md)')
    parser.add_argument('--column', default='referenceCode',
                        help='Nombre de la columna con el skuId (default: referenceCode)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Segundos entre requests (default: 0.5)')
    parser.add_argument('--account', default=None,
                        help='Nombre de cuenta VTEX (sobreescribe VTEX_ACCOUNT_NAME del .env)')
    parser.add_argument('--environment', default=None,
                        help='Environment VTEX (sobreescribe VTEX_ENVIRONMENT del .env)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout de requests en segundos (default: 30)')
    parser.add_argument('--quantity', type=int, default=0,
                        help='Cantidad a enviar (default: 0)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simula las operaciones sin hacer PATCH reales')
    return parser.parse_args()


def load_credentials(account_override=None, environment_override=None):
    app_key = os.getenv('X-VTEX-API-AppKey')
    app_token = os.getenv('X-VTEX-API-AppToken')
    account_name = account_override or os.getenv('VTEX_ACCOUNT_NAME')
    environment = environment_override or os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

    if not app_key:
        print("❌ Error: X-VTEX-API-AppKey no definido en .env")
        sys.exit(1)
    if not app_token:
        print("❌ Error: X-VTEX-API-AppToken no definido en .env")
        sys.exit(1)
    if not account_name:
        print("❌ Error: VTEX_ACCOUNT_NAME no definido en .env ni en --account")
        sys.exit(1)

    return app_key, app_token, account_name, environment


def read_unique_reference_codes(csv_path, column):
    """Lee y deduplica los referenceCodes del CSV de entrada."""
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo '{csv_path}'")
        sys.exit(1)

    all_codes = []
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
                all_codes.append(val)

    total_rows = len(all_codes)
    seen = set()
    unique_codes = []
    for code in all_codes:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)

    n_unique = len(unique_codes)
    total_calls = n_unique * len(WAREHOUSE_IDS)
    print(f"📂 {n_unique} referenceCodes únicos ({total_rows} filas en CSV) → {total_calls} llamadas totales ({n_unique} × {len(WAREHOUSE_IDS)})")
    return unique_codes, total_rows


def patch_inventory(sku_id, warehouse_id, account_name, environment, headers, timeout, quantity, retry_delay=10):
    """
    Envía PATCH para resetear el inventario de un SKU en una bodega.
    Retorna (status_code, error_message_or_none).
    """
    url = (
        f"https://{account_name}.{environment}.com.br"
        f"/api/logistics/pvt/inventory/skus/{sku_id}/warehouses/{warehouse_id}/quantity"
    )
    body = {"quantity": quantity, "unlimitedQuantity": False}
    try:
        resp = requests.patch(url, json=body, headers=headers, timeout=timeout)

        if resp.status_code in (200, 204):
            return resp.status_code, None

        if resp.status_code == 404:
            return 404, None

        if resp.status_code == 429:
            print(f"   ⚠️  Rate limit (429) — esperando {retry_delay}s...")
            time.sleep(retry_delay)
            resp = requests.patch(url, json=body, headers=headers, timeout=timeout)
            if resp.status_code in (200, 204):
                return resp.status_code, None
            return resp.status_code, f"HTTP {resp.status_code} después de retry"

        return resp.status_code, f"HTTP {resp.status_code}"

    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return None, f"ConnectionError: {e}"
    except Exception as e:
        return None, str(e)


def write_errors_csv(path, errors):
    fields = ['referenceCode', 'warehouseId', 'status', 'error']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(errors)
    print(f"💾 CSV de errores exportado: '{path}' ({len(errors)} filas)")


def write_report(path, stats, args, errors):
    now_str = stats['generated_at']
    n_skus = stats['n_skus']
    total_calls = stats['total_calls']
    updated = stats['updated']
    not_found = stats['not_found']
    failed = stats['failed']
    simulated = stats['simulated']
    is_dry_run = args.dry_run

    updated_pct = (updated / total_calls * 100) if total_calls else 0
    not_found_pct = (not_found / total_calls * 100) if total_calls else 0
    failed_pct = (failed / total_calls * 100) if total_calls else 0
    simulated_pct = (simulated / total_calls * 100) if total_calls else 0

    mode_label = "DRY-RUN" if is_dry_run else "REAL"
    wh_preview = ", ".join(WAREHOUSE_IDS[:6]) + f", ... ({len(WAREHOUSE_IDS)} total)"

    lines = [
        "# Reporte de Reset de Inventario VTEX",
        "",
        f"**Generado:** {now_str}  ",
        f"**Cuenta VTEX:** {stats['account_name']}  ",
        f"**Environment:** {stats['environment']}  ",
        f"**Modo:** {mode_label}",
        "",
        "---",
        "",
        "## 📊 Resumen Ejecutivo",
        "",
        "| Métrica | Cantidad | % |",
        "|---------|----------|---|",
        f"| SKUs únicos procesados | {n_skus} | — |",
        f"| Bodegas × SKU | {len(WAREHOUSE_IDS)} | — |",
        f"| Total llamadas API | {total_calls} | 100% |",
    ]

    if is_dry_run:
        lines.append(f"| 🔍 Simulados (dry-run) | {simulated} | {simulated_pct:.1f}% |")
    else:
        lines += [
            f"| ✅ Actualizados exitosamente | {updated} | {updated_pct:.1f}% |",
            f"| ❌ No encontrados (404) | {not_found} | {not_found_pct:.1f}% |",
            f"| ⚠️ Errores | {failed} | {failed_pct:.1f}% |",
        ]

    lines += [
        "",
        "## ⚙️ Configuración",
        "",
        f"- **Input:** `{args.input_csv}`",
        f"- **Columna:** `{args.column}`",
        f"- **Cantidad enviada:** {args.quantity}",
        f"- **Bodegas:** {len(WAREHOUSE_IDS)} ({wh_preview})",
        f"- **Delay entre requests:** {args.delay}s",
        f"- **Timeout:** {args.timeout}s",
        f"- **Modo dry-run:** {'Sí' if is_dry_run else 'No'}",
        "",
    ]

    if errors:
        errors_csv = stats.get('errors_csv', '')
        lines += [
            "## ⚠️ Errores de API",
            "",
            "| referenceCode | warehouseId | Status | Error |",
            "|---------------|-------------|--------|-------|",
        ]
        for err in errors[:50]:
            lines.append(
                f"| {err['referenceCode']} | {err['warehouseId']} | {err['status']} | {err['error']} |"
            )
        if len(errors) > 50:
            lines.append(f"| *(y {len(errors) - 50} más...)* | | | |")
        if errors_csv:
            lines += ["", f"CSV de errores exportado: `{errors_csv}`"]
        lines.append("")

    lines += [
        "---",
        "",
        "*Reporte generado automáticamente por `vtex_inventory_resetter.py`*",
    ]

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"📋 Reporte exportado: '{path}'")


def main():
    args = parse_args()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_report = args.report or f"inventory_reset_report_{timestamp}.md"

    app_key, app_token, account_name, environment = load_credentials(args.account, args.environment)

    headers = {
        'Content-Type': 'application/json',
        'X-VTEX-API-AppKey': app_key,
        'X-VTEX-API-AppToken': app_token,
    }

    unique_codes, total_rows = read_unique_reference_codes(args.input_csv, args.column)
    n_skus = len(unique_codes)
    total_calls = n_skus * len(WAREHOUSE_IDS)

    mode_label = "DRY-RUN" if args.dry_run else "REAL"
    print(f"\n🚀 Iniciando reset de inventario en VTEX")
    print(f"   Cuenta: {account_name} | Environment: {environment}")
    print(f"   Modo: {mode_label}")
    print(f"   SKUs únicos: {n_skus} | Bodegas: {len(WAREHOUSE_IDS)} | Total llamadas: {total_calls}")
    print(f"   Cantidad: {args.quantity} | Delay: {args.delay}s | Timeout: {args.timeout}s")
    print(f"   Reporte: {output_report}\n")

    errors = []
    count_updated = 0
    count_not_found = 0
    count_failed = 0
    count_simulated = 0
    call_num = 0

    for sku_id in unique_codes:
        for wh_id in WAREHOUSE_IDS:
            call_num += 1

            if args.dry_run:
                count_simulated += 1
                print(f"[{call_num}/{total_calls}] {sku_id} / WH {wh_id} → 🔍 dry-run (PATCH simulado)")
            else:
                status, error = patch_inventory(
                    sku_id, wh_id, account_name, environment,
                    headers, args.timeout, args.quantity
                )

                if status in (200, 204):
                    count_updated += 1
                    print(f"[{call_num}/{total_calls}] {sku_id} / WH {wh_id} → ✅ actualizado")
                elif status == 404:
                    count_not_found += 1
                    print(f"[{call_num}/{total_calls}] {sku_id} / WH {wh_id} → ❌ no encontrado (404)")
                else:
                    count_failed += 1
                    errors.append({
                        'referenceCode': sku_id,
                        'warehouseId': wh_id,
                        'status': status,
                        'error': error or '',
                    })
                    print(f"[{call_num}/{total_calls}] {sku_id} / WH {wh_id} → ⚠️  error ({status}: {error})")

            if call_num < total_calls:
                time.sleep(args.delay)

    print(f"\n✅ Proceso completado.")
    if args.dry_run:
        print(f"   Simulados:      {count_simulated}/{total_calls}")
    else:
        print(f"   Actualizados:   {count_updated}/{total_calls}")
        print(f"   No encontrados: {count_not_found}/{total_calls}")
        print(f"   Errores:        {count_failed}/{total_calls}")

    errors_csv = None
    if errors:
        errors_csv = f"inventory_reset_errors_{timestamp}.csv"
        write_errors_csv(errors_csv, errors)

    stats = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'account_name': account_name,
        'environment': environment,
        'n_skus': n_skus,
        'total_calls': total_calls,
        'updated': count_updated,
        'not_found': count_not_found,
        'failed': count_failed,
        'simulated': count_simulated,
        'errors_csv': errors_csv or '',
    }
    write_report(output_report, stats, args, errors)


if __name__ == '__main__':
    main()
