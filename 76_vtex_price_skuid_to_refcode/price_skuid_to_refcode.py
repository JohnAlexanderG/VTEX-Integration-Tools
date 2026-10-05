#!/usr/bin/env python3
"""
VTEX Price SKU ID -> Reference Code (formato ERP)

Convierte la exportación de precios de VTEX (indexada por SKU ID) al CSV de
precios en formato ERP (indexado por código de referencia), usando el export
"products-and-skus" de VTEX para mapear SKU ID -> SKU reference code.

Uso:
    python3 price_skuid_to_refcode.py <precios_vtex.xlsx> <products_and_skus.xlsx> <output_prefix> [--dry-run]

Ejemplo:
    python3 76_vtex_price_skuid_to_refcode/price_skuid_to_refcode.py \\
        precios.xlsx products-and-skus.xlsx output/didopet_precios

Entradas:
    - precios_vtex.xlsx: SKU ID, Cost Price, Base Price, List Price, Error Code, Error Message
    - products_and_skus.xlsx: Product ID, Product Name, SKU ID, SKU name, SKU reference code

Salidas:
    - {prefix}_erp_precios.csv:     codigo producto,Costo,Precio Venta,% IVA,Precio Lista o Precio Promocion
    - {prefix}_sin_refcode.csv:     Precios cuyo SKU ID no tiene código de referencia
    - {prefix}_skus_sin_precio.csv: SKUs del catálogo sin precio
    - {prefix}_errores.csv:         Filas con Error Code / Error Message (solo si existen)
    - {prefix}_REPORT.md:           Reporte con estadísticas
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

try:
    import openpyxl
except ImportError:
    print("❌ Error: falta openpyxl. Instalar con: pip install openpyxl")
    sys.exit(1)


ERP_HEADER = ['codigo producto', 'Costo', 'Precio Venta', '% IVA', 'Precio Lista o Precio Promocion']
PRICE_COLUMNS = ['SKU ID', 'Cost Price', 'Base Price', 'List Price']
SKU_COLUMNS = ['SKU ID', 'SKU reference code']
HEADER_SCAN_ROWS = 10


def header_columns(row):
    return {str(name).strip(): idx for idx, name in enumerate(row or []) if name is not None and str(name).strip()}


def read_xlsx(file_path, required_columns):
    """
    Lee la primera hoja de un xlsx como lista de dicts.

    Detecta la fila de encabezados como la primera (dentro de las primeras
    HEADER_SCAN_ROWS) que contiene todas las columnas requeridas. Así se omite
    la fila "Learn how to fill out this spreadsheet here" que VTEX agrega arriba.
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo '{file_path}' no existe")
        sys.exit(1)

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    rows = wb.worksheets[0].iter_rows(values_only=True)

    columns, first_columns, header_row = None, None, 0
    for header_row, row in enumerate(rows, start=1):
        candidate = header_columns(row)
        if first_columns is None and candidate:
            first_columns = candidate
        if all(c in candidate for c in required_columns):
            columns = candidate
            break
        if header_row >= HEADER_SCAN_ROWS:
            break

    if columns is None:
        found = first_columns or {}
        missing = [c for c in required_columns if c not in found]
        print(f"❌ Error: '{file_path}' no tiene las columnas: {', '.join(missing)}")
        print(f"   Columnas encontradas: {', '.join(found)}")
        sys.exit(1)

    if header_row > 1:
        print(f"   ℹ️  Encabezados detectados en fila {header_row} de '{os.path.basename(file_path)}' "
              f"(se omitieron {header_row - 1} filas)")

    records = []
    for row in rows:
        record = {name: (row[idx] if idx < len(row) else None) for name, idx in columns.items()}
        if record.get('SKU ID') in (None, ''):
            continue
        records.append(record)
    wb.close()
    return records


def to_sku_id(value):
    """Normaliza SKU ID a int (el export de precios lo trae como float 1.0)."""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def format_price(value):
    """Escribe enteros sin decimales; conserva decimales si existen."""
    if value is None or value == '':
        return ''
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    return str(int(number)) if number == int(number) else str(number)


def is_blank(value):
    return value is None or str(value).strip() == ''


