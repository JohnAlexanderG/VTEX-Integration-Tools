#!/usr/bin/env python3
"""
dynamodb_to_json.py

Convierte un archivo CSV que contiene una columna con datos en formato DynamoDB
AttributeValue JSON a un archivo JSON plano. Los campos deserializados del DynamoDB
se fusionan con las demás columnas del CSV.

Funcionalidad:
- Lee archivos CSV con una columna que contiene JSON en formato DynamoDB AttributeValue
- Deserializa recursivamente los tipos DynamoDB (S, N, BOOL, NULL, L, M, SS, NS, BS)
- Fusiona los campos deserializados de forma plana con las demás columnas del CSV
- Soporta entrada desde stdin y salida a stdout para pipelines
- Mantiene codificación UTF-8 para caracteres especiales

Dependencias:
- Solo librería estándar: csv, json, argparse, sys

Ejecución:
    # Conversión básica
    python3 dynamodb_to_json.py entrada.csv salida.json --indent 4

    # Usando pipelines
    cat entrada.csv | python3 dynamodb_to_json.py - - -i 4

    # Columna personalizada
    python3 dynamodb_to_json.py entrada.csv salida.json --vtex-data-column my_column

Ejemplo:
    python3 43_dynamodb_to_json/dynamodb_to_json.py export.csv output.json --indent 4
"""
import csv
import json
import argparse
import sys


def deserialize_dynamodb_value(attr):
    """
    Convierte recursivamente un valor DynamoDB AttributeValue a un valor Python plano.

    Tipos soportados:
        {"S": "val"}         -> "val"
        {"N": "123"}         -> 123 (int) o 99.99 (float)
        {"BOOL": true}       -> True
        {"NULL": true}       -> None
        {"L": [...]}         -> [...] (recursivo)
        {"M": {...}}         -> {...} (recursivo)
        {"SS": [...]}        -> [...]
        {"NS": [...]}        -> [números]
        {"BS": [...]}        -> [...]

    Tipos desconocidos o malformados se retornan tal cual.
    """
    if not isinstance(attr, dict):
        return attr

    if len(attr) != 1:
        # No es un AttributeValue estándar, intentar deserializar como mapa
        return {k: deserialize_dynamodb_value(v) for k, v in attr.items()}

    type_key = next(iter(attr))
    value = attr[type_key]

    if type_key == "S":
        return value

    if type_key == "N":
        try:
            num = int(value)
            return num
        except (ValueError, TypeError):
            pass
        try:
            num = float(value)
            return num
        except (ValueError, TypeError):
            return value

    if type_key == "BOOL":
        return value

    if type_key == "NULL":
        return None

    if type_key == "L":
        if isinstance(value, list):
            return [deserialize_dynamodb_value(item) for item in value]
        return value

    if type_key == "M":
        if isinstance(value, dict):
            return {k: deserialize_dynamodb_value(v) for k, v in value.items()}
        return value

    if type_key == "SS":
        if isinstance(value, list):
            return list(value)
        return value

    if type_key == "NS":
        if isinstance(value, list):
            result = []
            for v in value:
                try:
                    result.append(int(v))
                except (ValueError, TypeError):
                    try:
                        result.append(float(v))
                    except (ValueError, TypeError):
                        result.append(v)
            return result
        return value

    if type_key == "BS":
        if isinstance(value, list):
            return list(value)
        return value

    # Tipo desconocido, retornar tal cual
    return attr


def process_csv_row(row, vtex_data_column):
    """
    Procesa una fila del CSV: copia las columnas normales y deserializa
    la columna DynamoDB, fusionando los campos resultantes de forma plana.

    :param row: diccionario de la fila CSV
    :param vtex_data_column: nombre de la columna con datos DynamoDB
    :return: diccionario con los datos procesados
    """
    result = {}

    # Copiar todas las columnas excepto vtex_data
    for key, value in row.items():
        if key != vtex_data_column:
            result[key] = value

    # Procesar la columna DynamoDB
    raw_value = row.get(vtex_data_column, "")

    if not raw_value or raw_value.strip() == "":
        return result

    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as e:
        sys.stderr.write(f"Advertencia: JSON malformado en columna '{vtex_data_column}': {e}\n")
        result[vtex_data_column] = raw_value
        return result

    deserialized = deserialize_dynamodb_value(parsed)

    if isinstance(deserialized, dict):
        # Fusionar campos de forma plana
        result.update(deserialized)
    else:
        # Si no es un diccionario, guardar bajo la clave original
        result[vtex_data_column] = deserialized

    return result


def convert_dynamodb_csv_to_json(input_file, output_file, indent=None, vtex_data_column="vtex_data"):
    """
    Lee un CSV con datos DynamoDB, los deserializa y escribe un JSON plano.

    :param input_file: archivo CSV de entrada (file-like object)
    :param output_file: archivo JSON de salida (file-like object)
    :param indent: nivel de indentación para el JSON
    :param vtex_data_column: nombre de la columna con datos DynamoDB
    """
    reader = csv.DictReader(input_file)

    if reader.fieldnames and vtex_data_column not in reader.fieldnames:
        sys.stderr.write(
            f"Advertencia: columna '{vtex_data_column}' no encontrada en el CSV. "
            f"Columnas disponibles: {reader.fieldnames}\n"
        )

    records = []
    error_count = 0

    for i, row in enumerate(reader, start=1):
        try:
            processed = process_csv_row(row, vtex_data_column)
            records.append(processed)
        except Exception as e:
            error_count += 1
            sys.stderr.write(f"Error procesando fila {i}: {e}\n")
            # Incluir la fila sin procesar como fallback
            fallback = {k: v for k, v in row.items()}
            records.append(fallback)

    json.dump(records, output_file, ensure_ascii=False, indent=indent)
    output_file.write("\n")

    # Resumen a stderr
    sys.stderr.write(f"Procesados: {len(records)} registros")
    if error_count > 0:
        sys.stderr.write(f" ({error_count} con errores)")
    sys.stderr.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convierte CSV con datos DynamoDB AttributeValue JSON a JSON plano.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="-",
        help="Archivo CSV de entrada (por defecto: stdin)",
    )
    parser.add_argument(
        "json_output",
        nargs="?",
        default="-",
        help="Archivo JSON de salida (por defecto: stdout)",
    )
    parser.add_argument(
        "-i",
        "--indent",
        type=int,
        default=None,
        help="Nivel de indentación para el JSON (por defecto: compacto)",
    )
    parser.add_argument(
        "--vtex-data-column",
        type=str,
        default="vtex_data",
        help="Nombre de la columna con datos DynamoDB (por defecto: vtex_data)",
    )
    args = parser.parse_args()

    try:
        # Entrada
        if args.input_file == "-":
            input_stream = sys.stdin
        else:
            input_stream = open(args.input_file, "r", encoding="utf-8")

        # Salida
        if args.json_output == "-":
            output_stream = sys.stdout
        else:
            output_stream = open(args.json_output, "w", encoding="utf-8")

        convert_dynamodb_csv_to_json(
            input_stream, output_stream, indent=args.indent, vtex_data_column=args.vtex_data_column
        )

        # Cerrar archivos si se abrieron
        if input_stream != sys.stdin:
            input_stream.close()
        if output_stream != sys.stdout:
            output_stream.close()

    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
