#!/usr/bin/env python3
"""
pum_spec_updater.py

Actualiza o crea especificaciones PUM (Precio Unitario de Medida) en productos VTEX.

Mapeo de datos:
  UNIDAD MINIMA PUM (ej: "gr", "ml", "Mt") → spec "UNIDAD DE MEDIDA"
  CANTIDAD PUM (ej: "2270", "4", "545")    → spec "VALOR UNIDAD DE MEDIDA"

Archivos de entrada:
  1. specs_csv: Exportación VTEX de especificaciones de producto (CSV)
     Columnas: Product ID, Product name, Product reference code, Brand ID, Brand,
               Department ID, Department, Category ID, Category, Field ID, Field name,
               Field type, Field values IDs, Field values, Specification IDs,
               Specification values
  2. pum_csv: CSV con datos PUM (pum_encontrados.csv)
     Columnas: SKU reference code, CANTIDAD PUM, UNIDAD MINIMA PUM
  3. --products-csv (opcional): CSV de productos VTEX para fallback de Product ID
     Columnas: Product ID, Product Name, SKU ID, SKU name, SKU reference code

APIs VTEX:
  POST /api/catalog_system/pvt/products/{productId}/specification  → Actualizar spec existente (array body)
  PUT  /api/catalog/pvt/product/{productId}/specificationvalue     → Crear spec nueva
  GET  /api/catalog_system/pvt/products/{productId}/specification  → Auto-descubrir GroupName

Uso:
    # Solo actualizar (productos con specs existentes)
    python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv

    # Actualizar + crear (con vtex_products.csv para fallback)
    python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --products-csv vtex_products.csv

    # Dry run
    python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --products-csv vtex_products.csv --dry-run

    # Custom delay
    python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --delay 2.0
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raiz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

VTEX_APP_KEY = os.getenv('X-VTEX-API-AppKey')
VTEX_APP_TOKEN = os.getenv('X-VTEX-API-AppToken')
VTEX_ACCOUNT = os.getenv('VTEX_ACCOUNT_NAME')
VTEX_ENVIRONMENT = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

DEFAULT_DELAY = 1.0
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

SPEC_UNIDAD = "UNIDAD DE MEDIDA"
SPEC_VALOR = "VALOR UNIDAD DE MEDIDA"


def validate_credentials():
    missing = []
    if not VTEX_APP_KEY:
        missing.append('X-VTEX-API-AppKey')
    if not VTEX_APP_TOKEN:
        missing.append('X-VTEX-API-AppToken')
    if not VTEX_ACCOUNT:
        missing.append('VTEX_ACCOUNT_NAME')
    if missing:
        raise ValueError(f"Credenciales VTEX faltantes en .env: {', '.join(missing)}")
    print(f"  Cuenta VTEX: {VTEX_ACCOUNT}")
    print(f"  Ambiente: {VTEX_ENVIRONMENT}")


def build_headers():
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-VTEX-API-AppKey': VTEX_APP_KEY,
        'X-VTEX-API-AppToken': VTEX_APP_TOKEN,
    }


def api_request(method, url, payload=None, timeout=DEFAULT_TIMEOUT, retries=MAX_RETRIES):
    """Ejecuta request con reintentos y backoff exponencial."""
    for attempt in range(retries + 1):
        try:
            if method == 'POST':
                resp = requests.post(url, headers=build_headers(), json=payload, timeout=timeout)
            elif method == 'PUT':
                resp = requests.put(url, headers=build_headers(), json=payload, timeout=timeout)
            elif method == 'GET':
                resp = requests.get(url, headers=build_headers(), timeout=timeout)
            else:
                raise ValueError(f"Metodo HTTP no soportado: {method}")

            if resp.status_code in (200, 201, 204):
                return {'success': True, 'status_code': resp.status_code, 'response': resp.json() if resp.text else {}}

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = DEFAULT_DELAY * (BACKOFF_FACTOR ** attempt)
                print(f"    Retry {attempt + 1}/{retries} - HTTP {resp.status_code} (esperando {wait:.1f}s)")
                time.sleep(wait)
                continue

            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text
            return {'success': False, 'status_code': resp.status_code, 'error': err_body}

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait = DEFAULT_DELAY * (BACKOFF_FACTOR ** attempt)
                print(f"    Retry {attempt + 1}/{retries} - Timeout (esperando {wait:.1f}s)")
                time.sleep(wait)
                continue
            return {'success': False, 'status_code': 'timeout', 'error': 'Request timeout'}

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait = DEFAULT_DELAY * (BACKOFF_FACTOR ** attempt)
                print(f"    Retry {attempt + 1}/{retries} - Error de conexion (esperando {wait:.1f}s)")
                time.sleep(wait)
                continue
            return {'success': False, 'status_code': 'request_error', 'error': str(e)}

    return {'success': False, 'status_code': 'max_retries', 'error': 'Max retries exceeded'}


# ---------------------------------------------------------------------------
# Paso 1: Cargar CSV de especificaciones
# ---------------------------------------------------------------------------
def load_specs_csv(specs_path):
    """
    Carga CSV de especificaciones VTEX y construye lookup por Product reference code.

    Retorna:
        specs_lookup = {
            "001663": {
                "product_id": "46",
                "unidad_field_id": "1083",   # o None si no existe
                "valor_field_id": "1026",    # o None si no existe
            }
        }
    """
    specs_lookup = {}
    row_count = 0

    with open(specs_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        required = {'Product ID', 'Product reference code', 'Field ID', 'Field name'}
        missing = required - set(headers)
        if missing:
            raise ValueError(f"CSV de specs no contiene columnas requeridas: {missing}\nColumnas disponibles: {headers}")

        for row in reader:
            row_count += 1
            ref_code = row.get('Product reference code', '').strip()
            field_name = row.get('Field name', '').strip()
            field_id = row.get('Field ID', '').strip()
            product_id = row.get('Product ID', '').strip()

            if not ref_code or not field_name:
                continue

            if field_name not in (SPEC_UNIDAD, SPEC_VALOR):
                continue

            if ref_code not in specs_lookup:
                specs_lookup[ref_code] = {
                    'product_id': product_id,
                    'unidad_field_id': None,
                    'valor_field_id': None,
                }

            if field_name == SPEC_UNIDAD:
                specs_lookup[ref_code]['unidad_field_id'] = field_id
            elif field_name == SPEC_VALOR:
                specs_lookup[ref_code]['valor_field_id'] = field_id

            # Asegurar product_id consistente
            if product_id:
                specs_lookup[ref_code]['product_id'] = product_id

    print(f"  Filas leidas: {row_count}")
    print(f"  Productos con specs PUM: {len(specs_lookup)}")
    return specs_lookup


# ---------------------------------------------------------------------------
# Paso 2: Cargar vtex_products.csv (fallback Product ID)
# ---------------------------------------------------------------------------
def load_products_csv(products_path):
    """
    Carga CSV de productos VTEX y construye lookup ref_code -> product_id.
    """
    products_lookup = {}

    with open(products_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        required = {'Product ID', 'SKU reference code'}
        missing = required - set(headers)
        if missing:
            raise ValueError(f"CSV de productos no contiene columnas requeridas: {missing}\nColumnas disponibles: {headers}")

        for row in reader:
            ref_code = row.get('SKU reference code', '').strip()
            product_id = row.get('Product ID', '').strip()
            if ref_code and product_id:
                products_lookup[ref_code] = product_id

    print(f"  Productos cargados: {len(products_lookup)}")
    return products_lookup


# ---------------------------------------------------------------------------
# Paso 3: Cargar pum_encontrados.csv
# ---------------------------------------------------------------------------
def load_pum_csv(pum_path):
    """
    Carga CSV con datos PUM.
    Retorna lista de dicts con 'ref_code', 'cantidad_pum', 'unidad_pum'.
    """
    pum_data = []
    skipped = 0

    with open(pum_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        required = {'SKU reference code', 'CANTIDAD PUM', 'UNIDAD MINIMA PUM'}
        missing = required - set(headers)
        if missing:
            raise ValueError(f"CSV PUM no contiene columnas requeridas: {missing}\nColumnas disponibles: {headers}")

        for row in reader:
            ref_code = row.get('SKU reference code', '').strip()
            cantidad = row.get('CANTIDAD PUM', '').strip()
            unidad = row.get('UNIDAD MINIMA PUM', '').strip()

            if not ref_code:
                skipped += 1
                continue
            if not cantidad and not unidad:
                skipped += 1
                continue

            pum_data.append({
                'ref_code': ref_code,
                'cantidad_pum': cantidad,
                'unidad_pum': unidad,
            })

    print(f"  Registros PUM validos: {len(pum_data)}")
    if skipped:
        print(f"  Registros PUM omitidos (vacios): {skipped}")
    return pum_data


# ---------------------------------------------------------------------------
# Paso 4: Clasificar productos
# ---------------------------------------------------------------------------
def classify_products(pum_data, specs_lookup, products_lookup):
    """
    Clasifica cada registro PUM en:
      - update_list: tiene specs en CSV, usar POST catalog_system con array body
      - create_list: tiene Product ID via vtex_products.csv, usar PUT con FieldName
      - partial_list: tiene una spec pero no la otra en CSV (POST catalog_system + PUT mixto)
      - not_found: sin Product ID en ningun CSV

    Retorna (update_list, create_list, not_found_list)
    """
    update_list = []
    create_list = []
    not_found_list = []

    for item in pum_data:
        ref = item['ref_code']

        if ref in specs_lookup:
            spec = specs_lookup[ref]
            product_id = spec['product_id']
            has_unidad = spec['unidad_field_id'] is not None
            has_valor = spec['valor_field_id'] is not None

            if has_unidad and has_valor:
                # Ambas specs existen -> full update via POST catalog_system
                update_list.append({
                    'ref_code': ref,
                    'product_id': product_id,
                    'unidad_pum': item['unidad_pum'],
                    'cantidad_pum': item['cantidad_pum'],
                    'unidad_field_id': spec['unidad_field_id'],
                    'valor_field_id': spec['valor_field_id'],
                    'action': 'update',
                })
            else:
                # Parcial: POST catalog_system para la que tiene FieldId, PUT para la que falta
                update_list.append({
                    'ref_code': ref,
                    'product_id': product_id,
                    'unidad_pum': item['unidad_pum'],
                    'cantidad_pum': item['cantidad_pum'],
                    'unidad_field_id': spec['unidad_field_id'],
                    'valor_field_id': spec['valor_field_id'],
                    'action': 'partial',
                })
        elif products_lookup and ref in products_lookup:
            # No tiene specs pero tiene Product ID -> crear via PUT
            create_list.append({
                'ref_code': ref,
                'product_id': products_lookup[ref],
                'unidad_pum': item['unidad_pum'],
                'cantidad_pum': item['cantidad_pum'],
                'action': 'create',
            })
        else:
            not_found_list.append(item)

    return update_list, create_list, not_found_list


# ---------------------------------------------------------------------------
# Paso 5: Auto-descubrir GroupName
# ---------------------------------------------------------------------------
def discover_group_name(specs_lookup, timeout=DEFAULT_TIMEOUT):
    """
    Consulta la API de VTEX para descubrir el GroupName de las specs PUM.
    Usa un producto del specs_lookup que tenga UNIDAD DE MEDIDA.
    """
    base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"

    # Encontrar un product_id que tenga la spec
    sample_pid = None
    for ref, spec in specs_lookup.items():
        if spec['unidad_field_id'] is not None and spec['product_id']:
            sample_pid = spec['product_id']
            break

    if not sample_pid:
        return None

    url = f"{base_url}/api/catalog_system/pvt/products/{sample_pid}/specification"
    print(f"  Consultando specs del producto {sample_pid} para descubrir GroupName...")

    result = api_request('GET', url, timeout=timeout)
    if not result['success']:
        print(f"    Error al consultar specs: {result.get('error', 'Unknown')}")
        return None

    specs = result['response']
    if not isinstance(specs, list):
        return None

    for spec in specs:
        name = spec.get('Name', '')
        if name == SPEC_UNIDAD:
            group = spec.get('GroupName', '')
            if group:
                print(f"  GroupName descubierto: {group}")
                return group

    return None


# ---------------------------------------------------------------------------
# Paso 6: Ejecutar llamadas API
# ---------------------------------------------------------------------------
def execute_updates(update_list, create_list, group_name, delay, timeout, dry_run):
    """
    Ejecuta las llamadas API para actualizar y crear especificaciones.

    Retorna (successful, failed)
    """
    base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"
    successful = []
    failed = []
    total = len(update_list) + len(create_list)
    current = 0

    # --- Procesar updates (POST catalog_system) ---
    if update_list:
        print(f"\n  Actualizando {len(update_list)} productos (POST catalog_system)...")

    for item in update_list:
        current += 1
        pid = item['product_id']
        ref = item['ref_code']
        results_for_item = {'ref_code': ref, 'product_id': pid, 'action': item['action'], 'specs': []}
        item_ok = True

        # Build combined payload for specs that have Field IDs (update via catalog_system)
        update_payload = []
        if item['unidad_pum'] and item['unidad_field_id']:
            update_payload.append({"Value": [item['unidad_pum']], "Id": int(item['unidad_field_id']), "Name": SPEC_UNIDAD})
        if item['cantidad_pum'] and item['valor_field_id']:
            update_payload.append({"Value": [item['cantidad_pum']], "Id": int(item['valor_field_id']), "Name": SPEC_VALOR})

        # Execute single POST for all specs with Field IDs
        if update_payload:
            url = f"{base_url}/api/catalog_system/pvt/products/{pid}/specification"
            spec_names = " + ".join(s["Name"] for s in update_payload)
            spec_result = _execute_spec_call('POST', url, update_payload, spec_names, ref, pid, current, total, delay, timeout, dry_run)
            results_for_item['specs'].append(spec_result)
            if not spec_result['success']:
                item_ok = False

        # Handle specs without Field IDs (create via PUT specificationvalue)
        if item['unidad_pum'] and not item['unidad_field_id']:
            if not group_name:
                spec_result = {'success': False, 'spec': SPEC_UNIDAD, 'error': 'GroupName no disponible para crear spec'}
            else:
                url = f"{base_url}/api/catalog/pvt/product/{pid}/specificationvalue"
                payload = {"FieldName": SPEC_UNIDAD, "GroupName": group_name, "RootLevelSpecification": False, "FieldValues": [item['unidad_pum']]}
                spec_result = _execute_spec_call('PUT', url, payload, SPEC_UNIDAD, ref, pid, current, total, delay, timeout, dry_run)
            results_for_item['specs'].append(spec_result)
            if not spec_result['success']:
                item_ok = False

        if item['cantidad_pum'] and not item['valor_field_id']:
            if not group_name:
                spec_result = {'success': False, 'spec': SPEC_VALOR, 'error': 'GroupName no disponible para crear spec'}
            else:
                url = f"{base_url}/api/catalog/pvt/product/{pid}/specificationvalue"
                payload = {"FieldName": SPEC_VALOR, "GroupName": group_name, "RootLevelSpecification": False, "FieldValues": [item['cantidad_pum']]}
                spec_result = _execute_spec_call('PUT', url, payload, SPEC_VALOR, ref, pid, current, total, delay, timeout, dry_run)
            results_for_item['specs'].append(spec_result)
            if not spec_result['success']:
                item_ok = False

        results_for_item['timestamp'] = datetime.now().isoformat()
        if item_ok:
            successful.append(results_for_item)
        else:
            results_for_item['partial'] = any(s['success'] for s in results_for_item['specs'])
            failed.append(results_for_item)

    # --- Procesar creates (PUT) ---
    if create_list:
        if not group_name:
            print(f"\n  No se puede crear specs para {len(create_list)} productos: GroupName no disponible")
            print("  Use --group-name para especificarlo manualmente")
            for item in create_list:
                failed.append({
                    'ref_code': item['ref_code'],
                    'product_id': item['product_id'],
                    'action': 'create',
                    'specs': [
                        {'success': False, 'spec': SPEC_UNIDAD, 'error': 'GroupName no disponible'},
                        {'success': False, 'spec': SPEC_VALOR, 'error': 'GroupName no disponible'},
                    ],
                    'partial': False,
                    'timestamp': datetime.now().isoformat(),
                })
        else:
            print(f"\n  Creando specs en {len(create_list)} productos (PUT)...")

            for item in create_list:
                current += 1
                pid = item['product_id']
                ref = item['ref_code']
                results_for_item = {'ref_code': ref, 'product_id': pid, 'action': 'create', 'specs': []}
                item_ok = True

                # UNIDAD DE MEDIDA
                if item['unidad_pum']:
                    url = f"{base_url}/api/catalog/pvt/product/{pid}/specificationvalue"
                    payload = {"FieldName": SPEC_UNIDAD, "GroupName": group_name, "RootLevelSpecification": False, "FieldValues": [item['unidad_pum']]}
                    spec_result = _execute_spec_call('PUT', url, payload, SPEC_UNIDAD, ref, pid, current, total, delay, timeout, dry_run)
                    results_for_item['specs'].append(spec_result)
                    if not spec_result['success']:
                        item_ok = False

                # VALOR UNIDAD DE MEDIDA
                if item['cantidad_pum']:
                    url = f"{base_url}/api/catalog/pvt/product/{pid}/specificationvalue"
                    payload = {"FieldName": SPEC_VALOR, "GroupName": group_name, "RootLevelSpecification": False, "FieldValues": [item['cantidad_pum']]}
                    spec_result = _execute_spec_call('PUT', url, payload, SPEC_VALOR, ref, pid, current, total, delay, timeout, dry_run)
                    results_for_item['specs'].append(spec_result)
                    if not spec_result['success']:
                        item_ok = False

                results_for_item['timestamp'] = datetime.now().isoformat()
                if item_ok:
                    successful.append(results_for_item)
                else:
                    results_for_item['partial'] = any(s['success'] for s in results_for_item['specs'])
                    failed.append(results_for_item)

    return successful, failed


def _execute_spec_call(method, url, payload, spec_name, ref_code, product_id, current, total, delay, timeout, dry_run):
    """Ejecuta una llamada individual de spec con logging."""
    if dry_run:
        print(f"  [{current}/{total}] DRY RUN - {ref_code} (PID:{product_id}) {method} {spec_name}: {json.dumps(payload, ensure_ascii=False)}")
        return {'success': True, 'spec': spec_name, 'method': method, 'dry_run': True, 'payload': payload}

    time.sleep(delay)
    result = api_request(method, url, payload=payload, timeout=timeout)

    if result['success']:
        print(f"  [{current}/{total}] {ref_code} (PID:{product_id}) {spec_name}: OK")
        return {'success': True, 'spec': spec_name, 'method': method, 'status_code': result['status_code']}
    else:
        error_msg = str(result.get('error', 'Unknown'))
        if len(error_msg) > 120:
            error_msg = error_msg[:120] + '...'
        print(f"  [{current}/{total}] {ref_code} (PID:{product_id}) {spec_name}: FALLO - HTTP {result['status_code']} - {error_msg}")
        return {'success': False, 'spec': spec_name, 'method': method, 'status_code': result['status_code'], 'error': result.get('error')}


# ---------------------------------------------------------------------------
# Paso 7: Exportar resultados
# ---------------------------------------------------------------------------
def export_results(successful, failed, not_found, output_prefix, dry_run):
    """Exporta resultados a JSON, CSV y reporte markdown."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    files_generated = []

    # Exitosos
    if successful:
        path = f"{timestamp}_{output_prefix}_successful.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(successful, f, ensure_ascii=False, indent=2)
        files_generated.append(path)
        print(f"  {path}")

    # Fallidos
    if failed:
        path = f"{timestamp}_{output_prefix}_failed.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        files_generated.append(path)
        print(f"  {path}")

    # No encontrados
    if not_found:
        path = f"{timestamp}_{output_prefix}_not_matched.csv"
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['SKU reference code', 'CANTIDAD PUM', 'UNIDAD MINIMA PUM'])
            writer.writeheader()
            for item in not_found:
                writer.writerow({
                    'SKU reference code': item['ref_code'],
                    'CANTIDAD PUM': item['cantidad_pum'],
                    'UNIDAD MINIMA PUM': item['unidad_pum'],
                })
        files_generated.append(path)
        print(f"  {path}")

    # Reporte markdown
    report_path = f"{timestamp}_{output_prefix}_report.md"
    _generate_report(report_path, successful, failed, not_found, dry_run)
    files_generated.append(report_path)
    print(f"  {report_path}")

    return files_generated


