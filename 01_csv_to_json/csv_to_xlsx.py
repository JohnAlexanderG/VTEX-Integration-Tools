#!/usr/bin/env python3
"""
csv_to_xlsx.py

Script para convertir archivos CSV a formato Excel (.xlsx o .xls clasico).
Complementa el flujo de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Lee archivos CSV con codificación UTF-8 por defecto
- Detecta automáticamente el separador cuando no se especifica
- Convierte valores vacíos a cadenas vacías
- Exporta a la primera hoja de un archivo .xlsx o .xls (clásico), según --format
  o la extensión del archivo de salida

Dependencias:
- pandas: requerido para lectura de CSV y escritura de Excel
- openpyxl: requerido para escribir archivos .xlsx
- xlwt: requerido para escribir archivos .xls (clásico, límite 65536 filas / 256 columnas)

Ejecución:
    # Conversión básica CSV a XLSX (formato inferido de la extensión)
    python3 csv_to_xlsx.py entrada.csv salida.xlsx

    # Conversión a XLS clásico (formato inferido de la extensión)
    python3 csv_to_xlsx.py entrada.csv salida.xls

    # Forzar formato explícitamente con --format
    python3 csv_to_xlsx.py entrada.csv salida.xls --format xls

    # CSV separado por punto y coma
    python3 csv_to_xlsx.py entrada.csv salida.xlsx --delimiter ";"

    # CSV con codificación distinta
    python3 csv_to_xlsx.py entrada.csv salida.xlsx --encoding latin-1

Ejemplo:
    python3 01_csv_to_json/csv_to_xlsx.py productos.csv productos.xlsx
    python3 01_csv_to_json/csv_to_xlsx.py productos.csv productos.xls --format xls
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

try:
    import xlwt  # noqa: F401
    XLWT_AVAILABLE = True
except ImportError:
    XLWT_AVAILABLE = False

ENGINE_BY_FORMAT = {
    "xlsx": "openpyxl",
    "xls": "xlwt",
}


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


def resolve_output_format(output_file, format_arg):
    """
    Determina el formato de salida ('xlsx' o 'xls') a partir del flag --format
    o, si se omite, de la extensión del archivo de salida.

    :param output_file: Ruta del archivo de salida
    :param format_arg: Valor de --format ('xlsx', 'xls' o None)
    :return: 'xlsx' o 'xls'
    """
    if format_arg:
        return format_arg

    output_extension = os.path.splitext(output_file)[1].lower().lstrip(".")
    if output_extension not in ENGINE_BY_FORMAT:
        raise ValueError(
            "No se pudo determinar el formato de salida. "
            "Usa --format xlsx|xls o una extensión .xlsx/.xls"
        )
    return output_extension


def write_dataframe_to_excel(df, output_file, output_format, sheet_name="Sheet1"):
    """
    Escribe un DataFrame a un archivo Excel (.xlsx o .xls clásico).

    :param df: pandas.DataFrame con los datos
    :param output_file: Ruta del archivo de salida
    :param output_format: 'xlsx' o 'xls'
    :param sheet_name: Nombre de la hoja de Excel
    """
    if output_format == "xlsx" and not OPENPYXL_AVAILABLE:
        raise ImportError(
            "openpyxl es requerido para escribir archivos .xlsx.\n"
            "Instálalo con: pip install openpyxl"
        )
    if output_format == "xls" and not XLWT_AVAILABLE:
        raise ImportError(
            "xlwt es requerido para escribir archivos .xls (clásico).\n"
            "Instálalo con: pip install xlwt"
        )
    if output_format == "xls" and (len(df) > 65536 or len(df.columns) > 256):
        raise ValueError(
            f"El formato .xls clásico soporta máximo 65536 filas y 256 columnas "
            f"(datos: {len(df)} filas, {len(df.columns)} columnas). Usa --format xlsx."
        )

    if output_format == "xls":
        # pandas >= 2.0 eliminó el dispatch del engine "xlwt" en to_excel(),
        # por lo que el archivo .xls clásico se escribe directamente con xlwt.
        write_dataframe_to_xls(df, output_file, sheet_name=sheet_name)
    else:
        df.to_excel(
            output_file,
            index=False,
            engine=ENGINE_BY_FORMAT[output_format],
            sheet_name=sheet_name,
        )


def write_dataframe_to_xls(df, output_file, sheet_name="Sheet1"):
    """
    Escribe un DataFrame a un archivo .xls clásico usando xlwt directamente.

    :param df: pandas.DataFrame con los datos
    :param output_file: Ruta del archivo .xls de salida
    :param sheet_name: Nombre de la hoja de Excel
    """
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(sheet_name)

    for col_index, column_name in enumerate(df.columns):
        sheet.write(0, col_index, column_name)

    for row_index, row in enumerate(df.itertuples(index=False), start=1):
        for col_index, value in enumerate(row):
            sheet.write(row_index, col_index, value)

    workbook.save(output_file)


def main():
    """Función principal que maneja la conversión de CSV a Excel (.xlsx o .xls)."""
    parser = argparse.ArgumentParser(
        description="Convierte archivos CSV a formato Excel (.xlsx o .xls clásico).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Archivo .csv de entrada"
    )
    parser.add_argument(
        "output_file",
        help="Archivo .xlsx o .xls de salida"
    )
    parser.add_argument(
        "--format",
        dest="format",
        choices=["xlsx", "xls"],
        default=None,
        help="Formato de salida. Si se omite, se infiere de la extensión de output_file"
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
        help="Nombre de la hoja de salida (default: Sheet1)"
    )

    args = parser.parse_args()

    try:
        if not os.path.exists(args.input_file):
            raise FileNotFoundError(args.input_file)

        output_format = resolve_output_format(args.output_file, args.format)

        data = read_csv_to_dataframe(
            args.input_file,
            encoding=args.encoding,
            delimiter=args.delimiter
        )
        write_dataframe_to_excel(data, args.output_file, output_format, sheet_name=args.sheet_name)

        print(f"Successfully converted {args.input_file} to {args.output_file} ({output_format})")
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
