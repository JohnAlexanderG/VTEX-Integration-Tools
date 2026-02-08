#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_vtex_report.py

Script de análisis y reporte que evalúa la preparación de productos para 
catálogo VTEX. Quinto paso del flujo de transformación de datos.

Funcionalidad:
- Analiza productos procesados para determinar su preparación para VTEX
- Clasifica productos en 3 categorías basado en campos requeridos
- Genera múltiples archivos de salida para diferentes casos de uso
- Crea reporte markdown con resumen estadístico y archivos generados

Clasificación de Productos:
1. **Listos para crear**: Tienen DepartmentId, CategoryId y BrandId (todos no-null)
2. **Requieren crear categoría**: Falta CategoryId pero tienen campo "Categoría" 
3. **No se pueden crear**: Falta BrandId (campo crítico requerido por VTEX)

Archivos Generados:
- Reporte markdown principal con estadísticas
- JSON de productos listos para crear
- JSON de productos que requieren crear categoría  
- JSON y CSV de productos que no se pueden crear

Ejecución:
    # Generar reporte básico
    python3 generate_vtex_report.py input.json -o reporte.md
    
    # Con archivo de salida personalizado
    python3 generate_vtex_report.py productos_final.json -o analisis_productos.md

Ejemplo:
    python3 generate_vtex_report/generate_vtex_report.py productos_final.json -o reporte_vtex.md
