#!/usr/bin/env python3
"""
json_to_csv.py

Convertidor simple de archivos JSON a formato CSV. Utilidad inversa 
al proceso principal de transformación de datos.

Funcionalidad:
- Lee archivos JSON (objetos individuales o arrays de objetos)
- Extrae automáticamente todos los nombres de campos únicos
- Ordena campos alfabéticamente para consistencia
- Maneja valores faltantes rellenando con cadenas vacías
- Mantiene codificación UTF-8 para caracteres especiales
- Genera CSV con encabezados apropiados

Tipos de Entrada Soportados:
- Objeto JSON individual → CSV de 1 fila
- Array de objetos JSON → CSV de múltiples filas
- Campos inconsistentes entre objetos → se incluyen todos los campos únicos

Ejecución:
    # Conversión básica
    python3 json_to_csv.py input.json output.csv
    
    # Convertir datos procesados a CSV para revisión
    python3 json_to_csv.py productos_finales.json productos.csv

Ejemplo:
    python3 json_to_csv/json_to_csv.py datos_procesados.json revision_manual.csv

Casos de Uso:
- Exportar datos JSON procesados para revisión en Excel
- Generar CSVs para importación en otras herramientas
- Crear respaldos legibles de datos transformados
"""

import json
import csv
import argparse
import sys

def parse_args():
    parser = argparse.ArgumentParser(description='Convert JSON file to CSV.')
    parser.add_argument('input', help='Path to input JSON file')
    parser.add_argument('output', help='Path to output CSV file')
    return parser.parse_args()

def main():
    args = parse_args()
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'Error reading JSON file: {e}', file=sys.stderr)
        sys.exit(1)

    # Ensure data is a list of dicts
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        print('JSON content must be a list or object.', file=sys.stderr)
        sys.exit(1)

    # Collect all field names
    fieldnames = set()
    for item in records:
        if isinstance(item, dict):
            fieldnames.update(item.keys())
        else:
            print('Each item in JSON list must be an object.', file=sys.stderr)
            sys.exit(1)
    fieldnames = sorted(fieldnames)

    try:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in records:
                row = {field: item.get(field, '') for field in fieldnames}
                writer.writerow(row)
    except Exception as e:
        print(f'Error writing CSV file: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'Successfully converted {args.input} to {args.output}')

if __name__ == '__main__':
    main()
