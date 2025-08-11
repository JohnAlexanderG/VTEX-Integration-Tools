#!/usr/bin/env python3
"""
Script para eliminar todos los archivos/imágenes de SKUs en VTEX

Flujo del script:
1. Carga las variables de entorno desde el archivo .env en la raíz del proyecto
2. Lee un archivo JSON con una lista de SKU IDs a procesar
3. Para cada SKU ID:
   - Realiza DELETE a /api/catalog/pvt/stockkeepingunit/{skuId}/file
   - Elimina TODOS los archivos asociados al SKU
   - Registra el resultado en consola
4. Exporta los fallos a un archivo CSV para revisión manual
5. Genera un informe en markdown con estadísticas del proceso

Uso:
    python3 delete_sku_files.py <input_json> <failures_csv> [report_md] [--limit N]

Ejemplo:
    python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md
    python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md --limit 599
    python3 delete_sku_files.py sku_list.json failed_deletions.csv --limit 100

Variables de entorno requeridas (.env en raíz):
    - VTEX_ACCOUNT_NAME: Nombre de la cuenta VTEX
    - VTEX_ENVIRONMENT: Entorno VTEX (ej: vtexcommercestable)
    - X-VTEX-API-AppKey: Clave de aplicación VTEX
    - X-VTEX-API-AppToken: Token de aplicación VTEX

Formato del JSON de entrada:
[
    "123456",
    "123457", 
    "123458"
]

O también puede aceptar un objeto con SKU IDs como claves:
{
    "123456": {},
    "123457": {},
    "123458": {}
}
"""

import os
import sys
import json
import csv
import requests
import time
import argparse
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env en la raíz del proyecto
load_dotenv('../.env')

# Configuración de VTEX desde variables de entorno
ACCOUNT_NAME = os.getenv("VTEX_ACCOUNT_NAME")
ENVIRONMENT = os.getenv("VTEX_ENVIRONMENT")
APP_KEY = os.getenv("X-VTEX-API-AppKey")
APP_TOKEN = os.getenv("X-VTEX-API-AppToken")

# Validar que todas las variables estén configuradas
if not all([ACCOUNT_NAME, ENVIRONMENT, APP_KEY, APP_TOKEN]):
    print("Error: Please set VTEX_ACCOUNT_NAME, VTEX_ENVIRONMENT, X-VTEX-API-AppKey and X-VTEX-API-AppToken as environment variables.")
    sys.exit(1)

# Construir URL base para la API de VTEX
BASE_URL = f"https://{ACCOUNT_NAME}.{ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit"

# Configuración de rate limiting para no sobrecargar VTEX
REQUESTS_PER_SECOND = 2  # Máximo 2 requests por segundo para DELETE operations
BATCH_SIZE = 20  # Procesar en lotes de 20 SKUs
BATCH_DELAY = 3  # Pausa de 3 segundos entre lotes


def load_input(path, limit=None):
    """
    Carga el archivo JSON de entrada con los SKU IDs a procesar
    
    Args:
        path (str): Ruta al archivo JSON de entrada
        limit (int, optional): Máximo número de SKUs a procesar
        
    Returns:
        list: Lista de SKU IDs como strings (limitada si se especifica)
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Manejar diferentes formatos de entrada
    if isinstance(data, list):
        # Formato: ["123456", "123457", ...]
        sku_ids = [str(sku_id) for sku_id in data]
    elif isinstance(data, dict):
        # Formato: {"123456": {}, "123457": {}, ...}
        sku_ids = [str(sku_id) for sku_id in data.keys()]
    else:
        raise ValueError("Formato de JSON no soportado. Debe ser una lista o diccionario con SKU IDs.")
    
    # Aplicar límite si se especifica
    if limit is not None and limit > 0:
        original_count = len(sku_ids)
        sku_ids = sku_ids[:limit]
        print(f"⚠️  Límite aplicado: procesando {len(sku_ids):,} de {original_count:,} SKUs totales")
    
    return sku_ids


def write_failures(failures, csv_path):
    """
    Exporta los fallos de eliminación de archivos a un archivo CSV
    
    Args:
        failures (list): Lista de diccionarios con información de fallos
        csv_path (str): Ruta del archivo CSV de salida
    """
    fieldnames = ['SkuId', 'StatusCode', 'ErrorMessage', 'Timestamp']
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for item in failures:
            writer.writerow(item)


def generate_report(sku_ids, failures, successful_deletions, report_path):
    """
    Genera un informe en markdown del proceso de eliminación de archivos
    
    Args:
        sku_ids (list): Lista original de SKU IDs
        failures (list): Lista de fallos
        successful_deletions (int): Número de eliminaciones exitosas
        report_path (str): Ruta del archivo de informe
    """
    from datetime import datetime
    
    # Calcular estadísticas
    total_skus = len(sku_ids)
    total_failures = len(failures)
    success_rate = ((total_skus - total_failures) / total_skus * 100) if total_skus > 0 else 0
    
    # Analizar tipos de fallos por código de estado
    status_code_counts = {}
    for failure in failures:
        status_code = failure.get('StatusCode', 'Unknown')
        status_code_counts[status_code] = status_code_counts.get(status_code, 0) + 1
    
    # Generar contenido del informe
    report_content = f"""# 🗑️ Informe de Eliminación de Archivos SKU - VTEX

