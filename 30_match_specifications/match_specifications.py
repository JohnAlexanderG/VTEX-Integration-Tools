#!/usr/bin/env python3
"""
match_specifications.py

Compara y combina especificaciones de categoría y producto basándose en SKU.

Lee dos archivos CSV con datos de especificaciones y genera dos o tres salidas:
1. Especificaciones combinadas donde los SKUs coinciden (todas las columnas incluyendo _ProductId)
2. Especificaciones de productos sin categoría correspondiente (con _ProductId)
3. (Opcional) Especificaciones combinadas sin duplicados por ID

Funcionalidad:
- Normaliza SKUs para matching robusto (maneja comillas, espacios, formatos)
- Combina columnas de ambos archivos sin duplicar SKU
- Preserva campo _ProductId del archivo de productos en las salidas
- Deduplicación opcional por columna ID (conserva primera ocurrencia)
- Genera nombres de archivo con fecha automática
- Reporta estadísticas detalladas de matching y deduplicación

Ejecución:
    python3 match_specifications.py categorias.csv productos.csv

    Opciones:
    --sku-column NOMBRE      Nombre de columna SKU (default: "SKU")
    --deduplicate            Generar archivo sin duplicados por ID
    --id-column NOMBRE       Nombre de columna ID (default: "ID")

Ejemplos:
    # Matching básico
    python3 match_specifications.py specs_cat.csv specs_prod.csv

    # Con deduplicación
    python3 match_specifications.py specs_cat.csv specs_prod.csv --deduplicate

    # Con columna ID personalizada
    python3 match_specifications.py specs_cat.csv specs_prod.csv \
        --deduplicate --id-column "ProductID"

    Genera (sin deduplicación):
    - matched_specs_20260107.csv
    - unmatched_specs_20260107.csv

    Genera (con deduplicación):
    - matched_specs_20260107.csv
    - unmatched_specs_20260107.csv
    - matched_specs_unique_20260107.csv

Requisitos de entrada:
- Ambos archivos deben tener columna SKU (nombre configurable)
- Para deduplicación: archivo debe tener columna ID (nombre configurable)
- Encoding UTF-8
- Formato CSV válido
"""

import csv
import sys
import argparse
import os
from datetime import datetime


def normalize_sku(sku_value):
    """Normaliza un valor SKU removiendo comillas, espacios extras y convirtiendo a string.

    Esta función maneja múltiples formatos de SKU que pueden aparecer en CSV:
    - Con comillas dobles: "000013" → 000013
    - Con comillas simples: '000013' → 000013
    - Con espacios: " 000013 " → 000013
    - Valores numéricos: 13 → 13 (se preserva el formato original)

    Args:
        sku_value: Valor SKU a normalizar (puede ser str, int, float)

    Returns:
        str: SKU normalizado sin comillas ni espacios extras
    """
    if sku_value is None:
        return ""

    # Convertir a string si es necesario
    sku_str = str(sku_value)

    # Remover espacios al inicio y final
    sku_str = sku_str.strip()

    # Remover comillas dobles y simples al inicio y final
    # Esto maneja casos como: "000013", '000013', "000-013"
    sku_str = sku_str.strip('"').strip("'")

    # Remover espacios nuevamente por si había comillas con espacios: " '000013' "
    sku_str = sku_str.strip()

    return sku_str


def load_csv_with_validation(file_path, sku_column):
    """Carga un archivo CSV y valida que tenga la columna SKU requerida.

    Args:
        file_path: Ruta al archivo CSV
        sku_column: Nombre de la columna SKU a validar

    Returns:
        tuple: (lista de filas como diccionarios, lista de nombres de columnas)

    Raises:
        SystemExit: Si el archivo no existe o falta la columna SKU
    """
    # Validar que el archivo existe
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Validar que la columna SKU existe
            if sku_column not in fieldnames:
                print(f"Error: '{sku_column}' column not found in {file_path}")
                print(f"Available fields: {', '.join(fieldnames)}")
                sys.exit(1)

            # Leer todas las filas
            rows = list(reader)

        return rows, fieldnames

    except Exception as e:
        print(f"Error reading CSV file {file_path}: {e}")
        sys.exit(1)


