#!/usr/bin/env python3
"""
compare_json_to_csv.py

Script para comparar dos archivos JSON y exportar registros faltantes a CSV.
Compara registros por SKU (datos antiguos) vs RefId (datos nuevos) y exporta
los registros que están en los datos antiguos pero no en los nuevos.

Funcionalidad:
- Carga dos archivos JSON (datos antiguos y nuevos)
- Extrae todos los RefId de los datos nuevos
- Encuentra registros en datos antiguos cuyo SKU no existe en los RefId nuevos
- Exporta los registros faltantes a un archivo CSV

Ejecución:
    python3 compare_json_to_csv.py old_data.json new_data.json missing_records.csv

Ejemplo:
    python3 compare_json_to_csv.py productos_antiguos.json productos_nuevos.json faltantes.csv
"""
import json
import csv
import argparse

def load_json(path):
    """
    Carga un archivo JSON desde la ruta especificada.
    
    Args:
        path (str): Ruta al archivo JSON
        
    Returns:
        list/dict: Contenido del archivo JSON
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_csv(records, output_path, headers):
    """
    Escribe una lista de registros a un archivo CSV.
    
    Args:
        records (list): Lista de diccionarios con los registros a escribir
        output_path (str): Ruta del archivo CSV de salida
        headers (list): Lista con los nombres de las columnas
    """
    if not records:
        print('No missing records to write.')
        return

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for rec in records:
            # Solo incluir claves en el orden original
            row = {k: rec.get(k, '') for k in headers}
            writer.writerow(row)
    print(f'Wrote {len(records)} missing records to {output_path}')


def main():
    """
    Función principal que ejecuta la comparación de archivos JSON.
    
    Procesa argumentos de línea de comandos, carga los archivos JSON,
    realiza la comparación y exporta los resultados a CSV.
    """
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description='Export CSV of records in old-data JSON not found in new-data JSON by SKU vs RefId comparison.'
    )
    parser.add_argument('old_data', help='Path to old-data JSON file')
    parser.add_argument('new_data', help='Path to new-data JSON file')
    parser.add_argument('output_csv', help='Path for output CSV file')
    args = parser.parse_args()

    # Cargar archivos JSON
    print(f"Cargando datos antiguos desde: {args.old_data}")
    old_records = load_json(args.old_data)
    print(f"Cargando datos nuevos desde: {args.new_data}")
    new_records = load_json(args.new_data)

    # Preparar conjunto de valores RefId de los datos nuevos
    # Esto permite búsquedas rápidas O(1) en lugar de O(n)
    print("Extrayendo RefId de datos nuevos...")
    new_ids = { rec.get('RefId') for rec in new_records }
    print(f"Encontrados {len(new_ids)} RefId únicos en datos nuevos")

    # Filtrar registros antiguos donde SKU no está presente en new_ids
    # La comparación es: SKU (datos antiguos) vs RefId (datos nuevos)
    print("Comparando SKU de datos antiguos con RefId de datos nuevos...")
    missing = [ rec for rec in old_records if rec.get('SKU') not in new_ids ]
    print(f"Encontrados {len(missing)} registros faltantes")

    # Usar el orden de headers del primer registro de datos antiguos
    if old_records and isinstance(old_records, list):
        headers = list(old_records[0].keys())
    else:
        headers = []
        print('Warning: old-data JSON is empty or not a list.')

    # Escribir registros faltantes a CSV
    write_csv(missing, args.output_csv, headers)

if __name__ == '__main__':
    main()
