#!/usr/bin/env python3
"""
vtex_sku_ean_create.py

Script de creación masiva de EAN para SKUs VTEX usando la API privada del catálogo.
Continuación del flujo de creación de SKUs (paso 15) para asignar códigos EAN.

Funcionalidad:
- Crea valores EAN para SKUs en VTEX usando el endpoint POST /api/catalog/pvt/stockkeepingunit/{skuId}/ean/{ean}
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Implementa control de rate limiting para evitar saturar la API VTEX
- Procesa archivo de salida exitoso del paso 15 (SKU creation successful)
- Exporta respuestas exitosas y errores en archivos JSON separados
- Genera reporte markdown detallado con estadísticas y análisis de resultados
- Maneja todos los errores posibles de la API VTEX con logging comprehensivo

Control de Rate Limiting:
- Pausa de 1 segundo entre requests para respetar límites VTEX
- Backoff exponencial en caso de rate limiting (429)
- Retry automático hasta 3 intentos por SKU
- Timeout de 30 segundos por request

Estructura de Entrada:
- Lee archivo {timestamp}_vtex_sku_creation_successful.json del paso 15
- Formato esperado: array de objetos con 'response.Id' (skuId) y 'sku_data.Ean' (ean)

Estructura de Salida:
- {timestamp}_ean_creation_successful.json: EANs creados exitosamente
- {timestamp}_ean_creation_failed.json: EANs que fallaron con detalles del error
- {timestamp}_ean_creation_skipped.json: SKUs sin EAN o con EAN inválido
- {timestamp}_vtex_ean_creation_report.md: Reporte markdown con estadísticas completas

Ejecución:
    # Creación básica desde archivo del paso 15
    python3 vtex_sku_ean_create.py 20250801_224749_vtex_sku_creation_successful.json

    # Con configuración personalizada de timing
    python3 vtex_sku_ean_create.py successful_skus.json --delay 2 --timeout 45

    # Con archivos de salida personalizados
    python3 vtex_sku_ean_create.py datos.json --output-prefix custom_batch

Ejemplo:
    python3 15.2_vtex_sku_ean_create/vtex_sku_ean_create.py 15_vtex_sku_create/20250801_224749_vtex_sku_creation_successful.json

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
- Archivo JSON con resultados exitosos del paso 15
"""

import json
import requests
import argparse
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

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

