#!/usr/bin/env python3
"""
map_category_ids.py

Script de integración VTEX para mapear IDs de departamento y categoría desde 
el catálogo VTEX. Tercer paso del flujo de transformación de datos.

Funcionalidad:
- Conecta con la API de VTEX usando credenciales desde archivo .env local
- Descarga árbol completo de categorías del catálogo VTEX
- Normaliza nombres eliminando acentos y convirtiendo a minúsculas para matching robusto
- Procesa campo "CategoryPath" con formato jerárquico: "Departamento>Categoria>SubCategoria"
- Convierte formato de salida: "/" existentes → "-", primeros dos ">" → "/"
- Asigna IDs correspondientes:
  * DepartmentId: ID del departamento VTEX
  * CategoryId: ID de subcategoría si existe, sino ID de categoría, sino DepartmentId
- Genera reportes de salida:
  * JSON detallado con información completa de comparación
  * Markdown con estadísticas y errores agrupados
  * CSV con registros completos que fallaron en el mapeo (incluye motivo de error)
- Maneja casos especiales y errores de mapping con logging comprehensivo

Lógica de Mapeo:
- Si existe subcategoría → CategoryId = subcategory.id
- Si solo existe categoría → CategoryId = category.id  
- Si solo existe departamento → CategoryId = department.id
- Si no existe departamento → CategoryId = null

Ejecución:
    # Mapeo básico (usa variables del .env automáticamente)
    python3 map_category_ids.py input.json output.json --indent 4
    
    # Con endpoint personalizado si es necesario
    python3 map_category_ids.py data.json categorized.json --endpoint https://custom.vtexcommercestable.com.br/api/catalog_system/pub/category/tree/2/

Ejemplo:
    python3 map_category_ids/map_category_ids.py productos.json productos_categorized.json

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
"""
import argparse
import json
import requests
import sys
import unicodedata
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Leer credenciales y configuración VTEX
trex_app_key = os.getenv('X-VTEX-API-AppKey')
trex_app_token = os.getenv('X-VTEX-API-AppToken')
vtex_account_name = os.getenv('VTEX_ACCOUNT_NAME')
vtex_environment = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

if not trex_app_key or not trex_app_token:
    print("Debe definir X-VTEX-API-AppKey y X-VTEX-API-AppToken en el archivo .env", file=sys.stderr)
    sys.exit(1)

if not vtex_account_name:
    print("Debe definir VTEX_ACCOUNT_NAME en el archivo .env", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    'X-VTEX-API-AppKey': trex_app_key,
    'X-VTEX-API-AppToken': trex_app_token,
    'Content-Type': 'application/json'
}


def normalize(text):
    """
    Normaliza texto para comparación: elimina acentos, ñ→n, convierte a minúsculas.

    Ejemplos:
    - "Mantenimiento Baño" → "mantenimiento bano"
    - "Decoración" → "decoracion"
    - "ASEO" → "aseo"
    - "Niños y Niñas" → "ninos y ninas"
    """
    if not text:
        return ''

    # Normalización NFD: descompone caracteres acentuados (á → a + ´)
    nfd = unicodedata.normalize('NFD', text)

    # Eliminar marcas diacríticas (acentos, diéresis, etc.)
    without_accents = ''.join([c for c in nfd if unicodedata.category(c) != 'Mn'])

    # Reemplazar explícitamente ñ y Ñ por n (por si NFD no lo maneja)
    without_n = without_accents.replace('ñ', 'n').replace('Ñ', 'n')

    # Convertir a minúsculas y eliminar espacios al inicio/final
    normalized = without_n.lower().strip()

    return normalized


