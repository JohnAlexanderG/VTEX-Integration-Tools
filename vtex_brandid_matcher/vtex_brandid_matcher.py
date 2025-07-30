#!/usr/bin/env python3
"""
vtex_brandid_matcher.py

Script de integración VTEX para mapear BrandId de productos usando la API de marcas VTEX.
Cuarto paso del flujo de transformación de datos.

Funcionalidad:
- Conecta con la API de VTEX para obtener todas las marcas del catálogo
- Carga archivo de marcas local (marcas.json) con mapeo SKU → Marca
- Busca BrandId para cada producto basado en RefId → SKU → Marca → BrandId
- Asigna BrandId correspondiente a cada producto en el dataset
- Exporta productos sin BrandId encontrado a CSV para revisión manual
- Genera archivo final con todos los productos procesados

Flujo de Mapeo:
1. RefId del producto → busca SKU en marcas.json
2. SKU encontrado → obtiene nombre de Marca
3. Nombre de Marca → busca BrandId en catálogo VTEX (matching exacto, mayúsculas)
4. BrandId encontrado → asigna al producto, sino → BrandId = null

Ejecución:
    # Mapeo básico
    python3 vtex_brandid_matcher.py marcas.json data.json --account ACCOUNT_NAME
    
    # Con archivos de salida personalizados
    python3 vtex_brandid_matcher.py marcas.json data.json --account ACCOUNT_NAME --output_json final.json --output_csv faltantes.csv

Ejemplo:
    python3 vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json productos.json --account homesentry

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey y X-VTEX-API-AppToken
- marcas.json: archivo con mapeo de SKU a nombre de marca
"""
import json
import csv
import requests
import argparse
import os
from dotenv import load_dotenv

# Cargar variables desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Argument parser
parser = argparse.ArgumentParser(description='Mapear BrandId desde VTEX a data.json usando marcas.json')
parser.add_argument('marcas_file', help='Archivo JSON con las marcas (marcas.json)')
parser.add_argument('data_file', help='Archivo JSON con los datos (data.json)')
parser.add_argument('--output_json', default='data_brandid.json', help='Archivo de salida JSON con identación de 4 espacios')
parser.add_argument('--output_csv', default='no_brandid_found.csv', help='Archivo CSV de elementos sin BrandId')
parser.add_argument('--account', required=True, help='Nombre de cuenta de VTEX')
parser.add_argument('--env', default='vtexcommercestable', help='Ambiente de VTEX (por defecto: vtexcommercestable)')
args = parser.parse_args()

# Leer AppKey y AppToken desde el .env
app_key = os.getenv('X-VTEX-API-AppKey')
app_token = os.getenv('X-VTEX-API-AppToken')

if not app_key or not app_token:
    raise ValueError("X-VTEX-API-AppKey o X-VTEX-API-AppToken no definidos en .env")

# Headers para la autenticación
headers = {
    'Content-Type': 'application/json',
    'X-VTEX-API-AppKey': app_key,
    'X-VTEX-API-AppToken': app_token
}

# Endpoint VTEX
brand_url = f"https://{args.account}.{args.env}.com.br/api/catalog_system/pvt/brand/list"

# Obtener marcas de VTEX
response = requests.get(brand_url, headers=headers)
response.raise_for_status()
vtex_brands = response.json()

# Mapeo nombre -> id
brand_name_to_id = {brand['name'].strip().upper(): brand['id'] for brand in vtex_brands}

# Cargar archivos locales
with open(args.marcas_file, 'r', encoding='utf-8') as f:
    marcas = json.load(f)

with open(args.data_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Crear mapa SKU -> Marca
sku_to_marca = {item['SKU']: item['Marca'].strip().upper() for item in marcas if 'SKU' in item and 'Marca' in item}

# Salida
no_brandid = []

for item in data:
    ref_id = item.get('RefId')
    marca_nombre = sku_to_marca.get(ref_id)
    if marca_nombre:
        brand_id = brand_name_to_id.get(marca_nombre)
        item['BrandId'] = brand_id if brand_id is not None else None
        if brand_id is None:
            no_brandid.append(item)
    else:
        item['BrandId'] = None
        no_brandid.append(item)

# Guardar archivo de salida con identación 4 espacios
with open(args.output_json, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

# Guardar CSV de los que no se encontró BrandId
if no_brandid:
    with open(args.output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=no_brandid[0].keys())
        writer.writeheader()
        writer.writerows(no_brandid)

print("Proceso completado. Archivo JSON y CSV generados.")
