#!/usr/bin/env python3
"""
vtex_category_creator.py

Script de creación masiva de jerarquía de categorías VTEX usando la API privada del catálogo.
Crea estructura completa de 3 niveles: Departamentos → Categorías → Subcategorías/Líneas.

Funcionalidad:
- Crea categorías en VTEX usando el endpoint POST /api/catalog/pvt/category
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Verifica existencia de categorías antes de crear para evitar duplicados
- Implementa control de rate limiting para evitar saturar la API VTEX
- Procesa lista de productos desde archivo JSON con estructura plana
- Extrae jerarquía única de 3 niveles del JSON plano
- Proceso secuencial: primero departamentos, luego categorías, luego líneas
- Exporta categorías creadas, omitidas y errores en archivos JSON separados
- Genera reporte markdown detallado con estadísticas por nivel

Control de Rate Limiting:
- Pausa de 1 segundo entre requests de creación
- Sin delay para categorías omitidas (ya existentes)
- Backoff exponencial en caso de rate limiting (429)
- Retry automático hasta 3 intentos por categoría
- Timeout de 30 segundos por request

Idempotencia:
- Re-ejecuciones omiten todas las categorías existentes sin errores
- Matching robusto mediante normalización Unicode (sin acentos)

Estructura de Salida:
- {timestamp}_categories_created.json: Categorías creadas exitosamente
- {timestamp}_categories_skipped.json: Categorías que ya existían
- {timestamp}_categories_failed.json: Categorías que fallaron
- {timestamp}_category_creation_report.md: Reporte markdown con estadísticas completas

Ejecución:
    # Creación básica
    python3 vtex_category_creator.py input.json

    # Modo dry-run (simulación sin crear)
    python3 vtex_category_creator.py input.json --dry-run

    # Con configuración personalizada de timing
    python3 vtex_category_creator.py input.json --delay 2 --timeout 45

    # Con archivos de salida personalizados
    python3 vtex_category_creator.py datos.json --output-prefix custom_batch

Ejemplo:
    python3 24_vtex_category_creator/vtex_category_creator.py 01_csv_to_json/2025_11_24_ARBOL_CATEGORIA-VF.03.json

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
"""

import json
import requests
import argparse
import os
import sys
import time
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
from collections import OrderedDict

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