**Fecha de ejecución:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total SKUs procesados** | {total_skus:,} |
| **Eliminaciones exitosas** | {successful_deletions:,} |
| **Fallos totales** | {total_failures:,} |
| **Tasa de éxito** | {success_rate:.2f}% |

## 🎯 Resultados del Proceso

### ✅ Eliminaciones Exitosas
- **{successful_deletions:,} SKUs** procesados correctamente
- Todos los archivos/imágenes eliminados mediante DELETE a `/api/catalog/pvt/stockkeepingunit/{{skuId}}/file`

### ❌ Análisis de Fallos ({total_failures:,} total)

| Código de Estado | Cantidad | Descripción |
|------------------|----------|-------------|"""

    # Agregar detalles de fallos por código de estado
    for status_code, count in sorted(status_code_counts.items()):
        percentage = (count / total_failures * 100) if total_failures > 0 else 0
        status_description = {
            400: "Bad Request - SKU ID inválido o malformado",
            401: "Unauthorized - Credenciales de API incorrectas",
            403: "Forbidden - Sin permisos para eliminar archivos",
            404: "Not Found - SKU no existe o no tiene archivos",
            429: "Rate Limit - Demasiadas peticiones",
            500: "Internal Server Error - Error interno de VTEX"
        }.get(status_code, "Error desconocido")
        
        report_content += f"\n| **{status_code}** | {count:,} | {status_description} |"

    report_content += f"""

## 🔍 Detalles Técnicos

### Configuración Utilizada
- **Cuenta VTEX:** {ACCOUNT_NAME}
- **Entorno:** {ENVIRONMENT}
- **Endpoint base:** `https://{ACCOUNT_NAME}.{ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit`
- **Rate limiting:** {REQUESTS_PER_SECOND} requests/segundo
- **Tamaño de lote:** {BATCH_SIZE} SKUs por lote

### Operación Realizada
```http
DELETE /api/catalog/pvt/stockkeepingunit/{{skuId}}/file
X-VTEX-API-AppKey: {{API_KEY}}
X-VTEX-API-AppToken: {{API_TOKEN}}
```

**Nota:** Esta operación elimina TODOS los archivos asociados al SKU (imágenes, documentos, etc.)

## 📋 Archivos Generados

- **CSV de fallos:** Contiene todos los SKUs que no pudieron procesarse con detalles del error
- **Reporte MD:** Este archivo con estadísticas completas del proceso

## 🚀 Recomendaciones

### Para SKUs Fallidos
1. **Error 404:** Verificar que los SKU IDs existan en el catálogo
2. **Error 401/403:** Revisar permisos de las credenciales de API
3. **Error 429:** Reducir la velocidad de procesamiento (rate limiting)
4. **Error 500:** Contactar soporte de VTEX para errores del servidor

### Consideraciones Importantes
- **⚠️ IRREVERSIBLE:** Esta operación elimina permanentemente todos los archivos del SKU
- **🔄 Recuperación:** Los archivos eliminados no se pueden restaurar automáticamente
- **📝 Backup:** Asegúrate de tener respaldo de las imágenes antes de ejecutar

