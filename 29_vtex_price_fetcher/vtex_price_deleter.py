#!/usr/bin/env python3
"""
vtex_price_deleter.py

Script para eliminar precios de SKUs en VTEX usando la API de pricing.
Ejecuta DELETE https://api.vtex.com/{accountName}/pricing/prices/{itemId}
para cada referenceCode único en el CSV generado por vtex_price_fetcher.py.

Funcionalidad:
- Lee referenceCodes desde el CSV de salida de vtex_price_fetcher.py
- Deduplica por referenceCode (el DELETE aplica al ítem completo)
- Ejecuta DELETE por cada referenceCode único
- Soporta modo --dry-run para simular sin eliminar
- Maneja rate limiting con delay configurable y retry en HTTP 429
- Genera reporte Markdown con estadísticas del proceso
- Exporta CSV de errores si hay fallos

Ejecución:
    python3 vtex_price_deleter.py price_results_20260304_143000.csv
    python3 vtex_price_deleter.py input.csv --dry-run
    python3 vtex_price_deleter.py input.csv --delay 1.0 --column referenceCode
    python3 vtex_price_deleter.py input.csv --account mi_cuenta --timeout 60

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME
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


def parse_args():
    parser = argparse.ArgumentParser(
        description='Eliminar precios de SKUs en VTEX usando la API de pricing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 vtex_price_deleter.py price_results_20260304_143000.csv
  python3 vtex_price_deleter.py input.csv --dry-run
  python3 vtex_price_deleter.py input.csv --delay 1.0 --column referenceCode
  python3 vtex_price_deleter.py input.csv --account mi_cuenta --timeout 60
        """
    )
    parser.add_argument('input_csv', help='CSV generado por vtex_price_fetcher.py')
    parser.add_argument('-r', '--report', default=None,
                        help='Reporte Markdown (default: price_delete_report_{timestamp}.md)')
    parser.add_argument('--column', default='referenceCode',
                        help='Columna con el itemId (default: referenceCode)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Segundos entre requests (default: 0.5)')
    parser.add_argument('--account', default=None,
                        help='Nombre de cuenta VTEX (sobreescribe VTEX_ACCOUNT_NAME del .env)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout de requests en segundos (default: 30)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simula las operaciones sin hacer DELETE reales')
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
    # Deduplicate preserving order
    seen = set()
    unique_codes = []
    for code in all_codes:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)

    print(f"📂 {len(unique_codes)} referenceCodes únicos extraídos ({total_rows} filas totales en CSV)")
    return unique_codes, total_rows


def delete_price(ref_code, account_name, headers, timeout, retry_delay=10):
    """
    Elimina el precio de un itemId en la API de pricing VTEX.
    Retorna (status_code, error_message_or_none).
    """
    url = f"https://api.vtex.com/{account_name}/pricing/prices/{ref_code}"
    try:
        resp = requests.delete(url, headers=headers, timeout=timeout)

        if resp.status_code in (200, 204):
            return resp.status_code, None

        if resp.status_code == 404:
            return 404, None

        if resp.status_code == 429:
            print(f"   ⚠️  Rate limit (429) — esperando {retry_delay}s...")
            time.sleep(retry_delay)
            # Retry once
            resp = requests.delete(url, headers=headers, timeout=timeout)
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
    fields = ['referenceCode', 'status', 'error']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(errors)
    print(f"💾 CSV de errores exportado: '{path}' ({len(errors)} filas)")


