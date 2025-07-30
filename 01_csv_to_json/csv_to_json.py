#!/usr/bin/env python3
"""
csv_to_json.py

Script principal para convertir archivos CSV a formato JSON. Forma parte del flujo 
de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Lee archivos CSV con encabezados como primera línea
- Convierte cada fila a un objeto JSON usando encabezados como claves
- Soporta entrada desde stdin y salida a stdout para pipelines
- Mantiene codificación UTF-8 para caracteres especiales
- Permite formateo personalizado con indentación

Ejecución:
    # Conversión básica
    python3 csv_to_json.py entrada.csv salida.json --indent 4
    
    # Usando pipelines (stdin/stdout)
    cat entrada.csv | python3 csv_to_json.py - > salida.json
    
    # Formato compacto (sin indentación)
    python3 csv_to_json.py data.csv output.json

Ejemplo:
    python3 01_csv_to_json/csv_to_json.py productos.csv productos.json --indent 4
"""
import csv
import json
import argparse
import sys

def csv_to_json(csv_file, json_file, indent=None):
    """
    Convierte el contenido de csv_file a JSON y lo escribe en json_file.

    :param csv_file: archivo CSV de entrada (file-like object)
    :param json_file: archivo JSON de salida (file-like object)
    :param indent: nivel de indentación para el JSON (int) o None para formato compacto
    """
    # Leer todas las filas como diccionarios usando la primera línea como encabezados
    reader = csv.DictReader(csv_file)
    data = [row for row in reader]

    # Volcar a JSON
    if indent is not None:
        json.dump(data, json_file, ensure_ascii=False, indent=indent)
    else:
        json.dump(data, json_file, ensure_ascii=False)
    # Añadir salto de línea al final
    json_file.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description='Convierte archivos CSV a JSON.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'csv_input',
        nargs='?',
        type=argparse.FileType('r', encoding='utf-8'),
        default=sys.stdin,
        help='Archivo CSV de entrada (por defecto: stdin)'
    )
    parser.add_argument(
        'json_output',
        nargs='?',
        type=argparse.FileType('w', encoding='utf-8'),
        default=sys.stdout,
        help='Archivo JSON de salida (por defecto: stdout)'
    )
    parser.add_argument(
        '-i', '--indent',
        type=int,
        default=None,
        help='Nivel de indentación para el JSON (por defecto: compacto)'
    )
    args = parser.parse_args()

    try:
        csv_to_json(args.csv_input, args.json_output, indent=args.indent)
    except Exception as e:
        sys.stderr.write(f"Error al convertir CSV a JSON: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
