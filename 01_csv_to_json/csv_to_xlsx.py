#!/usr/bin/env python3
"""
csv_to_xlsx.py

Script para convertir archivos CSV a formato XLSX.
Complementa el flujo de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Lee archivos CSV con codificación UTF-8 por defecto
- Detecta automáticamente el separador cuando no se especifica
- Convierte valores vacíos a cadenas vacías
- Exporta a la primera hoja de un archivo XLSX

Dependencias:
- pandas: requerido para lectura de CSV y escritura de Excel
- openpyxl: requerido para escribir archivos .xlsx

Ejecución:
    # Conversión básica CSV a XLSX
    python3 csv_to_xlsx.py entrada.csv salida.xlsx

    # CSV separado por punto y coma
    python3 csv_to_xlsx.py entrada.csv salida.xlsx --delimiter ";"

    # CSV con codificación distinta
    python3 csv_to_xlsx.py entrada.csv salida.xlsx --encoding latin-1

Ejemplo:
    python3 01_csv_to_json/csv_to_xlsx.py productos.csv productos.xlsx
    python3 01_csv_to_json/csv_to_xlsx.py precios.csv precios.xlsx --delimiter ";"
"""
import argparse
import csv
import os
import sys

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import openpyxl  # noqa: F401
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def detect_delimiter(file_path, encoding):
    """
    Detecta el separador del CSV usando una muestra del archivo.

    :param file_path: Ruta del archivo CSV
    :param encoding: Codificación del archivo
    :return: Separador detectado, o coma si no se puede detectar
    """
    with open(file_path, "r", encoding=encoding, newline="") as f:
        sample = f.read(8192)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        return ","


def read_csv_to_dataframe(file_path, encoding="utf-8-sig", delimiter=None):
    """
    Lee un archivo CSV y lo convierte a DataFrame.

    :param file_path: Ruta del archivo CSV de entrada
    :param encoding: Codificación del archivo
    :param delimiter: Separador CSV. Si es None, se detecta automáticamente
    :return: pandas.DataFrame con los datos del CSV
    """
    if not PANDAS_AVAILABLE:
        raise ImportError(
            "pandas es requerido para leer archivos CSV.\n"
            "Instálalo con: pip install pandas"
        )

    if delimiter is None:
        delimiter = detect_delimiter(file_path, encoding)

    df = pd.read_csv(file_path, dtype=str, encoding=encoding, sep=delimiter)
    return df.fillna("")


def write_dataframe_to_xlsx(df, output_file, sheet_name="Sheet1"):
    """
    Escribe un DataFrame a un archivo XLSX.

    :param df: pandas.DataFrame con los datos
    :param output_file: Ruta del archivo XLSX de salida
    :param sheet_name: Nombre de la hoja de Excel
    """
    if not OPENPYXL_AVAILABLE:
        raise ImportError(
            "openpyxl es requerido para escribir archivos .xlsx.\n"
            "Instálalo con: pip install openpyxl"
        )

    output_extension = os.path.splitext(output_file)[1].lower()
    if output_extension != ".xlsx":
        raise ValueError("El archivo de salida debe tener extensión .xlsx")

    df.to_excel(output_file, index=False, engine="openpyxl", sheet_name=sheet_name)


def main():
    """Función principal que maneja la conversión de CSV a XLSX."""
    parser = argparse.ArgumentParser(
        description="Convierte archivos CSV a formato XLSX.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Archivo .csv de entrada"
    )
    parser.add_argument(
        "output_file",
        help="Archivo .xlsx de salida"
    )
    parser.add_argument(
        "--delimiter",
        "--sep",
        dest="delimiter",
        default=None,
        help="Separador CSV. Si se omite, se detecta automáticamente. Ejemplos: ',', ';', '\\t'"
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Codificación del CSV de entrada (default: utf-8-sig)"
    )
    parser.add_argument(
        "--sheet-name",
        default="Sheet1",
        help="Nombre de la hoja XLSX de salida (default: Sheet1)"
    )

    args = parser.parse_args()

    try:
        if not os.path.exists(args.input_file):
            raise FileNotFoundError(args.input_file)

        data = read_csv_to_dataframe(
            args.input_file,
            encoding=args.encoding,
            delimiter=args.delimiter
        )
        write_dataframe_to_xlsx(data, args.output_file, sheet_name=args.sheet_name)

        print(f"Successfully converted {args.input_file} to {args.output_file}")
        print(f"Total records: {len(data)}")
        print(f"Total columns: {len(data.columns)}")

    except ImportError as e:
        sys.stderr.write(f"Error de dependencias: {e}\n")
        sys.exit(1)
    except FileNotFoundError:
        sys.stderr.write(f"Error: Archivo no encontrado - {args.input_file}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error al convertir archivo: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