class VTEXEANCreator:
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

        # Estadísticas de procesamiento
        self.successful_eans = []
        self.failed_eans = []
        self.skipped_eans = []
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
        print(f"✅ Base URL: {self.base_url}")

    def validate_ean(self, ean):
        """Valida que el EAN sea válido (no vacío, no None, longitud apropiada)."""
        if not ean or ean == "" or ean.lower() == "null" or ean.lower() == "none":
            return False

        # EAN debe ser string y tener longitud apropiada (8, 12, 13, o 14 dígitos típicamente)
        ean_str = str(ean).strip()
        if len(ean_str) < 8 or len(ean_str) > 14:
            return False

        return True

    def create_ean(self, sku_id, ean, sku_data, retry_count=0):
        """Crea un EAN individual para un SKU en VTEX con manejo de errores y retry."""
        endpoint = f"{self.base_url}/api/catalog/pvt/stockkeepingunit/{sku_id}/ean/{ean}"

        try:
            # Rate limiting - pausa entre requests
            if self.total_processed > 0:
                time.sleep(self.delay)

            # Realizar request POST (el body está vacío según la documentación)
            response = self.session.post(
                endpoint,
                timeout=self.timeout
            )

            # Procesar respuesta
            if response.status_code == 200 or response.status_code == 201:
                # EAN creado exitosamente
                result = {
                    'sku_id': sku_id,
                    'ean': ean,
                    'ref_id': sku_data.get('RefId', 'N/A'),
                    'name': sku_data.get('Name', 'N/A'),
                    'product_id': sku_data.get('ProductId', 'N/A'),
                    'status_code': response.status_code,
                    'timestamp': datetime.now().isoformat()
                }
                self.successful_eans.append(result)
                print(f"✅ EAN creado: SKU {sku_id} - EAN {ean} - RefId {sku_data.get('RefId', 'N/A')}")
                return True

            elif response.status_code == 429:
                # Rate limiting - retry con backoff exponencial
                if retry_count < MAX_RETRIES:
                    wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                    print(f"⚠️ Rate limit alcanzado. Esperando {wait_time}s antes de reintentar...")
                    time.sleep(wait_time)
                    return self.create_ean(sku_id, ean, sku_data, retry_count + 1)
                else:
                    error_result = {
                        'sku_id': sku_id,
                        'ean': ean,
                        'ref_id': sku_data.get('RefId', 'N/A'),
                        'name': sku_data.get('Name', 'N/A'),
                        'product_id': sku_data.get('ProductId', 'N/A'),
                        'error': 'Rate limit exceeded - max retries reached',
                        'status_code': response.status_code,
                        'response_text': response.text,
                        'timestamp': datetime.now().isoformat(),
                        'retry_count': retry_count
                    }
                    self.failed_eans.append(error_result)
                    print(f"❌ EAN falló (rate limit): SKU {sku_id} - EAN {ean}")
                    return False

            else:
                # Error de API
                try:
                    error_response = response.json()
                except:
                    error_response = response.text

                error_result = {
                    'sku_id': sku_id,
                    'ean': ean,
                    'ref_id': sku_data.get('RefId', 'N/A'),
                    'name': sku_data.get('Name', 'N/A'),
                    'product_id': sku_data.get('ProductId', 'N/A'),
                    'error': f'API Error: {response.status_code}',
                    'status_code': response.status_code,
                    'response': error_response,
                    'timestamp': datetime.now().isoformat()
                }
                self.failed_eans.append(error_result)
                print(f"❌ EAN falló: SKU {sku_id} - Status: {response.status_code} - {error_response}")
                return False

        except requests.exceptions.Timeout:
            error_result = {
                'sku_id': sku_id,
                'ean': ean,
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'error': 'Request timeout',
                'timestamp': datetime.now().isoformat(),
                'timeout': self.timeout
            }
            self.failed_eans.append(error_result)
            print(f"❌ EAN falló (timeout): SKU {sku_id} - EAN {ean}")
            return False

        except requests.exceptions.RequestException as e:
            error_result = {
                'sku_id': sku_id,
                'ean': ean,
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'error': f'Request error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            self.failed_eans.append(error_result)
            print(f"❌ EAN falló (request error): SKU {sku_id} - {str(e)}")
            return False

        except Exception as e:
            error_result = {
                'sku_id': sku_id,
                'ean': ean,
                'ref_id': sku_data.get('RefId', 'N/A'),
                'name': sku_data.get('Name', 'N/A'),
                'product_id': sku_data.get('ProductId', 'N/A'),
                'error': f'Unexpected error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            self.failed_eans.append(error_result)
            print(f"❌ EAN falló (error inesperado): SKU {sku_id} - {str(e)}")
            return False

    def process_sku_data(self, sku_records):
        """Procesa lista completa de registros de SKU del paso 15."""
        self.start_time = datetime.now()
        total_records = len(sku_records)

        print(f"\n🚀 Iniciando creación de EANs para {total_records} SKUs en VTEX...")
        print(f"⏱️ Delay entre requests: {self.delay}s")
        print(f"⏱️ Timeout por request: {self.timeout}s")
        print("=" * 80)

        for i, record in enumerate(sku_records, 1):
            # Extraer datos del registro
            response_data = record.get('response', {})
            sku_data = record.get('sku_data', {})

            sku_id = response_data.get('Id')
            ean = sku_data.get('Ean')
            ref_id = sku_data.get('RefId', 'N/A')
            name = sku_data.get('Name', 'N/A')

            print(f"\n[{i}/{total_records}] Procesando SKU {sku_id} - RefId: {ref_id}")

            # Validar que tengamos SKU ID
            if not sku_id:
                skip_result = {
                    'ref_id': ref_id,
                    'name': name,
                    'reason': 'Missing SKU ID',
                    'sku_data': sku_data,
                    'timestamp': datetime.now().isoformat()
                }
                self.skipped_eans.append(skip_result)
                print(f"⚠️ Saltado: SKU sin ID - RefId {ref_id}")
                self.total_processed += 1
                continue

            # Validar EAN
            if not self.validate_ean(ean):
                skip_result = {
                    'sku_id': sku_id,
                    'ref_id': ref_id,
                    'name': name,
                    'ean_value': ean,
                    'reason': 'Invalid or missing EAN',
                    'sku_data': sku_data,
                    'timestamp': datetime.now().isoformat()
                }
                self.skipped_eans.append(skip_result)
                print(f"⚠️ Saltado: EAN inválido o faltante - SKU {sku_id} - EAN: '{ean}'")
                self.total_processed += 1
                continue

            # Crear EAN
            self.create_ean(sku_id, ean, sku_data)
            self.total_processed += 1

            # Mostrar progreso cada 10 registros
            if i % 10 == 0:
                success_rate = (len(self.successful_eans) / i) * 100 if i > 0 else 0
                print(f"📊 Progreso: {i}/{total_records} ({i/total_records*100:.1f}%) - Éxito: {success_rate:.1f}%")

        end_time = datetime.now()
        duration = end_time - self.start_time

        print("\n" + "=" * 80)
        print(f"✅ Procesamiento completado en {duration}")
        print(f"✅ EANs creados exitosamente: {len(self.successful_eans)}")
        print(f"❌ EANs fallidos: {len(self.failed_eans)}")
        print(f"⚠️ SKUs saltados: {len(self.skipped_eans)}")

        if self.total_processed > 0:
            attempted = len(self.successful_eans) + len(self.failed_eans)
            if attempted > 0:
                print(f"📊 Tasa de éxito: {(len(self.successful_eans)/attempted)*100:.1f}%")

    def export_results(self, output_prefix="ean_creation"):
        """Exporta resultados a archivos JSON y genera reporte markdown."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Exportar EANs exitosos
        if self.successful_eans:
            success_file = f"{timestamp}_{output_prefix}_successful.json"
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump(self.successful_eans, f, ensure_ascii=False, indent=2)
            print(f"✅ EANs exitosos exportados a: {success_file}")

        # Exportar EANs fallidos
        if self.failed_eans:
            failed_file = f"{timestamp}_{output_prefix}_failed.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_eans, f, ensure_ascii=False, indent=2)
            print(f"❌ EANs fallidos exportados a: {failed_file}")

        # Exportar SKUs saltados
        if self.skipped_eans:
            skipped_file = f"{timestamp}_{output_prefix}_skipped.json"
            with open(skipped_file, 'w', encoding='utf-8') as f:
                json.dump(self.skipped_eans, f, ensure_ascii=False, indent=2)
            print(f"⚠️ SKUs saltados exportados a: {skipped_file}")

        # Generar reporte markdown
        report_file = f"{timestamp}_vtex_{output_prefix}_report.md"
        self.generate_markdown_report(report_file)
        print(f"📋 Reporte generado: {report_file}")

    def generate_markdown_report(self, report_file):
        """Genera reporte detallado en formato markdown."""
        duration = datetime.now() - self.start_time if self.start_time else "N/A"
        success_count = len(self.successful_eans)
        failed_count = len(self.failed_eans)
        skipped_count = len(self.skipped_eans)
        total_count = self.total_processed
        attempted_count = success_count + failed_count
        success_rate = (success_count / attempted_count * 100) if attempted_count > 0 else 0

        # Agrupar errores por tipo
        error_summary = {}
        for failed in self.failed_eans:
            error_type = failed.get('error', 'Unknown error')
            if error_type not in error_summary:
                error_summary[error_type] = []
            error_summary[error_type].append(failed)

        # Agrupar razones de saltado
        skip_summary = {}
        for skipped in self.skipped_eans:
            reason = skipped.get('reason', 'Unknown reason')
            if reason not in skip_summary:
                skip_summary[reason] = []
            skip_summary[reason].append(skipped)

        report_content = f"""# Reporte de Creación de EANs VTEX

**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Account VTEX:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}
**Duración:** {duration}

## 📊 Resumen de Resultados

| Métrica | Valor |
|---------|-------|
| **Total Procesados** | {total_count} |
| **✅ EANs Creados Exitosamente** | {success_count} |
| **❌ EANs Fallidos** | {failed_count} |
| **⚠️ SKUs Saltados** | {skipped_count} |
| **📈 Tasa de Éxito** | {success_rate:.1f}% |
| **⏱️ Delay entre requests** | {self.delay}s |
| **⏱️ Timeout por request** | {self.timeout}s |

## ✅ EANs Creados Exitosamente ({success_count})

"""

        if self.successful_eans:
            report_content += "| SKU ID | EAN | RefId | Nombre | Product ID | Timestamp |\n|--------|-----|-------|--------|------------|----------|\n"
            for ean_record in self.successful_eans[:30]:  # Mostrar primeros 30
                sku_id = ean_record.get('sku_id', 'N/A')
                ean = ean_record.get('ean', 'N/A')
                ref_id = ean_record.get('ref_id', 'N/A')
                name = ean_record.get('name', 'N/A')[:40]
                product_id = ean_record.get('product_id', 'N/A')
                timestamp = ean_record.get('timestamp', 'N/A')[:19]
                report_content += f"| {sku_id} | {ean} | {ref_id} | {name} | {product_id} | {timestamp} |\n"

            if len(self.successful_eans) > 30:
                report_content += f"\n*... y {len(self.successful_eans) - 30} EANs más*\n"
        else:
            report_content += "*No se crearon EANs exitosamente*\n"

        report_content += f"\n## ❌ EANs Fallidos ({failed_count})\n\n"

        if self.failed_eans:
            # Resumen de errores agrupados
            report_content += "### 📋 Resumen de Errores\n\n"
            for error_type, errors in error_summary.items():
                report_content += f"- **{error_type}**: {len(errors)} casos\n"

            report_content += "\n### 📝 Detalle de EANs Fallidos\n\n"
            report_content += "| SKU ID | EAN | RefId | Nombre | Error | Status Code | Timestamp |\n|--------|-----|-------|--------|-------|-------------|----------|\n"

            for ean_record in self.failed_eans[:30]:  # Mostrar primeros 30
                sku_id = ean_record.get('sku_id', 'N/A')
                ean = ean_record.get('ean', 'N/A')
                ref_id = ean_record.get('ref_id', 'N/A')
                name = ean_record.get('name', 'N/A')[:30]
                error = ean_record.get('error', 'N/A')[:50]
                status_code = ean_record.get('status_code', 'N/A')
                timestamp = ean_record.get('timestamp', 'N/A')[:19]
                report_content += f"| {sku_id} | {ean} | {ref_id} | {name} | {error} | {status_code} | {timestamp} |\n"

            if len(self.failed_eans) > 30:
                report_content += f"\n*... y {len(self.failed_eans) - 30} EANs más en archivo JSON*\n"
        else:
            report_content += "*No hubo EANs fallidos*\n"

        report_content += f"\n## ⚠️ SKUs Saltados ({skipped_count})\n\n"

        if self.skipped_eans:
            # Resumen de razones de saltado
            report_content += "### 📋 Resumen de SKUs Saltados\n\n"
            for reason, skipped_list in skip_summary.items():
                report_content += f"- **{reason}**: {len(skipped_list)} SKUs\n"

            report_content += "\n### 📝 Detalle de SKUs Saltados\n\n"
            report_content += "| SKU ID | RefId | Nombre | EAN | Razón | Timestamp |\n|--------|-------|--------|-----|-------|----------|\n"

            for skipped_record in self.skipped_eans[:30]:  # Mostrar primeros 30
                sku_id = skipped_record.get('sku_id', 'N/A')
                ref_id = skipped_record.get('ref_id', 'N/A')
                name = skipped_record.get('name', 'N/A')[:30]
                ean = skipped_record.get('ean_value', 'N/A')
                reason = skipped_record.get('reason', 'N/A')
                timestamp = skipped_record.get('timestamp', 'N/A')[:19]
                report_content += f"| {sku_id} | {ref_id} | {name} | {ean} | {reason} | {timestamp} |\n"

            if len(self.skipped_eans) > 30:
                report_content += f"\n*... y {len(self.skipped_eans) - 30} SKUs más en archivo JSON*\n"
        else:
            report_content += "*No se saltaron SKUs*\n"

        # Análisis y recomendaciones
        report_content += f"\n## 🔍 Análisis y Recomendaciones\n\n"

        if success_rate >= 90:
            report_content += "✅ **Excelente tasa de éxito**. La integración funcionó correctamente.\n"
        elif success_rate >= 70:
            report_content += "⚠️ **Buena tasa de éxito** pero revisar EANs fallidos para mejoras.\n"
        else:
            report_content += "❌ **Baja tasa de éxito**. Revisar configuración y datos de entrada.\n"

        if skipped_count > 0:
            report_content += f"\n### SKUs Saltados:\n"
            for reason, skipped_list in sorted(skip_summary.items(), key=lambda x: len(x[1]), reverse=True):
                report_content += f"- **{reason}**: {len(skipped_list)} casos\n"

        if failed_count > 0:
            report_content += f"\n### Errores más comunes:\n"
            for error_type, errors in sorted(error_summary.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                report_content += f"- **{error_type}**: {len(errors)} casos\n"

        report_content += f"\n---\n*Reporte generado automáticamente por vtex_sku_ean_create.py*\n"

        # Escribir reporte
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

def main():
    parser = argparse.ArgumentParser(
        description="Crea EANs masivamente para SKUs VTEX usando la API del catálogo"
    )
    parser.add_argument("input_file",
                       help="Archivo JSON con resultados exitosos del paso 15 (vtex_sku_creation_successful.json)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                       help=f"Delay en segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Timeout en segundos por request (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output-prefix", default="ean_creation",
                       help="Prefijo para archivos de salida (default: ean_creation)")

    args = parser.parse_args()

    try:
        # Crear instancia del creador de EANs
        creator = VTEXEANCreator(delay=args.delay, timeout=args.timeout)

        # Validar credenciales
        creator.validate_credentials()

        # Cargar datos de SKUs desde archivo JSON
        print(f"\n📂 Cargando datos de SKUs desde: {args.input_file}")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            sku_records = json.load(f)

        # Validar formato de datos
        if not isinstance(sku_records, list):
            print("❌ Error: El archivo debe contener un array de registros de SKU")
            sys.exit(1)

        if not sku_records:
            print("❌ No se encontraron registros de SKU para procesar")
            sys.exit(1)

        print(f"✅ Cargados {len(sku_records)} registros de SKU para procesar")

        # Procesar SKUs
        creator.process_sku_data(sku_records)

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
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
