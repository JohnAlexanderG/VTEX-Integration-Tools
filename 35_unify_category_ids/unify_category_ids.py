#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unify_category_ids.py

Script para unificar los valores de las columnas 'categorieID' y 'SubcategorieID'
de un archivo CSV en una sola columna sin duplicados y ordenados numericamente.

Funcionalidad:
    - Lee un CSV con columnas: Path, DepartamentID, categorieID, SubcategorieID
    - Extrae todos los valores de categorieID y SubcategorieID
    - Elimina valores duplicados y vacios
    - Ordena los IDs numericamente de menor a mayor
    - Genera un CSV de salida con una sola columna 'categorieID'

Ejecucion:
    python3 unify_category_ids.py entrada.csv salida.csv
    python3 unify_category_ids.py entrada.csv salida.csv --delimiter ";"

Ejemplo de entrada:
    Path,DepartamentID,categorieID,SubcategorieID
    /ropa/camisas,1,10,100
    /ropa/pantalones,1,10,101
    /hogar/muebles,2,20,
    /hogar/decoracion,2,,200

Ejemplo de salida:
    categorieID
    10
    20
    100
    101
    200
"""

import argparse
import csv
import sys
import os


def is_valid_id(value):
    """
    Verifica si el valor es un ID valido (no vacio y convertible a entero).

    Args:
        value: Valor a verificar

    Returns:
        bool: True si es un ID valido, False en caso contrario
    """
    if value is None:
        return False

    value_str = str(value).strip()

    if not value_str:
        return False

    try:
        int(value_str)
        return True
    except ValueError:
        return False


def extract_category_ids(input_file, delimiter=','):
    """
    Extrae todos los IDs de categorieID y SubcategorieID del archivo CSV.

    Args:
        input_file: Ruta al archivo CSV de entrada
        delimiter: Delimitador del CSV (default: ',')

    Returns:
        set: Conjunto de IDs unicos como enteros
    """
    category_ids = set()
    rows_processed = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        # Verificar que las columnas necesarias existan
        fieldnames = reader.fieldnames or []
        has_categorie_id = 'categorieID' in fieldnames
        has_subcategorie_id = 'SubcategorieID' in fieldnames

        if not has_categorie_id and not has_subcategorie_id:
            print(f"   Advertencia: No se encontraron las columnas 'categorieID' ni 'SubcategorieID'", file=sys.stderr)
            print(f"   Columnas disponibles: {fieldnames}", file=sys.stderr)
            return category_ids

        for row in reader:
            rows_processed += 1

            # Extraer categorieID si existe
            if has_categorie_id:
                cat_id = row.get('categorieID', '')
                if is_valid_id(cat_id):
                    category_ids.add(int(str(cat_id).strip()))

            # Extraer SubcategorieID si existe
            if has_subcategorie_id:
                subcat_id = row.get('SubcategorieID', '')
                if is_valid_id(subcat_id):
                    category_ids.add(int(str(subcat_id).strip()))

    return category_ids, rows_processed


def write_output_csv(output_file, category_ids):
    """
    Escribe los IDs ordenados en un archivo CSV con formato de columna.

    Args:
        output_file: Ruta al archivo CSV de salida
        category_ids: Conjunto de IDs a escribir
    """
    sorted_ids = sorted(category_ids)

    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['categorieID'])

        for cat_id in sorted_ids:
            writer.writerow([cat_id])

    return sorted_ids


def main():
    parser = argparse.ArgumentParser(
        description='Unifica los valores de categorieID y SubcategorieID de un CSV en una sola columna ordenada.'
    )
    parser.add_argument('input', help='Ruta al archivo CSV de entrada')
    parser.add_argument('output', help='Ruta al archivo CSV de salida')
    parser.add_argument('--delimiter', default=',', help='Delimitador del CSV (default: ,)')

    args = parser.parse_args()

    # Verificar que el archivo de entrada existe
    if not os.path.exists(args.input):
        print(f"Error: El archivo de entrada no existe: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Procesando archivo: {args.input}")

    try:
        # Extraer IDs
        print("   Extrayendo IDs de categorieID y SubcategorieID...", end=" ")
        result = extract_category_ids(args.input, args.delimiter)

        if isinstance(result, tuple):
            category_ids, rows_processed = result
        else:
            category_ids = result
            rows_processed = 0

        print("Completado")

        # Escribir salida
        print(f"   Escribiendo archivo de salida: {args.output}...", end=" ")
        sorted_ids = write_output_csv(args.output, category_ids)
        print("Completado")

        # Estadisticas
        print(f"\nResultados:")
        print(f"   Filas procesadas: {rows_processed}")
        print(f"   IDs unicos encontrados: {len(sorted_ids)}")
        if sorted_ids:
            print(f"   Rango: {sorted_ids[0]} - {sorted_ids[-1]}")

        print(f"\nArchivo generado: {args.output}")

    except Exception as e:
        print(f"Error al procesar el archivo: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
