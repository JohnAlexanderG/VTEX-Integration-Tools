"""
Script para subir imágenes de SKUs a VTEX

Flujo del script:
1. Carga las variables de entorno desde el archivo .env en la raíz del proyecto
2. Lee un archivo JSON con estructura: {sku: [lista_de_imágenes]}
3. Para cada imagen válida (UrlValid=True y StatusCode=200):
   - Construye el payload JSON para la API de VTEX
   - Realiza POST a /api/catalog/pvt/stockkeepingunit/{sku}/file
   - Registra errores en caso de fallo
4. Exporta todos los fallos a un archivo CSV para revisión manual

Uso:
    python3 upload_sku_images.py <input_json> <failures_csv> [report_md]

Ejemplo:
    python3 upload_sku_images.py merged_sku_images.json failed_uploads.csv upload_report.md

Variables de entorno requeridas (.env en raíz):
    - VTEX_ACCOUNT_NAME: Nombre de la cuenta VTEX
    - VTEX_ENVIRONMENT: Entorno VTEX (ej: vtexcommercestable)
    - X-VTEX-API-AppKey: Clave de aplicación VTEX
    - X-VTEX-API-AppToken: Token de aplicación VTEX

Formato del JSON de entrada:
{
    "123456": [
        {
            "Name": "imagen1.jpg",
            "Text": "Descripción de la imagen",
            "Url": "https://ejemplo.com/imagen1.jpg",
            "Position": 1,
            "IsMain": true,
            "Label": "Principal",
            "UrlValid": true,
            "StatusCode": 200
        }
    ]
}
"""

import os
import sys
import json
import csv
import requests
import time
from urllib.parse import quote
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
REQUESTS_PER_SECOND = 1  # Máximo 1 request por segundo (conservador)
BATCH_SIZE = 25  # Procesar en lotes de 25 imágenes
BATCH_DELAY = 3  # Pausa de 3 segundos entre lotes


def load_input(path):
    """
    Carga el archivo JSON de entrada con las imágenes de SKUs
    
    Args:
        path (str): Ruta al archivo JSON de entrada
        
    Returns:
        dict: Diccionario con estructura {sku: [lista_de_imágenes]}
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_failures(failures, csv_path):
    """
    Exporta los fallos de subida de imágenes a un archivo CSV
    
    Args:
        failures (list): Lista de diccionarios con información de fallos
        csv_path (str): Ruta del archivo CSV de salida
    """
    fieldnames = [
        'Sku', 'Name', 'Text', 'Url', 'Position', 'IsMain', 'Label', 'UrlValid', 'StatusCode'
    ]
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for item in failures:
            writer.writerow(item)


def extract_filename_from_url(url):
    """
    Extrae el nombre del archivo desde la URL y aplica URL encoding para evitar errores con caracteres especiales
    
    Ejemplos:
        "https://cdn1.totalcommerce.cloud/homesentry/product-image/es/candado-40-ml-best-value-plateado-1.jpg" 
        → "candado-40-ml-best-value-plateado-1.jpg"
        
        "https://example.com/path/barre-puerta-mxh.-rigido-transparente-2.jpg" 
        → "barre-puerta-mxh%2E-rigido-transparente-2.jpg"
    
    Args:
        url (str): URL completa de la imagen
        
    Returns:
        str: Nombre del archivo con URL encoding aplicado
    """
    if not url:
        return ""
    
    # Extraer el nombre del archivo de la URL
    filename = url.split('/')[-1]
    
    if not filename:
        return ""
    
    # Verificar si tiene una extensión de archivo válida
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    has_valid_extension = any(filename.lower().endswith(ext) for ext in valid_extensions)
    
    if not has_valid_extension:
        return filename  # Devolver sin cambios si no es un archivo de imagen
    
    # Separar nombre y extensión
    if '.' in filename:
        name_part, extension = filename.rsplit('.', 1)
        # URL-encodear solo la parte del nombre, preservar la extensión
        encoded_name = quote(name_part, safe='/')
        return f"{encoded_name}.{extension}"
    
    return quote(filename, safe='/')


def generate_report(data, failures, successful_uploads, report_path):
    """
    Genera un informe en markdown del proceso de subida de imágenes
    
    Args:
        data (dict): Datos originales del JSON
        failures (list): Lista de fallos
        successful_uploads (int): Número de subidas exitosas
        report_path (str): Ruta del archivo de informe
    """
    from datetime import datetime
    
    # Calcular estadísticas
    total_skus = len(data)
    total_images = sum(len(images) for images in data.values())
    total_failures = len(failures)
    success_rate = ((total_images - total_failures) / total_images * 100) if total_images > 0 else 0
    
    # Análizar tipos de fallos
    url_invalid_count = sum(1 for f in failures if not f.get('UrlValid'))
    status_code_errors = sum(1 for f in failures if f.get('UrlValid') and f.get('StatusCode') != 200)
    api_errors = total_failures - url_invalid_count - status_code_errors
    
    # Generar contenido del informe
    report_content = f"""# 📊 Informe de Subida de Imágenes SKU - VTEX

