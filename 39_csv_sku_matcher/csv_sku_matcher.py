#!/usr/bin/env python3
"""
CSV SKU Matcher - Compare and filter CSV data based on existing VTEX SKUs.

This script compares SKUs from two CSV files:
- File 1: Existing SKUs with _SkuId, _SKUReferenceCode, _ProductId
- File 2: Data to filter with SKU column (can have multiple rows per SKU)

Outputs:
- Matched rows from file 2 enriched with _SkuId and _ProductId
- Non-matched rows from file 2
- Markdown report with statistics

Usage:
    python3 csv_sku_matcher.py existing_skus.csv data_to_filter.csv output_prefix

Examples:
    python3 csv_sku_matcher.py vtex_skus.csv specifications.csv filtered_specs
    python3 csv_sku_matcher.py skus.csv data.csv output/result
"""

import argparse
import csv
import sys
import os
from datetime import datetime


def make_unique_fieldnames(fieldnames):
    """
    Handle duplicate column names by appending numeric suffixes.
    Returns (unique_fieldnames, duplicates_found_flag)
    """
    seen = {}
    unique = []
    has_duplicates = False

    for name in fieldnames:
        if name in seen:
            has_duplicates = True
            seen[name] += 1
            unique.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            unique.append(name)

    return unique, has_duplicates


def load_existing_skus(file_path):
    """
    Load existing SKUs from file 1 into a dictionary.

    Returns:
        dict: Mapping of _SKUReferenceCode -> {'_SkuId': ..., '_ProductId': ...}
    """
    sku_map = {}

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ref_code = str(row.get('_SKUReferenceCode', '')).strip()
            if ref_code:
                sku_map[ref_code] = {
                    '_SkuId': row.get('_SkuId', ''),
                    '_ProductId': row.get('_ProductId', '')
                }

    return sku_map


def process_data_file(file_path, sku_map):
    """
    Process file 2 and separate matched/non-matched rows.

    Returns:
        tuple: (matched_rows, not_found_rows, fieldnames, stats)
    """
    matched = []
    not_found = []
    matched_skus = set()
    not_found_skus = set()

    with open(file_path, 'r', encoding='utf-8') as f:
        # Read header manually to handle duplicate column names
        csv_reader = csv.reader(f)
        original_fieldnames = next(csv_reader)

        # Handle duplicate column names
        fieldnames, has_duplicates = make_unique_fieldnames(original_fieldnames)
        if has_duplicates:
            print(f"   Warning: Duplicate column names detected, renamed to avoid data loss")

        # Create DictReader with unique fieldnames
        reader = csv.DictReader(f, fieldnames=fieldnames)

        for row in reader:
            sku = str(row.get('SKU', '')).strip()

            if sku in sku_map:
                # Enrich with _SkuId and _ProductId
                enriched_row = {
                    '_SkuId': sku_map[sku]['_SkuId'],
                    '_ProductId': sku_map[sku]['_ProductId'],
                    **row
                }
                matched.append(enriched_row)
                matched_skus.add(sku)
            else:
                not_found.append(row)
                if sku:
                    not_found_skus.add(sku)

    stats = {
        'total_rows': len(matched) + len(not_found),
        'matched_rows': len(matched),
        'not_found_rows': len(not_found),
        'unique_matched_skus': len(matched_skus),
        'unique_not_found_skus': len(not_found_skus)
    }

    return matched, not_found, fieldnames, stats


def export_csv(data, file_path, fieldnames):
    """Export data to CSV file."""
    if not data:
        return

    # Get all unique keys from data
    all_keys = set()
    for row in data:
        all_keys.update(row.keys())

    # Ensure _SkuId and _ProductId are first if present
    ordered_fields = []
    if '_SkuId' in all_keys:
        ordered_fields.append('_SkuId')
        all_keys.discard('_SkuId')
    if '_ProductId' in all_keys:
        ordered_fields.append('_ProductId')
        all_keys.discard('_ProductId')

    # Add remaining fields in original order if possible
    for field in fieldnames:
        if field in all_keys:
            ordered_fields.append(field)
            all_keys.discard(field)

    # Add any remaining fields
    ordered_fields.extend(sorted(all_keys))

    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=ordered_fields)
        writer.writeheader()
        writer.writerows(data)


def generate_report(args, sku_map, stats, output_files):
    """Generate markdown report with statistics."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_existing = len(sku_map)
    matched_pct = (stats['matched_rows'] / stats['total_rows'] * 100) if stats['total_rows'] > 0 else 0
    not_found_pct = (stats['not_found_rows'] / stats['total_rows'] * 100) if stats['total_rows'] > 0 else 0

    report = f"""# Reporte de Filtrado CSV por SKU

**Generado:** {timestamp}

## Archivos de Entrada

| Archivo | Descripcion |
|---------|-------------|
| SKUs existentes | `{args.existing_skus}` |
| Datos a filtrar | `{args.data_to_filter}` |

## Estadisticas

### SKUs de Referencia (Archivo 1)
- **Total de SKUs existentes:** {total_existing:,}

### Datos Procesados (Archivo 2)

