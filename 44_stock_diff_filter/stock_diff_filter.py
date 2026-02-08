#!/usr/bin/env python3
"""
Stock Difference Filter

Filters complete inventory to identify records that need VTEX updates by:
1. Matching against valid VTEX SKUs
2. Excluding records already processed with identical values
3. Excluding records identical to current VTEX inventory
4. Outputting only new or changed inventory records

Usage:
    python3 stock_diff_filter.py <vtex_file> <processed_file> <complete_file> <vtex_inventory_file> <output_prefix>

Example:
    python3 stock_diff_filter.py vtex_skus.xls uploaded.csv full_inventory.csv estoque.xls output

    Generates:
    - output_to_update.csv: Records needing VTEX updates
    - output_REPORT.md: Detailed statistics and analysis
"""

import csv
import json
import sys
import os
import argparse
from datetime import datetime
from collections import Counter

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False


def clean_sku(value):
    """Normalize SKU codes - strip whitespace, preserve leading zeros."""
    if value is None:
        return ''
    if PANDAS_AVAILABLE and pd.isna(value):
        return ''
    s = str(value).strip()
    # Remove .0 suffix from pandas float->string conversion
    if s.endswith('.0'):
        try:
            if float(s) == int(float(s)):
                s = str(int(float(s)))
        except (ValueError, OverflowError):
            pass
    return s


def clean_warehouse(value):
    """Normalize warehouse codes.

    - Strips whitespace
    - Removes Excel float artifacts (e.g., '95.0' -> '95')
    - Zero-pads purely numeric codes to 3 digits when length < 3 (e.g., '95' -> '095')
      This matches typical warehouse ids like 001, 021, 095, 140, 220.
    """
    if value is None:
        return ''
    # Handle pandas NaN
    if PANDAS_AVAILABLE and pd.isna(value):
        return ''

    s = str(value).strip()

    # Remove .0 suffix from pandas float->string conversion
    if s.endswith('.0'):
        try:
            if float(s) == int(float(s)):
                s = str(int(float(s)))
        except (ValueError, OverflowError):
            pass

    # Normalize purely numeric warehouses to 3 digits (keep longer ids as-is)
    if s.isdigit() and len(s) < 3:
        s = s.zfill(3)

    return s


def clean_quantity(value):
    """Normalize quantity - strip whitespace, remove leading zeros and float artifacts."""
    if value is None:
        return ''
    s = str(value).strip()
    try:
        s = str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def load_vtex_skus(file_path):
    """Load VTEX SKU reference codes from .xls export."""
    if not PANDAS_AVAILABLE:
        print("Error: pandas es requerido para leer archivos .xls")
        print("  Instalalo con: pip install pandas xlrd")
        sys.exit(1)

    if not XLRD_AVAILABLE:
        print("Error: xlrd es requerido para leer archivos .xls")
        print("  Instalalo con: pip install xlrd")
        sys.exit(1)

    if not os.path.isfile(file_path):
        print(f"Error: Archivo no encontrado: {file_path}")
        sys.exit(1)

    print(f"Cargando SKUs VTEX desde: {file_path}")

    try:
        # Read ALL sheets (some VTEX exports split data across multiple sheets)
        sheets = pd.read_excel(file_path, engine='xlrd', dtype=object, sheet_name=None)
        if not sheets:
            print(f"Error: No se encontraron hojas en el archivo: {file_path}")
            sys.exit(1)
        df = pd.concat(sheets.values(), ignore_index=True)
        print(f"  Hojas leidas: {', '.join(list(sheets.keys()))} (total filas={len(df):,})")
    except Exception as e:
        print(f"Error al leer archivo .xls: {e}")
        sys.exit(1)

    if '_SKUReferenceCode' not in df.columns:
        print(f"Error: Columna '_SKUReferenceCode' no encontrada en {file_path}")
        print(f"  Columnas disponibles: {', '.join(df.columns)}")
        sys.exit(1)

    vtex_skus = set()
    sku_id_map = {}
    skipped = 0
    sku_id_col = None
    for col in df.columns:
        if col.startswith('_SkuId'):
            sku_id_col = col
            break
    has_sku_id = sku_id_col is not None

    for _, row in df.iterrows():
        cleaned = clean_sku(row['_SKUReferenceCode'])
        if cleaned:
            vtex_skus.add(cleaned)
            if has_sku_id:
                sku_id = clean_sku(row[sku_id_col])
                if sku_id:
                    sku_id_map[cleaned] = sku_id
        else:
            skipped += 1

    print(f"  {len(vtex_skus):,} SKUs unicos cargados ({skipped:,} vacios omitidos)")
    if len(df) in (65535, 65536) and len(sheets) == 1:
        print("  [ADVERTENCIA] El archivo .xls puede estar truncado por limite de filas (65,536).")
        print("               Considera exportar a .xlsx/CSV o dividir el export.")
    if has_sku_id:
        print(f"  {len(sku_id_map):,} SKUs con _SkuId mapeado")
    else:
        print(f"  Advertencia: Columna '_SkuId' no encontrada, NDJSON no tendra _SkuId")
    if vtex_skus:
        sample = list(vtex_skus)[:5]
        print(f"  Muestra SKUs: {sample}")
    return vtex_skus, sku_id_map


