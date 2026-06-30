"""
txt_to_csv.py - Convierte archivos de texto plano (.txt) con delimitador punto y coma a formato CSV limpio.

El archivo de entrada tiene campos separados por ";" con espacios en blanco extra alrededor de cada valor.
Este script elimina esos espacios, descarta la columna vacía final (resultado del ";" al final de línea),
y genera un CSV estándar con codificación UTF-8.

Uso:
    python3 txt_to_csv.py input.txt output.csv
    python3 txt_to_csv.py input.txt output.csv --delimiter ","
    python3 txt_to_csv.py input.txt output.csv --skip-empty-rows
    python3 txt_to_csv.py input.txt  # genera output con el mismo nombre base

Ejemplos:
    python3 60_txt_to_csv/txt_to_csv.py datos.txt productos.csv
    python3 60_txt_to_csv/txt_to_csv.py datos.txt productos.csv --skip-empty-rows
    python3 60_txt_to_csv/txt_to_csv.py datos.txt productos.csv --delimiter "," --quotechar '"'
"""

import csv
import sys
import argparse
from pathlib import Path
from typing import Optional


# Columnas esperadas en el archivo de entrada
EXPECTED_COLUMNS = [
    "SKU",
    "Categoria",
    "Subcategoria",
    "Linea",
    "Nombre",
    "Descripcion",
    "Nombre Especificacion",
    "Especificacion",
    "cantidad",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convierte un .txt con delimitador ';' a CSV limpio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input",
        help="Archivo de texto de entrada (.txt)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Archivo CSV de salida (opcional; si se omite se genera con el mismo nombre base del input)",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="Delimitador para el CSV de salida (por defecto: ',')",
    )
    parser.add_argument(
        "--quotechar",
        default='"',
        help="Carácter de comillas para el CSV de salida (por defecto: '\"')",
    )
    parser.add_argument(
        "--skip-empty-rows",
        action="store_true",
        help="Omitir filas donde todos los campos estén vacíos",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="El archivo de entrada NO tiene fila de encabezado; usar columnas predefinidas",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Codificación del archivo de entrada (por defecto: utf-8)",
    )
    return parser.parse_args()


def resolve_output_path(input_path: str, output_arg: Optional[str]) -> Path:
    """Determina la ruta del archivo de salida."""
    if output_arg:
        return Path(output_arg)
    return Path(input_path).with_suffix(".csv")


def clean_field(value: str) -> str:
    """Elimina espacios en blanco al inicio y al final de un campo."""
    return value.strip()


def parse_line(line: str, input_separator: str = ";") -> list[str]:
    """
    Divide una línea por el separador, limpia cada campo y elimina
    la columna fantasma que aparece por el ';' al final de línea.
    """
    parts = line.rstrip("\n\r").split(input_separator)
    cleaned = [clean_field(p) for p in parts]

    # Si el último campo está vacío (por el ";" al final), descartarlo
    if cleaned and cleaned[-1] == "":
        cleaned = cleaned[:-1]

    return cleaned


def convert(
    input_path: str,
    output_path: Path,
    output_delimiter: str = ",",
    quotechar: str = '"',
    skip_empty_rows: bool = False,
    has_header: bool = True,
    encoding: str = "utf-8",
) -> dict:
    """
    Lee el archivo de texto, limpia los datos y escribe el CSV.

    Retorna un dict con estadísticas de la conversión.
    """
    stats = {
        "total_rows": 0,
        "written_rows": 0,
        "skipped_rows": 0,
        "output_file": str(output_path),
    }

    with open(input_path, encoding=encoding, errors="replace") as infile, \
         open(output_path, "w", newline="", encoding="utf-8") as outfile:

        writer = csv.writer(
            outfile,
            delimiter=output_delimiter,
            quotechar=quotechar,
            quoting=csv.QUOTE_MINIMAL,
        )

        header_written = False

        for raw_line in infile:
            # Ignorar líneas completamente vacías o solo whitespace
            if not raw_line.strip():
                continue

            fields = parse_line(raw_line)

            # Primera fila: encabezado
            if not header_written:
                if has_header:
                    writer.writerow(fields)
                    header_written = True
                    continue
                else:
                    # Usar columnas predefinidas si no hay encabezado
                    writer.writerow(EXPECTED_COLUMNS)
                    header_written = True

            stats["total_rows"] += 1

            # Omitir filas completamente vacías si se solicita
            if skip_empty_rows and all(f == "" for f in fields):
                stats["skipped_rows"] += 1
                continue

            writer.writerow(fields)
            stats["written_rows"] += 1

    return stats


def main():
    args = parse_args()

    input_path = args.input
    output_path = resolve_output_path(input_path, args.output)

    # Validar que el archivo de entrada existe
    if not Path(input_path).is_file():
        print(f"❌ Error: No se encontró el archivo de entrada '{input_path}'", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Leyendo:  {input_path}")
    print(f"💾 Guardando: {output_path}")

    try:
        stats = convert(
            input_path=input_path,
            output_path=output_path,
            output_delimiter=args.delimiter,
            quotechar=args.quotechar,
            skip_empty_rows=args.skip_empty_rows,
            has_header=not args.no_header,
            encoding=args.encoding,
        )
    except Exception as exc:
        print(f"❌ Error durante la conversión: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅ Conversión completada:")
    print(f"   Filas procesadas : {stats['total_rows']}")
    print(f"   Filas escritas   : {stats['written_rows']}")
    print(f"   Filas omitidas   : {stats['skipped_rows']}")
    print(f"   Archivo de salida: {stats['output_file']}")


if __name__ == "__main__":
    main()
