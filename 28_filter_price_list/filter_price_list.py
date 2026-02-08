#!/usr/bin/env python3
"""
VTEX Price List Filter

Filters a price list CSV to include only products that exist in VTEX.
Matches "_SKUReferenceCode" from VTEX products with "código producto" from price list.

Usage:
    python3 filter_price_list.py <vtex_products> <price_list> <output_prefix>

    vtex_products: CSV or JSON file with VTEX products (must have "_SKUReferenceCode" field)
    price_list: CSV file with price data (must have "código producto" field)
    output_prefix: Prefix for output files (will generate multiple files)

Example:
    python3 filter_price_list.py vtex_skus.csv prices.csv output

    Generates:
    - output_matched.csv: Prices with matching VTEX SKUs
    - output_vtex_without_price.csv: VTEX SKUs without prices
    - output_prices_without_sku.csv: Prices without VTEX SKUs
    - output_REPORT.md: Detailed statistics report

Output:
    - 3 CSV files with matched/unmatched data
    - 1 Markdown report with complete statistics
"""

import json
import csv
import sys
import argparse
from datetime import datetime


def _clean_fieldnames(fieldnames):
    """Remove empty/None headers that can appear in malformed CSVs."""
    if not fieldnames:
        return fieldnames
    return [fn for fn in fieldnames if fn is not None and str(fn).strip() != '']


def _sanitize_row(row):
    """Drop DictReader's extra-fields bucket (key None) to avoid DictWriter errors."""
    if row is None:
        return row
    if None in row:
        # DictReader stores extra columns (beyond header count) under key None
        row.pop(None, None)
    return row


def _is_missing_price(row, candidate_fields):
    """Return True if the row has no usable price value in any candidate field."""
    if not row or not candidate_fields:
        return False

    def _to_number(v):
        if v is None:
            return None
        s = str(v).strip()
        if s == '':
            return None
        # Normalize common formats: "1.234,56" or "1,234.56"
        s = s.replace(' ', '')
        if ',' in s and '.' in s:
            # Assume thousands separator is the first one that appears earlier
            if s.find('.') < s.find(','):
                # "1.234,56" -> "1234.56"
                s = s.replace('.', '').replace(',', '.')
            else:
                # "1,234.56" -> "1234.56"
                s = s.replace(',', '')
        else:
            # If only comma, treat as decimal separator
            if ',' in s and '.' not in s:
                s = s.replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None

    for field in candidate_fields:
        if field in row:
            n = _to_number(row.get(field))
            if n is not None and n > 0:
                return False
    return True


def load_vtex_data(file_path):
    """
    Load VTEX SKU data from CSV or JSON file.

    Args:
        file_path: Path to VTEX products file (CSV or JSON)

    Returns:
        tuple: (dict of SKU ID -> full row data, fieldnames list)
    """
    vtex_data = {}
    fieldnames = []

    # Determine file type by extension
    if file_path.lower().endswith('.json'):
        # Load from JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Handle both list and dict formats
            if isinstance(data, list):
                if data:
                    fieldnames = list(data[0].keys())
                for item in data:
                    if '_SKUReferenceCode' in item:
                        sku_id = str(item['_SKUReferenceCode']).strip()
                        if sku_id:
                            vtex_data[sku_id] = item
            elif isinstance(data, dict):
                for item in data.values():
                    if isinstance(item, dict) and '_SKUReferenceCode' in item:
                        if not fieldnames and item:
                            fieldnames = list(item.keys())
                        sku_id = str(item['_SKUReferenceCode']).strip()
                        if sku_id:
                            vtex_data[sku_id] = item

    else:
        # Load from CSV
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Check if required field exists
            if '_SKUReferenceCode' not in fieldnames:
                print(f"Error: Field '_SKUReferenceCode' not found in {file_path}")
                print(f"Available fields: {', '.join(fieldnames)}")
                sys.exit(1)

            for row in reader:
                sku_id = str(row['_SKUReferenceCode']).strip()
                if sku_id:
                    vtex_data[sku_id] = row

    fieldnames = _clean_fieldnames(fieldnames)

    return vtex_data, fieldnames


