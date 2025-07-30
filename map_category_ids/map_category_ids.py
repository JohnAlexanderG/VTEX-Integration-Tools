#!/usr/bin/env python3
"""
map_category_ids.py

Script de integración VTEX para mapear IDs de departamento y categoría desde 
el catálogo VTEX. Tercer paso del flujo de transformación de datos.

Funcionalidad:
- Conecta con la API de VTEX usando credenciales desde archivo .env local
- Descarga árbol completo de categorías del catálogo VTEX
- Normaliza nombres eliminando acentos y convirtiendo a minúsculas para matching robusto
- Procesa campo "Categoría" con formato jerárquico: "Departamento>Categoria>SubCategoria"
- Asigna IDs correspondientes:
  * DepartmentId: ID del departamento VTEX
  * CategoryId: ID de subcategoría si existe, sino ID de categoría, sino DepartmentId
- Genera reporte detallado en markdown con estadísticas y errores agrupados
- Maneja casos especiales y errores de mapping con logging comprehensivo

Lógica de Mapeo:
- Si existe subcategoría → CategoryId = subcategory.id
- Si solo existe categoría → CategoryId = category.id  
- Si solo existe departamento → CategoryId = department.id
- Si no existe departamento → CategoryId = null

Ejecución:
    # Mapeo básico con endpoint por defecto
    python3 map_category_ids.py input.json output.json --indent 4
    
    # Con endpoint personalizado
    python3 map_category_ids.py data.json categorized.json --endpoint vtexcommercestable --indent 4

Ejemplo:
    python3 map_category_ids/map_category_ids.py productos.json productos_categorized.json --endpoint vtexcommercestable

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey y X-VTEX-API-AppToken
"""
import argparse
import json
import requests
import sys
import unicodedata
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# Leer credenciales VTEX
trex_app_key = os.getenv('X-VTEX-API-AppKey')
trex_app_token = os.getenv('X-VTEX-API-AppToken')

if not trex_app_key or not trex_app_token:
    print("Debe definir X-VTEX-API-AppKey y X-VTEX-API-AppToken en el archivo .env", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    'X-VTEX-API-AppKey': trex_app_key,
    'X-VTEX-API-AppToken': trex_app_token,
    'Content-Type': 'application/json'
}


def normalize(text):
    """Elimina acentos y convierte a minúsculas."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', text)
    without_accents = ''.join([c for c in nfkd if unicodedata.category(c) != 'Mn'])
    return without_accents.lower().strip()


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


def generate_log_report(log_data, output_file):
    """Genera un archivo de log optimizado en formato markdown."""
    log_filename = output_file.replace('.json', '_category_log.md')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Procesar datos para eliminar duplicados y agrupar
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
    
    with open(log_filename, 'w', encoding='utf-8') as f:
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
        
        # Categorías exitosas agrupadas por departamento
        f.write(f"## ✅ Categorías Encontradas ({unique_successful} rutas únicas)\n\n")
        if successful_unique:
            # Agrupar por departamento
            by_dept = {}
            for path, data in successful_unique.items():
                dept = data['department'] or 'Sin Departamento'
                if dept not in by_dept:
                    by_dept[dept] = []
                by_dept[dept].append((path, data))
            
            for dept, items in sorted(by_dept.items()):
                f.write(f"### {dept}\n\n")
                for path, data in sorted(items):
                    cat = data['category'] or ''
                    subcat = data['subcategory'] or ''
                    count_info = f" *(×{data['count']})*" if data['count'] > 1 else ""
                    
                    if subcat:
                        f.write(f"- **{cat}** → {subcat}{count_info}\n")
                    elif cat:
                        f.write(f"- **{cat}**{count_info}\n")
                    else:
                        f.write(f"- Solo departamento{count_info}\n")
                f.write("\n")
        else:
            f.write("*No hay categorías exitosas.*\n\n")
        
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
                    f.write(f"- `{path}`{count_info}\n")
                f.write("\n")
        else:
            f.write("*No hay errores.*\n\n")
        
        f.write(f"---\n*Generado automáticamente*\n")
    
    return log_filename


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
        'failed': []
    }
    
    for rec in records:
        cat_path = rec.get('Categoría', '')
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
            'subcategory_found': False
        }
        
        if parts:
            # Departamento
            d_norm = normalize(parts[0])
            mapping_status['department'] = parts[0]
            dept_entry = tree_map.get(d_norm)
            if dept_entry:
                dept_id = dept_entry['id']
                mapping_status['department_found'] = True
                
                if len(parts) > 1:
                    # Categoría
                    c_norm = normalize(parts[1])
                    mapping_status['category'] = parts[1]
                    cat_entry = dept_entry['children'].get(c_norm)
                    if cat_entry:
                        mapping_status['category_found'] = True
                        cat_id = cat_entry['id']
                        
                        if len(parts) > 2:
                            # Subcategoría
                            s_norm = normalize(parts[2])
                            mapping_status['subcategory'] = parts[2]
                            sub_id = cat_entry['children'].get(s_norm)
                            if sub_id:
                                mapping_status['subcategory_found'] = True
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
        else:
            log_data['successful'].append(mapping_status)
        
        rec['DepartmentId'] = dept_id
        rec['CategoryId'] = cat_id
        mapped.append(rec)
    
    return mapped, log_data


def main():
    parser = argparse.ArgumentParser(description='Mapea DepartmentId y CategoryId para productos VTEX')
    parser.add_argument('input_file', help='Archivo JSON de entrada con lista de productos')
    parser.add_argument('output_file', help='Archivo JSON de salida con IDs agregados')
    parser.add_argument('--endpoint', default='https://homesentry.vtexcommercestable.com.br/api/catalog_system/pub/category/tree/2/',
                        help='Endpoint VTEX para categoría')
    parser.add_argument('--indent', type=int, default=4,
                        help='Nivel de indentación para el JSON de salida')
    args = parser.parse_args()

    # 1. Obtener árbol de categorías
    tree = fetch_category_tree(args.endpoint)

    # 2. Construir mapeo
    tree_map = build_tree_map(tree)

    # 3. Leer datos de entrada
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        print(f"Error al leer archivo de entrada: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Mapear IDs
    mapped_records, log_data = map_ids_to_records(records, tree_map)

    # 5. Generar reporte de log
    log_filename = generate_log_report(log_data, args.output_file)
    print(f"Reporte de categorías generado en {log_filename}")

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