def build_tree_map(tree):
    """Construye un mapeo anidado de nombres normalizados a datos de categoría."""
    dept_map = {}
    for dept in tree:
        d_name = normalize(dept.get('name'))
        dept_map[d_name] = {
            'id': dept.get('id'),
            'children': {}
        }
        for cat in dept.get('children', []):
            c_name = normalize(cat.get('name'))
            dept_map[d_name]['children'][c_name] = {
                'id': cat.get('id'),
                'children': {}
            }
            for sub in cat.get('children', []):
                s_name = normalize(sub.get('name'))
                dept_map[d_name]['children'][c_name]['children'][s_name] = sub.get('id')
    return dept_map


def generate_log_reports(log_data, output_file, tree_map):
    """Genera archivos de log detallados en formato JSON, markdown y CSV para fallidos."""
    # Archivo JSON detallado con toda la información de comparación
    json_log_filename = output_file.replace('.json', '_comparison_log.json')
    md_log_filename = output_file.replace('.json', '_category_log.md')
    csv_failed_filename = output_file.replace('.json', '_fallidos.csv')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Preparar datos detallados para JSON
    detailed_log = {
        'timestamp': timestamp,
        'summary': {
            'total_processed': len(log_data['successful']) + len(log_data['failed']),
            'successful': len(log_data['successful']),
            'failed': len(log_data['failed'])
        },
        'vtex_categories_available': {
            'departments': list(tree_map.keys()),
            'department_count': len(tree_map),
            'full_tree': {}
        },
        'comparison_details': []
    }

    # Incluir árbol completo de VTEX para referencia (con nombres normalizados)
    for dept_norm, dept_data in tree_map.items():
        detailed_log['vtex_categories_available']['full_tree'][dept_norm] = {
            'id': dept_data['id'],
            'normalized_name': dept_norm,  # Mostrar el nombre normalizado
            'categories': {}
        }
        for cat_norm, cat_data in dept_data['children'].items():
            detailed_log['vtex_categories_available']['full_tree'][dept_norm]['categories'][cat_norm] = {
                'id': cat_data['id'],
                'normalized_name': cat_norm,  # Mostrar el nombre normalizado
                'subcategories': {}
            }
            # Incluir subcategorías con sus nombres normalizados
            for sub_norm, sub_id in cat_data['children'].items():
                detailed_log['vtex_categories_available']['full_tree'][dept_norm]['categories'][cat_norm]['subcategories'][sub_norm] = {
                    'id': sub_id,
                    'normalized_name': sub_norm
                }

    # Combinar todos los registros con detalles de comparación
    all_records = log_data['successful'] + log_data['failed']

    for record in all_records:
        detail = {
            'category_path_original': record['category_path'],
            'parsing': {
                'department': {
                    'original': record.get('department'),
                    'normalized': normalize(record.get('department', '')) if record.get('department') else None
                },
                'category': {
                    'original': record.get('category'),
                    'normalized': normalize(record.get('category', '')) if record.get('category') else None
                },
                'subcategory': {
                    'original': record.get('subcategory'),
                    'normalized': normalize(record.get('subcategory', '')) if record.get('subcategory') else None
                }
            },
            'matching_results': {
                'department_found': record.get('department_found', False),
                'department_id': record.get('department_id'),
                'category_found': record.get('category_found', False),
                'category_id': record.get('category_id'),
                'subcategory_found': record.get('subcategory_found', False),
                'subcategory_id': record.get('subcategory_id')
            },
            'status': 'success' if record in log_data['successful'] else 'failed'
        }

        # Agregar categorías disponibles en VTEX para el departamento
        if record.get('department'):
            dept_norm = normalize(record['department'])
            if dept_norm in tree_map:
                detail['vtex_available_categories'] = list(tree_map[dept_norm]['children'].keys())

                # Si hay categoría, agregar subcategorías disponibles
                if record.get('category'):
                    cat_norm = normalize(record['category'])
                    if cat_norm in tree_map[dept_norm]['children']:
                        detail['vtex_available_subcategories'] = list(
                            tree_map[dept_norm]['children'][cat_norm]['children'].keys()
                        )

        detailed_log['comparison_details'].append(detail)

    # Guardar JSON detallado
    with open(json_log_filename, 'w', encoding='utf-8') as f:
        json.dump(detailed_log, f, indent=2, ensure_ascii=False)

    # Procesar datos para eliminar duplicados y agrupar para markdown
    successful_unique = {}
    failed_unique = {}

    # Agrupar exitosos por ruta única
    for item in log_data['successful']:
        path = item['category_path']
        if path not in successful_unique:
            successful_unique[path] = {
                'department': item['department'],
                'category': item['category'],
                'subcategory': item['subcategory'],
                'count': 1
            }
        else:
            successful_unique[path]['count'] += 1

    # Agrupar fallidos por tipo de error
    for item in log_data['failed']:
        path = item['category_path']
        error_reasons = []
        if not item['department_found']:
            error_reasons.append("Departamento no existe")
        if item['category'] and not item['category_found']:
            error_reasons.append("Categoría no existe")
        if item['subcategory'] and not item['subcategory_found']:
            error_reasons.append("Subcategoría no existe")

        error_key = ", ".join(error_reasons)

        if path not in failed_unique:
            failed_unique[path] = {
                'department': item['department'],
                'category': item['category'],
                'subcategory': item['subcategory'],
                'error': error_key,
                'count': 1
            }
        else:
            failed_unique[path]['count'] += 1

    # Generar markdown
    with open(md_log_filename, 'w', encoding='utf-8') as f:
        f.write(f"# Reporte de Mapeo de Categorías VTEX\n\n")
        f.write(f"**Fecha:** {timestamp}\n\n")

        # Resumen
        total_successful = len(log_data['successful'])
        total_failed = len(log_data['failed'])
        total_processed = total_successful + total_failed
        unique_successful = len(successful_unique)
        unique_failed = len(failed_unique)

        f.write(f"## 📊 Resumen\n\n")
        f.write(f"- **Total procesado:** {total_processed} registros\n")
        f.write(f"- **Exitosos:** {total_successful} ({unique_successful} rutas únicas)\n")
        f.write(f"- **Fallidos:** {total_failed} ({unique_failed} rutas únicas)\n")
        f.write(f"- **Tasa de éxito:** {(total_successful/total_processed*100):.1f}%\n\n")
        f.write(f"- **Archivo de comparación detallada:** `{json_log_filename}`\n\n")

        # Errores agrupados por tipo
        f.write(f"## ❌ Errores Encontrados ({unique_failed} rutas únicas)\n\n")
        if failed_unique:
            # Agrupar por tipo de error
            by_error = {}
            for path, data in failed_unique.items():
                error = data['error']
                if error not in by_error:
                    by_error[error] = []
                by_error[error].append((path, data))

            for error_type, items in sorted(by_error.items()):
                f.write(f"### {error_type}\n\n")
                for path, data in sorted(items):
                    count_info = f" *(×{data['count']})*" if data['count'] > 1 else ""
                    dept_norm = normalize(data['department']) if data['department'] else None

                    # Mostrar qué hay disponible en VTEX
                    vtex_info = ""
                    if dept_norm and dept_norm in tree_map:
                        cats_available = list(tree_map[dept_norm]['children'].keys())
                        if cats_available and data['category']:
                            cat_norm = normalize(data['category'])
                            vtex_info = f"\n  - VTEX tiene en '{data['department']}': {cats_available[:10]}{'...' if len(cats_available) > 10 else ''}"

                    f.write(f"- `{path}`{count_info}{vtex_info}\n")
                f.write("\n")
        else:
            f.write("*No hay errores.*\n\n")

        f.write(f"---\n*Generado automáticamente*\n")

    # Exportar CSV con registros fallidos completos
    if log_data.get('failed_records'):
        try:
            with open(csv_failed_filename, 'w', encoding='utf-8', newline='') as csvfile:
                # Obtener todas las claves de los registros fallidos
                all_keys = set()
                for record in log_data['failed_records']:
                    all_keys.update(record.keys())

                # Ordenar las claves, poniendo _error_reason al final
                fieldnames = sorted([k for k in all_keys if k != '_error_reason'])
                if '_error_reason' in all_keys:
                    fieldnames.append('_error_reason')

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(log_data['failed_records'])

            print(f"  - Registros fallidos CSV: {csv_failed_filename}")
        except Exception as e:
            print(f"⚠️  Error al generar CSV de fallidos: {e}", file=sys.stderr)

    return json_log_filename, md_log_filename, csv_failed_filename