def filter_price_list(vtex_file, price_file, output_prefix):
    """
    Filter price list and generate multiple output files.

    Args:
        vtex_file: Path to VTEX products file (CSV or JSON)
        price_file: Path to price list CSV
        output_prefix: Prefix for output files
    """
    print(f"Cargando datos de SKU VTEX desde: {vtex_file}")
    vtex_data, vtex_fieldnames = load_vtex_data(vtex_file)
    print(f"Cargados {len(vtex_data)} IDs de SKU únicos desde VTEX")

    print(f"\nProcesando lista de precios: {price_file}")

    matched_prices = []
    unmatched_prices = []
    found_sku_ids = set()
    matched_without_price = []

    # Read price list
    with open(price_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        price_fieldnames = _clean_fieldnames(reader.fieldnames)

        if not price_fieldnames:
            print(f"Error: Could not detect headers in {price_file}. Is the file empty or missing a header row?")
            sys.exit(1)

        # Check if required field exists
        if 'código producto' not in price_fieldnames:
            print(f"Error: Field 'código producto' not found in {price_file}")
            print(f"Available fields: {', '.join(price_fieldnames)}")
            sys.exit(1)

        # Heuristic: detect possible price columns in the price list
        lowered = {fn.lower(): fn for fn in price_fieldnames}
        preferred = [
            'precio', 'price', 'valor', 'value', 'precio lista', 'precio_lista',
            'precio_unitario', 'precio unitario', 'precio final', 'precio_final',
            'precio venta', 'precio_venta', 'pvp', 'p. venta'
        ]
        candidate_price_fields = [lowered[k] for k in preferred if k in lowered]
        if not candidate_price_fields:
            # Fallback: any column containing 'precio' or 'price'
            for fn in price_fieldnames:
                lfn = fn.lower()
                if 'precio' in lfn or 'price' in lfn:
                    candidate_price_fields.append(fn)

        # Filter rows
        for row in reader:
            row = _sanitize_row(row)
            codigo = str(row['código producto']).strip()

            if codigo in vtex_data:
                matched_prices.append(row)
                found_sku_ids.add(codigo)

                # Also capture SKUs found but missing/empty price
                if _is_missing_price(row, candidate_price_fields):
                    matched_without_price.append(row)
            else:
                unmatched_prices.append(row)

    # Find VTEX SKUs without prices
    vtex_without_price = []
    for sku_id, sku_data in vtex_data.items():
        if sku_id not in found_sku_ids:
            vtex_without_price.append(sku_data)

    # Generate output filenames
    matched_file = f"{output_prefix}_matched.csv"
    matched_missing_price_file = f"{output_prefix}_matched_missing_price.csv"
    vtex_no_price_file = f"{output_prefix}_vtex_without_price.csv"
    prices_no_sku_file = f"{output_prefix}_prices_without_sku.csv"
    report_file = f"{output_prefix}_REPORT.md"

    # Write matched prices
    print(f"\nEscribiendo precios coincidentes en: {matched_file}")
    with open(matched_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=price_fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(matched_prices)

    # Write matched SKUs but with missing/empty price
    print(f"Escribiendo SKUs encontrados pero sin precio en: {matched_missing_price_file}")
    with open(matched_missing_price_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=price_fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(matched_without_price)

    # Write VTEX SKUs without prices
    print(f"Escribiendo SKUs de VTEX sin precios en: {vtex_no_price_file}")
    with open(vtex_no_price_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=_clean_fieldnames(vtex_fieldnames), extrasaction='ignore')
        writer.writeheader()
        writer.writerows(vtex_without_price)

    # Write prices without VTEX SKUs
    print(f"Escribiendo precios sin SKUs de VTEX en: {prices_no_sku_file}")
    with open(prices_no_sku_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=price_fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(unmatched_prices)

    # Calculate statistics
    total_vtex = len(vtex_data)
    total_prices = len(matched_prices) + len(unmatched_prices)
    matched_count = len(matched_prices)
    matched_missing_price_count = len(matched_without_price)
    vtex_no_price_count = len(vtex_without_price)
    prices_no_sku_count = len(unmatched_prices)

    # Generate report
    print(f"Generando reporte: {report_file}")
    generate_report(
        report_file,
        vtex_file,
        price_file,
        total_vtex,
        total_prices,
        matched_count,
        matched_missing_price_count,
        vtex_no_price_count,
        prices_no_sku_count,
        matched_file,
        matched_missing_price_file,
        vtex_no_price_file,
        prices_no_sku_file
    )

    # Print statistics
    print(f"\n{'='*70}")
    print(f"RESULTADOS DEL FILTRADO")
    print(f"{'='*70}")
    print(f"SKUs VTEX:")
    print(f"  Total en VTEX:               {total_vtex}")
    print(f"  Con precios (coincidentes):  {matched_count} ({matched_count/total_vtex*100:.1f}%)")
    print(f"  Encontrados pero sin precio: {matched_missing_price_count} ({matched_missing_price_count/total_vtex*100:.1f}%)")
    print(f"  Sin precios:                 {vtex_no_price_count} ({vtex_no_price_count/total_vtex*100:.1f}%)")
    print(f"\nLista de Precios:")
    print(f"  Total de precios:            {total_prices}")
    print(f"  Con SKU VTEX (coincidentes): {matched_count} ({matched_count/total_prices*100:.1f}%)")
    print(f"  Sin SKU VTEX:                {prices_no_sku_count} ({prices_no_sku_count/total_prices*100:.1f}%)")
    print(f"{'='*70}")
    print(f"\nArchivos de Salida Generados:")
    print(f"  1. {matched_file}")
    print(f"  2. {matched_missing_price_file}")
    print(f"  3. {vtex_no_price_file}")
    print(f"  4. {prices_no_sku_file}")
    print(f"  5. {report_file}")
    print(f"{'='*70}")


def generate_report(report_file, vtex_file, price_file, total_vtex, total_prices,
                    matched_count, matched_missing_price_count, vtex_no_price_count, prices_no_sku_count,
                    matched_file, matched_missing_price_file, vtex_no_price_file, prices_no_sku_file):
    """
    Generate a detailed markdown report.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Reporte de Filtrado de Lista de Precios VTEX

**Generado:** {timestamp}

## Archivos de Entrada

- **Productos VTEX:** `{vtex_file}`
- **Lista de Precios:** `{price_file}`

## Estadísticas Resumidas

### Análisis de SKUs VTEX

| Métrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Total de SKUs VTEX | {total_vtex} | 100.0% |
| SKUs con precios (coincidentes) | {matched_count} | {matched_count/total_vtex*100:.1f}% |
| SKUs encontrados pero sin precio | {matched_missing_price_count} | {matched_missing_price_count/total_vtex*100:.1f}% |
| SKUs sin precios | {vtex_no_price_count} | {vtex_no_price_count/total_vtex*100:.1f}% |

### Análisis de Lista de Precios

| Métrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Total de entradas de precios | {total_prices} | 100.0% |
| Precios con SKU VTEX (coincidentes) | {matched_count} | {matched_count/total_prices*100:.1f}% |
| Precios sin SKU VTEX | {prices_no_sku_count} | {prices_no_sku_count/total_prices*100:.1f}% |

## Archivos de Salida

### 1. Registros Coincidentes
**Archivo:** `{matched_file}`
**Descripción:** Entradas de precios que tienen SKUs VTEX correspondientes
**Registros:** {matched_count}

Estos son precios que pueden ser aplicados a productos VTEX existentes.

### 2. SKUs Encontrados Pero Sin Precio
**Archivo:** `{matched_missing_price_file}`
**Descripción:** Entradas que sí coinciden con SKU VTEX pero no tienen valor de precio (vacío o 0) en columnas detectadas
**Registros:** {matched_missing_price_count}

Estos registros requieren corrección de la lista de precios antes de aplicar precios en VTEX.

### 3. SKUs VTEX Sin Precios
**Archivo:** `{vtex_no_price_file}`
**Descripción:** SKUs VTEX que no tienen entradas de precio correspondientes
**Registros:** {vtex_no_price_count}

Estos son productos en VTEX que carecen de información de precios. Acción requerida: Agregar precios para estos SKUs.

### 4. Precios Sin SKUs VTEX
**Archivo:** `{prices_no_sku_file}`
**Descripción:** Entradas de precios que no tienen SKUs VTEX correspondientes
**Registros:** {prices_no_sku_count}

Estos son precios para productos que aún no existen en VTEX. Acción requerida: Crear estos productos en VTEX antes de aplicar precios.

## Recomendaciones

### Si SKUs Encontrados Pero Sin Precio > 0
- Revisar los {matched_missing_price_count} registros en `{matched_missing_price_file}`
- Corregir/llenar el valor de precio en la lista de precios (precio vacío o 0)
- Re-ejecutar el filtro

### Si SKUs VTEX Sin Precios > 0
- Revisar los {vtex_no_price_count} SKUs en `{vtex_no_price_file}`
- Agregar información de precios para estos productos
- Re-ejecutar el filtro para asegurar que todos los productos tengan precios

### Si Precios Sin SKUs VTEX > 0
- Revisar las {prices_no_sku_count} entradas en `{prices_no_sku_file}`
- Crear estos productos en VTEX usando el flujo de creación de productos
- Después de la creación, re-ejecutar el filtro para emparejar los nuevos precios

## Lógica de Emparejamiento

- **Campo de Emparejamiento (VTEX):** `_SKUReferenceCode`
- **Campo de Emparejamiento (Precios):** `código producto`
- **Tipo de Emparejamiento:** Coincidencia exacta de cadena (sensible a mayúsculas, espacios en blanco recortados)

---

*Generado por Filtro de Lista de Precios VTEX*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)


def main():
    parser = argparse.ArgumentParser(
        description='Filter price list and generate comprehensive reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 filter_price_list.py vtex_products.csv prices.csv output
  python3 filter_price_list.py vtex_products.json prices.csv results

Output Files (using prefix "output"):
  - output_matched.csv: Prices with matching VTEX SKUs
  - output_vtex_without_price.csv: VTEX SKUs without prices
  - output_prices_without_sku.csv: Prices without VTEX SKUs
  - output_REPORT.md: Detailed statistics report

Input Requirements:
  - VTEX file must have "_SKUReferenceCode" field
  - Price list must have "código producto" field
  - Both files must be UTF-8 encoded
        '''
    )

    parser.add_argument('vtex_file', help='VTEX products file (CSV or JSON)')
    parser.add_argument('price_file', help='Price list CSV file')
    parser.add_argument('output_prefix', help='Prefix for output files')

    args = parser.parse_args()

    # Validate input files exist
    import os
    if not os.path.exists(args.vtex_file):
        print(f"Error: VTEX file not found: {args.vtex_file}")
        sys.exit(1)

    if not os.path.exists(args.price_file):
        print(f"Error: Price list file not found: {args.price_file}")
        sys.exit(1)

    # Run filter
    filter_price_list(args.vtex_file, args.price_file, args.output_prefix)


if __name__ == '__main__':
    main()