def load_vtex_inventory(file_path):
    """Load current VTEX inventory from .xls export and build lookup dictionary."""
    if not PANDAS_AVAILABLE:
        print("Error: pandas es requerido para leer archivos .xls")
        print("  Instalalo con: pip install pandas xlrd")
        sys.exit(1)

    if not XLRD_AVAILABLE:
        print("Error: xlrd es requerido para leer archivos .xls")
        print("  Instalalo con: pip install xlrd")
        sys.exit(1)

    if not os.path.isfile(file_path):
        print(f"Error: Archivo no encontrado: {file_path}")
        sys.exit(1)

    print(f"\nCargando inventario VTEX actual desde: {file_path}")

    try:
        # Read ALL sheets (some VTEX exports split inventory across multiple sheets)
        sheets = pd.read_excel(file_path, engine='xlrd', dtype=object, sheet_name=None)
        if not sheets:
            print(f"Error: No se encontraron hojas en el archivo: {file_path}")
            sys.exit(1)
        df = pd.concat(sheets.values(), ignore_index=True)
        print(f"  Hojas leidas: {', '.join(list(sheets.keys()))} (total filas={len(df):,})")
    except Exception as e:
        print(f"Error al leer archivo .xls: {e}")
        sys.exit(1)

    required_cols = ['RefId', 'WarehouseId', 'TotalQuantity']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"Error: Columnas requeridas no encontradas en {file_path}")
        print(f"  Faltantes: {', '.join(missing)}")
        print(f"  Disponibles: {', '.join(df.columns)}")
        sys.exit(1)

    vtex_inventory = {}
    skipped = 0

    for _, row in df.iterrows():
        ref_id = clean_sku(row['RefId'])
        warehouse = clean_warehouse(row['WarehouseId'])
        quantity = clean_quantity(row['TotalQuantity'])

        if ref_id and warehouse:
            vtex_inventory[(ref_id, warehouse)] = quantity
        else:
            skipped += 1

    print(f"  {len(vtex_inventory):,} registros cargados ({skipped:,} incompletos omitidos)")
    # Heuristic warning for legacy .xls row limits
    # NOTE: .xls max rows is 65,536 including header; if a file is truncated you often see 65,535 data rows.
    if len(df) in (65535, 65536) and len(sheets) == 1:
        print("  [ADVERTENCIA] El archivo .xls puede estar truncado por limite de filas (65,536).")
        print("               Considera exportar a .xlsx/CSV o dividir el export.")
    if vtex_inventory:
        sample = list(vtex_inventory.items())[:3]
        print(f"  Muestra inventario VTEX: {[(k, v) for k, v in sample]}")
    return vtex_inventory