**Fecha de ejecución:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total SKUs procesados** | {total_skus:,} |
| **Total imágenes procesadas** | {total_images:,} |
| **Subidas exitosas** | {successful_uploads:,} |
| **Fallos totales** | {total_failures:,} |
| **Tasa de éxito** | {success_rate:.2f}% |

## 🎯 Resultados del Proceso

### ✅ Subidas Exitosas
- **{successful_uploads:,} imágenes** subidas correctamente a VTEX
- Imágenes procesadas con `UrlValid=True` y `StatusCode=200`
- Enviadas mediante POST a `/api/catalog/pvt/stockkeepingunit/{{sku}}/file`

### ❌ Análisis de Fallos ({total_failures:,} total)

| Tipo de Fallo | Cantidad | Porcentaje |
|---------------|----------|------------|
| **URLs inválidas** | {url_invalid_count:,} | {(url_invalid_count/total_failures*100):.1f}% |
| **Errores de StatusCode** | {status_code_errors:,} | {(status_code_errors/total_failures*100):.1f}% |
| **Errores de API VTEX** | {api_errors:,} | {(api_errors/total_failures*100):.1f}% |

## 🔍 Detalles Técnicos

### Configuración Utilizada
- **Cuenta VTEX:** {ACCOUNT_NAME}
- **Entorno:** {ENVIRONMENT}
- **Endpoint base:** `https://{ACCOUNT_NAME}.{ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit`

### Estructura de Datos Procesada
```json
{{
  "sku_id": [
    {{
      "name": "Nombre del producto",
      "text": "descripcion-slug",
      "url": "https://cdn.ejemplo.com/imagen.jpg",
      "position": 0,
      "isMain": true,
      "label": "Main"
    }}
  ]
}}
```

## 📋 Archivos Generados

- **CSV de fallos:** Contiene todos los registros que no pudieron procesarse
- **Reporte MD:** Este archivo con estadísticas completas

## 🚀 Recomendaciones

### Para Imágenes Fallidas
1. **URLs inválidas:** Verificar accesibilidad de las URLs
2. **Errores de StatusCode:** Revisar disponibilidad de recursos
3. **Errores de API:** Verificar permisos y límites de VTEX

### Optimizaciones Futuras
- Implementar reintentos para errores temporales de red
- Agregar validación de formato de imagen antes de subir
- Considerar procesamiento en lotes para mejor rendimiento