def fetch_category_tree(endpoint):
    try:
        resp = requests.get(endpoint, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error al descargar árbol de categorías: {e}", file=sys.stderr)
        sys.exit(1)


def map_ids_to_records(records, tree_map):
    mapped = []
    log_data = {
        'successful': [],
        'failed': [],
        'failed_records': []  # Almacenar registros completos que fallaron
    }

    print(f"\n🔄 Procesando {len(records)} registros...")

    for i, rec in enumerate(records, 1):
        cat_path = rec.get('CategoryPath', rec.get('Categoría', ''))  # Soporte para ambos nombres
        parts = [p.strip() for p in cat_path.split('>') if p.strip()]
        dept_id = None
        cat_id = None
        mapping_status = {
            'category_path': cat_path,
            'department': None,
            'category': None,
            'subcategory': None,
            'department_found': False,
            'category_found': False,
            'subcategory_found': False,
            'department_id': None,
            'category_id': None,
            'subcategory_id': None
        }

        # Mostrar progreso simple cada 100 registros
        if i % 100 == 0 or i == len(records):
            print(f"  Procesados: {i}/{len(records)}")

        if parts:
            # Departamento
            d_norm = normalize(parts[0])
            mapping_status['department'] = parts[0]
            dept_entry = tree_map.get(d_norm)

            if dept_entry:
                dept_id = dept_entry['id']
                mapping_status['department_found'] = True
                mapping_status['department_id'] = dept_id

                if len(parts) > 1:
                    # Categoría
                    c_norm = normalize(parts[1])
                    mapping_status['category'] = parts[1]
                    cat_entry = dept_entry['children'].get(c_norm)

                    if cat_entry:
                        mapping_status['category_found'] = True
                        cat_id = cat_entry['id']
                        mapping_status['category_id'] = cat_id

                        if len(parts) > 2:
                            # Subcategoría
                            s_norm = normalize(parts[2])
                            mapping_status['subcategory'] = parts[2]
                            sub_id = cat_entry['children'].get(s_norm)

                            if sub_id:
                                mapping_status['subcategory_found'] = True
                                mapping_status['subcategory_id'] = sub_id
                                cat_id = sub_id
        
        # Ajuste final de lógica:
        if dept_id is not None and cat_id is None:
            cat_id = dept_id
        if dept_id is None:
            cat_id = None
        
        # Determinar si el mapeo fue exitoso o falló
        has_failures = False
        if parts:
            if not mapping_status['department_found']:
                has_failures = True
            if len(parts) > 1 and not mapping_status['category_found']:
                has_failures = True
            if len(parts) > 2 and not mapping_status['subcategory_found']:
                has_failures = True

        if has_failures:
            log_data['failed'].append(mapping_status)
            # Guardar una copia del registro completo original para exportar a CSV
            failed_record = rec.copy()
            failed_record['_error_reason'] = []
            if not mapping_status['department_found']:
                failed_record['_error_reason'].append('Departamento no existe')
            if len(parts) > 1 and not mapping_status['category_found']:
                failed_record['_error_reason'].append('Categoría no existe')
            if len(parts) > 2 and not mapping_status['subcategory_found']:
                failed_record['_error_reason'].append('Subcategoría no existe')
            failed_record['_error_reason'] = ', '.join(failed_record['_error_reason'])
            log_data['failed_records'].append(failed_record)
        else:
            log_data['successful'].append(mapping_status)
        
        # Renombrar/actualizar campo CategoryPath y agregar IDs
        if 'Categoría' in rec:
            category_path_value = rec.pop('Categoría')  # Renombrar si existe el campo antiguo
        else:
            category_path_value = cat_path  # Usar el valor procesado
        
        # Reemplazar "/" existentes por "-" y luego los dos primeros ">" con "/"
        if category_path_value:
            # Paso 1: Reemplazar cualquier "/" existente por "-"
            category_path_value = category_path_value.replace('/', '-')
            
            # Paso 2: Dividir por ">" y reconstruir con "/" para los dos primeros separadores
            path_parts = category_path_value.split('>')
            if len(path_parts) >= 2:
                # Primer separador: Departamento/Categoría
                formatted_path = path_parts[0] + '/' + path_parts[1]
                # Segundo separador si existe: Departamento/Categoría/Subcategoría
                if len(path_parts) >= 3:
                    formatted_path += '/' + path_parts[2]
                # Mantener ">" para separadores adicionales si los hay
                if len(path_parts) > 3:
                    formatted_path += '>' + '>'.join(path_parts[3:])
                category_path_value = formatted_path
        
        rec['CategoryPath'] = category_path_value
        rec['DepartmentId'] = dept_id
        rec['CategoryId'] = cat_id
        mapped.append(rec)
    
    print(f"\n✅ Procesamiento completado: {len(log_data['successful'])} exitosos, {len(log_data['failed'])} fallidos")
    return mapped, log_data


def main():
    parser = argparse.ArgumentParser(description='Mapea DepartmentId y CategoryId para productos VTEX')
    parser.add_argument('input_file', help='Archivo JSON de entrada con lista de productos')
    parser.add_argument('output_file', help='Archivo JSON de salida con IDs agregados')
    # Construir endpoint por defecto usando variables de entorno
    default_endpoint = f'https://{vtex_account_name}.{vtex_environment}.com.br/api/catalog_system/pub/category/tree/2/'
    parser.add_argument('--endpoint', default=default_endpoint,
                        help='Endpoint VTEX para categoría')
    parser.add_argument('--indent', type=int, default=4,
                        help='Nivel de indentación para el JSON de salida')
    args = parser.parse_args()

    # 1. Obtener árbol de categorías
    print(f"🌐 Descargando árbol de categorías desde: {args.endpoint}")
    tree = fetch_category_tree(args.endpoint)
    print(f"📊 Árbol descargado: {len(tree)} departamentos encontrados")

    # 2. Construir mapeo
    print("🗺️  Construyendo mapeo de categorías...")
    tree_map = build_tree_map(tree)
    total_categories = sum(len(dept['children']) for dept in tree_map.values())
    total_subcategories = sum(
        len(cat['children']) for dept in tree_map.values() 
        for cat in dept['children'].values()
    )
    print(f"📋 Mapeo completado: {len(tree_map)} departamentos, {total_categories} categorías, {total_subcategories} subcategorías")

    # 3. Leer datos de entrada
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        print(f"Error al leer archivo de entrada: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Mapear IDs
    mapped_records, log_data = map_ids_to_records(records, tree_map)

    # 5. Generar reportes de log (JSON detallado, Markdown resumen y CSV de fallidos)
    json_log_filename, md_log_filename, csv_failed_filename = generate_log_reports(log_data, args.output_file, tree_map)
    print(f"\n📄 Reportes generados:")
    print(f"  - Log detallado JSON: {json_log_filename}")
    print(f"  - Resumen Markdown: {md_log_filename}")
    if log_data.get('failed_records'):
        print(f"  - Registros fallidos CSV: {csv_failed_filename}")

    # 6. Escribir salida
    try:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(mapped_records, f, indent=args.indent, ensure_ascii=False)
        print(f"Archivo de salida guardado en {args.output_file}")
    except Exception as e:
        print(f"Error al escribir archivo de salida: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
