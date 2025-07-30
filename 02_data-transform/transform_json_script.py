#!/usr/bin/env python3
"""
transform_json_script.py

Script de transformación JSON que divide claves compuestas en campos individuales 
normalizados. Segundo paso del flujo de transformación de datos VTEX.

Funcionalidad:
- Procesa claves con formato "Campo1, Campo2, Campo3" separándolas en campos individuales
- Normaliza nombres de campos (espacios → guiones bajos, caracteres especiales eliminados)
- Asocia cada valor con su campo correspondiente basado en posición
- Mantiene campos no compuestos sin cambios
- Soporta tanto objetos individuales como arrays de objetos JSON

Procesamiento:
- "Lista de Precios 1, Lista de Precios 2" → "Lista_de_Precios_1", "Lista_de_Precios_2"
- "valor1, valor2" → se asignan respectivamente a cada campo normalizado
- Aplica regex para normalización: espacios/guiones → "_", caracteres especiales eliminados

Ejecución:
    # Transformación básica
    python3 transform_json_script.py entrada.json salida.json --indent 4
    
    # Con indentación personalizada
    python3 transform_json_script.py data.json transformed.json --indent 2

Ejemplo:
    python3 02_data-transform/transform_json_script.py productos.json productos_transform.json --indent 4
"""
import json
import argparse
import re

def normalize_label(label: str) -> str:
    """
    Normalize a label by stripping whitespace and replacing spaces and other non-alphanumeric characters with underscores.
    """
    # Remove leading/trailing whitespace
    lbl = label.strip()
    # Replace spaces and dashes with underscore
    lbl = re.sub(r"[\s-]+", "_", lbl)
    # Remove any characters that are not alphanumeric or underscore
    lbl = re.sub(r"[^A-Za-z0-9_]", "", lbl)
    return lbl

def transform_item(item: dict) -> dict:
    """
    Takes a dictionary `item` and splits any keys containing commas into separate keys with their corresponding values.
    Keys like "Lista de Precios 1, Lista de Precios 2" will become:
      "Lista_de_Precios_1": value1,
      "Lista_de_Precios_2": value2
    """
    result = {}
    for key, value in item.items():
        if ',' in key:
            # Split composite key into individual labels
            labels = [lbl for lbl in key.split(',') if lbl.strip()]
            # Split the values by comma
            values = [val for val in value.split(',') if val.strip()]
            # Pair each label with its corresponding value
            for lbl, val in zip(labels, values):
                normalized = normalize_label(lbl)
                result[normalized] = val.strip()
        else:
            # Keep original key/value pairs
            result[key] = value
    return result


def transform_json(input_path: str, output_path: str, indent: int):
    """
    Reads a JSON file from `input_path`, transforms its contents by splitting composite keys,
    and writes the result to `output_path` with the specified indentation.
    """
    with open(input_path, 'r', encoding='utf-8') as infile:
        data = json.load(infile)

    # Handle both single object and list of objects
    if isinstance(data, dict):
        transformed = transform_item(data)
    elif isinstance(data, list):
        transformed = [transform_item(item) for item in data]
    else:
        raise ValueError('Input JSON must be an object or an array of objects')

    with open(output_path, 'w', encoding='utf-8') as outfile:
        json.dump(transformed, outfile, ensure_ascii=False, indent=indent)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Transform JSON by splitting composite keys into separate fields, normalizing names.'
    )
    parser.add_argument(
        'input', help='Path to the input JSON file'
    )
    parser.add_argument(
        'output', help='Path where the transformed JSON will be saved'
    )
    parser.add_argument(
        '-i', '--indent', type=int, default=4,
        help='Number of spaces to use for indentation in the output JSON'
    )

    args = parser.parse_args()
    transform_json(args.input, args.output, args.indent)

    print(f"Transformed JSON has been written to {args.output} with indent={args.indent}")

