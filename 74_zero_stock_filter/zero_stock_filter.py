#!/usr/bin/env python3
"""
Zero Stock Filter

Filtra un CSV de inventario por bodegas (formato: una fila por SKU/bodega,
~17-18 bodegas) y deja solo las filas cuya cantidad (EXISTENCIA) es 0.

Usage:
    python3 zero_stock_filter.py <input_csv> <output_csv> [--column EXISTENCIA] [--delimiter ,]

Example:
    python3 zero_stock_filter.py inventario_bodegas.csv inventario_sin_stock.csv
    python3 zero_stock_filter.py inventario.csv sin_stock.csv --column CANTIDAD
    python3 zero_stock_filter.py inventario.csv sin_stock.csv --delimiter ";"

Input Fields (auto-detected, nombres exactos pueden traer espacios):
    CODIGO SKU        : identificador del producto
    CODIGO SUCURSAL   : identificador de la bodega
    EXISTENCIA        : cantidad en stock (puede venir con ceros a la izquierda,
                         ej. "000000000")

Notes:
    - Si la columna de cantidad no se llama EXISTENCIA, usa --column para
      indicar el nombre exacto.
    - Tolera filas con una coma sobrante al final (columna fantasma sin
      encabezado), un patrón visto en exports de inventario reales.
    - Las filas se preservan tal cual (sin recortar espacios) en el CSV de
      salida; solo se usa el valor recortado para decidir si la cantidad es 0.
    - Filas donde la cantidad no se puede interpretar como número se omiten
      y se reportan al final, no se consideran "en 0".
"""

import csv
import os
import sys
import argparse


QUANTITY_CANDIDATES = ['EXISTENCIA', 'CANTIDAD', 'STOCK', 'QTY', 'QUANTITY', 'DISPONIBLE']


def detect_quantity_column(fieldnames, override=None):
    if override:
        for fn in fieldnames:
            if fn is not None and fn.strip() == override.strip():
                return fn
        return None

    for candidate in QUANTITY_CANDIDATES:
        for fn in fieldnames:
            if fn is not None and fn.strip().upper() == candidate:
                return fn
    return None


def parse_quantity(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value.replace(',', '.'))
        except ValueError:
            return None


def filter_zero_stock(input_csv, output_csv, column=None, delimiter=','):
    with open(input_csv, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames

        if not fieldnames:
            print(f"Error: no se pudieron leer columnas de {input_csv}")
            sys.exit(1)

        quantity_column = detect_quantity_column(fieldnames, column)
        if not quantity_column:
            print("Error: no se encontró la columna de cantidad.")
            print(f"Columnas disponibles: {', '.join(repr(fn) for fn in fieldnames)}")
            print("Especifica la columna correcta con --column NOMBRE_COLUMNA")
            sys.exit(1)

        print(f"Usando columna de cantidad: {quantity_column!r}")

        zero_rows = []
        total_rows = 0
        skipped_rows = 0

        for row in reader:
            total_rows += 1
            qty = parse_quantity(row.get(quantity_column))
            if qty is None:
                skipped_rows += 1
                continue
            if qty == 0:
                zero_rows.append(row)

    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(zero_rows)

    print(f"\nTotal de filas procesadas: {total_rows:,}")
    print(f"Filas con cantidad = 0:    {len(zero_rows):,}")
    if skipped_rows:
        print(f"Filas omitidas (cantidad no numérica o vacía): {skipped_rows:,}")
    print(f"\nArchivo generado: {output_csv}")


def main():
    parser = argparse.ArgumentParser(
        description='Filtra un CSV de inventario por bodegas dejando solo las filas con cantidad = 0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  python3 zero_stock_filter.py inventario_bodegas.csv inventario_sin_stock.csv
  python3 zero_stock_filter.py inventario.csv sin_stock.csv --column CANTIDAD
  python3 zero_stock_filter.py inventario.csv sin_stock.csv --delimiter ";"
        '''
    )
    parser.add_argument('input_csv', help='CSV de entrada con inventario por bodegas')
    parser.add_argument('output_csv', help='CSV de salida con solo las filas en 0')
    parser.add_argument('--column', help='Nombre exacto de la columna de cantidad (si no es EXISTENCIA/CANTIDAD/STOCK/...)')
    parser.add_argument('--delimiter', default=',', help='Delimitador del CSV (por defecto ",")')

    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: no se encontró el archivo de entrada: {args.input_csv}")
        sys.exit(1)

    filter_zero_stock(args.input_csv, args.output_csv, args.column, args.delimiter)


if __name__ == '__main__':
    main()