class VTEXCategoryCreator:
    def __init__(self, delay=DEFAULT_DELAY, timeout=DEFAULT_TIMEOUT, dry_run=False):
        self.delay = delay
        self.timeout = timeout
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-VTEX-API-AppKey': VTEX_APP_KEY,
            'X-VTEX-API-AppToken': VTEX_APP_TOKEN
        })
        self.base_url = f"https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br"
        self.endpoint = f"{self.base_url}/api/catalog/pvt/category"
        self.tree_endpoint = f"{self.base_url}/api/catalog_system/pub/category/tree/2/"

        # Tracking por nivel
        self.created_categories = []
        self.skipped_categories = []
        self.failed_categories = []

        # Mapeo de IDs creados/existentes por nivel
        self.department_ids = {}  # nombre_normalizado -> id
        self.category_ids = {}    # "dept_norm > cat_norm" -> id

        # Árbol de categorías existentes en VTEX
        self.existing_tree_map = {}

        # Estadísticas
        self.start_time = None
        self.total_processed = 0

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
        if self.dry_run:
            print(f"🔍 MODO DRY-RUN: No se crearán categorías reales")
        else:
            print(f"✅ Endpoint: {self.endpoint}")

    def normalize(self, text):
        """Elimina acentos y convierte a minúsculas para matching robusto."""
        if not text:
            return ''
        nfkd = unicodedata.normalize('NFKD', text)
        without_accents = ''.join([c for c in nfkd if unicodedata.category(c) != 'Mn'])
        normalized = without_accents.lower().strip()
        return normalized

    def fetch_existing_tree(self):
        """Obtiene el árbol completo de categorías existentes en VTEX."""
        try:
            print(f"\n🌐 Descargando árbol de categorías desde VTEX...")
            response = self.session.get(self.tree_endpoint, timeout=self.timeout)
            response.raise_for_status()
            tree = response.json()
            print(f"✅ Árbol descargado: {len(tree)} departamentos encontrados")
            return tree
        except Exception as e:
            print(f"❌ Error al descargar árbol de categorías: {e}")
            sys.exit(1)

    def build_tree_map(self, tree):
        """Construye un mapeo anidado de nombres normalizados a datos de categoría."""
        dept_map = {}
        for dept in tree:
            d_name = self.normalize(dept.get('name', ''))
            if not d_name:
                continue
            dept_map[d_name] = {
                'id': dept.get('id'),
                'name': dept.get('name'),
                'children': {}
            }
            for cat in dept.get('children', []):
                c_name = self.normalize(cat.get('name', ''))
                if not c_name:
                    continue
                dept_map[d_name]['children'][c_name] = {
                    'id': cat.get('id'),
                    'name': cat.get('name'),
                    'children': {}
                }
                for sub in cat.get('children', []):
                    s_name = self.normalize(sub.get('name', ''))
                    if not s_name:
                        continue
                    dept_map[d_name]['children'][c_name]['children'][s_name] = {
                        'id': sub.get('id'),
                        'name': sub.get('name')
                    }

        print(f"🗺️  Mapeo construido:")
        total_cats = sum(len(dept['children']) for dept in dept_map.values())
        total_subcats = sum(
            len(cat['children']) for dept in dept_map.values()
            for cat in dept['children'].values()
        )
        print(f"   - {len(dept_map)} departamentos")
        print(f"   - {total_cats} categorías")
        print(f"   - {total_subcats} subcategorías")

        return dept_map

    def extract_hierarchy(self, records):
        """
        Extrae jerarquía única de 3 niveles del JSON plano.
        Retorna 3 diccionarios ordenados: departments, categories, lines.
        """
        departments = OrderedDict()
        categories = OrderedDict()
        lines = OrderedDict()

        for rec in records:
            dept_name = rec.get('CATEGORIA', '').strip()
            cat_name = rec.get('SUBCATEGORIA', '').strip()
            line_name = rec.get('LINEA', '').strip()

            dept_code = rec.get('NVO COD CAT', '')
            cat_code = rec.get('NVO COD SUBC', '')
            line_code = rec.get('NVO COD LINEA', '')

            # Nivel 1: Departamento
            if dept_name and dept_name not in departments:
                departments[dept_name] = {
                    'code': dept_code,
                    'original_name': dept_name
                }

            # Nivel 2: Categoría (con clave compuesta para evitar colisiones)
            if dept_name and cat_name:
                cat_key = f"{dept_name} > {cat_name}"
                if cat_key not in categories:
                    categories[cat_key] = {
                        'parent': dept_name,
                        'code': cat_code,
                        'original_name': cat_name
                    }

            # Nivel 3: Línea
            if dept_name and cat_name and line_name:
                line_key = f"{dept_name} > {cat_name} > {line_name}"
                if line_key not in lines:
                    lines[line_key] = {
                        'parent_dept': dept_name,
                        'parent_cat': cat_name,
                        'code': line_code,
                        'original_name': line_name
                    }

        print(f"\n📊 Jerarquía extraída del JSON:")
        print(f"   - {len(departments)} departamentos únicos")
        print(f"   - {len(categories)} categorías únicas")
        print(f"   - {len(lines)} líneas/subcategorías únicas")

        return departments, categories, lines

    def create_or_skip_category(self, name, father_id, level, retry_count=0):
        """
        Verifica si una categoría existe y la crea si no.
        Retorna: (category_id, status) donde status = 'created', 'skipped', o 'failed'
        """
        name_norm = self.normalize(name)

        # Verificar si ya existe en el árbol VTEX
        if level == 1:
            # Departamento
            if name_norm in self.existing_tree_map:
                existing_id = self.existing_tree_map[name_norm]['id']
                self.skipped_categories.append({
                    'name': name,
                    'level': level,
                    'father_id': father_id,
                    'category_id': existing_id,
                    'reason': 'Already exists in VTEX'
                })
                return (existing_id, 'skipped')

        elif level == 2:
            # Categoría - buscar bajo departamento padre
            for dept_name_norm, dept_data in self.existing_tree_map.items():
                if dept_data['id'] == father_id:
                    if name_norm in dept_data['children']:
                        existing_id = dept_data['children'][name_norm]['id']
                        self.skipped_categories.append({
                            'name': name,
                            'level': level,
                            'father_id': father_id,
                            'category_id': existing_id,
                            'reason': 'Already exists in VTEX'
                        })
                        return (existing_id, 'skipped')
                    break

        elif level == 3:
            # Subcategoría - buscar bajo categoría padre
            for dept_data in self.existing_tree_map.values():
                for cat_data in dept_data['children'].values():
                    if cat_data['id'] == father_id:
                        if name_norm in cat_data['children']:
                            existing_id = cat_data['children'][name_norm]['id']
                            self.skipped_categories.append({
                                'name': name,
                                'level': level,
                                'father_id': father_id,
                                'category_id': existing_id,
                                'reason': 'Already exists in VTEX'
                            })
                            return (existing_id, 'skipped')
                        break

        # No existe - crear
        if self.dry_run:
            # Modo simulación
            fake_id = 99999 + len(self.created_categories)
            self.created_categories.append({
                'name': name,
                'level': level,
                'father_id': father_id,
                'category_id': fake_id,
                'dry_run': True
            })
            return (fake_id, 'created')

        # Rate limiting - pausa entre requests de creación
        if self.total_processed > 0 and retry_count == 0:
            time.sleep(self.delay)

        # Construir request body
        request_body = {
            'Name': name,
            'Keywords': name,
            'Title': name,
            'Description': f'Productos de {name}',
            'FatherCategoryId': father_id,
            'IsActive': True,
            'ShowInStoreFront': True
        }

        try:
            response = self.session.post(
                self.endpoint,
                json=request_body,
                timeout=self.timeout
            )

            if response.status_code in (200, 201):
                # Categoría creada exitosamente
                result = response.json()
                category_id = result.get('Id')

                self.created_categories.append({
                    'name': name,
                    'level': level,
                    'father_id': father_id,
                    'category_id': category_id,
                    'response': result,
                    'timestamp': datetime.now().isoformat()
                })

                return (category_id, 'created')

            elif response.status_code == 429:
                # Rate limiting - retry con backoff exponencial
                if retry_count < MAX_RETRIES:
                    wait_time = self.delay * (BACKOFF_FACTOR ** retry_count)
                    print(f"   ⚠️ Rate limit alcanzado. Esperando {wait_time}s antes de reintentar...")
                    time.sleep(wait_time)
                    return self.create_or_skip_category(name, father_id, level, retry_count + 1)
                else:
                    self.failed_categories.append({
                        'name': name,
                        'level': level,
                        'father_id': father_id,
                        'error': 'Rate limit exceeded - max retries reached',
                        'status_code': response.status_code,
                        'response_text': response.text,
                        'timestamp': datetime.now().isoformat()
                    })
                    return (None, 'failed')

            else:
                # Error de API
                try:
                    error_response = response.json()
                except:
                    error_response = response.text

                self.failed_categories.append({
                    'name': name,
                    'level': level,
                    'father_id': father_id,
                    'error': f'API Error: {response.status_code}',
                    'status_code': response.status_code,
                    'response': error_response,
                    'timestamp': datetime.now().isoformat()
                })
                return (None, 'failed')

        except requests.exceptions.Timeout:
            self.failed_categories.append({
                'name': name,
                'level': level,
                'father_id': father_id,
                'error': 'Request timeout',
                'timeout': self.timeout,
                'timestamp': datetime.now().isoformat()
            })
            return (None, 'failed')

        except requests.exceptions.RequestException as e:
            self.failed_categories.append({
                'name': name,
                'level': level,
                'father_id': father_id,
                'error': f'Request error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
            return (None, 'failed')

        except Exception as e:
            self.failed_categories.append({
                'name': name,
                'level': level,
                'father_id': father_id,
                'error': f'Unexpected error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
            return (None, 'failed')

    def process_level_1_departments(self, departments):
        """Procesa y crea departamentos (Nivel 1)."""
        print(f"\n{'='*80}")
        print(f"📂 NIVEL 1: Procesando {len(departments)} departamentos")
        print(f"{'='*80}")

        created = 0
        skipped = 0
        failed = 0

        for i, (dept_name, dept_data) in enumerate(departments.items(), 1):
            print(f"\n[{i}/{len(departments)}] Departamento: {dept_name}")

            category_id, status = self.create_or_skip_category(
                name=dept_name,
                father_id=None,
                level=1
            )

            if status == 'created':
                print(f"   ✅ Creado - ID: {category_id}")
                created += 1
            elif status == 'skipped':
                print(f"   ⏭️  Omitido - Ya existe (ID: {category_id})")
                skipped += 1
            else:
                print(f"   ❌ Falló")
                failed += 1

            # Guardar ID para usar como padre en nivel 2
            if category_id:
                dept_name_norm = self.normalize(dept_name)
                self.department_ids[dept_name_norm] = category_id

            self.total_processed += 1

            # Progreso cada 10 items
            if i % 10 == 0:
                print(f"\n📊 Progreso Nivel 1: {i}/{len(departments)} - Creados: {created}, Omitidos: {skipped}, Fallidos: {failed}")

        print(f"\n✅ Nivel 1 completado: {created} creados, {skipped} omitidos, {failed} fallidos")
        return created, skipped, failed

    def process_level_2_categories(self, categories):
        """Procesa y crea categorías (Nivel 2)."""
        print(f"\n{'='*80}")
        print(f"📁 NIVEL 2: Procesando {len(categories)} categorías")
        print(f"{'='*80}")

        created = 0
        skipped = 0
        failed = 0

        for i, (cat_key, cat_data) in enumerate(categories.items(), 1):
            cat_name = cat_data['original_name']
            parent_dept = cat_data['parent']

            print(f"\n[{i}/{len(categories)}] Categoría: {parent_dept} > {cat_name}")

            # Obtener ID del departamento padre
            parent_dept_norm = self.normalize(parent_dept)
            father_id = self.department_ids.get(parent_dept_norm)

            if not father_id:
                print(f"   ❌ Padre no encontrado: {parent_dept}")
                self.failed_categories.append({
                    'name': cat_name,
                    'level': 2,
                    'father_id': None,
                    'error': f'Parent department not found: {parent_dept}',
                    'timestamp': datetime.now().isoformat()
                })
                failed += 1
                continue

            category_id, status = self.create_or_skip_category(
                name=cat_name,
                father_id=father_id,
                level=2
            )

            if status == 'created':
                print(f"   ✅ Creado - ID: {category_id}")
                created += 1
            elif status == 'skipped':
                print(f"   ⏭️  Omitido - Ya existe (ID: {category_id})")
                skipped += 1
            else:
                print(f"   ❌ Falló")
                failed += 1

            # Guardar ID para usar como padre en nivel 3
            if category_id:
                cat_key_norm = f"{parent_dept_norm} > {self.normalize(cat_name)}"
                self.category_ids[cat_key_norm] = category_id

            self.total_processed += 1

            # Progreso cada 10 items
            if i % 10 == 0:
                print(f"\n📊 Progreso Nivel 2: {i}/{len(categories)} - Creados: {created}, Omitidos: {skipped}, Fallidos: {failed}")

        print(f"\n✅ Nivel 2 completado: {created} creados, {skipped} omitidos, {failed} fallidos")
        return created, skipped, failed

    def process_level_3_lines(self, lines):
        """Procesa y crea líneas/subcategorías (Nivel 3)."""
        print(f"\n{'='*80}")
        print(f"📄 NIVEL 3: Procesando {len(lines)} líneas/subcategorías")
        print(f"{'='*80}")

        created = 0
        skipped = 0
        failed = 0

        for i, (line_key, line_data) in enumerate(lines.items(), 1):
            line_name = line_data['original_name']
            parent_dept = line_data['parent_dept']
            parent_cat = line_data['parent_cat']

            print(f"\n[{i}/{len(lines)}] Línea: {parent_dept} > {parent_cat} > {line_name}")

            # Obtener ID de la categoría padre
            parent_dept_norm = self.normalize(parent_dept)
            parent_cat_norm = self.normalize(parent_cat)
            cat_key_norm = f"{parent_dept_norm} > {parent_cat_norm}"
            father_id = self.category_ids.get(cat_key_norm)

            if not father_id:
                print(f"   ❌ Padre no encontrado: {parent_dept} > {parent_cat}")
                self.failed_categories.append({
                    'name': line_name,
                    'level': 3,
                    'father_id': None,
                    'error': f'Parent category not found: {parent_dept} > {parent_cat}',
                    'timestamp': datetime.now().isoformat()
                })
                failed += 1
                continue

            category_id, status = self.create_or_skip_category(
                name=line_name,
                father_id=father_id,
                level=3
            )

            if status == 'created':
                print(f"   ✅ Creado - ID: {category_id}")
                created += 1
            elif status == 'skipped':
                print(f"   ⏭️  Omitido - Ya existe (ID: {category_id})")
                skipped += 1
            else:
                print(f"   ❌ Falló")
                failed += 1

            self.total_processed += 1

            # Progreso cada 10 items
            if i % 10 == 0:
                print(f"\n📊 Progreso Nivel 3: {i}/{len(lines)} - Creados: {created}, Omitidos: {skipped}, Fallidos: {failed}")

        print(f"\n✅ Nivel 3 completado: {created} creados, {skipped} omitidos, {failed} fallidos")
        return created, skipped, failed

    def process_all_levels(self, records):
        """Procesa todos los niveles secuencialmente."""
        self.start_time = datetime.now()

        # Fase 1: Fetch árbol existente
        if not self.dry_run:
            tree = self.fetch_existing_tree()
            self.existing_tree_map = self.build_tree_map(tree)
        else:
            print(f"\n🔍 Modo DRY-RUN: Omitiendo descarga del árbol VTEX")
            self.existing_tree_map = {}

        # Fase 2: Extraer jerarquía del JSON
        departments, categories, lines = self.extract_hierarchy(records)

        # Fase 3: Procesar por niveles
        stats = {}
        stats['level_1'] = self.process_level_1_departments(departments)
        stats['level_2'] = self.process_level_2_categories(categories)
        stats['level_3'] = self.process_level_3_lines(lines)

        # Resumen final
        end_time = datetime.now()
        duration = end_time - self.start_time

        print(f"\n{'='*80}")
        print(f"🎉 PROCESO COMPLETADO")
        print(f"{'='*80}")
        print(f"⏱️  Duración: {duration}")
        print(f"\n📊 Resumen por Nivel:")
        print(f"   Nivel 1 (Departamentos):  Creados: {stats['level_1'][0]}, Omitidos: {stats['level_1'][1]}, Fallidos: {stats['level_1'][2]}")
        print(f"   Nivel 2 (Categorías):     Creados: {stats['level_2'][0]}, Omitidos: {stats['level_2'][1]}, Fallidos: {stats['level_2'][2]}")
        print(f"   Nivel 3 (Líneas):         Creados: {stats['level_3'][0]}, Omitidos: {stats['level_3'][1]}, Fallidos: {stats['level_3'][2]}")
        print(f"\n📈 Totales:")
        total_created = sum(s[0] for s in stats.values())
        total_skipped = sum(s[1] for s in stats.values())
        total_failed = sum(s[2] for s in stats.values())
        print(f"   ✅ Total creados: {total_created}")
        print(f"   ⏭️  Total omitidos: {total_skipped}")
        print(f"   ❌ Total fallidos: {total_failed}")

        return stats

    def export_results(self, output_prefix="category_creation"):
        """Exporta resultados a archivos JSON y genera reporte markdown."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Exportar categorías creadas
        if self.created_categories:
            created_file = f"{timestamp}_{output_prefix}_created.json"
            with open(created_file, 'w', encoding='utf-8') as f:
                json.dump(self.created_categories, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Categorías creadas exportadas a: {created_file}")

        # Exportar categorías omitidas
        if self.skipped_categories:
            skipped_file = f"{timestamp}_{output_prefix}_skipped.json"
            with open(skipped_file, 'w', encoding='utf-8') as f:
                json.dump(self.skipped_categories, f, ensure_ascii=False, indent=2)
            print(f"⏭️  Categorías omitidas exportadas a: {skipped_file}")

        # Exportar categorías fallidas
        if self.failed_categories:
            failed_file = f"{timestamp}_{output_prefix}_failed.json"
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_categories, f, ensure_ascii=False, indent=2)
            print(f"❌ Categorías fallidas exportadas a: {failed_file}")

        # Generar reporte markdown
        report_file = f"{timestamp}_{output_prefix}_report.md"
        self.generate_markdown_report(report_file)
        print(f"📋 Reporte generado: {report_file}")

    def generate_markdown_report(self, report_file):
        """Genera reporte detallado en formato markdown."""
        duration = datetime.now() - self.start_time if self.start_time else "N/A"

        created_count = len(self.created_categories)
        skipped_count = len(self.skipped_categories)
        failed_count = len(self.failed_categories)
        total_count = created_count + skipped_count + failed_count

        # Estadísticas por nivel
        created_by_level = {1: 0, 2: 0, 3: 0}
        skipped_by_level = {1: 0, 2: 0, 3: 0}
        failed_by_level = {1: 0, 2: 0, 3: 0}

        for item in self.created_categories:
            created_by_level[item['level']] += 1
        for item in self.skipped_categories:
            skipped_by_level[item['level']] += 1
        for item in self.failed_categories:
            failed_by_level[item['level']] += 1

        # Agrupar errores por tipo
        error_summary = {}
        for failed in self.failed_categories:
            error_type = failed.get('error', 'Unknown error')
            if error_type not in error_summary:
                error_summary[error_type] = []
            error_summary[error_type].append(failed)

        report_content = f"""# Reporte de Creación de Categorías VTEX

**Fecha:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Account VTEX:** {VTEX_ACCOUNT}
**Environment:** {VTEX_ENVIRONMENT}
**Duración:** {duration}
**Modo:** {'DRY-RUN (Simulación)' if self.dry_run else 'Producción'}

## 📊 Resumen General

| Métrica | Valor |
|---------|-------|
| **Total Procesado** | {total_count} |
| **✅ Creados** | {created_count} |
| **⏭️ Omitidos (ya existían)** | {skipped_count} |
| **❌ Fallidos** | {failed_count} |
| **⏱️ Delay entre requests** | {self.delay}s |
| **⏱️ Timeout por request** | {self.timeout}s |

## 📈 Estadísticas por Nivel

### Nivel 1: Departamentos

| Métrica | Valor |
|---------|-------|
| Creados | {created_by_level[1]} |
| Omitidos | {skipped_by_level[1]} |
| Fallidos | {failed_by_level[1]} |

### Nivel 2: Categorías

| Métrica | Valor |
|---------|-------|
| Creados | {created_by_level[2]} |
| Omitidos | {skipped_by_level[2]} |
| Fallidos | {failed_by_level[2]} |

### Nivel 3: Líneas/Subcategorías

| Métrica | Valor |
|---------|-------|
| Creados | {created_by_level[3]} |
| Omitidos | {skipped_by_level[3]} |
| Fallidos | {failed_by_level[3]} |

## ✅ Categorías Creadas ({created_count})

"""

        if self.created_categories:
            report_content += "| Nombre | Nivel | Father ID | Category ID | Timestamp |\n|--------|-------|-----------|-------------|----------|\n"
            for item in self.created_categories[:30]:  # Mostrar primeras 30
                name = item.get('name', 'N/A')[:50]
                level = item.get('level', 'N/A')
                father_id = item.get('father_id', 'N/A')
                category_id = item.get('category_id', 'N/A')
                timestamp = item.get('timestamp', 'N/A')[:19] if 'timestamp' in item else 'N/A'
                report_content += f"| {name} | {level} | {father_id} | {category_id} | {timestamp} |\n"

            if len(self.created_categories) > 30:
                report_content += f"\n*... y {len(self.created_categories) - 30} categorías más*\n"
        else:
            report_content += "*No se crearon categorías*\n"

        report_content += f"\n## ⏭️ Categorías Omitidas ({skipped_count})\n\n"

        if self.skipped_categories:
            report_content += "| Nombre | Nivel | Father ID | Category ID (existente) | Razón |\n|--------|-------|-----------|------------------------|-------|\n"
            for item in self.skipped_categories[:30]:  # Mostrar primeras 30
                name = item.get('name', 'N/A')[:50]
                level = item.get('level', 'N/A')
                father_id = item.get('father_id', 'N/A')
                category_id = item.get('category_id', 'N/A')
                reason = item.get('reason', 'N/A')[:40]
                report_content += f"| {name} | {level} | {father_id} | {category_id} | {reason} |\n"

            if len(self.skipped_categories) > 30:
                report_content += f"\n*... y {len(self.skipped_categories) - 30} categorías más*\n"
        else:
            report_content += "*No se omitieron categorías*\n"

        report_content += f"\n## ❌ Categorías Fallidas ({failed_count})\n\n"

        if self.failed_categories:
            # Resumen de errores agrupados
            report_content += "### 📋 Resumen de Errores\n\n"
            for error_type, errors in error_summary.items():
                report_content += f"- **{error_type}**: {len(errors)} categorías\n"

            report_content += "\n### 📝 Detalle de Categorías Fallidas\n\n"
            report_content += "| Nombre | Nivel | Father ID | Error | Status Code | Timestamp |\n|--------|-------|-----------|-------|-------------|----------|\n"

            for item in self.failed_categories[:30]:  # Mostrar primeras 30
                name = item.get('name', 'N/A')[:40]
                level = item.get('level', 'N/A')
                father_id = item.get('father_id', 'N/A')
                error = item.get('error', 'N/A')[:60]
                status_code = item.get('status_code', 'N/A')
                timestamp = item.get('timestamp', 'N/A')[:19] if 'timestamp' in item else 'N/A'
                report_content += f"| {name} | {level} | {father_id} | {error} | {status_code} | {timestamp} |\n"

            if len(self.failed_categories) > 30:
                report_content += f"\n*... y {len(self.failed_categories) - 30} categorías más en archivo JSON*\n"
        else:
            report_content += "*No hubo categorías fallidas*\n"

        # Análisis y recomendaciones
        report_content += f"\n## 🔍 Análisis y Recomendaciones\n\n"

        if failed_count == 0 and created_count > 0:
            report_content += "✅ **Excelente**. Todas las categorías nuevas fueron creadas exitosamente.\n"
        elif failed_count == 0 and skipped_count > 0:
            report_content += "✅ **Perfecto**. Todas las categorías ya existían. El sistema es idempotente.\n"
        elif failed_count > 0:
            report_content += f"⚠️ **Atención**: {failed_count} categorías fallaron. Revisar errores para corregir.\n"

        if failed_count > 0:
            report_content += f"\n### Errores más comunes:\n"
            for error_type, errors in sorted(error_summary.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                report_content += f"- **{error_type}**: {len(errors)} casos\n"

        report_content += f"\n---\n*Reporte generado automáticamente por vtex_category_creator.py*\n"

        # Escribir reporte
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)


def main():
    parser = argparse.ArgumentParser(
        description="Crea jerarquía completa de categorías en VTEX (3 niveles) desde JSON plano"
    )
    parser.add_argument("input_file", help="Archivo JSON con lista de productos/categorías")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                       help=f"Delay en segundos entre requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Timeout en segundos por request (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output-prefix", default="category_creation",
                       help="Prefijo para archivos de salida (default: category_creation)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Modo simulación: no crea categorías reales, solo muestra lo que haría")

    args = parser.parse_args()

    try:
        # Crear instancia del creador de categorías
        creator = VTEXCategoryCreator(
            delay=args.delay,
            timeout=args.timeout,
            dry_run=args.dry_run
        )

        # Validar credenciales
        creator.validate_credentials()

        # Cargar datos desde archivo JSON
        print(f"\n📂 Cargando datos desde: {args.input_file}")
        with open(args.input_file, 'r', encoding='utf-8') as f:
            records = json.load(f)

        # Manejar tanto array como objeto individual
        if isinstance(records, dict):
            records = [records]

        if not records:
            print("❌ No se encontraron registros para procesar")
            sys.exit(1)

        print(f"✅ Cargados {len(records)} registros para procesar")

        # Procesar todos los niveles
        creator.process_all_levels(records)

        # Exportar resultados
        creator.export_results(args.output_prefix)

        # Mostrar resumen final
        print(f"\n🎉 Proceso completado exitosamente!")
        if creator.dry_run:
            print(f"🔍 Recuerda: Esto fue un DRY-RUN. No se crearon categorías reales.")
            print(f"   Para crear categorías realmente, ejecuta sin --dry-run")

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