def write_csv(file_path, fieldnames, rows):
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def generate_report(report_file, stats, files, duplicates):
    lines = [
        "# 💲 Conversión de precios VTEX: SKU ID → Código de referencia",
        "",
        f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 📁 Archivos de entrada",
        f"- Precios VTEX: `{stats['prices_file']}`",
        f"- Productos y SKUs: `{stats['skus_file']}`",
        "",
        "## 📊 Estadísticas",
        "| Métrica | Cantidad |",
        "|---|---:|",
        f"| Filas de precios leídas | {stats['prices_total']:,} |",
        f"| SKUs en catálogo | {stats['skus_total']:,} |",
        f"| ✅ Precios convertidos (formato ERP) | {stats['matched']:,} |",
        f"| ⚠️ Precios sin código de referencia | {stats['without_refcode']:,} |",
        f"| ❌ Filas con error en export | {stats['errors']:,} |",
        f"| ⚠️ SKU ID duplicados en precios | {stats['duplicate_price_ids']:,} |",
        f"| ℹ️ SKUs del catálogo sin precio | {stats['skus_without_price']:,} |",
        "",
        "## 📄 Archivos generados",
    ]
    lines += [f"- `{path}`" for path in files]

    if duplicates:
        lines += ["", "## ⚠️ Códigos de referencia compartidos por varios SKU ID", "",
                  "| Código de referencia | SKU IDs |", "|---|---|"]
        lines += [f"| {ref} | {', '.join(str(s) for s in ids)} |" for ref, ids in duplicates.items()]

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(
        description='Convierte la exportación de precios VTEX (SKU ID) a CSV ERP (código de referencia)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('prices_file', help='xlsx de precios VTEX (SKU ID, Cost Price, Base Price, List Price, ...)')
    parser.add_argument('skus_file', help='xlsx products-and-skus con columna "SKU reference code"')
    parser.add_argument('output_prefix', help='Prefijo de los archivos de salida')
    parser.add_argument('--dry-run', action='store_true', help='Analiza sin escribir archivos')
    args = parser.parse_args()

    print("📥 Leyendo archivos...")
    prices = read_xlsx(args.prices_file, PRICE_COLUMNS)
    skus = read_xlsx(args.skus_file, SKU_COLUMNS)
    print(f"   Precios: {len(prices):,} filas | SKUs: {len(skus):,} filas")

    sku_map = {}
    for sku in skus:
        sku_id = to_sku_id(sku['SKU ID'])
        if sku_id is not None:
            sku_map[sku_id] = sku

    erp_rows, without_refcode, error_rows = [], [], []
    refcode_to_ids = defaultdict(list)
    seen_ids, duplicate_price_ids = set(), 0

    for price in prices:
        sku_id = to_sku_id(price['SKU ID'])
        if sku_id in seen_ids:
            duplicate_price_ids += 1
        seen_ids.add(sku_id)

        if not is_blank(price.get('Error Code')) or not is_blank(price.get('Error Message')):
            error_rows.append([price['SKU ID'], price.get('Cost Price'), price.get('Base Price'),
                               price.get('List Price'), price.get('Error Code'), price.get('Error Message')])
            continue

        sku = sku_map.get(sku_id)
        refcode = '' if sku is None or is_blank(sku['SKU reference code']) else str(sku['SKU reference code']).strip()
        if not refcode:
            without_refcode.append([sku_id, format_price(price['Cost Price']),
                                    format_price(price['Base Price']), format_price(price['List Price'])])
            continue

        refcode_to_ids[refcode].append(sku_id)
        erp_rows.append([refcode, format_price(price['Cost Price']), format_price(price['Base Price']),
                         '', format_price(price['List Price'])])

    skus_without_price = [
        [sku_id, sku.get('SKU reference code') or '', sku.get('Product ID') or '', sku.get('SKU name') or '']
        for sku_id, sku in sku_map.items() if sku_id not in seen_ids
    ]
    duplicates = {ref: ids for ref, ids in refcode_to_ids.items() if len(ids) > 1}

    stats = {
        'prices_file': args.prices_file,
        'skus_file': args.skus_file,
        'prices_total': len(prices),
        'skus_total': len(sku_map),
        'matched': len(erp_rows),
        'without_refcode': len(without_refcode),
        'errors': len(error_rows),
        'duplicate_price_ids': duplicate_price_ids,
        'skus_without_price': len(skus_without_price),
    }

    print("\n📊 Resultados:")
    print(f"   ✅ Precios convertidos:          {stats['matched']:,}")
    print(f"   ⚠️  Sin código de referencia:     {stats['without_refcode']:,}")
    print(f"   ❌ Filas con error en export:    {stats['errors']:,}")
    print(f"   ⚠️  SKU ID duplicados en precios: {stats['duplicate_price_ids']:,}")
    print(f"   ℹ️  SKUs del catálogo sin precio: {stats['skus_without_price']:,}")
    if duplicates:
        print(f"   ⚠️  {len(duplicates)} códigos de referencia asociados a más de un SKU ID (ver reporte)")

    if args.dry_run:
        print("\n🔍 Dry-run: no se escribieron archivos")
        return

    output_dir = os.path.dirname(args.output_prefix)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    prefix = args.output_prefix
    files = []

    erp_file = f"{prefix}_erp_precios.csv"
    write_csv(erp_file, ERP_HEADER, erp_rows)
    files.append(erp_file)

    without_file = f"{prefix}_sin_refcode.csv"
    write_csv(without_file, PRICE_COLUMNS, without_refcode)
    files.append(without_file)

    no_price_file = f"{prefix}_skus_sin_precio.csv"
    write_csv(no_price_file, ['SKU ID', 'SKU reference code', 'Product ID', 'SKU name'], skus_without_price)
    files.append(no_price_file)

    if error_rows:
        errors_file = f"{prefix}_errores.csv"
        write_csv(errors_file, PRICE_COLUMNS + ['Error Code', 'Error Message'], error_rows)
        files.append(errors_file)

    report_file = f"{prefix}_REPORT.md"
    generate_report(report_file, stats, files, duplicates)
    files.append(report_file)

    print("\n📄 Archivos generados:")
    for path in files:
        print(f"   {path}")


if __name__ == '__main__':
    main()
