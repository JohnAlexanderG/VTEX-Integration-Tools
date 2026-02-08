#!/usr/bin/env python3
"""
fix_category_errors.py

Script para corregir errores de categorías en datos de productos VTEX mediante
cross-referencia entre dos archivos JSON basándose en un reporte markdown de errores.

Funcionalidad:
- Lee reporte markdown generado por map_category_ids.py con Categoría problemáticos
- Extrae Categoría entre backticks del formato: `Departamento>Categoría>SubCategoría`
- Por cada Categoría problemático:
  * Busca en input-1.json (datos principales) para obtener el SKU
  * Busca ese SKU en input-2.json (datos de referencia) para obtener Categoría correcta
  * Reemplaza TODAS las ocurrencias del Categoría problemático con Categoría correcta
- Genera reporte detallado en markdown con estadísticas y errores
- Maneja errores sin detener ejecución (log y continúa)

Ejecución:
    # Uso básico
    python3 fix_category_errors.py error_log.md input1.json input2.json output.json

    # Con indentación personalizada
    python3 fix_category_errors.py error_log.md input1.json input2.json output.json --indent 2

Ejemplo:
    python3 25_fix_category_errors/fix_category_errors.py \\
      06_map_category_ids/PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada_category_log.md \\
      PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada.json \\
      reference_products.json \\
      PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada-FIXED.json

Archivos de entrada:
- Markdown: Reporte de errores con Categoría entre backticks
- input-1.json: JSON con Categoría y SKU (datos principales)
- input-2.json: JSON con SKU y Categoría (datos de referencia)

Archivos de salida:
- output.json: Versión corregida de input-1.json
- YYYYMMDD_HHMMSS_category_fix_report.md: Reporte legible con estadísticas
- YYYYMMDD_HHMMSS_category_fix_log.json: Log detallado para análisis
"""

import argparse
import json
import sys
import re
import os
from datetime import datetime


def parse_markdown_errors(markdown_file):
    """
    Extrae Categoría problemáticos del archivo markdown.

    Busca líneas con formato: - `Categoría` *(×N)*
    donde Categoría está entre backticks.

    Args:
        markdown_file: Ruta al archivo markdown con errores

    Returns:
        Set[str] de Categoría únicos problemáticos

    Ejemplos:
        - `Aseo>Ambientadores Hogar>Pilas Recargables AA` → extraído
        - `Camping>Carpas>NO EXISTE LINEA` *(×12)* → extraído
    """
    problematic_paths = set()
    pattern = r'-\s*`([^`]+)`(?:\s*\*\(×\d+\)\*)?'

    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            for line in f:
                matches = re.findall(pattern, line)
                for match in matches:
                    problematic_paths.add(match.strip())
    except FileNotFoundError:
        print(f"❌ Error: Archivo markdown no encontrado: {markdown_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al leer markdown: {e}", file=sys.stderr)
        sys.exit(1)

    return problematic_paths