| Metrica | Filas | SKUs Unicos | Porcentaje |
|---------|-------|-------------|------------|
| Total procesadas | {stats['total_rows']:,} | - | 100.0% |
| Coincidencias | {stats['matched_rows']:,} | {stats['unique_matched_skus']:,} | {matched_pct:.1f}% |
| No encontrados | {stats['not_found_rows']:,} | {stats['unique_not_found_skus']:,} | {not_found_pct:.1f}% |

## Archivos Generados

### 1. Coincidencias (Matched)
**Archivo:** `{output_files['matched']}`
**Filas:** {stats['matched_rows']:,}

Contiene todas las filas del archivo de datos donde el SKU existe en el archivo de SKUs existentes.
Cada fila incluye `_SkuId` y `_ProductId` del archivo de referencia.

### 2. No Encontrados (Not Found)
**Archivo:** `{output_files['not_found']}`
**Filas:** {stats['not_found_rows']:,}

Contiene todas las filas del archivo de datos donde el SKU NO existe en el archivo de SKUs existentes.
Estos SKUs pueden requerir creacion en VTEX antes de poder procesar sus datos.

## Resumen

- Se procesaron **{stats['total_rows']:,}** filas del archivo de datos
- **{stats['matched_rows']:,}** filas ({matched_pct:.1f}%) tienen SKUs existentes en VTEX
- **{stats['not_found_rows']:,}** filas ({not_found_pct:.1f}%) tienen SKUs que no existen

"""

    if stats['not_found_rows'] > 0:
        report += f"""## Recomendaciones

- Revise el archivo `{output_files['not_found']}` para identificar los SKUs faltantes
- Verifique si los SKUs no encontrados necesitan ser creados en VTEX
- Una vez creados los SKUs faltantes, vuelva a ejecutar este script
"""

    return report


def main():
    parser = argparse.ArgumentParser(
        description='Compare and filter CSV data based on existing VTEX SKUs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 csv_sku_matcher.py vtex_skus.csv specifications.csv filtered_specs
  python3 csv_sku_matcher.py skus.csv data.csv output/result
        """
    )
    parser.add_argument('existing_skus',
                        help='CSV file with existing SKUs (_SkuId, _SKUReferenceCode, _ProductId)')
    parser.add_argument('data_to_filter',
                        help='CSV file with data to filter (must have SKU column)')
    parser.add_argument('output_prefix',
                        help='Prefix for output files')

    args = parser.parse_args()

    # Validate input files exist
    if not os.path.exists(args.existing_skus):
        print(f"Error: File '{args.existing_skus}' not found")
        sys.exit(1)

    if not os.path.exists(args.data_to_filter):
        print(f"Error: File '{args.data_to_filter}' not found")
        sys.exit(1)

    # Create output directory if needed
    output_dir = os.path.dirname(args.output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("=" * 70)
    print("CSV SKU Matcher")
    print("=" * 70)

    # Load existing SKUs
    print(f"\n📁 Loading existing SKUs from: {args.existing_skus}")
    try:
        sku_map = load_existing_skus(args.existing_skus)
        print(f"   ✓ Loaded {len(sku_map):,} unique SKUs")
    except Exception as e:
        print(f"   ✗ Error loading file: {e}")
        sys.exit(1)

    # Process data file
    print(f"\n📁 Processing data file: {args.data_to_filter}")
    try:
        matched, not_found, fieldnames, stats = process_data_file(args.data_to_filter, sku_map)
        print(f"   ✓ Processed {stats['total_rows']:,} rows")
    except Exception as e:
        print(f"   ✗ Error processing file: {e}")
        sys.exit(1)

    # Define output files
    output_files = {
        'matched': f"{args.output_prefix}_matched.csv",
        'not_found': f"{args.output_prefix}_not_found.csv",
        'report': f"{args.output_prefix}_REPORT.md"
    }

    # Export matched data
    print(f"\n📊 Exporting results...")
    if matched:
        export_csv(matched, output_files['matched'], fieldnames)
        print(f"   ✓ Matched: {output_files['matched']} ({stats['matched_rows']:,} rows)")
    else:
        print(f"   - No matched rows to export")

    # Export not found data
    if not_found:
        export_csv(not_found, output_files['not_found'], fieldnames)
        print(f"   ✓ Not found: {output_files['not_found']} ({stats['not_found_rows']:,} rows)")
    else:
        print(f"   - No unmatched rows to export")

    # Generate report
    report = generate_report(args, sku_map, stats, output_files)
    with open(output_files['report'], 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"   ✓ Report: {output_files['report']}")

    # Print summary
    matched_pct = (stats['matched_rows'] / stats['total_rows'] * 100) if stats['total_rows'] > 0 else 0
    not_found_pct = (stats['not_found_rows'] / stats['total_rows'] * 100) if stats['total_rows'] > 0 else 0

    print("\n" + "=" * 70)
    print("📋 Summary")
    print("=" * 70)
    print(f"   Total rows processed:    {stats['total_rows']:,}")
    print(f"   Matched rows:            {stats['matched_rows']:,} ({matched_pct:.1f}%)")
    print(f"   Not found rows:          {stats['not_found_rows']:,} ({not_found_pct:.1f}%)")
    print(f"   Unique matched SKUs:     {stats['unique_matched_skus']:,}")
    print(f"   Unique not found SKUs:   {stats['unique_not_found_skus']:,}")
    print("=" * 70)
    print("✓ Done!")


if __name__ == '__main__':
    main()
