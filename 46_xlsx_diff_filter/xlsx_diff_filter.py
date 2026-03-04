"""
xlsx_diff_filter.py — Compara dos archivos .xlsx y extrae registros nuevos.

Compara el archivo base con el archivo nuevo usando una columna clave.
Los encabezados en ambos archivos de entrada están en la SEGUNDA línea (fila 2).
El archivo de salida tiene los encabezados en la PRIMERA línea (estándar).

Genera un .xlsx con los registros del archivo nuevo que NO existen en el archivo base.

Usage:
    python3 xlsx_diff_filter.py <base_file.xlsx> <new_file.xlsx> <output_file.xlsx> --key-column COLUMNA
    python3 xlsx_diff_filter.py base.xlsx nuevos.xlsx diff.xlsx -k "SKU"
    python3 xlsx_diff_filter.py base.xlsx nuevos.xlsx diff.xlsx -k "Código" --sheet "Hoja1" -v

Examples:
    python3 46_xlsx_diff_filter/xlsx_diff_filter.py base.xlsx nuevos.xlsx diff.xlsx --key-column "SKU"
    python3 46_xlsx_diff_filter/xlsx_diff_filter.py base.xlsx nuevos.xlsx diff.xlsx -k "Código" -v
"""

import argparse
import sys

try:
    import pandas as pd
    import openpyxl
except ImportError as e:
    print(f"Error: Dependencia faltante — {e}")
    print("Instalar con: pip install pandas openpyxl")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compara dos archivos .xlsx y extrae registros del archivo nuevo que no existen en el base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("base_file", help="Archivo base de referencia (.xlsx)")
    parser.add_argument("new_file", help="Archivo con datos nuevos (.xlsx)")
    parser.add_argument("output_file", help="Ruta del archivo de salida (.xlsx)")
    parser.add_argument(
        "--key-column", "-k",
        required=True,
        metavar="COLUMNA",
        help="Nombre exacto de la columna clave para comparación",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        metavar="HOJA",
        help="Nombre o índice (0-based) de la hoja a leer (default: primera hoja)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Logging detallado",
    )
    return parser.parse_args()


def load_xlsx(path: str, sheet, verbose: bool) -> pd.DataFrame:
    """Lee un archivo .xlsx con encabezados en la segunda línea (header=1)."""
    # Intentar convertir sheet a entero si es posible
    try:
        sheet = int(sheet)
    except (ValueError, TypeError):
        pass

    if verbose:
        print(f"  Leyendo: {path} (hoja: {sheet!r}, encabezados en fila 2)")

    try:
        df = pd.read_excel(path, sheet_name=sheet, header=1, dtype=str)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{path}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error al leer '{path}': {e}")
        sys.exit(1)

    # Eliminar columnas completamente sin nombre (artefactos de Excel)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed:")]

    if verbose:
        print(f"    Filas leídas: {len(df)}, Columnas: {list(df.columns)}")

    return df


def validate_key_column(df: pd.DataFrame, key_column: str, file_label: str):
    if key_column not in df.columns:
        print(f"Error: La columna '{key_column}' no existe en {file_label}.")
        print(f"  Columnas disponibles: {list(df.columns)}")
        sys.exit(1)


def main():
    args = parse_args()

    print(f"Archivo base:  {args.base_file}")
    print(f"Archivo nuevo: {args.new_file}")
    print(f"Columna clave: {args.key_column}")

    # Cargar archivos
    base_df = load_xlsx(args.base_file, args.sheet, args.verbose)
    new_df = load_xlsx(args.new_file, args.sheet, args.verbose)

    # Validar columna clave
    validate_key_column(base_df, args.key_column, f"'{args.base_file}'")
    validate_key_column(new_df, args.key_column, f"'{args.new_file}'")

    # Construir set de claves del archivo base
    base_keys = set(base_df[args.key_column].dropna().astype(str).str.strip())

    if args.verbose:
        print(f"\n  Claves únicas en base: {len(base_keys)}")

    # Filtrar registros del archivo nuevo que NO están en el base
    mask = ~new_df[args.key_column].astype(str).str.strip().isin(base_keys)
    new_records_df = new_df[mask].reset_index(drop=True)

    # Estadísticas
    print(f"\nResultados:")
    print(f"  Total registros en base:  {len(base_df)}")
    print(f"  Total registros en nuevo: {len(new_df)}")
    print(f"  Registros nuevos (diff):  {len(new_records_df)}")

    if len(new_records_df) == 0:
        print("\nNo hay registros nuevos. No se genera archivo de salida.")
        return

    # Escribir output con encabezados en fila 1 (estándar)
    try:
        new_records_df.to_excel(args.output_file, index=False)
        print(f"\nArchivo generado: {args.output_file}")
    except Exception as e:
        print(f"Error al escribir '{args.output_file}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