def match_specifications(category_file, product_file, sku_column):
    """Compara especificaciones de categoría y producto por SKU.

    Args:
        category_file: Ruta al archivo CSV de especificaciones de categoría
        product_file: Ruta al archivo CSV de especificaciones de producto
        sku_column: Nombre de la columna SKU en ambos archivos

    Returns:
        tuple: (matched_rows, unmatched_rows, category_fieldnames, product_fieldnames, category_data)
    """
    print(f"Loading category specifications from: {category_file}")
    category_rows, category_fieldnames = load_csv_with_validation(category_file, sku_column)
    print(f"Loaded {len(category_rows)} category specification records")

    print(f"\nLoading product specifications from: {product_file}")
    product_rows, product_fieldnames = load_csv_with_validation(product_file, sku_column)
    print(f"Loaded {len(product_rows)} product specification records")

    # Crear diccionario de mapeo SKU -> datos de categoría
    # Si hay SKUs duplicados, la última ocurrencia sobrescribe
    category_data = {}
    skipped_empty_skus_cat = 0

    for row in category_rows:
        sku = normalize_sku(row.get(sku_column, ''))
        if sku == '':
            skipped_empty_skus_cat += 1
            continue
        category_data[sku] = row

    if skipped_empty_skus_cat > 0:
        print(f"  Skipped {skipped_empty_skus_cat} category records with empty SKU")

    print(f"  Unique category SKUs: {len(category_data)}")

    # Procesar productos y clasificar en matched/unmatched
    matched_rows = []
    unmatched_rows = []
    skipped_empty_skus_prod = 0

    for row in product_rows:
        sku = normalize_sku(row.get(sku_column, ''))

        if sku == '':
            skipped_empty_skus_prod += 1
            continue

        if sku in category_data:
            # Combinar datos: categoría + producto
            # Crear nuevo diccionario con todas las columnas
            merged_row = {}

            # Primero agregar SKU
            merged_row[sku_column] = sku

            # Agregar columnas de categoría (excepto SKU)
            for field in category_fieldnames:
                if field != sku_column:
                    merged_row[field] = category_data[sku].get(field, '')

            # Agregar columnas de producto (excepto SKU)
            for field in product_fieldnames:
                if field != sku_column:
                    merged_row[field] = row.get(field, '')

            matched_rows.append(merged_row)
        else:
            unmatched_rows.append(row)

    if skipped_empty_skus_prod > 0:
        print(f"  Skipped {skipped_empty_skus_prod} product records with empty SKU")

    return matched_rows, unmatched_rows, category_fieldnames, product_fieldnames, category_data


def write_csv_output(file_path, rows, fieldnames):
    """Escribe filas a un archivo CSV con los nombres de columna especificados.

    Args:
        file_path: Ruta del archivo de salida
        rows: Lista de diccionarios con los datos
        fieldnames: Lista de nombres de columnas en el orden deseado
    """
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_by_id(rows, id_column, fieldnames):
    """Elimina registros duplicados conservando la primera ocurrencia por ID.

    Args:
        rows: Lista de diccionarios con los datos
        id_column: Nombre de la columna ID para identificar duplicados
        fieldnames: Lista de nombres de columnas para validación

    Returns:
        tuple: (unique_rows, duplicates_count)

    Raises:
        SystemExit: Si la columna ID no existe en los datos
    """
    # Validar que la columna ID existe
    if id_column not in fieldnames:
        print(f"Error: '{id_column}' column not found in matched results")
        print(f"Available fields: {', '.join(fieldnames)}")
        sys.exit(1)

    seen_ids = set()
    unique_rows = []
    duplicates_count = 0
    skipped_empty_ids = 0

    for row in rows:
        id_value = str(row.get(id_column, '')).strip()

        # Saltar registros sin ID
        if not id_value or id_value == '':
            skipped_empty_ids += 1
            continue

        # Si es primera ocurrencia, agregar
        if id_value not in seen_ids:
            seen_ids.add(id_value)
            unique_rows.append(row)
        else:
            duplicates_count += 1

    if skipped_empty_ids > 0:
        print(f"  Skipped {skipped_empty_ids} record(s) with empty {id_column}")

    return unique_rows, duplicates_count


def print_statistics(total_cat, unique_cat, total_prod, matched_count, unmatched_count,
                    matched_file, unmatched_file, unique_file=None,
                    unique_count=0, duplicates_removed=0, id_column=None):
    """Imprime estadísticas detalladas del proceso de matching.

    Args:
        total_cat: Total de registros en archivo de categorías
        unique_cat: SKUs únicos en archivo de categorías
        total_prod: Total de registros en archivo de productos
        matched_count: Cantidad de productos con match
        unmatched_count: Cantidad de productos sin match
        matched_file: Ruta del archivo de coincidencias
        unmatched_file: Ruta del archivo de no encontrados
        unique_file: Ruta del archivo deduplicado (opcional)
        unique_count: Cantidad de registros únicos (opcional)
        duplicates_removed: Cantidad de duplicados removidos (opcional)
        id_column: Nombre de columna ID usada para deduplicación (opcional)
    """
    # Calcular porcentajes
    match_pct = (matched_count / total_prod * 100) if total_prod > 0 else 0
    unmatch_pct = (unmatched_count / total_prod * 100) if total_prod > 0 else 0

    print(f"\n{'='*70}")
    print(f"CSV SPECIFICATION MATCHING RESULTS")
    print(f"{'='*70}")
    print(f"\nFile 1 (Category Specifications):")
    print(f"  Total records:                {total_cat:,}")
    print(f"  Unique SKUs:                  {unique_cat:,}")

    print(f"\nFile 2 (Product Specifications):")
    print(f"  Total records:                {total_prod:,}")
    print(f"  Matched with File 1:          {matched_count:,} ({match_pct:.1f}%)")
    print(f"  Not found in File 1:          {unmatched_count:,} ({unmatch_pct:.1f}%)")

    print(f"\nOutput Files Generated:")
    print(f"  1. {matched_file}")
    print(f"  2. {unmatched_file}")

    # Si hay deduplicación, agregar información adicional
    if unique_file:
        print(f"  3. {unique_file} ({duplicates_removed} duplicate(s) removed)")

        print(f"\nDeduplication Summary:")
        print(f"  Original matched records:     {matched_count:,}")
        print(f"  Unique records by '{id_column}':    {unique_count:,}")
        print(f"  Duplicates removed:           {duplicates_removed:,}")

    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description='Match and merge category and product specifications by SKU',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic matching
  python3 match_specifications.py specs_categoria.csv specs_producto.csv

  # With custom SKU column
  python3 match_specifications.py cat_specs.csv prod_specs.csv --sku-column "CODIGO"

  # With deduplication (removes duplicate IDs)
  python3 match_specifications.py cat_specs.csv prod_specs.csv --deduplicate

  # With custom ID column for deduplication
  python3 match_specifications.py cat_specs.csv prod_specs.csv \\
    --deduplicate --id-column "ProductID"