def _generate_report(report_path, successful, failed, not_found, dry_run):
    """Genera reporte markdown detallado."""
    total_products = len(successful) + len(failed)
    total_not_found = len(not_found)
    success_rate = (len(successful) / total_products * 100) if total_products > 0 else 0

    # Contar llamadas individuales
    total_spec_calls = sum(len(s.get('specs', [])) for s in successful + failed)
    ok_calls = sum(1 for s in successful for sp in s.get('specs', []) if sp.get('success'))
    fail_calls = sum(1 for s in failed for sp in s.get('specs', []) if not sp.get('success'))
    partial_count = sum(1 for f in failed if f.get('partial'))

    # Agrupar errores
    error_groups = {}
    for f in failed:
        for sp in f.get('specs', []):
            if not sp.get('success'):
                code = str(sp.get('status_code', 'unknown'))
                if code not in error_groups:
                    error_groups[code] = []
                error_groups[code].append(f['ref_code'])

    # Clasificar por accion
    updated = [s for s in successful if s.get('action') in ('update', 'partial')]
    created = [s for s in successful if s.get('action') == 'create']

    content = f"""# Reporte de Actualizacion de Especificaciones PUM en VTEX

**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Cuenta VTEX:** {VTEX_ACCOUNT}
**Ambiente:** {VTEX_ENVIRONMENT}
{"**Modo:** DRY RUN (sin llamadas API)" if dry_run else ""}

## Resumen de Resultados

| Metrica | Valor |
|---------|-------|
| **Productos procesados** | {total_products} |
| **Productos exitosos** | {len(successful)} |
| **Productos fallidos** | {len(failed)} |
| **Parcialmente actualizados** | {partial_count} |
| **Sin match (no encontrados)** | {total_not_found} |
| **Tasa de exito** | {success_rate:.1f}% |

### Detalle de Operaciones

| Metrica | Valor |
|---------|-------|
| **Llamadas API totales** | {total_spec_calls} |
| **Llamadas exitosas** | {ok_calls} |
| **Llamadas fallidas** | {fail_calls} |
| **Specs actualizadas (POST catalog_system)** | {len(updated)} productos |
| **Specs creadas (PUT)** | {len(created)} productos |

"""

    if updated:
        content += f"## Productos Actualizados ({len(updated)})\n\n"
        content += "| RefId | Product ID | Specs |\n|-------|-----------|-------|\n"
        for item in updated[:30]:
            specs_summary = ", ".join(s['spec'] for s in item.get('specs', []) if s.get('success'))
            content += f"| {item['ref_code']} | {item['product_id']} | {specs_summary} |\n"
        if len(updated) > 30:
            content += f"\n*... y {len(updated) - 30} productos mas*\n"
        content += "\n"

    if created:
        content += f"## Productos con Specs Creadas ({len(created)})\n\n"
        content += "| RefId | Product ID | Specs |\n|-------|-----------|-------|\n"
        for item in created[:30]:
            specs_summary = ", ".join(s['spec'] for s in item.get('specs', []) if s.get('success'))
            content += f"| {item['ref_code']} | {item['product_id']} | {specs_summary} |\n"
        if len(created) > 30:
            content += f"\n*... y {len(created) - 30} productos mas*\n"
        content += "\n"

    if failed:
        content += f"## Productos Fallidos ({len(failed)})\n\n"
        if error_groups:
            content += "### Resumen de Errores\n\n"
            for code, refs in sorted(error_groups.items(), key=lambda x: len(x[1]), reverse=True):
                sample = ", ".join(refs[:10])
                more = f" ... y {len(refs) - 10} mas" if len(refs) > 10 else ""
                content += f"- **HTTP {code}**: {len(refs)} llamadas - RefIds: {sample}{more}\n"
            content += "\n"

        content += "### Detalle\n\n"
        content += "| RefId | Product ID | Accion | Parcial | Error |\n|-------|-----------|--------|---------|-------|\n"
        for item in failed[:30]:
            errors = "; ".join(str(s.get('error', ''))[:60] for s in item.get('specs', []) if not s.get('success'))
            partial = "Si" if item.get('partial') else "No"
            content += f"| {item['ref_code']} | {item['product_id']} | {item['action']} | {partial} | {errors} |\n"
        if len(failed) > 30:
            content += f"\n*... y {len(failed) - 30} productos mas en JSON*\n"
        content += "\n"

    if not_found:
        content += f"## Productos Sin Match ({total_not_found})\n\n"
        content += "Estos productos PUM no se encontraron en ninguno de los CSVs de referencia.\n\n"
        content += "| SKU Reference Code | Cantidad PUM | Unidad PUM |\n|-------------------|-------------|------------|\n"
        for item in not_found[:20]:
            content += f"| {item['ref_code']} | {item['cantidad_pum']} | {item['unidad_pum']} |\n"
        if len(not_found) > 20:
            content += f"\n*... y {len(not_found) - 20} mas en CSV*\n"
        content += "\n"

    content += "---\n*Reporte generado por pum_spec_updater.py*\n"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Actualizar o crear especificaciones PUM (Precio Unitario de Medida) en VTEX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Solo actualizar (productos con specs existentes)
  python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv

  # Actualizar + crear (con vtex_products.csv para fallback)
  python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --products-csv vtex_products.csv

  # Dry run
  python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --dry-run

  # Con GroupName conocido
  python3 pum_spec_updater.py specs_export.csv pum_encontrados.csv --products-csv vtex_products.csv --group-name "Especificaciones"
        """
    )
    parser.add_argument('specs_csv', help='CSV exportacion de especificaciones VTEX')
    parser.add_argument('pum_csv', help='CSV con datos PUM (pum_encontrados.csv)')
    parser.add_argument('--products-csv', help='CSV de productos VTEX para Product ID fallback (habilita creacion de specs)')
    parser.add_argument('--group-name', help='Nombre del grupo de specs (si se conoce; si no, se auto-descubre)')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY, help=f'Segundos entre llamadas API (default: {DEFAULT_DELAY})')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help=f'Timeout por request en segundos (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--dry-run', action='store_true', help='Previsualizar sin ejecutar llamadas API')
    parser.add_argument('--output-prefix', default='pum_spec_update', help='Prefijo archivos de salida (default: pum_spec_update)')

    args = parser.parse_args()

    # Validar archivos de entrada
    for path, label in [(args.specs_csv, 'specs CSV'), (args.pum_csv, 'PUM CSV')]:
        if not os.path.exists(path):
            print(f"Error: Archivo '{path}' no encontrado ({label})")
            sys.exit(1)
    if args.products_csv and not os.path.exists(args.products_csv):
        print(f"Error: Archivo '{args.products_csv}' no encontrado (products CSV)")
        sys.exit(1)

    try:
        # Validar credenciales (no necesarias en dry-run, pero validar igual)
        print("=" * 70)
        print("  PUM Spec Updater - Especificaciones VTEX")
        print("=" * 70)
        validate_credentials()

        if args.dry_run:
            print("  Modo: DRY RUN (sin llamadas API)")

        # Paso 1: Cargar CSV de especificaciones
        print(f"\n[1/7] Cargando CSV de especificaciones: {args.specs_csv}")
        specs_lookup = load_specs_csv(args.specs_csv)

        # Paso 2: Cargar vtex_products.csv (opcional)
        products_lookup = {}
        if args.products_csv:
            print(f"\n[2/7] Cargando CSV de productos VTEX: {args.products_csv}")
            products_lookup = load_products_csv(args.products_csv)
        else:
            print(f"\n[2/7] Sin CSV de productos (solo actualizacion, sin creacion)")

        # Paso 3: Cargar pum_encontrados.csv
        print(f"\n[3/7] Cargando CSV PUM: {args.pum_csv}")
        pum_data = load_pum_csv(args.pum_csv)

        if not pum_data:
            print("\nNo hay datos PUM para procesar")
            sys.exit(0)

        # Paso 4: Clasificar productos
        print(f"\n[4/7] Clasificando productos...")
        update_list, create_list, not_found_list = classify_products(pum_data, specs_lookup, products_lookup)

        print(f"  A actualizar (POST catalog_system): {len(update_list)}")
        print(f"  A crear (PUT):        {len(create_list)}")
        print(f"  Sin match:            {len(not_found_list)}")

        if not update_list and not create_list:
            print("\nNo hay productos para procesar (todos sin match)")
            # Exportar not_found
            if not_found_list:
                print(f"\n[7/7] Exportando resultados...")
                export_results([], [], not_found_list, args.output_prefix, args.dry_run)
            sys.exit(0)

        # Paso 5: Auto-descubrir GroupName (si necesario)
        group_name = args.group_name
        needs_group = create_list or any(
            item.get('action') == 'partial' for item in update_list
        )

        if needs_group and not group_name:
            print(f"\n[5/7] Auto-descubriendo GroupName...")
            if args.dry_run:
                print("  DRY RUN: saltando auto-descubrimiento de GroupName")
                group_name = "<AUTO-DISCOVER>"
            else:
                group_name = discover_group_name(specs_lookup, timeout=args.timeout)
                if not group_name:
                    print("  No se pudo descubrir GroupName automaticamente")
                    if create_list:
                        print("  Use --group-name para especificarlo manualmente")
                        print(f"  {len(create_list)} productos no podran tener specs creadas")
        else:
            print(f"\n[5/7] GroupName: {group_name or 'no requerido'}")

        # Paso 6: Ejecutar llamadas API
        print(f"\n[6/7] Ejecutando llamadas API...")
        print(f"  Delay: {args.delay}s | Timeout: {args.timeout}s | Retries: {MAX_RETRIES}")
        successful, failed = execute_updates(
            update_list, create_list, group_name,
            delay=args.delay, timeout=args.timeout, dry_run=args.dry_run
        )

        # Paso 7: Exportar resultados
        print(f"\n[7/7] Exportando resultados...")
        export_results(successful, failed, not_found_list, args.output_prefix, args.dry_run)

        # Resumen final
        total = len(successful) + len(failed)
        print(f"\n{'=' * 70}")
        print(f"  Resumen Final")
        print(f"{'=' * 70}")
        print(f"  Productos exitosos:    {len(successful)}")
        print(f"  Productos fallidos:    {len(failed)}")
        print(f"  Sin match:             {len(not_found_list)}")
        if total > 0:
            rate = len(successful) / total * 100
            print(f"  Tasa de exito:         {rate:.1f}%")
        print()

    except ValueError as e:
        print(f"\nError de configuracion: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
