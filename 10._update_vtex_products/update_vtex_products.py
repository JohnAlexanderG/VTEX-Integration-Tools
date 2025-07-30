#!/usr/bin/env python3
"""
update_vtex_products.py

Script de gestión masiva de productos VTEX que actualiza el estado de productos
en el catálogo. Útil para operaciones de mantenimiento de catálogo.

Funcionalidad:
- Obtiene todos los IDs de productos del catálogo VTEX usando paginación
- Descarga información completa de cada producto via API
- Modifica campos IsActive e IsVisible a False para desactivar productos
- Actualiza cada producto individualmente via API PUT
- Exporta lista de productos actualizados a archivo JSON
- Implementa rate limiting para evitar sobrecarga de API

Proceso de Actualización:
1. Paginación de GetProductAndSkuIds para obtener todos los product IDs
2. Para cada product ID: GET → Modificar → PUT
3. Acumula productos actualizados en memoria
4. Exporta resultado final a JSON

Ejecución:
    # Actualización masiva (desactiva todos los productos)
    python3 update_vtex_products.py
    
    # Los productos se marcarán como IsActive=false, IsVisible=false

Ejemplo:
    python3 10._update_vtex_products/update_vtex_products.py

Archivos requeridos:
- .env en la raíz del proyecto con VTEX_ACCOUNT_NAME, VTEX_ENVIRONMENT, X-VTEX-API-AppKey, X-VTEX-API-AppToken

⚠️  ADVERTENCIA: Este script modifica todos los productos del catálogo VTEX
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

# Carga variables de entorno desde el archivo .env en la raíz del proyecto
# Debes incluir en tu .env:
# VTEX_ACCOUNT_NAME=tuAccountName
# VTEX_ENVIRONMENT=tuEnvironment (por ejemplo: vtexcommercestable)
# X-VTEX-API-AppKey=***
# X-VTEX-API-AppToken=***
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

ACCOUNT = os.getenv("VTEX_ACCOUNT_NAME")
ENV = os.getenv("VTEX_ENVIRONMENT")
API_KEY = os.getenv("X-VTEX-API-AppKey")
API_TOKEN = os.getenv("X-VTEX-API-AppToken")

if not all([ACCOUNT, ENV, API_KEY, API_TOKEN]):
    raise EnvironmentError(
        "Faltan variables de entorno. Asegúrate de definir VTEX_ACCOUNT_NAME, VTEX_ENVIRONMENT, X-VTEX-API-AppKey y X-VTEX-API-AppToken en tu .env"
    )

BASE_URL = f"https://{ACCOUNT}.{ENV}.com.br"
HEADERS = {
    "X-VTEX-API-AppKey": API_KEY,
    "X-VTEX-API-AppToken": API_TOKEN,
    "Content-Type": "application/json"
}


def get_all_product_ids(chunk_size=250):
    """Paginación sobre GetProductAndSkuIds para obtener todos los productId."""
    product_ids = []
    from_idx = 0
    total = None

    while total is None or from_idx < total:
        to_idx = from_idx + chunk_size - 1
        url = (
            f"{BASE_URL}/api/catalog_system/pvt/products/GetProductAndSkuIds"
            f"?_from={from_idx}&_to={to_idx}"
        )
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        # Agrega cada productId (maneja si vienen como dicts o strings)
        for item in data.get("data", []):
            if isinstance(item, dict):
                pid = item.get("productId")
            else:
                pid = item
            if pid is not None:
                product_ids.append(pid)

        # Determina total de elementos
        range_info = data.get("range", {})
        total = range_info.get("total", total if total is not None else 0)
        from_idx = to_idx + 1

        # Pequeño delay para evitar 429
        time.sleep(0.2)

    return product_ids


def update_products(product_ids, output_file="updated_products.json"):
    """
    Por cada productId:
    - GET datos del producto
    - Modifica IsActive e IsVisible a False
    - PUT de vuelta al API
    - Acumula productos actualizados en una lista
    """
    updated_list = []

    for pid in product_ids:
        get_url = f"{BASE_URL}/api/catalog/pvt/product/{pid}"
        r_get = requests.get(get_url, headers=HEADERS)
        r_get.raise_for_status()
        product = r_get.json()

        # Actualiza campos
        product["IsActive"] = False
        product["IsVisible"] = False

        # Envía actualización
        r_put = requests.put(get_url, headers=HEADERS, json=product)
        r_put.raise_for_status()

        updated_list.append(product)

        # Breve pausa
        time.sleep(0.1)

    # Exporta resultado a JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(updated_list, f, ensure_ascii=False, indent=2)

    print(f"Se actualizaron {len(updated_list)} productos. Output en: {output_file}")


if __name__ == "__main__":
    print("Obteniendo IDs de productos...")
    ids = get_all_product_ids()
    print(f"Total de productos encontrados: {len(ids)}")
    print("Actualizando productos...")
    update_products(ids)