def load_processed_inventory(file_path):
    """Load processed inventory from CSV and build lookup dictionary."""
    if not os.path.isfile(file_path):
        print(f"Error: Archivo no encontrado: {file_path}")
        sys.exit(1)

    print(f"\nCargando inventario procesado desde: {file_path}")

    processed_lookup = {}
    total_records = 0
    skipped = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        required_cols = ['CODIGO SKU', 'CODIGO SUCURSAL', 'EXISTENCIA']
        if not all(col in (reader.fieldnames or []) for col in required_cols):
            print(f"Error: Columnas requeridas no encontradas en {file_path}")
            print(f"  Requeridas: {', '.join(required_cols)}")
            print(f"  Disponibles: {', '.join(reader.fieldnames or [])}")
            sys.exit(1)

        for row in reader:
            total_records += 1
            sku = clean_sku(row.get('CODIGO SKU', ''))
            warehouse = clean_warehouse(row.get('CODIGO SUCURSAL', ''))
            quantity = clean_quantity(row.get('EXISTENCIA', ''))

            if sku and warehouse:
                processed_lookup[(sku, warehouse)] = quantity
            else:
                skipped += 1

    print(f"  {len(processed_lookup):,} registros cargados de {total_records:,} filas "
          f"({skipped:,} incompletos omitidos)")
    if processed_lookup:
        sample = list(processed_lookup.items())[:3]
        print(f"  Muestra procesado: {[(k, v) for k, v in sample]}")
    return processed_lookup, total_records


