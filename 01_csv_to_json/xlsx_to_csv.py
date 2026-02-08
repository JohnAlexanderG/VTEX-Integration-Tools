#!/usr/bin/env python3
"""
xlsx_to_csv.py

Script para convertir archivos Excel (.xlsx, .xls) a formato CSV.
Complementa el flujo de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Lee archivos XLSX (Excel Open XML format) y XLS (Excel Binary format)
- Convierte la primera hoja a formato CSV estándar
- Mantiene codificación UTF-8 para caracteres especiales españoles
- Maneja valores NaN convirtiéndolos a cadenas vacías
- Preserva todos los nombres de columnas y estructura de datos
- Permite especificar en qué fila están los encabezados (útil cuando la primera fila no contiene los nombres de columnas)
- Detección automática del tipo de archivo según la extensión

Dependencias:
- pandas: requerido para lectura de archivos Excel
- openpyxl: requerido para archivos .xlsx (Excel Open XML format)
- xlrd: requerido para archivos .xls (Excel Binary format)

Ejecución:
    # Conversión básica XLSX/XLS a CSV (encabezados en primera fila)
    python3 xlsx_to_csv.py entrada.xlsx salida.csv
    python3 xlsx_to_csv.py entrada.xls salida.csv

    # Encabezados en segunda fila (usar --header-row 1, indexado desde 0)
    python3 xlsx_to_csv.py entrada.xlsx salida.csv --header-row 1

    # Encabezados en tercera fila
    python3 xlsx_to_csv.py entrada.xls salida.csv --header-row 2

    # Conversión con rutas absolutas
    python3 xlsx_to_csv.py /ruta/completa/productos.xlsx /ruta/salida/productos.csv

Ejemplo:
    python3 01_csv_to_json/xlsx_to_csv.py tiendas-sentry.xlsx tiendas-sentry.csv
    python3 01_csv_to_json/xlsx_to_csv.py estoque.xls estoque.csv
    python3 01_csv_to_json/xlsx_to_csv.py productos.xlsx productos.csv --header-row 1
"""
import csv
import sys
import argparse
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False


def read_excel_to_dict(file_path, header_row=0):
    """
    Lee un archivo Excel (.xlsx o .xls) y lo convierte a lista de diccionarios.

    :param file_path: Ruta del archivo .xlsx o .xls a leer
    :param header_row: Fila donde están los encabezados (0-indexed, default: 0)
    :return: Lista de diccionarios representando las filas del archivo
    :raises ImportError: Si pandas o los engines necesarios no están instalados
    :raises Exception: Si hay error al leer el archivo
    """
    if not PANDAS_AVAILABLE:
        raise ImportError(
            "pandas es requerido para leer archivos Excel.\n"
            "Instálalo con: pip install pandas"
        )

    # Detectar el tipo de archivo por extensión
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == '.xlsx':
        if not OPENPYXL_AVAILABLE:
            raise ImportError(
                "openpyxl es requerido para leer archivos .xlsx.\n"
                "Instálalo con: pip install openpyxl"
            )
        engine = 'openpyxl'
    elif file_extension == '.xls':
        if not XLRD_AVAILABLE:
            raise ImportError(
                "xlrd es requerido para leer archivos .xls.\n"
                "Instálalo con: pip install xlrd"
            )
        engine = 'xlrd'
    else:
        raise ValueError(
            f"Formato de archivo no soportado: {file_extension}\n"
            "Solo se soportan archivos .xlsx y .xls"
        )

    # Leer el archivo Excel (primera hoja por defecto)
    # header_row especifica qué fila contiene los nombres de columnas
    df = pd.read_excel(file_path, engine=engine, header=header_row)

    # Convertir NaN a cadenas vacías para mantener compatibilidad con CSV
    df = df.fillna('')

    # Convertir a lista de diccionarios
    return df.to_dict('records')


def write_dict_to_csv(data, output_file):
    """
    Escribe una lista de diccionarios a un archivo CSV.

    :param data: Lista de diccionarios con los datos
    :param output_file: Ruta del archivo CSV de salida
    :raises ValueError: Si la lista de datos está vacía
    """
    if not data:
        raise ValueError("No hay datos para escribir en el archivo CSV")

    # Obtener todos los nombres de columna (fieldnames)
    fieldnames = list(data[0].keys())

    # Escribir el archivo CSV con codificación UTF-8
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in data:
            writer.writerow(row)


def main():
    """Función principal que maneja la conversión de Excel a CSV."""
    parser = argparse.ArgumentParser(
        description='Convierte archivos Excel (.xlsx, .xls) a formato CSV.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'input_file',
        help='Archivo .xlsx o .xls de entrada'
    )
    parser.add_argument(
        'output_file',
        help='Archivo .csv de salida'
    )
    parser.add_argument(
        '--header-row',
        type=int,
        default=0,
        help='Fila donde están los encabezados (0-indexed, default: 0)\n'
             'Ejemplo: --header-row 1 para encabezados en la segunda fila'
    )

    args = parser.parse_args()

    try:
        # Leer archivo Excel (detecta automáticamente .xlsx o .xls)
        data = read_excel_to_dict(args.input_file, header_row=args.header_row)

        # Escribir archivo CSV
        write_dict_to_csv(data, args.output_file)

        # Mensaje de éxito
        print(f"Successfully converted {args.input_file} to {args.output_file}")
        print(f"Total records: {len(data)}")

    except ImportError as e:
        sys.stderr.write(f"Error de dependencias: {e}\n")
        sys.exit(1)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: Archivo no encontrado - {args.input_file}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error al convertir archivo: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
