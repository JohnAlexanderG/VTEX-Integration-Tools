#!/usr/bin/env python3
"""
Script de prueba para debuggear subida de una sola imagen a VTEX

Uso:
    python3 test_single_upload.py <sku_id> <image_url> <image_name>

Ejemplo:
    python3 test_single_upload.py 67 "https://example.com/image.jpg" "Test Image"
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('../.env')

# Configuración de VTEX
ACCOUNT_NAME = os.getenv("VTEX_ACCOUNT_NAME")
ENVIRONMENT = os.getenv("VTEX_ENVIRONMENT")
APP_KEY = os.getenv("X-VTEX-API-AppKey")
APP_TOKEN = os.getenv("X-VTEX-API-AppToken")

def test_single_upload(sku_id, image_url, image_name):
    """
    Prueba la subida de una sola imagen con diferentes formatos de payload
    """
    if not all([ACCOUNT_NAME, ENVIRONMENT, APP_KEY, APP_TOKEN]):
        print("❌ Error: Variables de entorno VTEX no configuradas")
        sys.exit(1)
    
    base_url = f"https://{ACCOUNT_NAME}.{ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit"
    endpoint = f"{base_url}/{sku_id}/file"
    
    headers = {
        'X-VTEX-API-AppKey': APP_KEY,
        'X-VTEX-API-AppToken': APP_TOKEN,
        'Content-Type': 'application/json'
    }
    
    print(f"🔧 Configuración:")
    print(f"   Cuenta: {ACCOUNT_NAME}")
    print(f"   Entorno: {ENVIRONMENT}")
    print(f"   SKU ID: {sku_id}")
    print(f"   Endpoint: {endpoint}")
    print(f"   Image URL: {image_url}")
    print(f"   Image Name: {image_name}")
    print()
    
    # Diferentes formatos de payload para probar
    payloads_to_test = [
        {
            "name": "Formato Original (lowercase keys)",
            "payload": {
                'name': image_name,
                'text': image_name.lower().replace(' ', '-'),
                'url': image_url,
                'position': 0,
                'isMain': True,
                'label': 'Main'
            }
        },
        {
            "name": "Formato Capitalizado (PascalCase keys)",
            "payload": {
                'Name': image_name,
                'Text': image_name.lower().replace(' ', '-'),
                'Url': image_url,
                'Position': 0,
                'IsMain': True,
                'Label': 'Main'
            }
        },
        {
            "name": "Formato Mínimo (solo campos requeridos)",
            "payload": {
                'Name': image_name,
                'Url': image_url
            }
        },
        {
            "name": "Formato con Text vacío",
            "payload": {
                'Name': image_name,
                'Text': '',
                'Url': image_url,
                'Position': 0,
                'IsMain': True,
                'Label': ''
            }
        }
    ]
    
    for i, test_case in enumerate(payloads_to_test, 1):
        print(f"🧪 Test {i}/4: {test_case['name']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=4)}")
        
        try:
            response = requests.post(endpoint, headers=headers, json=test_case['payload'], timeout=30)
            
            print(f"   📊 Status Code: {response.status_code}")
            print(f"   📄 Response Headers: {dict(response.headers)}")
            
            if response.text:
                try:
                    response_json = response.json()
                    print(f"   📋 Response JSON: {json.dumps(response_json, indent=4)}")
                except:
                    print(f"   📄 Response Text: {response.text[:500]}")
            else:
                print(f"   📄 Response: (empty)")
            
            if response.status_code in (200, 201):
                print(f"   ✅ ÉXITO! Imagen subida correctamente")
                break
            else:
                print(f"   ❌ FALLO con status {response.status_code}")
                
        except Exception as e:
            print(f"   💥 Error de conexión: {str(e)}")
        
        print("-" * 60)
        
        if i < len(payloads_to_test):
            print("   ⏱️  Esperando 3 segundos antes del siguiente test...")
            import time
            time.sleep(3)

def main():
    if len(sys.argv) != 4:
        print("Uso: python3 test_single_upload.py <sku_id> <image_url> <image_name>")
        print("Ejemplo: python3 test_single_upload.py 67 'https://example.com/image.jpg' 'Test Image'")
        sys.exit(1)
    
    sku_id = sys.argv[1]
    image_url = sys.argv[2] 
    image_name = sys.argv[3]
    
    test_single_upload(sku_id, image_url, image_name)

if __name__ == '__main__':
    main()