def filter_complete_inventory(vtex_skus, processed_lookup, vtex_inventory_lookup, complete_file, output_prefix, sku_id_map=None):
    """Filter complete inventory to identify records needing updates."""
    if not os.path.isfile(complete_file):
        print(f"Error: Archivo no encontrado: {complete_file}")
        sys.exit(1)

    print(f"\nProcesando inventario completo: {complete_file}")
    print(f"Filtrando por SKUs VTEX y comparando con inventario procesado...")
    print("Nota: CODIGO SUCURSAL/WarehouseId se normaliza a 3 digitos (ej: 95->095, 1->001).")

    to_update = []

    total_complete = 0
    matched_vtex = 0
    omitted_identical = 0
    omitted_identical_vtex = 0
    not_in_vtex = 0
    skus_in_output = Counter()
    logged_first_vtex_mismatch = False

    with open(complete_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = [f for f in (reader.fieldnames or []) if f is not None]

        required_cols = ['CODIGO SKU', 'CODIGO SUCURSAL', 'EXISTENCIA']
        if not all(col in (fieldnames or []) for col in required_cols):
            print(f"Error: Columnas requeridas no encontradas en {complete_file}")
            print(f"  Requeridas: {', '.join(required_cols)}")
            print(f"  Disponibles: {', '.join(fieldnames or [])}")
            sys.exit(1)

        for row in reader:
            total_complete += 1
            sku = clean_sku(row.get('CODIGO SKU', ''))
            warehouse = clean_warehouse(row.get('CODIGO SUCURSAL', ''))
            quantity = clean_quantity(row.get('EXISTENCIA', ''))

            if total_complete % 100_000 == 0:
                print(f"  ... {total_complete:,} registros procesados "
                      f"(vtex={matched_vtex:,} omit_proc={omitted_identical:,} "
                      f"omit_vtex={omitted_identical_vtex:,} update={len(to_update):,})")

            if not sku or not warehouse:
                continue

            if sku not in vtex_skus:
                not_in_vtex += 1
                continue

            matched_vtex += 1
            key = (sku, warehouse)

            if key in processed_lookup and processed_lookup[key] == quantity:
                omitted_identical += 1
                if omitted_identical == 1:
                    print(f"  [LOG] Primer identico procesado: key={key} qty='{quantity}'")
                continue

            if key in vtex_inventory_lookup and vtex_inventory_lookup[key] == quantity:
                omitted_identical_vtex += 1
                if omitted_identical_vtex == 1:
                    print(f"  [LOG] Primer identico VTEX: key={key} complete_qty='{quantity}' vtex_qty='{vtex_inventory_lookup[key]}'")
                continue

            if not logged_first_vtex_mismatch and key in vtex_inventory_lookup:
                print(f"  [LOG] Primer mismatch VTEX: key={key} complete_qty='{quantity}' vtex_qty='{vtex_inventory_lookup[key]}'")
                logged_first_vtex_mismatch = True

            clean_row = {k: v for k, v in row.items() if k is not None}
            to_update.append(clean_row)
            skus_in_output[sku] += 1
            if len(to_update) == 1:
                print(f"  [LOG] Primer registro a actualizar: sku='{sku}' wh='{warehouse}' qty='{quantity}'")

    print(f"  ... {total_complete:,} registros procesados (completo)")

    # Write output CSV
    output_file = f"{output_prefix}_to_update.csv"
    report_file = f"{output_prefix}_REPORT.md"

    print(f"\n  Ecuacion: {matched_vtex:,} matched - {omitted_identical:,} ident_proc"
          f" - {omitted_identical_vtex:,} ident_vtex = {len(to_update):,} a actualizar")
    print(f"\nEscribiendo {len(to_update):,} registros en: {output_file}")
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(to_update)

    # Write NDJSON for VTEX inventory upload
    if sku_id_map is None:
        sku_id_map = {}
    ndjson_file = f"{output_prefix}_to_update.ndjson"
    ndjson_count = 0
    no_skuid_count = 0
    with open(ndjson_file, 'w', encoding='utf-8') as nf:
        for row in to_update:
            sku = clean_sku(row.get('CODIGO SKU', ''))
            warehouse = clean_warehouse(row.get('CODIGO SUCURSAL', ''))
            quantity = clean_quantity(row.get('EXISTENCIA', ''))
            sku_id = sku_id_map.get(sku)
            if sku_id is None:
                no_skuid_count += 1
                continue
            record = {
                "_SkuId": int(sku_id),
                "_SKUReferenceCode": sku,
                "warehouseId": warehouse,
                "quantity": int(quantity),
                "unlimitedQuantity": False
            }
            nf.write(json.dumps(record, ensure_ascii=False) + '\n')
            ndjson_count += 1

    print(f"Escribiendo {ndjson_count:,} registros NDJSON en: {ndjson_file}")
    if no_skuid_count > 0:
        print(f"  {no_skuid_count:,} registros omitidos del NDJSON (sin _SkuId)")

    # Statistics
    unique_skus = len(skus_in_output)
    avg_wh = len(to_update) / unique_skus if unique_skus > 0 else 0
    max_wh = max(skus_in_output.values()) if skus_in_output else 0
    min_wh = min(skus_in_output.values()) if skus_in_output else 0

    stats = {
        'total_vtex_skus': len(vtex_skus),
        'total_processed': len(processed_lookup),
        'total_vtex_inventory': len(vtex_inventory_lookup),
        'total_complete': total_complete,
        'matched_vtex': matched_vtex,
        'not_in_vtex': not_in_vtex,
        'omitted_identical': omitted_identical,
        'omitted_identical_vtex': omitted_identical_vtex,
        'to_update': len(to_update),
        'unique_skus': unique_skus,
        'avg_wh': avg_wh,
        'max_wh': max_wh,
        'min_wh': min_wh,
        'ndjson_count': ndjson_count,
        'no_skuid_count': no_skuid_count,
    }

    generate_report(report_file, stats, output_file, ndjson_file)
    print_statistics(stats, output_file, report_file, ndjson_file)


def generate_report(report_file, stats, output_file, ndjson_file):
    """Generate detailed markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    matched_pct = stats['matched_vtex'] / stats['total_complete'] * 100 if stats['total_complete'] > 0 else 0
    not_vtex_pct = stats['not_in_vtex'] / stats['total_complete'] * 100 if stats['total_complete'] > 0 else 0
    omitted_pct = stats['omitted_identical'] / stats['matched_vtex'] * 100 if stats['matched_vtex'] > 0 else 0
    omitted_vtex_pct = stats['omitted_identical_vtex'] / stats['matched_vtex'] * 100 if stats['matched_vtex'] > 0 else 0
    update_pct = stats['to_update'] / stats['matched_vtex'] * 100 if stats['matched_vtex'] > 0 else 0

    report = f"""# Reporte de Filtrado de Diferencias de Inventario

**Generado:** {timestamp}

## Resumen

Inventario completo comparado contra SKUs VTEX, registros ya procesados e inventario VTEX actual.
Solo se exportan registros nuevos o con cantidades modificadas.

## Estadisticas

### Fuentes de Datos

| Fuente | Registros |
|--------|-----------|
| SKUs en VTEX | {stats['total_vtex_skus']:,} |
| Inventario procesado | {stats['total_processed']:,} |
| Inventario VTEX actual | {stats['total_vtex_inventory']:,} |
| Inventario completo | {stats['total_complete']:,} |

### Filtrado por SKU VTEX

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Total registros analizados | {stats['total_complete']:,} | 100.0% |
| Con SKU valido en VTEX | {stats['matched_vtex']:,} | {matched_pct:.1f}% |
| SKU no encontrado en VTEX | {stats['not_in_vtex']:,} | {not_vtex_pct:.1f}% |

### Analisis de Diferencias (sobre registros con SKU VTEX)

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Identicos al procesado (omitidos) | {stats['omitted_identical']:,} | {omitted_pct:.1f}% |
| Identicos al inventario VTEX (omitidos) | {stats['omitted_identical_vtex']:,} | {omitted_vtex_pct:.1f}% |
| A actualizar (nuevos/modificados) | {stats['to_update']:,} | {update_pct:.1f}% |

### Distribucion de Almacenes en Salida

| Metrica | Valor |
|---------|-------|
| SKUs unicos a actualizar | {stats['unique_skus']:,} |
| Promedio almacenes/SKU | {stats['avg_wh']:.1f} |
| Maximo almacenes para un SKU | {stats['max_wh']} |
| Minimo almacenes para un SKU | {stats['min_wh']} |

## Archivos de Salida

- **CSV:** `{output_file}` - {stats['to_update']:,} registros ({stats['unique_skus']:,} SKUs unicos)
- **NDJSON:** `{ndjson_file}` - {stats['ndjson_count']:,} registros VTEX-ready ({stats['no_skuid_count']:,} omitidos sin _SkuId)

## Logica de Procesamiento

1. Cargar SKUs validos desde VTEX (.xls)
2. Cargar inventario ya procesado (.csv) como lookup
3. Cargar inventario VTEX actual (.xls) como lookup
4. Para cada registro del inventario completo:
   - Si SKU no existe en VTEX -> omitir
   - Si (SKU, ALMACEN, CANTIDAD) identico al procesado -> omitir
   - Si (SKU, ALMACEN, CANTIDAD) identico al inventario VTEX actual -> omitir
   - Si es nuevo o cantidad diferente -> incluir en salida

---
*Generado por stock_diff_filter.py - VTEX Integration Tools*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Reporte generado: {report_file}")


def print_statistics(stats, output_file, report_file, ndjson_file):
    """Print statistics to console."""
    tc = stats['total_complete']
    mv = stats['matched_vtex']

    print(f"\n{'='*60}")
    print(f"RESULTADOS DEL FILTRADO DE DIFERENCIAS")
    print(f"{'='*60}")
    print(f"SKUs VTEX:              {stats['total_vtex_skus']:,}")
    print(f"Inventario procesado:   {stats['total_processed']:,} registros")
    print(f"Inventario VTEX actual: {stats['total_vtex_inventory']:,} registros")
    print(f"Inventario completo:    {tc:,} registros")
    print(f"{'='*60}")
    print(f"Con SKU VTEX:           {mv:,} ({mv/tc*100:.1f}%)" if tc > 0 else f"Con SKU VTEX:           {mv:,}")
    print(f"Sin SKU VTEX:           {stats['not_in_vtex']:,} ({stats['not_in_vtex']/tc*100:.1f}%)" if tc > 0 else f"Sin SKU VTEX:           {stats['not_in_vtex']:,}")
    print(f"{'='*60}")
    print(f"Identicos proc (omit): {stats['omitted_identical']:,} ({stats['omitted_identical']/mv*100:.1f}%)" if mv > 0 else f"Identicos proc (omit): {stats['omitted_identical']:,}")
    print(f"Identicos VTEX (omit): {stats['omitted_identical_vtex']:,} ({stats['omitted_identical_vtex']/mv*100:.1f}%)" if mv > 0 else f"Identicos VTEX (omit): {stats['omitted_identical_vtex']:,}")
    print(f"A actualizar:           {stats['to_update']:,} ({stats['to_update']/mv*100:.1f}%)" if mv > 0 else f"A actualizar:           {stats['to_update']:,}")
    print(f"  SKUs unicos:          {stats['unique_skus']:,}")
    if stats['unique_skus'] > 0:
        print(f"  Almacenes/SKU:        {stats['avg_wh']:.1f} prom, {stats['max_wh']} max, {stats['min_wh']} min")
    print(f"{'='*60}")
    print(f"NDJSON:                 {stats['ndjson_count']:,} registros")
    if stats['no_skuid_count'] > 0:
        print(f"  Sin _SkuId (omitidos): {stats['no_skuid_count']:,}")
    print(f"{'='*60}")
    print(f"\nArchivos generados:")
    print(f"  {output_file}")
    print(f"  {ndjson_file}")
    print(f"  {report_file}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description='Filtra inventario completo para identificar registros que necesitan actualizacion en VTEX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  python3 stock_diff_filter.py vtex_skus.xls uploaded.csv full_inventory.csv estoque.xls output
  python3 stock_diff_filter.py vtex_export.xls procesado.csv completo.csv inventario_vtex.xls resultado

Archivos de Salida (usando prefijo "output"):
  - output_to_update.csv    Registros que necesitan actualizacion
  - output_REPORT.md        Reporte de estadisticas

Logica:
  1. Cargar SKUs validos desde VTEX (archivo .xls, columna _SKUReferenceCode)
  2. Cargar inventario ya procesado (CSV con CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)
  3. Cargar inventario VTEX actual (archivo .xls, columnas RefId, WarehouseId, TotalQuantity)
  4. Del inventario completo, extraer solo registros donde:
     - El SKU existe en VTEX
     - Y el (SKU, ALMACEN, CANTIDAD) NO es identico al ya procesado
     - Y el (SKU, ALMACEN, CANTIDAD) NO es identico al inventario VTEX actual
        '''
    )

    parser.add_argument('vtex_file',
                        help='Archivo .xls con SKUs VTEX (columna _SKUReferenceCode)')
    parser.add_argument('processed_file',
                        help='CSV con inventario ya procesado (CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)')
    parser.add_argument('complete_file',
                        help='CSV con inventario completo (CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)')
    parser.add_argument('vtex_inventory_file',
                        help='Archivo .xls con inventario VTEX actual (RefId, WarehouseId, TotalQuantity)')
    parser.add_argument('output_prefix',
                        help='Prefijo para archivos de salida')

    args = parser.parse_args()

    for label, path in [('VTEX', args.vtex_file),
                        ('Procesado', args.processed_file),
                        ('Completo', args.complete_file),
                        ('Inventario VTEX', args.vtex_inventory_file)]:
        if not os.path.exists(path):
            print(f"Error: Archivo {label} no encontrado: {path}")
            sys.exit(1)

    print(f"{'='*60}")
    print(f"FILTRO DE DIFERENCIAS DE INVENTARIO")
    print(f"{'='*60}")

    vtex_skus, sku_id_map = load_vtex_skus(args.vtex_file)
    processed_lookup, _ = load_processed_inventory(args.processed_file)
    vtex_inventory_lookup = load_vtex_inventory(args.vtex_inventory_file)
    filter_complete_inventory(vtex_skus, processed_lookup, vtex_inventory_lookup, args.complete_file, args.output_prefix, sku_id_map)


if __name__ == '__main__':
    main()