Output Files:
  Without --deduplicate:
    - matched_specs_YYYYMMDD.csv: Merged records where SKUs match
    - unmatched_specs_YYYYMMDD.csv: Records from file 2 not in file 1

  With --deduplicate:
    - matched_specs_YYYYMMDD.csv: Merged records where SKUs match
    - unmatched_specs_YYYYMMDD.csv: Records from file 2 not in file 1
    - matched_specs_unique_YYYYMMDD.csv: Matched records without duplicates by ID

Input Requirements:
  - Both files must have the SKU column (name configurable)
  - For deduplication: matched results must have the ID column (name configurable)
  - Both files must be UTF-8 encoded
  - Valid CSV format
        '''
    )

    parser.add_argument('category_specs', help='CSV file with category specifications')
    parser.add_argument('product_specs', help='CSV file with product specifications')
    parser.add_argument('--sku-column', default='SKU',
                       help='Name of SKU column in both files (default: SKU)')
    parser.add_argument('--deduplicate', action='store_true',
                       help='Generate deduplicated output file (removes duplicate IDs)')
    parser.add_argument('--id-column', default='ID',
                       help='Name of ID column for deduplication (default: ID)')

    args = parser.parse_args()

    # Generar nombres de archivo de salida con fecha
    fecha = datetime.now().strftime('%Y%m%d')
    matched_file = f"matched_specs_{fecha}.csv"
    unmatched_file = f"unmatched_specs_{fecha}.csv"
    unique_file = f"matched_specs_unique_{fecha}.csv"

    try:
        # Ejecutar matching
        matched_rows, unmatched_rows, category_fieldnames, product_fieldnames, category_data = \
            match_specifications(args.category_specs, args.product_specs, args.sku_column)

        # Construir fieldnames para archivo de coincidencias
        # Orden: SKU primero, luego columnas de categoría (sin SKU), luego columnas de producto (sin SKU)
        output_fieldnames_matched = [args.sku_column]
        output_fieldnames_matched.extend([f for f in category_fieldnames if f != args.sku_column])
        output_fieldnames_matched.extend([f for f in product_fieldnames if f != args.sku_column])

        # Escribir archivo de coincidencias
        print(f"\nWriting matched specifications to: {matched_file}")
        write_csv_output(matched_file, matched_rows, output_fieldnames_matched)

        # Escribir archivo de no encontrados
        print(f"Writing unmatched specifications to: {unmatched_file}")
        write_csv_output(unmatched_file, unmatched_rows, product_fieldnames)

        # Variables para deduplicación (inicializadas como None)
        unique_rows = None
        duplicates_removed = 0

        # Si se solicita deduplicación, generar archivo único
        if args.deduplicate:
            if len(matched_rows) > 0:
                print(f"\nPerforming deduplication by '{args.id_column}' column...")
                unique_rows, duplicates_removed = deduplicate_by_id(
                    matched_rows,
                    args.id_column,
                    output_fieldnames_matched
                )

                # Escribir archivo deduplicado
                print(f"Writing deduplicated specifications to: {unique_file}")
                write_csv_output(unique_file, unique_rows, output_fieldnames_matched)
            else:
                print(f"\nNo matched records to deduplicate, skipping unique file generation")
                unique_file = None

        # Calcular y mostrar estadísticas
        # Necesitamos recargar category_rows para el conteo total
        with open(args.category_specs, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            total_cat = sum(1 for _ in reader)

        with open(args.product_specs, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            total_prod = sum(1 for _ in reader)

        # Llamar print_statistics con información de deduplicación si aplica
        print_statistics(
            total_cat,
            len(category_data),
            total_prod,
            len(matched_rows),
            len(unmatched_rows),
            matched_file,
            unmatched_file,
            unique_file if args.deduplicate and len(matched_rows) > 0 else None,
            len(unique_rows) if unique_rows else 0,
            duplicates_removed,
            args.id_column
        )

        print(f"\nProcess completed successfully")

    except KeyboardInterrupt:
        print(f"\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