def write_report(path, stats, args, errors):
    now_str = stats['generated_at']
    total = stats['total']
    deleted = stats['deleted']
    not_found = stats['not_found']
    failed = stats['failed']
    simulated = stats['simulated']
    is_dry_run = args.dry_run

    deleted_pct = (deleted / total * 100) if total else 0
    not_found_pct = (not_found / total * 100) if total else 0
    failed_pct = (failed / total * 100) if total else 0
    simulated_pct = (simulated / total * 100) if total else 0

    mode_label = "DRY-RUN" if is_dry_run else "REAL"

    lines = [
        "# Reporte de Eliminación de Precios VTEX",
        "",
        f"**Generado:** {now_str}  ",
        f"**Cuenta VTEX:** {stats['account_name']}  ",
        f"**Modo:** {mode_label}",
        "",
        "---",
        "",
        "## 📊 Resumen Ejecutivo",
        "",
        "| Métrica | Cantidad | Porcentaje |",
        "|---------|----------|------------|",
        f"| Total referenceCodes únicos | {total} | 100% |",
    ]

    if is_dry_run:
        lines.append(f"| 🔍 Simulados (dry-run) | {simulated} | {simulated_pct:.1f}% |")
    else:
        lines += [
            f"| ✅ Eliminados exitosamente | {deleted} | {deleted_pct:.1f}% |",
            f"| ❌ No encontrados (404) | {not_found} | {not_found_pct:.1f}% |",
            f"| ⚠️ Errores | {failed} | {failed_pct:.1f}% |",
        ]

    lines += [
        "",
        "## ⚙️ Configuración",
        "",
        f"- **Input:** `{args.input_csv}`",
        f"- **Columna:** `{args.column}`",
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
            "| referenceCode | Status | Error |",
            "|---------------|--------|-------|",
        ]
        for err in errors[:50]:
            lines.append(f"| {err['referenceCode']} | {err['status']} | {err['error']} |")
        if len(errors) > 50:
            lines.append(f"| *(y {len(errors) - 50} más...)* | | |")
        if errors_csv:
            lines += ["", f"CSV de errores exportado: `{errors_csv}`"]
        lines.append("")

    lines += [
        "---",
        "",
        "*Reporte generado automáticamente por `vtex_price_deleter.py`*",
    ]

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"📋 Reporte exportado: '{path}'")


def main():
    args = parse_args()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_report = args.report or f"price_delete_report_{timestamp}.md"

    app_key, app_token, account_name = load_credentials(args.account)

    headers = {
        'Content-Type': 'application/json',
        'X-VTEX-API-AppKey': app_key,
        'X-VTEX-API-AppToken': app_token,
    }

    unique_codes, total_rows = read_unique_reference_codes(args.input_csv, args.column)
    total = len(unique_codes)

    mode_label = "DRY-RUN" if args.dry_run else "REAL"
    print(f"\n🚀 Iniciando eliminación de precios en VTEX")
    print(f"   Cuenta: {account_name}")
    print(f"   Modo: {mode_label}")
    print(f"   Total a procesar: {total}")
    print(f"   Delay: {args.delay}s | Timeout: {args.timeout}s")
    print(f"   Reporte: {output_report}\n")

    errors = []
    count_deleted = 0
    count_not_found = 0
    count_failed = 0
    count_simulated = 0

    for i, ref_code in enumerate(unique_codes, start=1):
        if args.dry_run:
            count_simulated += 1
            print(f"[{i}/{total}] {ref_code} → 🔍 dry-run (DELETE simulado)")
        else:
            status, error = delete_price(ref_code, account_name, headers, args.timeout)

            if status in (200, 204):
                count_deleted += 1
                print(f"[{i}/{total}] {ref_code} → ✅ eliminado")
            elif status == 404:
                count_not_found += 1
                print(f"[{i}/{total}] {ref_code} → ❌ no encontrado (404)")
            else:
                count_failed += 1
                errors.append({'referenceCode': ref_code, 'status': status, 'error': error or ''})
                print(f"[{i}/{total}] {ref_code} → ⚠️  error ({status}: {error})")

        if i < total:
            time.sleep(args.delay)

    print(f"\n✅ Proceso completado.")
    if args.dry_run:
        print(f"   Simulados:   {count_simulated}/{total}")
    else:
        print(f"   Eliminados:  {count_deleted}/{total}")
        print(f"   No encontrados: {count_not_found}/{total}")
        print(f"   Errores:     {count_failed}/{total}")

    errors_csv = None
    if errors:
        errors_csv = f"price_delete_errors_{timestamp}.csv"
        write_errors_csv(errors_csv, errors)

    stats = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'account_name': account_name,
        'total': total,
        'deleted': count_deleted,
        'not_found': count_not_found,
        'failed': count_failed,
        'simulated': count_simulated,
        'errors_csv': errors_csv or '',
    }
    write_report(output_report, stats, args, errors)


if __name__ == '__main__':
    main()
