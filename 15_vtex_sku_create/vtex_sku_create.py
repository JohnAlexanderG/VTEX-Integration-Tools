#!/usr/bin/env python3
"""
vtex_sku_create.py

Script de creación masiva de SKUs VTEX usando la API privada del catálogo.
Continuación del flujo de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Crea SKUs en VTEX usando el endpoint POST /api/catalog/pvt/stockkeepingunit
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Implementa control de rate limiting para evitar saturar la API VTEX
- Procesa lista de SKUs desde archivo JSON formateado
- Exporta respuestas exitosas y errores en archivos JSON separados
- Genera reporte markdown detallado con estadísticas y análisis de resultados
- Maneja todos los errores posibles de la API VTEX con logging comprehensivo

Control de Rate Limiting:
- Pausa de 1 segundo entre requests para respetar límites VTEX
- Backoff exponencial en caso de rate limiting (429)
- Retry automático hasta 3 intentos por SKU
- Timeout de 30 segundos por request

Estructura de Salida:
- {timestamp}_successful_skus.json: SKUs creados exitosamente
- {timestamp}_failed_skus.json: SKUs que fallaron con detalles del error
- {timestamp}_vtex_sku_creation_report.md: Reporte markdown con estadísticas completas

Ejecución:
    # Creación básica
    python3 vtex_sku_create.py skus_vtex.json
    
    # Con configuración personalizada de timing
    python3 vtex_sku_create.py skus.json --delay 2 --timeout 45
    
    # Con archivos de salida personalizados
    python3 vtex_sku_create.py datos.json --output-prefix custom_batch

Ejemplo:
    python3 15_vtex_sku_create/vtex_sku_create.py vtex_ready_skus.json

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
"""

import json
import requests
import argparse
import os  
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
import unicodedata

# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Configuración de la API VTEX
VTEX_APP_KEY = os.getenv('X-VTEX-API-AppKey')
VTEX_APP_TOKEN = os.getenv('X-VTEX-API-AppToken')
VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT_NAME')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

# Configuración de rate limiting
DEFAULT_DELAY = 1.0  # Segundos entre requests
DEFAULT_TIMEOUT = 30  # Timeout por request
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