---
*Informe generado automáticamente por delete_sku_files.py*
"""

    # Escribir el informe
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Informe generado: {report_path}")


def delete_sku_files(sku_ids):
    """
    Elimina todos los archivos de los SKUs especificados mediante la API de VTEX
    
    Args:
        sku_ids (list): Lista de SKU IDs como strings
        
    Returns:
        tuple: (failures_list, successful_deletions_count)
    """
    failures = []
    successful_deletions = 0
    processed_skus = 0
    api_requests_made = 0
    
    total_skus = len(sku_ids)
    
    print(f"🚀 Iniciando proceso de eliminación de archivos SKU:")
    print(f"   📦 Total SKUs a procesar: {total_skus:,}")
    print(f"   🔗 Endpoint base: {BASE_URL}")
    print(f"   🚦 Rate limiting: {REQUESTS_PER_SECOND} requests/segundo")
    print(f"   📦 Lotes de: {BATCH_SIZE} SKUs con pausa de {BATCH_DELAY}s")
    print(f"   ⚠️  ADVERTENCIA: Esta operación ELIMINARÁ PERMANENTEMENTE todos los archivos de los SKUs")
    print("-" * 80)
    
    # Configurar headers para autenticación con VTEX
    headers = {
        'X-VTEX-API-AppKey': APP_KEY,
        'X-VTEX-API-AppToken': APP_TOKEN,
        'Content-Type': 'application/json'
    }

    # Variable para controlar el rate limiting
    last_request_time = 0
    request_interval = 1.0 / REQUESTS_PER_SECOND  # Intervalo entre requests

    # Procesar cada SKU
    for index, sku_id in enumerate(sku_ids, 1):
        processed_skus += 1
        print(f"🗑️  [{index:,}/{total_skus:,}] Procesando SKU: {sku_id}")
        
        # Rate limiting: asegurar que no enviamos más de X requests por segundo
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        
        if time_since_last_request < request_interval:
            sleep_time = request_interval - time_since_last_request
            print(f"   ⏱️  Rate limiting: esperando {sleep_time:.2f}s...")
            time.sleep(sleep_time)
        
        endpoint = f"{BASE_URL}/{sku_id}/file"
        
        try:
            # Realizar DELETE request para eliminar todos los archivos del SKU
            response = requests.delete(endpoint, headers=headers, timeout=30)
            
            api_requests_made += 1
            last_request_time = time.time()
            
            # Verificar si la eliminación fue exitosa
            if response.status_code in (200, 204):
                successful_deletions += 1
                print(f"   ✅ Archivos eliminados exitosamente")
            elif response.status_code == 404:
                # SKU no existe o no tiene archivos - consideramos como éxito
                successful_deletions += 1
                print(f"   ✅ SKU no tiene archivos o no existe (404 - OK)")
            elif response.status_code == 429:  # Too Many Requests
                print(f"   🚦 Rate limit excedido - reintentando en 10s...")
                time.sleep(10)
                
                # Reintentar una vez
                response = requests.delete(endpoint, headers=headers, timeout=30)
                
                if response.status_code in (200, 204, 404):
                    successful_deletions += 1
                    print(f"   ✅ Reintento exitoso")
                else:
                    print(f"   ❌ Reintento falló - HTTP {response.status_code}")
                    error_message = response.text[:200] if response.text else 'No response body'
                    failures.append({
                        'SkuId': sku_id,
                        'StatusCode': response.status_code,
                        'ErrorMessage': error_message,
                        'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    })
            else:
                print(f"   ❌ Error HTTP {response.status_code}")
                try:
                    error_message = response.text[:200] if response.text else 'No response body'
                    print(f"   📄 Response: {error_message}")
                except:
                    error_message = f"HTTP {response.status_code}"
                
                failures.append({
                    'SkuId': sku_id,
                    'StatusCode': response.status_code,
                    'ErrorMessage': error_message,
                    'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout - reintentando...")
            try:
                time.sleep(2)
                response = requests.delete(endpoint, headers=headers, timeout=30)
                
                if response.status_code in (200, 204, 404):
                    successful_deletions += 1
                    print(f"   ✅ Reintento exitoso tras timeout")
                else:
                    print(f"   ❌ Reintento falló tras timeout")
                    failures.append({
                        'SkuId': sku_id,
                        'StatusCode': 'Timeout Retry Failed',
                        'ErrorMessage': f"HTTP {response.status_code}",
                        'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                    })
            except Exception as e:
                print(f"   💥 Error en reintento: {str(e)[:50]}...")
                failures.append({
                    'SkuId': sku_id,
                    'StatusCode': 'Timeout',
                    'ErrorMessage': str(e)[:100],
                    'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
        except Exception as e:
            print(f"   💥 Error de conexión: {str(e)[:50]}...")
            failures.append({
                'SkuId': sku_id,
                'StatusCode': 'Connection Error',
                'ErrorMessage': str(e)[:100],
                'Timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Pausa entre lotes para no sobrecargar VTEX
        if processed_skus % BATCH_SIZE == 0:
            progress_pct = (processed_skus / total_skus) * 100
            print(f"📊 Progreso: {processed_skus:,}/{total_skus:,} ({progress_pct:.1f}%) - API calls: {api_requests_made}")
            print(f"   ✅ {successful_deletions:,} exitosas, ❌ {len(failures):,} fallos")
            if processed_skus < total_skus:  # No pausar en el último lote
                print(f"   ⏸️  Pausa de {BATCH_DELAY}s entre lotes...")
                time.sleep(BATCH_DELAY)

    # Resumen final
    print("=" * 80)
    print(f"🏁 PROCESO COMPLETADO")
    print(f"   📊 SKUs procesados: {processed_skus:,}")
    print(f"   ✅ Eliminaciones exitosas: {successful_deletions:,}")
    print(f"   ❌ Fallos totales: {len(failures):,}")
    print(f"   🌐 Total API calls realizadas: {api_requests_made:,}")
    print(f"   📈 Tasa de éxito: {(successful_deletions/processed_skus*100):.2f}%")
    print("=" * 80)

    return failures, successful_deletions


def main():
    """
    Función principal del script
    
    Flujo:
    1. Validar argumentos de línea de comandos con soporte para --limit
    2. Cargar lista de SKU IDs del archivo JSON de entrada (con límite opcional)
    3. Procesar eliminación de archivos en VTEX
    4. Exportar fallos a archivo CSV
    5. Generar informe en markdown
    6. Mostrar resumen de resultados
    """
    parser = argparse.ArgumentParser(
        description='Elimina todos los archivos/imágenes de SKUs en VTEX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 delete_sku_files.py data.json failures.csv
  python3 delete_sku_files.py data.json failures.csv report.md --limit 599
  python3 delete_sku_files.py data.json failures.csv --limit 100
  
Formatos de JSON soportados:
  Lista: ["123", "124", "125"]
  Objeto: {"123": {...}, "124": {...}}
        """
    )
    
    parser.add_argument('input_json', help='Archivo JSON con SKU IDs')
    parser.add_argument('failures_csv', help='Archivo CSV para exportar fallos')
    parser.add_argument('report_md', nargs='?', help='Archivo MD para el informe (opcional)')
    parser.add_argument('--limit', type=int, help='Límite de SKUs a procesar (ej: --limit 599)')
    
    args = parser.parse_args()
    
    # Determinar nombre del reporte si no se especifica
    report_md = args.report_md or args.failures_csv.replace('.csv', '_report.md')

    print("🔧 Configuración VTEX:")
    print(f"   🏢 Cuenta: {ACCOUNT_NAME}")
    print(f"   🌐 Entorno: {ENVIRONMENT}")
    print(f"   🔑 API Key: {APP_KEY[:15]}...")
    print(f"   📁 Archivo de entrada: {args.input_json}")
    print(f"   📄 CSV de fallos: {args.failures_csv}")
    print(f"   📋 Informe: {report_md}")
    if args.limit:
        print(f"   🔢 Límite de procesamiento: {args.limit:,} SKUs")
    print()

    # Ejecutar flujo principal
    print("📂 Cargando SKU IDs del archivo JSON...")
    sku_ids = load_input(args.input_json, limit=args.limit)
    print(f"✅ {len(sku_ids):,} SKU IDs listos para procesar")
    print()
    
    failures, successful_deletions = delete_sku_files(sku_ids)
    
    print("\n💾 Generando archivos de salida...")
    write_failures(failures, args.failures_csv)
    generate_report(sku_ids, failures, successful_deletions, report_md)
    
    print()
    print("🎉 PROCESO FINALIZADO CON ÉXITO!")
    print(f"   ✅ {successful_deletions:,} SKUs procesados correctamente")
    print(f"   ❌ {len(failures):,} SKUs fallaron")
    print(f"   📄 Fallos exportados a: {args.failures_csv}")
    print(f"   📋 Informe generado: {report_md}")


if __name__ == '__main__':
    main()