def load_json_file(file_path, description):
    """
    Carga archivo JSON con manejo robusto de errores.

    Args:
        file_path: Ruta al archivo JSON
        description: Descripción del archivo para mensajes de error

    Returns:
        Lista de registros del JSON
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: Archivo no encontrado: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"❌ Error: {description} debe ser una lista JSON", file=sys.stderr)
            sys.exit(1)

        return data

    except json.JSONDecodeError as e:
        print(f"❌ Error: JSON inválido en {description}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al cargar {description}: {e}", file=sys.stderr)
        sys.exit(1)


def build_sku_index(records, sku_field='SKU'):
    """
    Construye índice {SKU: record} para búsqueda O(1).

    Args:
        records: Lista de registros JSON
        sku_field: Nombre del campo que contiene el SKU

    Returns:
        Dict[str, dict] mapeando SKU a registro completo
    """
    index = {}
    for record in records:
        sku = record.get(sku_field)
        if sku and sku not in index:
            index[sku] = record

    return index


def process_category_fixes(problematic_paths, input1_data, input2_index):
    """
    Procesa correcciones de categorías y construye mapping de reemplazos.

    Por cada Categoría problemático:
    1. Busca en input1_data para obtener SKU
    2. Busca SKU en input2_index para obtener Categoría correcta
    3. Construye mapping: {Categoría_viejo: Categoría_nueva}

    Args:
        problematic_paths: Set de Categoría problemáticos
        input1_data: Lista de registros del JSON principal
        input2_index: Dict {SKU: record} del JSON de referencia

    Returns:
        Dict con log de procesamiento incluyendo:
        - successful_fixes: Lista de correcciones exitosas
        - path_not_found_errors: Errores de Categoría no encontrado
        - sku_not_found_errors: Errores de SKU no encontrado
        - replacement_map: Mapping de reemplazos {viejo: nuevo}
    """
    log = {
        'successful_fixes': [],
        'path_not_found_errors': [],
        'sku_not_found_errors': [],
        'replacement_map': {}
    }

    print(f"\n🔍 Procesando {len(problematic_paths)} Categoría problemáticos...")

    for path in sorted(problematic_paths):
        # Buscar Categoría en input-1 para obtener SKU
        found_record = None
        for record in input1_data:
            if record.get('Categoría') == path:
                found_record = record
                break

        if not found_record:
            log['path_not_found_errors'].append({
                'problematic_path': path,
                'error': 'Categoría no encontrado en input-1.json'
            })
            print(f"   ⚠️  Categoría no encontrado: {path}")
            continue

        # Obtener SKU del registro encontrado
        sku = found_record.get('SKU')
        if not sku:
            log['path_not_found_errors'].append({
                'problematic_path': path,
                'error': 'Registro sin campo SKU'
            })
            print(f"   ⚠️  Registro sin SKU para Categoría: {path}")
            continue

        # Buscar SKU en input-2 para obtener Categoría correcta
        ref_record = input2_index.get(sku)
        if not ref_record:
            log['sku_not_found_errors'].append({
                'problematic_path': path,
                'sku': sku,
                'error': 'SKU no encontrado en input-2.json'
            })
            print(f"   ⚠️  SKU {sku} no encontrado en input-2.json")
            continue

        # Obtener Categoría correcta
        correct_category = ref_record.get('Categoría')
        if not correct_category:
            log['sku_not_found_errors'].append({
                'problematic_path': path,
                'sku': sku,
                'error': 'Campo Categoría vacío en input-2.json'
            })
            print(f"   ⚠️  Categoría vacía para SKU {sku}")
            continue

        # Agregar a mapping de reemplazos
        log['replacement_map'][path] = correct_category
        log['successful_fixes'].append({
            'problematic_path': path,
            'sku': sku,
            'correct_category': correct_category
        })
        print(f"   ✅ {path} → {correct_category}")

    return log


def apply_category_fixes(data, replacement_map, field='Categoría'):
    """
    Aplica todos los reemplazos de Categoría en un solo paso.

    Args:
        data: Lista de registros JSON
        replacement_map: Dict {Categoría_viejo: Categoría_nueva}
        field: Nombre del campo a actualizar

    Returns:
        Tuple (data_modificada, total_records_modified)
    """
    records_modified = 0

    for record in data:
        current_value = record.get(field)
        if current_value in replacement_map:
            record[field] = replacement_map[current_value]
            records_modified += 1

    return data, records_modified


def generate_markdown_report(log_data, output_file):
    """
    Genera reporte en formato markdown con estadísticas y errores.

    Args:
        log_data: Dict con información de procesamiento
        output_file: Nombre del archivo JSON de salida (para nombres de reporte)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = output_file.replace('.json', f'_{timestamp}_category_fix_report.md')

    total_processed = log_data['total_paths_processed']
    successful = len(log_data['successful_fixes'])
    path_errors = len(log_data['path_not_found_errors'])
    sku_errors = len(log_data['sku_not_found_errors'])
    success_rate = log_data['success_rate']

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('# Reporte de Corrección de Categorías VTEX\n\n')
        f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Resumen
        f.write('## 📊 Resumen General\n\n')
        f.write('| Métrica | Valor |\n')
        f.write('|---------|-------|\n')
        f.write(f'| **Total Categoría procesados** | {total_processed} |\n')
        f.write(f'| **✅ Correcciones exitosas** | {successful} |\n')
        f.write(f'| **❌ Errores (Categoría no encontrado)** | {path_errors} |\n')
        f.write(f'| **❌ Errores (SKU no encontrado)** | {sku_errors} |\n')
        f.write(f'| **📈 Tasa de éxito** | {success_rate:.1f}% |\n')
        f.write(f'| **📝 Registros modificados** | {log_data["total_records_modified"]} |\n\n')

        # Archivos de entrada
        f.write('## 📂 Archivos Procesados\n\n')
        f.write(f'- **Markdown:** `{log_data["input_files"]["markdown"]}`\n')
        f.write(f'- **Input-1 (Principal):** `{log_data["input_files"]["input_1"]}`\n')
        f.write(f'- **Input-2 (Referencia):** `{log_data["input_files"]["input_2"]}`\n')
        f.write(f'- **Output (Corregido):** `{output_file}`\n\n')

        # Correcciones exitosas
        if log_data['successful_fixes']:
            f.write('## ✅ Correcciones Exitosas\n\n')

            # Mostrar primeras 50 correcciones en tabla
            display_count = min(50, len(log_data['successful_fixes']))
            f.write(f'Mostrando {display_count} de {successful} correcciones:\n\n')
            f.write('| Categoría Problemático | SKU | Categoría Correcta |\n')
            f.write('|---------------------------|-----|--------------------|\n')

            for fix in log_data['successful_fixes'][:display_count]:
                path = fix['problematic_path']
                sku = fix['sku']
                category = fix['correct_category']
                f.write(f'| `{path}` | {sku} | `{category}` |\n')

            if successful > display_count:
                f.write(f'\n*... y {successful - display_count} correcciones más (ver log JSON para lista completa)*\n')

            f.write('\n')

        # Errores: Categoría no encontrado
        if log_data['path_not_found_errors']:
            f.write('## ❌ Errores: Categoría No Encontrado\n\n')
            f.write(f'Total: {path_errors} errores\n\n')

            for error in log_data['path_not_found_errors'][:20]:
                f.write(f'- `{error["problematic_path"]}`\n')
                f.write(f'  - ⚠️  {error["error"]}\n')

            if path_errors > 20:
                f.write(f'\n*... y {path_errors - 20} errores más*\n')

            f.write('\n')

        # Errores: SKU no encontrado
        if log_data['sku_not_found_errors']:
            f.write('## ❌ Errores: SKU No Encontrado\n\n')
            f.write(f'Total: {sku_errors} errores\n\n')

            for error in log_data['sku_not_found_errors'][:20]:
                f.write(f'- `{error["problematic_path"]}`\n')
                f.write(f'  - SKU: {error["sku"]}\n')
                f.write(f'  - ⚠️  {error["error"]}\n')

            if sku_errors > 20:
                f.write(f'\n*... y {sku_errors - 20} errores más*\n')

            f.write('\n')

        f.write('---\n')
        f.write('*Generado automáticamente por fix_category_errors.py*\n')

    print(f"\n📄 Reporte markdown generado: {report_file}")
    return report_file