class VTEXSKUCreator:
    def __init__(self, delay=DEFAULT_DELAY, timeout=DEFAULT_TIMEOUT):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-VTEX-API-AppKey': VTEX_APP_KEY,
            'X-VTEX-API-AppToken': VTEX_APP_TOKEN
        })
        self.base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"
        self.endpoint = f"{self.base_url}/api/catalog/pvt/stockkeepingunit"
        
        # Estadísticas de procesamiento
        self.successful_skus = []
        self.failed_skus = []
        self.total_processed = 0
        self.start_time = None
        
    def validate_credentials(self):
        """Valida que todas las credenciales VTEX estén configuradas."""
        missing_credentials = []
        
        if not VTEX_APP_KEY:
            missing_credentials.append('X-VTEX-API-AppKey')
        if not VTEX_APP_TOKEN:
            missing_credentials.append('X-VTEX-API-AppToken')
        if not VTEX_ACCOUNT:
            missing_credentials.append('VTEX_ACCOUNT_NAME')
            
        if missing_credentials:
            raise ValueError(f"Credenciales VTEX faltantes en .env: {', '.join(missing_credentials)}")
            
        print(f"✅ Credenciales VTEX configuradas para cuenta: {VTEX_ACCOUNT}")
        print(f"✅ Endpoint: {self.endpoint}")
        
    def create_sku(self, sku_data, retry_count=0):
        """Crea un SKU individual en VTEX con manejo de errores y retry."""
        try:
            # Rate limiting - pausa entre requests
            if self.total_processed > 0:
                time.sleep(self.delay)
            
            # Realizar request POST
            response = self.session.post(
                self.endpoint,
                json=sku_data,
                timeout=self.timeout
            )
            
            # Procesar respuesta
            if response.status_code == 200 or response.status_code == 201:
                # SKU creado exitosamente
                result = {
                    'sku_data': sku_data,
                    'response': response.json(),
                    'status_code': response.status_code,
                    'ref_id': sku_data.get('RefId', 'N/A'),
                    'name': sku_data.get('Name', 'N/A'),
                    'product_id': sku_data.get('ProductId', 'N/A'),
                    'timestamp': datetime.now().isoformat()
                }
                self.successful_skus.append(result)
                print(f"✅ SKU creado: {sku_data.get('RefId', 'N/A')} - {sku_data.get('Name', 'N/A')[:50]}")
                return True
                
            elif response.status_code == 429:
                # Rate limiting - retry con backoff exponencial
                if retry_count < MAX_RETRIES:
                    wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                    print(f"⚠️ Rate limit alcanzado. Esperando {wait_time}s antes de reintentar...")
                    time.sleep(wait_time)
                    return self.create_sku(sku_data, retry_count + 1)
                else:
                    error_result = {
                        'sku_data': sku_data,
                        'error': 'Rate limit exceeded - max retries reached',
                        'status_code': response.status_code,
                        'response_text': response.text,
                        'ref_id': sku_data.get('RefId', 'N/A'),
                        'name': sku_data.get('Name', 'N/A'),
                        'product_id': sku_data.get('ProductId', 'N/A'),
                        'timestamp': datetime.now().isoformat(),
                        'retry_count': retry_count
                    }
                    self.failed_skus.append(error_result)
                    print(f"❌ SKU falló (rate limit): {sku_data.get('RefId', 'N/A')}")
                    return False
                    
            else:
                # Error de API
                try:
                    error_response = response.json()
                except:
                    error_response = response.text
                    
                error_result = {
                    'sku_data': sku_data,
                    'error': f'API Error: {response.status_code}',
                    'status_code': response.status_code,
                    'response': error_response,
                    'ref_id': sku_data.get('RefId', 'N/A'),
                    'name': sku_data.get('Name', 'N/A'),
                    'product_id': sku_data.get('ProductId', 'N/A'),
                    'timestamp': datetime.now().isoformat()
                }
                self.failed_skus.append(error_result)
                print(f"❌ SKU falló: {sku_data.get('RefId', 'N/A')} - Status: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            error_result = {
                'sku_data': sku_data,
                'error': 'Request timeout',
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'timestamp': datetime.now().isoformat(),
                'timeout': self.timeout
            }
            self.failed_skus.append(error_result)
            print(f"❌ SKU falló (timeout): {sku_data.get('RefId', 'N/A')}")
            return False
            
        except requests.exceptions.RequestException as e:
            error_result = {
                'sku_data': sku_data,
                'error': f'Request error: {str(e)}',
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'timestamp': datetime.now().isoformat()
            }
            self.failed_skus.append(error_result)
            print(f"❌ SKU falló (request error): {sku_data.get('RefId', 'N/A')}")
            return False
            
        except Exception as e:
            error_result = {
                'sku_data': sku_data,
                'error': f'Unexpected error: {str(e)}',
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'timestamp': datetime.now().isoformat()
            }
            self.failed_skus.append(error_result)
            print(f"❌ SKU falló (error inesperado): {sku_data.get('RefId', 'N/A')}")
            return False
    
    def process_skus(self, skus):
        """Procesa lista completa de SKUs."""
        self.start_time = datetime.now()
        total_skus = len(skus)
        
        print(f"\n🚀 Iniciando creación de {total_skus} SKUs en VTEX...")
        print(f"⏱️ Delay entre requests: {self.delay}s")
        print(f"⏱️ Timeout por request: {self.timeout}s")
        print("=" * 80)
        
        for i, sku in enumerate(skus, 1):
            print(f"\n[{i}/{total_skus}] Procesando SKU...")
            self.create_sku(sku)
            self.total_processed += 1
            
            # Mostrar progreso cada 10 SKUs
            if i % 10 == 0:
                success_rate = (len(self.successful_skus) / i) * 100
                print(f"📊 Progreso: {i}/{total_skus} ({i/total_skus*100:.1f}%) - Éxito: {success_rate:.1f}%")
        
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        print("\n" + "=" * 80)
        print(f"✅ Procesamiento completado en {duration}")
        print(f"✅ SKUs exitosos: {len(self.successful_skus)}")
        print(f"❌ SKUs fallidos: {len(self.failed_skus)}")
        print(f"📊 Tasa de éxito: {(len(self.successful_skus)/total_skus)*100:.1f}%")
        
    def export_results(self, output_prefix="vtex_sku_creation"):
        """Exporta resultados a archivos JSON y genera reporte markdown."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Exportar SKUs exitosos
        if self.successful_skus:
            success_file = f"{timestamp}_{output_prefix}_successful.json"
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump(self.successful_skus, f, ensure_ascii=False, indent=2)
            print(f"✅ SKUs exitosos exportados a: {success_file}")
        
        # Exportar SKUs fallidos
        if self.failed_skus:
            failed_file = f"{timestamp}_{output_prefix}_failed.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_skus, f, ensure_ascii=False, indent=2)
            print(f"❌ SKUs fallidos exportados a: {failed_file}")
        
        # Generar reporte markdown
        report_file = f"{timestamp}_{output_prefix}_report.md"
        self.generate_markdown_report(report_file)
        print(f"📋 Reporte generado: {report_file}")
        
    def generate_markdown_report(self, report_file):
        """Genera reporte detallado en formato markdown."""
        duration = datetime.now() - self.start_time if self.start_time else "N/A"
        success_count = len(self.successful_skus)
        failed_count = len(self.failed_skus)
        total_count = self.total_processed
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        # Agrupar errores por tipo
        error_summary = {}
        for failed in self.failed_skus:
            error_type = failed.get('error', 'Unknown error')
            if error_type not in error_summary:
                error_summary[error_type] = []
            error_summary[error_type].append(failed)
        
        report_content = f"""# Reporte de Creación de SKUs VTEX

**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Account VTEX:** {VTEX_ACCOUNT}  
**Environment:** {VTEX_ENVIRONMENT}  
**Duración:** {duration}  

## 📊 Resumen de Resultados

