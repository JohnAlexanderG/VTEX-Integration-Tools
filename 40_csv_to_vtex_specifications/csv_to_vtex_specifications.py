#!/usr/bin/env python3
"""
CSV to VTEX Specifications Transformer.

Transforma un CSV con datos de productos al formato requerido para
importar especificaciones de producto en VTEX.

Input CSV headers:
    _SkuId,_ProductId,SKU,Categoria,Subcategoria,Linea,Nombre Especificacion,
    Especificacion,cantidad,,COGNOTACIÓN,ID,DepartamentID,categorieID,

Output CSV headers:
    categoryId,groupName,specificationName,specificationValue,productId,
    fieldTypeId,isFilter,isRequired,isOnProductDetails

Usage:
    python3 csv_to_vtex_specifications.py <input.csv> <output.csv> [--invalid <invalid.csv>]

Examples:
    python3 csv_to_vtex_specifications.py matched_data.csv vtex_specs.csv
    python3 csv_to_vtex_specifications.py matched_data.csv vtex_specs.csv --invalid invalidos.csv
"""

import argparse
import csv
import sys
import os


def transform_row(row):
    """
    Transforma una fila del CSV de entrada al formato de especificaciones VTEX.
    """
    nombre_spec = row.get('Nombre Especificacion', '')
    especificacion = row.get('Especificacion', '')

    # Si Especificacion es igual a Nombre Especificacion, usar cantidad
    if especificacion == nombre_spec:
        spec_value = row.get('cantidad', '')
    else:
        spec_value = especificacion

    return {
        'categoryId': row.get('categorieID', ''),
        'groupName': 'Especificaciones',
        'specificationName': nombre_spec,
        'specificationValue': spec_value,
        'productId': row.get('_ProductId', ''),
        'fieldTypeId': 5,
        'isFilter': 'TRUE',
        'isRequired': 'FALSE',
        'isOnProductDetails': 'TRUE'
    }


def process_csv(input_file, output_file, invalid_file=None):
    """
    Procesa el CSV de entrada y genera el CSV de salida con formato VTEX.
    Opcionalmente exporta las filas inválidas a un archivo separado.
    """
    output_rows = []
    invalid_rows = []
    total_rows = 0
    input_headers = None

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        input_headers = reader.fieldnames

        for row in reader:
            total_rows += 1
            transformed = transform_row(row)
            output_rows.append(transformed)

    # Escribir CSV de salida
    output_headers = [
        'categoryId',
        'groupName',
        'specificationName',
        'specificationValue',
        'productId',
        'fieldTypeId',
        'isFilter',
        'isRequired',
        'isOnProductDetails'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_headers)
        writer.writeheader()
        writer.writerows(output_rows)

    # Escribir CSV de filas inválidas si se especificó archivo
    if invalid_file and invalid_rows and input_headers:
        invalid_dir = os.path.dirname(invalid_file)
        if invalid_dir and not os.path.exists(invalid_dir):
            os.makedirs(invalid_dir)

        with open(invalid_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=input_headers)
            writer.writeheader()
            writer.writerows(invalid_rows)

    return {
        'total_rows': total_rows,
        'output_rows': len(output_rows),
        'invalid_rows': len(invalid_rows),
        'invalid_file': invalid_file
    }


def main():
    parser = argparse.ArgumentParser(
        description='Transforma CSV al formato de especificaciones VTEX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 csv_to_vtex_specifications.py matched_data.csv vtex_specs.csv
  python3 csv_to_vtex_specifications.py input.csv output/specifications.csv
        """
    )
    parser.add_argument('input_csv',
                        help='CSV de entrada con datos de productos')
    parser.add_argument('output_csv',
                        help='CSV de salida con formato de especificaciones VTEX')
    parser.add_argument('--invalid', '-i',
                        dest='invalid_csv',
                        help='CSV de salida para filas inválidas (sin especificación)')

    args = parser.parse_args()

    # Validar archivo de entrada
    if not os.path.exists(args.input_csv):
        print(f"Error: Archivo '{args.input_csv}' no encontrado")
        sys.exit(1)

    # Crear directorio de salida si es necesario
    output_dir = os.path.dirname(args.output_csv)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("=" * 70)
    print("CSV to VTEX Specifications Transformer")
    print("=" * 70)

    print(f"\n📁 Archivo de entrada:   {args.input_csv}")
    print(f"📁 Archivo de salida:    {args.output_csv}")
    if args.invalid_csv:
        print(f"📁 Archivo inválidos:    {args.invalid_csv}")

    try:
        stats = process_csv(args.input_csv, args.output_csv, args.invalid_csv)
    except Exception as e:
        print(f"\n✗ Error procesando archivo: {e}")
        sys.exit(1)

    # Mostrar estadísticas
    print("\n" + "=" * 70)
    print("📋 Resumen")
    print("=" * 70)
    print(f"   Filas leídas:      {stats['total_rows']:,}")
    print(f"   Filas exportadas:  {stats['output_rows']:,}")
    print(f"   Filas inválidas:   {stats['invalid_rows']:,} (sin especificación)")
    print("=" * 70)
    print(f"✓ Archivo generado: {args.output_csv}")
    if stats['invalid_file'] and stats['invalid_rows'] > 0:
        print(f"✓ Inválidos exportados: {stats['invalid_file']}")


if __name__ == '__main__':
    main()