def generate_json_log(log_data, output_file):
    """
    Genera log detallado en formato JSON.

    Args:
        log_data: Dict con información de procesamiento
        output_file: Nombre del archivo JSON de salida (para nombres de log)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = output_file.replace('.json', f'_{timestamp}_category_fix_log.json')

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=4, ensure_ascii=False)

    print(f"📄 Log JSON generado: {log_file}")
    return log_file


def main():
    parser = argparse.ArgumentParser(
        description='Corrige errores de categorías mediante cross-referencia entre JSONs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    # Uso básico
    python3 fix_category_errors.py error_log.md input1.json input2.json output.json

    # Con indentación personalizada
    python3 fix_category_errors.py error_log.md input1.json input2.json output.json --indent 2
        """
    )

    parser.add_argument('error_report_md',
                       help='Archivo markdown con Categoría problemáticos')
    parser.add_argument('input_1_json',
                       help='JSON principal con Categoría y SKU')
    parser.add_argument('input_2_json',
                       help='JSON de referencia con SKU y Categoría')
    parser.add_argument('output_json',
                       help='Archivo JSON de salida con categorías corregidas')
    parser.add_argument('--indent', type=int, default=4,
                       help='Nivel de indentación JSON (default: 4)')

    args = parser.parse_args()

    print('🚀 Iniciando corrección de categorías...\n')

    # 1. Parsear markdown para extraer Categoría problemáticos
    print(f"🔍 Parseando archivo markdown: {args.error_report_md}")
    problematic_paths = parse_markdown_errors(args.error_report_md)

    if not problematic_paths:
        print("✅ No se encontraron Categoría problemáticos en el markdown")
        print("   El proceso finalizó exitosamente sin cambios necesarios")
        sys.exit(0)

    print(f"   Encontrados: {len(problematic_paths)} Categoría únicos problemáticos\n")

    # 2. Cargar input-1.json (datos principales)
    print(f"📖 Cargando {args.input_1_json}...")
    input1_data = load_json_file(args.input_1_json, 'input-1.json')
    print(f"   Registros cargados: {len(input1_data)}\n")

    # 3. Cargar input-2.json y construir índice SKU
    print(f"📖 Cargando {args.input_2_json}...")
    input2_data = load_json_file(args.input_2_json, 'input-2.json')
    print(f"   Registros cargados: {len(input2_data)}")

    print("🔨 Construyendo índice SKU...")
    input2_index = build_sku_index(input2_data, 'SKU')
    print(f"   SKUs únicos indexados: {len(input2_index)}\n")

    # 4. Procesar correcciones
    log_data = process_category_fixes(problematic_paths, input1_data, input2_index)

    # 5. Aplicar reemplazos
    print(f"\n🔄 Aplicando {len(log_data['replacement_map'])} reemplazos...")
    modified_data, records_modified = apply_category_fixes(
        input1_data,
        log_data['replacement_map']
    )
    print(f"   Registros modificados: {records_modified}")

    # 6. Guardar output.json
    print(f"\n💾 Guardando archivo de salida: {args.output_json}")
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(modified_data, f, indent=args.indent, ensure_ascii=False)
    print("   ✅ Archivo guardado exitosamente")

    # 7. Preparar log completo
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    successful = len(log_data['successful_fixes'])
    total_processed = len(problematic_paths)
    success_rate = (successful / total_processed * 100) if total_processed > 0 else 0

    log_data.update({
        'timestamp': timestamp,
        'input_files': {
            'markdown': args.error_report_md,
            'input_1': args.input_1_json,
            'input_2': args.input_2_json
        },
        'total_paths_processed': total_processed,
        'total_records_modified': records_modified,
        'success_rate': success_rate
    })

    # 8. Generar reportes
    print("\n📊 Generando reportes...")
    generate_markdown_report(log_data, args.output_json)
    generate_json_log(log_data, args.output_json)

    # 9. Resumen en consola
    print('\n' + '='*80)
    print('🎉 PROCESO COMPLETADO')
    print('='*80)
    print(f"📊 Total procesado: {total_processed} Categoría")
    print(f"✅ Exitosos: {successful} ({success_rate:.1f}%)")
    print(f"❌ Errores (Categoría no encontrado): {len(log_data['path_not_found_errors'])}")
    print(f"❌ Errores (SKU no encontrado): {len(log_data['sku_not_found_errors'])}")
    print(f"📝 Registros modificados: {records_modified}")
    print('='*80 + '\n')


if __name__ == '__main__':
    main()
