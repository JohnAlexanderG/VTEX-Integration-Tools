#!/usr/bin/env python3
"""
translate_keys.py

Script para traducir claves de JSON del español al inglés y eliminar duplicados.
Convierte las claves en español a inglés y mantiene solo la versión en inglés
cuando existe una clave duplicada.

Uso:
    python3 translate_keys.py input.json output.json --indent 4
"""
import json
import argparse
import sys

def get_translation_map():
    """
    Retorna un diccionario con las traducciones de español a inglés
    y las claves que deben ser eliminadas cuando existe la versión en inglés.
    """
    translation_map = {
        "Contenedor": "Container",
        "Nombre": "Name",  # Se elimina "Nombre" y se mantiene "Name"
        "Creado": "Created",
        "Imágenes": "Images",
        "Para_recogida": "For_pickup",
        "Categoría": "CategoryPath",
        "Stock": "Stock",  # Ya está en inglés
        "Eliminó": "Deleted",
        "Producto_Descontinuado": "Discontinued_Product",
        "Vender_usando_ERP": "Sell_using_ERP",
        "Vender_en_la_Tienda_Web": "Sell_on_Web_Store",
        "Vender_usando_POS": "Sell_using_POS",
        "Vender_a_través_de_EDI": "Sell_through_EDI",
        "Peso": "Weight",
        "Precio_Sugerido": "Suggested_Price",
        "Lista_de_Precios_1": "Price_List_1",
        "Lista_de_Precios_2": "Price_List_2",
        "Lista_de_Precios_3": "Price_List_3"
    }
    
    # Claves que deben eliminarse si existe la versión en inglés
    keys_to_remove_if_english_exists = {
        "Nombre": "Name",  # Eliminar "Nombre" si existe "Name"
        "Descripción": "Description"  # Eliminar "Descripción" si existe "Description"
    }
    
    return translation_map, keys_to_remove_if_english_exists

def translate_item(item):
    """
    Traduce las claves de un objeto JSON del español al inglés
    y elimina duplicados manteniendo la versión en inglés.
    Ordena las claves alfabéticamente en el resultado.
    """
    translation_map, keys_to_remove = get_translation_map()
    result = {}
    
    # Primero, verificar qué claves en inglés ya existen
    english_keys_present = set()
    for key in item.keys():
        if key in keys_to_remove.values():  # Es una clave en inglés
            english_keys_present.add(key)
    
    # Procesar cada clave
    for key, value in item.items():
        # Si es una clave que debe eliminarse porque existe la versión en inglés
        if key in keys_to_remove and keys_to_remove[key] in english_keys_present:
            continue  # Saltar esta clave (eliminarla)
        
        # Si tiene traducción, usar la traducción
        if key in translation_map:
            translated_key = translation_map[key]
            # Procesar valor especial para Categoría
            if key == "Categoría":
                processed_value = value.replace(">", "/")
                result[translated_key] = processed_value
            else:
                result[translated_key] = value
        else:
            # Mantener la clave original
            result[key] = value
    
    # Ordenar las claves alfabéticamente
    sorted_result = {}
    for key in sorted(result.keys()):
        sorted_result[key] = result[key]
    
    return sorted_result

def translate_json(input_file, output_file, indent=None):
    """
    Lee un archivo JSON, traduce las claves y escribe el resultado.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error al leer el archivo de entrada: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Procesar los datos
    if isinstance(data, dict):
        translated_data = translate_item(data)
    elif isinstance(data, list):
        translated_data = [translate_item(item) for item in data]
    else:
        print("El archivo JSON debe contener un objeto o una lista de objetos", file=sys.stderr)
        sys.exit(1)
    
    # Escribir el resultado
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(translated_data, f, ensure_ascii=False, indent=indent)
            f.write("\n")
    except Exception as e:
        print(f"Error al escribir el archivo de salida: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Traduce claves de JSON del español al inglés y elimina duplicados.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'input_file',
        help='Archivo JSON de entrada'
    )
    parser.add_argument(
        'output_file',
        help='Archivo JSON de salida'
    )
    parser.add_argument(
        '-i', '--indent',
        type=int,
        default=4,
        help='Nivel de indentación para el JSON de salida (por defecto: 4)'
    )
    
    args = parser.parse_args()
    
    translate_json(args.input_file, args.output_file, args.indent)
    print(f"Traducción completada. Archivo guardado en: {args.output_file}")

if __name__ == '__main__':
    main()