---
*Informe generado automáticamente por upload_sku_images.py*
"""

    # Escribir el informe
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Report generated: {report_path}")


def upload_images(data):
    """
    Sube las imágenes válidas a VTEX mediante la API con rate limiting
    
    Flujo:
    1. Para cada SKU en el dataset
    2. Para cada imagen del SKU
    3. Si la imagen es válida (UrlValid=True y StatusCode=200):
       - Aplicar rate limiting (1 request/segundo)
       - Construir payload JSON
       - POST a /api/catalog/pvt/stockkeepingunit/{sku}/file
       - Verificar respuesta de la API
    4. Si la imagen no es válida o falla la subida, agregar a fallos
    5. Pausa entre lotes para no sobrecargar VTEX
    
    Args:
        data (dict): Diccionario con estructura {sku: [lista_de_imágenes]}
        
    Returns:
        tuple: (failures_list, successful_uploads_count)
    """
    failures = []
    successful_uploads = 0
    processed_images = 0
    skipped_images = 0
    api_requests_made = 0
    
    # Calcular totales para mostrar progreso
    total_skus = len(data)
    total_images = sum(len(images) for images in data.values())
    
    print(f"🚀 Iniciando proceso de subida de imágenes:")
    print(f"   📦 Total SKUs: {total_skus:,}")
    print(f"   🖼️  Total imágenes: {total_images:,}")
    print(f"   🔗 Endpoint: {BASE_URL}")
    print(f"   🚦 Rate limiting: {REQUESTS_PER_SECOND} request/segundo (conservador)")
    print(f"   📦 Lotes de: {BATCH_SIZE} imágenes con pausa de {BATCH_DELAY}s")
    print("-" * 60)
    
    # Configurar headers para autenticación con VTEX
    headers = {
        'X-VTEX-API-AppKey': APP_KEY,
        'X-VTEX-API-AppToken': APP_TOKEN,
        'Content-Type': 'application/json'
    }

    # Variable para controlar el rate limiting
    last_request_time = 0
    request_interval = 1.0 / REQUESTS_PER_SECOND  # Intervalo entre requests (1.0 segundo para 1/seg)

    # Procesar cada SKU y sus imágenes
    sku_count = 0
    for sku, images in data.items():
        sku_count += 1
        print(f"📋 [{sku_count:,}/{total_skus:,}] Procesando SKU: {sku} ({len(images)} imágenes)")
        
        sku_successes = 0
        sku_failures = 0
        
        for img_index, img in enumerate(images, 1):
            processed_images += 1
            
            # Preparar registro para tracking de errores
            record = {
                'Sku': sku,
                'Name': img.get('Name'),
                'Text': img.get('Text'),
                'Url': img.get('Url'),
                'Position': img.get('Position'),
                'IsMain': img.get('IsMain', ''),
                'Label': img.get('Label', ''),
                'UrlValid': img.get('UrlValid'),
                'StatusCode': img.get('StatusCode')
            }

            # Solo procesar imágenes válidas
            if img.get('UrlValid') and img.get('StatusCode') == 200:
                # Rate limiting: asegurar que no enviamos más de X requests por segundo
                current_time = time.time()
                time_since_last_request = current_time - last_request_time
                
                if time_since_last_request < request_interval:
                    sleep_time = request_interval - time_since_last_request
                    print(f"   ⏱️  Rate limiting: esperando {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                
                endpoint = f"{BASE_URL}/{sku}/file"
                try:
                    # Construir payload para la API de VTEX
                    # Extraer el nombre del archivo desde la URL y aplicar URL encoding
                    # para evitar errores con caracteres especiales como puntos
                    image_url = img.get('Url', '')
                    image_filename = extract_filename_from_url(image_url)
                    
                    payload = {
                        'Name': image_filename,
                        'Text': img.get('Text', ''), 
                        'Url': image_url,
                        'Position': img.get('Position', 0),
                        'IsMain': img.get('IsMain', False),
                        'Label': img.get('Label', '')
                    }
                    
                    # Validar payload antes de enviar
                    if not payload['Name'] or not payload['Url']:
                        print(f"   ❌ [{img_index}/{len(images)}] Payload inválido - Name o Url faltante")
                        record['StatusCode'] = 'Invalid Payload'
                        failures.append(record)
                        sku_failures += 1
                        continue
                    
                    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                    
                    api_requests_made += 1
                    last_request_time = time.time()
                    
                    # Verificar si la subida fue exitosa
                    if resp.status_code in (200, 201):
                        successful_uploads += 1
                        sku_successes += 1
                        print(f"   ✅ [{img_index}/{len(images)}] Imagen subida correctamente (Pos: {img.get('Position', 'N/A')})")
                    elif resp.status_code == 429:  # Too Many Requests
                        sku_failures += 1
                        print(f"   🚦 [{img_index}/{len(images)}] Rate limit excedido - reintentando en 10s...")
                        time.sleep(10)
                        # Reintentar una vez
                        resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                        
                        if resp.status_code in (200, 201):
                            successful_uploads += 1
                            sku_successes += 1
                            sku_failures -= 1
                            print(f"   ✅ [{img_index}/{len(images)}] Reintento exitoso (Pos: {img.get('Position', 'N/A')})")
                        else:
                            print(f"   ❌ [{img_index}/{len(images)}] Reintento falló - HTTP {resp.status_code}")
                            record['StatusCode'] = resp.status_code
                            failures.append(record)
                    else:
                        sku_failures += 1
                        try:
                            error_body = resp.text[:200] if resp.text else 'No response body'
                            print(f"   ❌ [{img_index}/{len(images)}] Error HTTP {resp.status_code} - {img.get('Name', 'N/A')}")
                            print(f"      📄 Response: {error_body}")
                        except:
                            print(f"   ❌ [{img_index}/{len(images)}] Error HTTP {resp.status_code} - {img.get('Name', 'N/A')}")
                        record['StatusCode'] = resp.status_code
                        failures.append(record)
                        
                except requests.exceptions.Timeout:
                    sku_failures += 1
                    print(f"   ⏰ [{img_index}/{len(images)}] Timeout - reintentando...")
                    try:
                        time.sleep(2)
                        resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
                        
                        if resp.status_code in (200, 201):
                            successful_uploads += 1
                            sku_successes += 1
                            sku_failures -= 1
                            print(f"   ✅ [{img_index}/{len(images)}] Reintento exitoso tras timeout")
                        else:
                            print(f"   ❌ [{img_index}/{len(images)}] Reintento falló tras timeout")
                            failures.append(record)
                    except Exception as e:
                        print(f"   💥 [{img_index}/{len(images)}] Error en reintento: {str(e)[:30]}...")
                        failures.append(record)
                        
                except Exception as e:
                    sku_failures += 1
                    print(f"   💥 [{img_index}/{len(images)}] Error de conexión: {str(e)[:50]}...")
                    failures.append(record)
            else:
                # Saltar imagen inválida y registrar como fallo
                skipped_images += 1
                sku_failures += 1
                status_info = f"UrlValid={img.get('UrlValid')}, StatusCode={img.get('StatusCode')}"
                print(f"   ⏭️  [{img_index}/{len(images)}] Imagen inválida saltada ({status_info})")
                failures.append(record)
            
            # Pausa entre lotes para no sobrecargar VTEX
            if processed_images % BATCH_SIZE == 0:
                progress_pct = (processed_images / total_images) * 100
                print(f"📊 Progreso: {processed_images:,}/{total_images:,} ({progress_pct:.1f}%) - API calls: {api_requests_made}")
                print(f"   ✅ {successful_uploads:,} exitosas, ❌ {len(failures):,} fallos")
                if processed_images < total_images:  # No pausar en el último lote
                    print(f"   ⏸️  Pausa de {BATCH_DELAY}s entre lotes...")
                    time.sleep(BATCH_DELAY)
        
        # Resumen por SKU
        print(f"   📈 SKU {sku} completado: ✅ {sku_successes} exitosas, ❌ {sku_failures} fallos")
        print()

    # Resumen final
    print("=" * 60)
    print(f"🏁 PROCESO COMPLETADO")
    print(f"   📊 Imágenes procesadas: {processed_images:,}")
    print(f"   ✅ Subidas exitosas: {successful_uploads:,}")
    print(f"   ❌ Fallos totales: {len(failures):,}")
    print(f"   ⏭️  Imágenes saltadas: {skipped_images:,}")
    print(f"   🌐 Total API calls realizadas: {api_requests_made:,}")
    print(f"   📈 Tasa de éxito: {(successful_uploads/processed_images*100):.2f}%")
    print("=" * 60)

    return failures, successful_uploads


def main():
    """
    Función principal del script
    
    Flujo:
    1. Validar argumentos de línea de comandos
    2. Cargar datos del archivo JSON de entrada
    3. Procesar subida de imágenes a VTEX
    4. Exportar fallos a archivo CSV
    5. Generar informe en markdown
    6. Mostrar resumen de resultados
    """
    if len(sys.argv) not in (3, 4):
        print("Usage: python upload_sku_images.py <input_json> <failures_csv> [report_md]")
        print("Example: python upload_sku_images.py data.json failures.csv report.md")
        sys.exit(1)

    input_json = sys.argv[1]
    output_csv = sys.argv[2]
    report_md = sys.argv[3] if len(sys.argv) == 4 else output_csv.replace('.csv', '_report.md')

    print("🔧 Configuración VTEX:")
    print(f"   🏢 Cuenta: {ACCOUNT_NAME}")
    print(f"   🌐 Entorno: {ENVIRONMENT}")
    print(f"   🔑 API Key: {APP_KEY[:15]}...")
    print(f"   📁 Archivo de entrada: {input_json}")
    print(f"   📄 CSV de fallos: {output_csv}")
    print(f"   📋 Informe: {report_md}")
    print()

    # Ejecutar flujo principal
    print("📂 Cargando datos del archivo JSON...")
    data = load_input(input_json)
    print(f"✅ Datos cargados correctamente")
    print()
    
    failures, successful_uploads = upload_images(data)
    
    print("\n💾 Generando archivos de salida...")
    write_failures(failures, output_csv)
    generate_report(data, failures, successful_uploads, report_md)
    
    print()
    print("🎉 PROCESO FINALIZADO CON ÉXITO!")
    print(f"   ✅ {successful_uploads:,} imágenes subidas correctamente")
    print(f"   ❌ {len(failures):,} imágenes fallaron")
    print(f"   📄 Fallos exportados a: {output_csv}")
    print(f"   📋 Informe generado: {report_md}")


if __name__ == '__main__':
    main()