"""
import json
import argparse
import sys
import csv
import os

def main():
    parser = argparse.ArgumentParser(
        description='Genera un reporte Markdown para productos VTEX basado en DepartmentId, CategoryId y BrandId.'
    )
    parser.add_argument('input', help='Ruta al archivo JSON de entrada')
    parser.add_argument('-o', '--output', default='report.md', help='Ruta al archivo Markdown de salida')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("🚀 INICIANDO GENERACIÓN DE REPORTE VTEX")
    print("="*70)
    print(f"📂 Archivo de entrada: {args.input}")
    print(f"📄 Archivo de salida: {args.output}")
    print()

    try:
        print("📖 Leyendo archivo JSON de entrada...", end=" ")
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("✓ Completado")
    except Exception as e:
        print(f"✗ Error al leer el archivo JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Asumimos que el JSON es una lista de items
    items = data if isinstance(data, list) else data.get('items', [])

    total = len(items)
    print(f"📊 Total de productos encontrados: {total}")
    print()

    creatable = []
    category_creatable = []  # Para JSON
    not_creatable = []  # Para CSV

    print("🔍 Clasificando productos...")
    print("   Categorías:")
    print("   ✅ Listos para crear (DepartmentId + CategoryId + BrandId)")
    print("   🔧 Requieren crear categoría (sin CategoryId pero con nombre de categoría)")
    print("   ❌ No se pueden crear (sin BrandId)")
    print()

    for idx, item in enumerate(items, 1):
        # Mostrar progreso cada 100 productos
        if idx % 100 == 0 or idx == total:
            print(f"   Procesando... {idx}/{total} productos ({(idx/total)*100:.1f}%)")

        dept_id = item.get('DepartmentId')
        cat_id = item.get('CategoryId')
        brand_id = item.get('BrandId')
        categoria_field = item.get('Categoría') or item.get('Categoria')

        # Lógica de clasificación para creación en VTEX
        if dept_id is not None and cat_id is not None and brand_id is not None:
            # Productos completamente preparados para creación
            creatable.append(item)
        elif brand_id is None:
            # Si falta BrandId, no se puede crear el producto (regla crítica)
            not_creatable.append(item)
        elif cat_id is None and categoria_field:
            # Si falta CategoryId pero tenemos nombre de categoría, podemos crear la categoría
            category_creatable.append(item)
        else:
            # Otros casos donde faltan campos requeridos
            not_creatable.append(item)

    print()
    print("📋 RESUMEN DE CLASIFICACIÓN:")
    print(f"   ✅ Listos para crear: {len(creatable)} productos ({(len(creatable)/total)*100:.1f}%)")
    print(f"   🔧 Requieren crear categoría: {len(category_creatable)} productos ({(len(category_creatable)/total)*100:.1f}%)")
    print(f"   ❌ No se pueden crear: {len(not_creatable)} productos ({(len(not_creatable)/total)*100:.1f}%)")
    print()

    print("-"*70)
    print("💾 GENERANDO ARCHIVOS DE SALIDA")
    print("-"*70)

    # Generar archivo JSON para productos listos para crear
    if creatable:
        json_creatable = args.output.replace('.md', '_listos_para_crear.json')
        try:
            print(f"📝 Generando JSON de productos listos para crear...", end=" ")
            with open(json_creatable, 'w', encoding='utf-8') as json_file:
                json.dump(creatable, json_file, ensure_ascii=False, indent=2)
            print(f"✓ {os.path.basename(json_creatable)} ({len(creatable)} productos)")
        except Exception as e:
            print(f"✗ Error al escribir archivo JSON: {e}", file=sys.stderr)

    # Generar archivo JSON para productos con categoría a crear
    if category_creatable:
        json_filename = args.output.replace('.md', '_categoria_a_crear.json')
        try:
            print(f"📝 Generando JSON de productos con categoría a crear...", end=" ")
            with open(json_filename, 'w', encoding='utf-8') as json_file:
                json.dump(category_creatable, json_file, ensure_ascii=False, indent=2)
            print(f"✓ {os.path.basename(json_filename)} ({len(category_creatable)} productos)")
        except Exception as e:
            print(f"✗ Error al escribir archivo JSON: {e}", file=sys.stderr)

    # Generar archivos para productos que no se pueden crear
    if not_creatable:
        # Archivo JSON
        json_not_creatable = args.output.replace('.md', '_no_se_pueden_crear.json')
        try:
            print(f"📝 Generando JSON de productos no creables...", end=" ")
            with open(json_not_creatable, 'w', encoding='utf-8') as json_file:
                json.dump(not_creatable, json_file, ensure_ascii=False, indent=2)
            print(f"✓ {os.path.basename(json_not_creatable)} ({len(not_creatable)} productos)")
        except Exception as e:
            print(f"✗ Error al escribir archivo JSON: {e}", file=sys.stderr)

        # Archivo CSV
        csv_filename = args.output.replace('.md', '_no_se_pueden_crear.csv')
        try:
            print(f"📝 Generando CSV de productos no creables...", end=" ")
            # Obtener todas las claves únicas de todos los productos
            all_keys = set()
            for item in not_creatable:
                all_keys.update(item.keys())

            with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(not_creatable)
            print(f"✓ {os.path.basename(csv_filename)} ({len(not_creatable)} productos)")
        except Exception as e:
            print(f"✗ Error al escribir archivo CSV: {e}", file=sys.stderr)

    # Generar reporte Markdown (simplificado)
    try:
        print(f"📝 Generando reporte Markdown...", end=" ")
        with open(args.output, 'w', encoding='utf-8') as md:
            md.write('# Reporte de Creación de Productos VTEX\n\n')
            md.write(f'- **Total de productos procesados:** {total}\n')
            md.write(f'- **Productos listos para crear:** {len(creatable)}\n')
            md.write(f'- **Productos que requieren crear categoría:** {len(category_creatable)}\n')
            md.write(f'- **Productos que no se pueden crear:** {len(not_creatable)}\n\n')

            md.write('## Archivos Generados\n\n')
            if creatable:
                json_creatable = args.output.replace('.md', '_listos_para_crear.json')
                md.write(f'- **Productos listos para crear:** `{os.path.basename(json_creatable)}` ({len(creatable)} productos)\n')
            if category_creatable:
                json_filename = args.output.replace('.md', '_categoria_a_crear.json')
                md.write(f'- **Productos con categoría a crear:** `{os.path.basename(json_filename)}` ({len(category_creatable)} productos)\n')
            if not_creatable:
                json_not_creatable = args.output.replace('.md', '_no_se_pueden_crear.json')
                csv_filename = args.output.replace('.md', '_no_se_pueden_crear.csv')
                md.write(f'- **Productos que no se pueden crear (JSON):** `{os.path.basename(json_not_creatable)}` ({len(not_creatable)} productos)\n')
                md.write(f'- **Productos que no se pueden crear (CSV):** `{os.path.basename(csv_filename)}` ({len(not_creatable)} productos)\n')

            md.write('\n---\n\n')
            md.write('*Para ver los detalles completos, consulta los archivos JSON y CSV generados.*\n')

        print(f"✓ {os.path.basename(args.output)}")
    except Exception as e:
        print(f"✗ Error al escribir el archivo Markdown: {e}", file=sys.stderr)
        sys.exit(1)

    print()
    print("="*70)
    print("✨ PROCESO COMPLETADO EXITOSAMENTE")
    print("="*70)
    print(f"📊 Total procesados: {total}")
    print(f"✅ Listos para crear: {len(creatable)} ({(len(creatable)/total)*100:.1f}%)")
    print(f"🔧 Requieren crear categoría: {len(category_creatable)} ({(len(category_creatable)/total)*100:.1f}%)")
    print(f"❌ No se pueden crear: {len(not_creatable)} ({(len(not_creatable)/total)*100:.1f}%)")
    print(f"\n📄 Reporte principal: {args.output}")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
