#!/usr/bin/env python3
"""
transform_json_category.py

Script especializado para transformar estructura de categorías desde 
campos separados a formato jerárquico. Procesa datos específicos de Sentry.

Funcionalidad:
- Une campos CATEGORIA, SUBCATEGORIA y LINEA en un campo jerárquico único
- Utiliza separador ">" para crear jerarquía: "CATEGORIA>SUBCATEGORIA>LINEA"
- Elimina campos originales después de la unión
- Detecta elementos problemáticos con "/" en SUBCATEGORIA o LINEA
- Exporta elementos problemáticos a CSV para revisión manual
- Elimina duplicados en exportación CSV basado en campos problemáticos

Transformación:
- CATEGORIA: "Cuidado Personal"
- SUBCATEGORIA: "Cuidado del Pelo" 
- LINEA: "Secadores"
- Resultado: "Cuidado Personal>Cuidado del Pelo>Secadores"

Ejecución:
    # Transformación básica
    python3 transform_json_category.py input.json output.json --indent 4
    
    # Con exportación CSV de elementos problemáticos
    python3 transform_json_category.py input.json output.json --csv-export problemas.csv

Ejemplo:
    python3 transform_json_category/transform_json_category.py productos.json productos_categorizados.json --csv-export subcategorias_problematicas.csv

Casos Especiales:
- Campos vacíos se omiten de la jerarquía
- Elementos con "/" en subcategoría/línea se exportan para revisión
- Deduplicación automática en exportación CSV
"""

import json
import csv
import argparse

def transform(input_path, output_path, indent, csv_output_path=None):
    """
    Lee un archivo JSON de entrada, une los campos CATEGORIA, SUBCATEGORIA y LINEA,
    y escribe un nuevo JSON de salida con indentación de espacios según parámetro.
    Si se especifica csv_output_path, exporta a CSV los elementos donde SUBCATEGORIA contenga '/'.
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Asegurar que trabajamos con una lista de elementos
    items = data if isinstance(data, list) else [data]

    transformed = []
    csv_export_items = []
    seen_items = set()
    
    for item in items:
        categoria = item.get("CATEGORIA", "")
        subcategoria = item.get("SUBCATEGORIA", "")
        linea = item.get("LINEA", "")
        
        # Verificar si SUBCATEGORIA o LINEA contienen '/' para exportar a CSV
        has_slash_in_subcategoria = subcategoria and "/" in subcategoria
        has_slash_in_linea = linea and "/" in linea
        
        if csv_output_path and (has_slash_in_subcategoria or has_slash_in_linea):
            # Crear una clave única basada en los campos que tienen '/'
            unique_key = (subcategoria if has_slash_in_subcategoria else "", 
                         linea if has_slash_in_linea else "")
            
            if unique_key not in seen_items:
                csv_export_items.append(item)
                seen_items.add(unique_key)
        
        # Unir los campos no vacíos con '>'
        combined = ">".join(filter(None, [categoria, subcategoria, linea]))

        # Construir nuevo objeto sin las claves originales
        new_item = {k: v for k, v in item.items() if k not in ("CATEGORIA", "SUBCATEGORIA", "LINEA")}
        new_item["CATEGORIA"] = combined
        transformed.append(new_item)

    # Si la entrada no era lista, devolver un solo objeto
    result = transformed[0] if not isinstance(data, list) else transformed

    # Escribir el JSON de salida con indentación configurada
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    
    # Exportar a CSV si se especificó la ruta y hay elementos que exportar
    if csv_output_path and csv_export_items:
        export_to_csv(csv_export_items, csv_output_path)


def export_to_csv(items, csv_path):
    """
    Exporta una lista de elementos JSON a un archivo CSV.
    """
    if not items:
        return
    
    # Obtener todas las claves únicas de todos los elementos
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    
    # Ordenar las claves para tener un orden consistente
    fieldnames = sorted(all_keys)
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def main():
    parser = argparse.ArgumentParser(
        description="Transforma un JSON uniendo CATEGORIA, SUBCATEGORIA y LINEA en un solo campo."
    )
    parser.add_argument(
        "input",
        help="Ruta al archivo JSON de entrada"
    )
    parser.add_argument(
        "output",
        help="Ruta al archivo JSON de salida"
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=4,
        help="Número de espacios para la indentación (por defecto 4)"
    )
    parser.add_argument(
        "--csv-export",
        help="Ruta al archivo CSV para exportar elementos donde SUBCATEGORIA o LINEA contengan '/'"
    )
    args = parser.parse_args()
    transform(args.input, args.output, args.indent, args.csv_export)

if __name__ == "__main__":
    main()
