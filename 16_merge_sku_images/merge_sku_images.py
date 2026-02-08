#!/usr/bin/env python3
"""Combina CSV y JSON para construir objetos de imagen SKU de VTEX con validación opcional de URL.

Ejemplo de uso:
  python3 merge_sku_images.py --json-input products.json --csv-input images.csv --output-json sku_images.json --not-found-csv missing.csv
  
  # Con validación de URL:
  python3 merge_sku_images.py --json-input products.json --csv-input images.csv --output-json sku_images.json --validate-urls --url-timeout 15

El script espera:
  - Entrada JSON: una lista de objetos que contengan al menos un campo (default: RefId) que coincida con los valores SKU del CSV.
    Soporta múltiples formatos:
    * Formato simple: {"RefId": "000013", ...}
    * Formato anidado: {"sku_data": {"RefId": "000013"}, "ref_id": "000013", ...}
  - Entrada CSV: columnas incluyendo SKU, PRODUCTO, URL, y opcionalmente IMAGEN (usado para preservar orden).
    Los SKUs en el CSV pueden venir en múltiples formatos que son normalizados automáticamente:
    * Sin comillas: 000013, 000-013
    * Con comillas dobles: "000013", "000-013"
    * Con comillas simples: '000013', '000-013'
    * Con espacios extras: " 000013 ", " '000013' "

Salida:
  - JSON mapeando cada SKU coincidente a una lista de objetos descriptores de imagen listos para creación de archivos VTEX.
  - CSV de filas cuyo SKU no fue encontrado en la lista de referencia JSON.

Estructura por objeto imagen:
  {  # primera imagen por SKU incluye IsMain y Label
     "IsMain": true,
     "Label": "Main",
     "Name": <PRODUCTO del CSV>,
     "Text": <PRODUCTO slugificado>,
     "Url": <URL del CSV>,
     "Position": <índice base-0 en el grupo>,
     "UrlValid": <true/false si se usa --validate-urls>,
     "StatusCode": <código de estado HTTP si se usa --validate-urls>,
     "ValidationError": <mensaje de error si falló la validación>
  }
  Las imágenes subsecuentes omiten IsMain/Label (no son requeridos).
  Los campos de validación URL (UrlValid, StatusCode, ValidationError) solo se agregan cuando se usa la bandera --validate-urls.
"""

import argparse
import json
import csv
import sys
import unicodedata
import re
import requests
from collections import defaultdict


def validate_url(url: str, timeout: int = 10) -> dict:
    """Valida si una URL existe realizando una petición HTTP HEAD.
    
    Esta función hace una petición HTTP real para verificar si la URL de imagen
    es accesible y retorna una respuesta válida. Usa el método HEAD para minimizar
    la transferencia de datos mientras verifica la validez de la URL.
    
    Args:
        url: La URL de imagen a validar
        timeout: Tiempo límite de petición en segundos (default: 10)
    
    Returns:
        dict: {
            'valid': bool,        # True si URL retorna status < 400
            'status_code': int,   # Código de estado HTTP o None si falló
            'error': str         # Mensaje de error si falló, None en caso contrario
        }
    """
    if not url or not url.strip():
        return {'valid': False, 'status_code': None, 'error': 'URL vacía'}
    
    try:
        # Usar petición HEAD para minimizar transferencia de datos
        response = requests.head(url.strip(), timeout=timeout, allow_redirects=True)
        return {
            'valid': response.status_code < 400,
            'status_code': response.status_code,
            'error': None
        }
    except requests.exceptions.RequestException as e:
        return {
            'valid': False,
            'status_code': None,
            'error': str(e)
        }


def normalize_sku(sku_value: str) -> str:
    """Normaliza un valor SKU removiendo comillas, espacios extras y convirtiendo a string.

    Esta función maneja múltiples formatos de SKU que pueden aparecer en CSV:
    - Con comillas dobles: "000013" → 000013
    - Con comillas simples: '000013' → 000013
    - Con espacios: " 000013 " → 000013
    - Con guiones: "000-013" → 000-013 (se preservan)
    - Valores numéricos: 13 → 000013 (se preserva el formato original)

    Args:
        sku_value: Valor SKU a normalizar (puede ser str, int, float)

    Returns:
        str: SKU normalizado sin comillas ni espacios extras
    """
    if sku_value is None:
        return ""

    # Convertir a string si es necesario
    sku_str = str(sku_value)

    # Remover espacios al inicio y final
    sku_str = sku_str.strip()

    # Remover comillas dobles y simples al inicio y final
    # Esto maneja casos como: "000013", '000013', "000-013"
    sku_str = sku_str.strip('"').strip("'")

    # Remover espacios nuevamente por si había comillas con espacios: " '000013' "
    sku_str = sku_str.strip()

    return sku_str


