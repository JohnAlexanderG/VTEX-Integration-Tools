#!/usr/bin/env python3
"""
SKU ProductId Matcher

Matches SKU field from data file with _SKUReferenceCode from mapping file
and outputs CSV with all data fields plus _ProductId.

Usage:
    python3 sku_productid_matcher.py mapping_file data_file output.csv

Example:
    python3 sku_productid_matcher.py skus.json products.json output.csv
    python3 sku_productid_matcher.py skus.csv products.csv output.csv
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime


def load_file(file_path):
    """Load JSON or CSV file based on extension."""
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo '{file_path}' no existe")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif ext in ['.csv', '.xls', '.xlsx']:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = [row for row in reader]
        else:
            print(f"❌ Error: Extensión '{ext}' no soportada. Use .json o .csv")
            sys.exit(1)

        if not isinstance(data, list):
            print(f"❌ Error: El archivo debe contener una lista de registros")
            sys.exit(1)

        return data

    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido en '{file_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al leer '{file_path}': {e}")
        sys.exit(1)


def clean_value(value):
    """Clean and normalize a value for matching."""
    if value is None:
        return ''
    return str(value).strip()


def build_mapping(mapping_data):
    """Build dictionary mapping _SKUReferenceCode -> _ProductId."""
    mapping = {}

    # Check for required field
    if not mapping_data:
        print("❌ Error: El archivo de mapeo está vacío")
        sys.exit(1)

    sample = mapping_data[0]
    if '_SKUReferenceCode' not in sample:
        print(f"❌ Error: Campo '_SKUReferenceCode' no encontrado en archivo de mapeo")
        print(f"   Campos disponibles: {list(sample.keys())}")
        sys.exit(1)

    if '_ProductId' not in sample:
        print(f"❌ Error: Campo '_ProductId' no encontrado en archivo de mapeo")
        print(f"   Campos disponibles: {list(sample.keys())}")
        sys.exit(1)

    for item in mapping_data:
        ref_code = clean_value(item.get('_SKUReferenceCode'))
        product_id = clean_value(item.get('_ProductId'))

        if ref_code and ref_code != 'None':
            mapping[ref_code] = product_id

    return mapping


def process_data(data, mapping):
    """Process data file and add _ProductId from mapping."""
    if not data:
        print("❌ Error: El archivo de datos está vacío")
        sys.exit(1)

    sample = data[0]
    if 'SKU' not in sample:
        print(f"❌ Error: Campo 'SKU' no encontrado en archivo de datos")
        print(f"   Campos disponibles: {list(sample.keys())}")
        sys.exit(1)

    results = []
    not_matched_list = []

    for item in data:
        sku = clean_value(item.get('SKU'))

        # Copy all fields from original record
        result = item.copy()

        # Add _ProductId from mapping
        if sku in mapping:
            result['_ProductId'] = mapping[sku]
        else:
            result['_ProductId'] = ''
            not_matched_list.append(item.copy())

        results.append(result)

    matched = len(results) - len(not_matched_list)
    return results, matched, not_matched_list


def export_csv(data, output_path):
    """Export data to CSV file."""
    if not data:
        print("⚠️ No hay datos para exportar")
        return

    # Get all unique keys, with _ProductId first
    keys = list(data[0].keys())
    if '_ProductId' in keys:
        keys.remove('_ProductId')
        keys.insert(0, '_ProductId')

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for item in data:
            writer.writerow(item)

    print(f"✅ Archivo exportado: {output_path}")


def generate_report(output_path, stats, not_matched_list):
    """Generate markdown report with statistics."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# SKU ProductId Matcher - Reporte\n\n")
        f.write(f"**Fecha:** {stats['timestamp']}\n\n")

        f.write("## Archivos procesados\n\n")
        f.write(f"- **Archivo de mapeo:** `{stats['mapping_file']}` ({stats['mapping_count']} registros)\n")
        f.write(f"- **Archivo de datos:** `{stats['data_file']}` ({stats['data_count']} registros)\n")
        f.write(f"- **Referencias en mapeo:** {stats['mapping_refs']} referencias unicas\n\n")

        f.write("## Resultados\n\n")
        f.write(f"| Metrica | Valor |\n")
        f.write(f"|---------|-------|\n")
        f.write(f"| Total registros | {stats['total']} |\n")
        f.write(f"| Con _ProductId | {stats['matched']} |\n")
        f.write(f"| Sin match | {stats['not_matched']} |\n")
        f.write(f"| Tasa de match | {stats['match_rate']:.1f}% |\n\n")

        f.write("## Archivos generados\n\n")
        f.write(f"- `{stats['output_file']}` - Resultados completos\n")
        if stats['not_matched'] > 0:
            f.write(f"- `{stats['no_match_file']}` - Registros sin match\n")
        f.write(f"- `{stats['report_file']}` - Este reporte\n\n")

        if not_matched_list:
            f.write("## SKUs sin match\n\n")
            f.write("| # | SKU |\n")
            f.write("|---|-----|\n")
            for i, item in enumerate(not_matched_list, 1):
                sku = item.get('SKU', 'N/A')
                f.write(f"| {i} | {sku} |\n")

    print(f"✅ Reporte generado: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Match SKU con _SKUReferenceCode y agregar _ProductId al archivo de salida'
    )
    parser.add_argument('mapping_file',
                        help='Archivo con _SkuId, _SKUReferenceCode, _ProductId')
    parser.add_argument('data_file',
                        help='Archivo con campo SKU a enriquecer')
    parser.add_argument('output_file',
                        help='Archivo CSV de salida')

    args = parser.parse_args()

    # Generate additional output file names
    base_name = os.path.splitext(args.output_file)[0]
    no_match_file = f"{base_name}_no_match.csv"
    report_file = f"{base_name}_report.md"

    print("=" * 60)
    print("🔧 SKU ProductId Matcher")
    print("=" * 60)
    print(f"\n📋 Configuración:")
    print(f"   Archivo de mapeo: {args.mapping_file}")
    print(f"   Archivo de datos: {args.data_file}")
    print(f"   Archivo de salida: {args.output_file}")
    print()

    # Load files
    print("📂 Cargando archivos...")
    mapping_data = load_file(args.mapping_file)
    print(f"   ✓ Archivo de mapeo: {len(mapping_data)} registros")

    data = load_file(args.data_file)
    print(f"   ✓ Archivo de datos: {len(data)} registros")
    print()

    # Build mapping
    print("🔗 Construyendo mapeo _SKUReferenceCode -> _ProductId...")
    mapping = build_mapping(mapping_data)
    print(f"   ✓ {len(mapping)} referencias únicas en mapeo")
    print()

    # Process data
    print("🔍 Procesando datos...")
    results, matched, not_matched_list = process_data(data, mapping)
    not_matched = len(not_matched_list)
    print()

    # Export results (only matched records)
    print("💾 Exportando resultados...")
    matched_results = [r for r in results if r.get('_ProductId')]
    export_csv(matched_results, args.output_file)

    # Export not matched records
    if not_matched_list:
        export_csv(not_matched_list, no_match_file)

    # Calculate match rate
    match_rate = (matched / len(results)) * 100 if results else 0

    # Generate report
    stats = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'mapping_file': args.mapping_file,
        'data_file': args.data_file,
        'mapping_count': len(mapping_data),
        'data_count': len(data),
        'mapping_refs': len(mapping),
        'total': len(results),
        'matched': matched,
        'not_matched': not_matched,
        'match_rate': match_rate,
        'output_file': args.output_file,
        'no_match_file': no_match_file,
        'report_file': report_file
    }
    generate_report(report_file, stats, not_matched_list)

    # Summary
    print()
    print("=" * 60)
    print("📊 Resumen")
    print("=" * 60)
    print(f"   Total registros: {len(results)}")
    print(f"   ✅ Con _ProductId: {matched}")
    print(f"   ⚠️ Sin match: {not_matched}")
    print(f"   📈 Tasa de match: {match_rate:.1f}%")
    print()
    print("✓ Proceso completado exitosamente")


if __name__ == '__main__':
    main()