| Métrica | Valor |
|---------|-------|
| **Total Procesados** | {total_count} |
| **✅ Exitosos** | {success_count} |
| **❌ Fallidos** | {failed_count} |
| **📈 Tasa de Éxito** | {success_rate:.1f}% |
| **⏱️ Delay entre requests** | {self.delay}s |
| **⏱️ Timeout por request** | {self.timeout}s |

## ✅ SKUs Creados Exitosamente ({success_count})

"""
        
        if self.successful_skus:
            report_content += "| RefId | Nombre | Product ID | SKU ID | Timestamp |\n|-------|--------|------------|--------|----------|\n"
            for sku in self.successful_skus[:20]:  # Mostrar primeros 20
                ref_id = sku.get('ref_id', 'N/A')
                name = sku.get('name', 'N/A')[:50]
                product_id = sku.get('product_id', 'N/A')
                sku_id = sku.get('response', {}).get('Id', 'N/A') if isinstance(sku.get('response'), dict) else 'N/A'
                timestamp = sku.get('timestamp', 'N/A')[:19]  # Solo fecha y hora
                report_content += f"| {ref_id} | {name} | {product_id} | {sku_id} | {timestamp} |\n"
            
            if len(self.successful_skus) > 20:
                report_content += f"\n*... y {len(self.successful_skus) - 20} SKUs más*\n"
        else:
            report_content += "*No se crearon SKUs exitosamente*\n"
            
        report_content += f"\n## ❌ SKUs Fallidos ({failed_count})\n\n"
        
        if self.failed_skus:
            # Resumen de errores agrupados
            report_content += "### 📋 Resumen de Errores\n\n"
            for error_type, errors in error_summary.items():
                report_content += f"- **{error_type}**: {len(errors)} SKUs\n"
            
            report_content += "\n### 📝 Detalle de SKUs Fallidos\n\n"
            report_content += "| RefId | Nombre | Product ID | Error | Status Code | Timestamp |\n|-------|--------|------------|-------|-------------|----------|\n"
            
            for sku in self.failed_skus[:30]:  # Mostrar primeros 30
                ref_id = sku.get('ref_id', 'N/A') 
                name = sku.get('name', 'N/A')[:40]
                product_id = sku.get('product_id', 'N/A')
                error = sku.get('error', 'N/A')[:60]
                status_code = sku.get('status_code', 'N/A')
                timestamp = sku.get('timestamp', 'N/A')[:19]
                report_content += f"| {ref_id} | {name} | {product_id} | {error} | {status_code} | {timestamp} |\n"
                
            if len(self.failed_skus) > 30:
                report_content += f"\n*... y {len(self.failed_skus) - 30} SKUs más en archivo JSON*\n"
        else:
            report_content += "*No hubo SKUs fallidos*\n"
            
        # Análisis y recomendaciones
        report_content += f"\n## 🔍 Análisis y Recomendaciones\n\n"
        
        if success_rate >= 90:
            report_content += "✅ **Excelente tasa de éxito**. La integración funcionó correctamente.\n"
        elif success_rate >= 70:
            report_content += "⚠️ **Buena tasa de éxito** pero revisar SKUs fallidos para mejoras.\n"
        else:
            report_content += "❌ **Baja tasa de éxito**. Revisar configuración y datos de entrada.\n"
            
        if failed_count > 0:
            report_content += f"\n### Errores más comunes:\n"
            for error_type, errors in sorted(error_summary.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                report_content += f"- **{error_type}**: {len(errors)} casos\n"
                
        report_content += f"\n---\n*Reporte generado automáticamente por vtex_sku_create.py*\n"
        
        # Escribir reporte
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

def main():
    parser = argparse.ArgumentParser(
        description="Crea SKUs masivamente en VTEX usando la API del catálogo"
    )
    parser.add_argument("input_file", help="Archivo JSON con lista de SKUs para crear")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, 
                       help=f"Delay en segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Timeout en segundos por request (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output-prefix", default="vtex_sku_creation",
                       help="Prefijo para archivos de salida (default: vtex_sku_creation)")
    
    args = parser.parse_args()
    
    try:
        # Crear instancia del creador de SKUs
        creator = VTEXSKUCreator(delay=args.delay, timeout=args.timeout)
        
        # Validar credenciales
        creator.validate_credentials()
        
        # Cargar SKUs desde archivo JSON
        print(f"\n📂 Cargando SKUs desde: {args.input_file}")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            skus_data = json.load(f)
        
        # Manejar tanto array como objeto individual
        if isinstance(skus_data, dict):
            skus = [skus_data]
        else:
            skus = skus_data
            
        if not skus:
            print("❌ No se encontraron SKUs para procesar")
            sys.exit(1)
            
        print(f"✅ Cargados {len(skus)} SKUs para procesar")
        
        # Procesar SKUs
        creator.process_skus(skus)
        
        # Exportar resultados
        creator.export_results(args.output_prefix)
        
        # Mostrar resumen final
        print(f"\n🎉 Proceso completado exitosamente!")
        
    except FileNotFoundError:
        print(f"❌ Error: Archivo '{args.input_file}' no encontrado")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido en archivo de entrada: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error de configuración: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()