def slugify(value: str) -> str:
    """Convierte texto a formato slug: minúsculas, sin acentos, guiones en lugar de espacios."""
    # Slugify simplificado: minúsculas, quitar acentos, reemplazar no-alfanuméricos con guiones
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    # reemplazar espacios y caracteres no deseados con guión
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def load_json(path: str):
    """Carga archivo JSON y valida que sea una lista de objetos."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("El archivo JSON debe ser una lista de objetos.")
    return data


def main():
    parser = argparse.ArgumentParser(description="Combina CSV de imágenes SKU con JSON de referencia y produce JSON de archivos VTEX.")
    parser.add_argument("--json-input", required=True, help="Ruta al archivo JSON con SKUs (debe contener campo como RefId)")
    parser.add_argument("--csv-input", required=True, help="Ruta al archivo CSV con columnas incluyendo SKU, PRODUCTO, URL")
    parser.add_argument("--output-json", default="output.json", help="Ruta para escribir la salida JSON combinada")
    parser.add_argument("--not-found-csv", default="not_found.csv", help="Ruta CSV para filas con SKU no encontrado en JSON")
    parser.add_argument("--json-key", default="RefId", help="Nombre del campo dentro de objetos JSON para coincidir con columna SKU del CSV")
    parser.add_argument("--csv-sku-column", default="SKU", help="Nombre de columna en CSV que contiene el SKU")
    parser.add_argument("--csv-product-column", default="PRODUCTO", help="Nombre de columna en CSV para nombre del producto")
    parser.add_argument("--csv-url-column", default="URL", help="Nombre de columna en CSV para URL de imagen")
    parser.add_argument("--csv-order-column", default="IMAGEN", help="Nombre de columna en CSV usado para ordenar dentro del grupo SKU (opcional)")
    parser.add_argument("--validate-urls", action="store_true", help="Validar cada URL de imagen haciendo peticiones HTTP")
    parser.add_argument("--url-timeout", type=int, default=10, help="Tiempo límite en segundos para peticiones de validación URL (default: 10)")
    args = parser.parse_args()

    try:
        json_items = load_json(args.json_input)
    except Exception as e:
        print(f"Error cargando entrada JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Construir conjunto de identificadores SKU válidos desde JSON
    # Soporta múltiples formatos:
    # 1. Formato antiguo: {"RefId": "000013", ...}
    # 2. Formato nuevo: {"sku_data": {"RefId": "000013"}, "ref_id": "000013", ...}
    valid_skus = set()
    for item in json_items:
        ref_id_found = False
        ref_id_value = None

        # Intentar buscar directamente en el nivel raíz (formato antiguo o ref_id en formato nuevo)
        if args.json_key in item:
            ref_id_value = item[args.json_key]
            ref_id_found = True

        # Intentar buscar en sku_data (formato nuevo)
        elif "sku_data" in item and isinstance(item["sku_data"], dict):
            if args.json_key in item["sku_data"]:
                ref_id_value = item["sku_data"][args.json_key]
                ref_id_found = True

        # Intentar buscar ref_id en nivel raíz (formato nuevo - campo alternativo)
        if not ref_id_found and "ref_id" in item and args.json_key.lower() == "refid":
            ref_id_value = item["ref_id"]
            ref_id_found = True

        # Si aún no se encuentra, intentar fallback insensible a mayúsculas en nivel raíz
        if not ref_id_found:
            for k in item:
                if k.lower() == args.json_key.lower():
                    ref_id_value = item[k]
                    ref_id_found = True
                    break

        # Si todavía no se encuentra, intentar en sku_data con fallback insensible a mayúsculas
        if not ref_id_found and "sku_data" in item and isinstance(item["sku_data"], dict):
            for k in item["sku_data"]:
                if k.lower() == args.json_key.lower():
                    ref_id_value = item["sku_data"][k]
                    break

        # Normalizar y agregar el SKU encontrado
        if ref_id_value is not None:
            normalized_sku = normalize_sku(ref_id_value)
            if normalized_sku:  # Solo agregar si no está vacío después de normalizar
                valid_skus.add(normalized_sku)

    if not valid_skus:
        print(f"Advertencia: no se extrajeron SKUs del JSON usando clave '{args.json_key}'.", file=sys.stderr)
    else:
        print(f"SKUs extraídos exitosamente: {len(valid_skus)} únicos encontrados")

    # Leer CSV y agrupar filas por SKU
    # Normalizar SKUs del CSV para manejar comillas y espacios
    groups = defaultdict(list)
    not_found_rows = []
    with open(args.csv_input, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        headers = reader.fieldnames or []
        for row in reader:
            sku_raw = row.get(args.csv_sku_column, "")
            sku = normalize_sku(sku_raw)

            if sku == "":
                continue
            if sku not in valid_skus:
                not_found_rows.append(row)
                continue
            groups[sku].append(row)

    # Preparar estructura de salida
    output = {}
    for sku, rows in groups.items():
        # Ordenamiento opcional si la columna de orden existe y es numérica
        order_key = args.csv_order_column
        try:
            if all(order_key in r for r in rows):
                # ordenar por entero si es posible, usar orden original como fallback
                def sort_val(r):
                    try:
                        return int(r.get(order_key, 0))
                    except Exception:
                        return 0
                rows = sorted(rows, key=sort_val)
        except Exception:
            pass

        image_objs = []
        for idx, r in enumerate(rows):
            name = r.get(args.csv_product_column, "").strip()
            url = r.get(args.csv_url_column, "").strip()
            text = slugify(name) if name else ""
            image_obj = {
                "Name": name,
                "Text": text,
                "Url": url,
                "Position": idx,
            }
            if idx == 0:
                image_obj["IsMain"] = True
                image_obj["Label"] = "Main"
            image_objs.append(image_obj)
        output[sku] = image_objs

    # PASO 1: Escribir JSON inicial con todas las imágenes que se incluirán en archivo final
    # Esto crea la estructura base sin campos de validación
    with open(args.output_json, "w", encoding="utf-8") as outf:
        json.dump(output, outf, indent=2, ensure_ascii=False)

    # PASO 2: Validar URLs SOLO para imágenes que están en el archivo de salida final
    # Esto asegura que solo validemos URLs que realmente se usarán, no todas las entradas CSV
    if args.validate_urls:
        print(f"\nValidando URLs en el archivo de salida: {args.output_json}")
        print("IMPORTANTE: Solo se validan las URLs que quedaron en el archivo final\n")
        valid_urls = 0
        invalid_urls = 0
        
        # Procesar cada SKU y sus imágenes que están en la salida final
        for sku, images in output.items():
            for idx, image in enumerate(images):
                url = image.get("Url", "")
                
                # Hacer petición HTTP para validar si la URL de imagen realmente existe
                validation_result = validate_url(url, args.url_timeout)
                
                # Agregar campos de validación al objeto imagen existente en memoria
                image["UrlValid"] = validation_result['valid']
                image["StatusCode"] = validation_result['status_code']
                if validation_result['error']:
                    image["ValidationError"] = validation_result['error']
                
                # Contar resultados y mostrar progreso en tiempo real
                if validation_result['valid']:
                    valid_urls += 1
                    status_icon = "✓"
                else:
                    invalid_urls += 1
                    status_icon = "✗"
                
                status_info = validation_result.get('status_code', validation_result.get('error', 'Error'))
                print(f"  {sku} imagen {idx+1}: {url} -> {status_icon} ({status_info})")
        
        # PASO 3: Reescribir el archivo JSON incluyendo los nuevos campos de validación
        # Esto actualiza el mismo archivo con campos UrlValid, StatusCode y ValidationError
        with open(args.output_json, "w", encoding="utf-8") as outf:
            json.dump(output, outf, indent=2, ensure_ascii=False)
        
        print(f"\nValidación completada: ✓ {valid_urls} válidas, ✗ {invalid_urls} inválidas")
        print(f"Archivo actualizado con campos de validación: {args.output_json}")

    # Escribir CSV de no encontrados si hay alguno
    if not_found_rows:
        with open(args.not_found_csv, "w", newline="", encoding="utf-8") as nf:
            writer = csv.DictWriter(nf, fieldnames=headers)
            writer.writeheader()
            writer.writerows(not_found_rows)

    # Resumen a stdout
    total_processed = sum(len(v) for v in output.values())
    print(f"\nResumen:")
    print(f"SKUs en referencia JSON: {len(valid_skus)}")
    print(f"Grupos SKU encontrados en CSV: {len(output)}")
    print(f"Total imágenes exportadas: {total_processed}")
    
    if not_found_rows:
        print(f"Filas sin SKU coincidente escritas en: {args.not_found_csv} (count={len(not_found_rows)})")
    else:
        print("Todos los SKUs del CSV coincidieron con la referencia JSON.")


if __name__ == "__main__":
    main()
