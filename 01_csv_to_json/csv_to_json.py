#!/usr/bin/env python3
"""
csv_to_json.py

Script principal para convertir archivos CSV y XLS/XLSX/XLSB a formato JSON. Forma parte del flujo
de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Lee archivos CSV, XLS, XLSX y XLSB con encabezados como primera línea
- Convierte cada fila a un objeto JSON usando encabezados como claves
- Soporta entrada desde stdin para archivos CSV y salida a stdout para pipelines
- Mantiene codificación UTF-8 para caracteres especiales
- Permite formateo personalizado con indentación
- Detecta automáticamente el formato basado en la extensión del archivo

Dependencias:
- pandas: requerido para lectura de archivos Excel
- openpyxl: requerido para archivos .xlsx (instalado automáticamente con pandas)
- xlrd: requerido para archivos .xls antiguos
- pyxlsb: requerido para archivos .xlsb (Excel Binary Workbook)

Ejecución:
    # Conversión CSV básica
    python3 csv_to_json.py entrada.csv salida.json --indent 4

    # Conversión XLS/XLSX
    python3 csv_to_json.py productos.xls productos.json --indent 4
    python3 csv_to_json.py productos.xlsx productos.json --indent 4

    # Conversión XLSB
    python3 csv_to_json.py productos.xlsb productos.json --indent 4

    # Usando pipelines (solo CSV desde stdin/stdout)
    cat entrada.csv | python3 csv_to_json.py - > salida.json

    # Formato compacto (sin indentación)
    python3 csv_to_json.py data.csv output.json

Ejemplo:
    python3 01_csv_to_json/csv_to_json.py productos.csv productos.json --indent 4
    python3 01_csv_to_json/csv_to_json.py productos.xlsx productos.json --indent 4
    python3 01_csv_to_json/csv_to_json.py productos.xlsb productos.json --indent 4
"""
import csv
import json
import argparse
import sys
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import pyxlsb
    PYXLSB_AVAILABLE = True
except ImportError:
    PYXLSB_AVAILABLE = False

def is_excel_file(filename):
    """Detecta si el archivo es de formato Excel basado en su extensión."""
    if filename == '-' or filename is None:
        return False
    return filename.lower().endswith(('.xls', '.xlsx', '.xlsb'))

def read_excel_to_dict(file_path):
    """Lee un archivo Excel y lo convierte a lista de diccionarios."""
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas es requerido para leer archivos Excel. Instálalo con: pip install pandas")

    # Determinar el engine basado en la extensión del archivo
    if file_path.lower().endswith('.xlsx'):
        engine = 'openpyxl'
    elif file_path.lower().endswith('.xlsb'):
        if not PYXLSB_AVAILABLE:
            raise ImportError("pyxlsb es requerido para leer archivos .xlsb. Instálalo con: pip install pyxlsb")
        engine = 'pyxlsb'
    else:  # .xls
        engine = 'xlrd'

    # Leer el archivo Excel (primera hoja por defecto)
    df = pd.read_excel(file_path, engine=engine)

    # Convertir NaN a cadenas vacías para mantener compatibilidad
    df = df.fillna('')

    # Convertir a lista de diccionarios
    return df.to_dict('records')

def data_to_json(input_file, json_file, indent=None, file_path=None):
    """
    Convierte datos de CSV o Excel a JSON.
    
    :param input_file: archivo de entrada (file-like object) o None para Excel
    :param json_file: archivo JSON de salida (file-like object)
    :param indent: nivel de indentación para el JSON (int) o None para formato compacto
    :param file_path: ruta del archivo para detectar formato (usado para Excel)
    """
    if file_path and is_excel_file(file_path):
        # Procesar archivo Excel
        data = read_excel_to_dict(file_path)
    else:
        # Procesar archivo CSV
        reader = csv.DictReader(input_file)
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
        description='Convierte archivos CSV y Excel (XLS/XLSX/XLSB) a JSON.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default='-',
        help='Archivo de entrada CSV/XLS/XLSX/XLSB (por defecto: stdin para CSV)'
    )
    parser.add_argument(
        'json_output',
        nargs='?',
        default='-',
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
        # Determinar si es entrada estándar o archivo
        if args.input_file == '-':
            # Entrada estándar (solo CSV)
            input_stream = sys.stdin
            file_path = None
        else:
            file_path = args.input_file
            if is_excel_file(file_path):
                # Archivo Excel - no necesitamos abrir como stream
                input_stream = None
            else:
                # Archivo CSV
                input_stream = open(file_path, 'r', encoding='utf-8')
        
        # Determinar archivo de salida
        if args.json_output == '-':
            output_stream = sys.stdout
        else:
            output_stream = open(args.json_output, 'w', encoding='utf-8')
        
        # Procesar archivo
        data_to_json(input_stream, output_stream, indent=args.indent, file_path=file_path)
        
        # Cerrar archivos si se abrieron
        if input_stream and input_stream != sys.stdin:
            input_stream.close()
        if output_stream != sys.stdout:
            output_stream.close()
            
    except Exception as e:
        sys.stderr.write(f"Error al convertir archivo a JSON: {e}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
