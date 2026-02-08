#!/usr/bin/env python3
"""
vtex_brandid_matcher.py

Script de integración VTEX para mapear BrandId de productos usando la API de marcas VTEX.
Cuarto paso del flujo de transformación de datos.

Funcionalidad:
- Conecta con la API de VTEX para obtener todas las marcas del catálogo
- Carga archivo de marcas local (marcas.json) con mapeo SKU → Marca
- Busca BrandId para cada producto basado en RefId → SKU → Marca → BrandId
- Normaliza nombres de marcas (elimina acentos, ñ→n) para matching robusto
- Soporta tanto campo "Marca" como "MARCA" en el archivo de marcas
- Soporta tanto campo "RefId" como "SKU" en el archivo de productos
- Asigna BrandId correspondiente a cada producto en el dataset
- Exporta productos sin BrandId encontrado a CSV para revisión manual
- Genera reporte detallado en Markdown con estadísticas y recomendaciones
- Muestra logs detallados en terminal durante el procesamiento

Flujo de Mapeo:
1. RefId/SKU del producto → busca en marcas.json
2. SKU encontrado → obtiene nombre de Marca
3. Nombre de Marca → normaliza (elimina acentos, ñ→n, lowercase)
4. Marca normalizada → busca BrandId en catálogo VTEX
5. BrandId encontrado → asigna al producto, sino → BrandId = null

Ejecución:
    # Mapeo básico (usa configuración del .env automáticamente)
    python3 vtex_brandid_matcher.py marcas.json data.json

    # Con archivos de salida personalizados
    python3 vtex_brandid_matcher.py marcas.json data.json \
        --output_json final.json \
        --output_csv faltantes.csv \
        --output_report reporte.md

    # Con configuración personalizada (sobrescribe .env)
    python3 vtex_brandid_matcher.py marcas.json data.json --account ACCOUNT_NAME --env vtexcommercestable

Ejemplo:
    python3 vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json productos.json

Archivos de salida generados:
    - data_brandid.json: Todos los productos con campo BrandId asignado
    - no_brandid_found.csv: Productos sin BrandId para revisión manual
    - brand_matching_report.md: Reporte detallado con estadísticas y recomendaciones

Archivos requeridos:
- .env en la raíz del proyecto con X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME y VTEX_ENVIRONMENT
- marcas.json: archivo con mapeo de SKU a nombre de marca
"""
import json
import csv
import requests
import argparse
import os
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables desde .env en la raíz del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)


def normalize(text):
    """
    Normaliza texto para comparación: elimina acentos, ñ→n, convierte a minúsculas.

    Ejemplos:
    - "Café Del Campo" → "cafe del campo"
    - "Niños" → "ninos"
    - "ILUMAX" → "ilumax"
    """
    if not text:
        return ''

    # Normalización NFD: descompone caracteres acentuados (á → a + ´)
    nfd = unicodedata.normalize('NFD', text)

    # Eliminar marcas diacríticas (acentos, diéresis, etc.)
    without_accents = ''.join([c for c in nfd if unicodedata.category(c) != 'Mn'])

    # Reemplazar explícitamente ñ y Ñ por n
    without_n = without_accents.replace('ñ', 'n').replace('Ñ', 'n')

    # Convertir a minúsculas y eliminar espacios al inicio/final
    normalized = without_n.lower().strip()

    return normalized


def find_similar_brands(target, brand_list, max_results=3):
    """Encuentra marcas similares que empiezan con las mismas letras o contienen el target"""
    if not target or len(target) < 3:
        return ['(target muy corto)']

    similar = [b for b in brand_list if target[:3] in b or b[:3] in target]
    return similar[:max_results] if similar else ['(ninguna similar)']

# Argument parser
parser = argparse.ArgumentParser(description='Mapear BrandId desde VTEX a data.json usando marcas.json')
parser.add_argument('marcas_file', help='Archivo JSON con las marcas (marcas.json)')
parser.add_argument('data_file', help='Archivo JSON con los datos (data.json)')
parser.add_argument('--output_json', default='data_brandid.json', help='Archivo de salida JSON con identación de 4 espacios')
parser.add_argument('--output_csv', default='no_brandid_found.csv', help='Archivo CSV de elementos sin BrandId')
parser.add_argument('--output_report', default='brand_matching_report.md', help='Archivo de reporte en formato Markdown')
parser.add_argument('--account', help='Nombre de cuenta de VTEX (opcional, usa VTEX_ACCOUNT_NAME del .env)')
parser.add_argument('--env', help='Ambiente de VTEX (opcional, usa VTEX_ENVIRONMENT del .env)')
args = parser.parse_args()

# Leer credenciales y configuración VTEX desde el .env
app_key = os.getenv('X-VTEX-API-AppKey')
app_token = os.getenv('X-VTEX-API-AppToken')
vtex_account_name = os.getenv('VTEX_ACCOUNT_NAME')
vtex_environment = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable')

if not app_key or not app_token:
    raise ValueError("X-VTEX-API-AppKey o X-VTEX-API-AppToken no definidos en .env")

if not vtex_account_name:
    raise ValueError("VTEX_ACCOUNT_NAME no definido en .env")

# Usar valores del .env o argumentos como fallback
account_name = args.account or vtex_account_name
environment = args.env or vtex_environment

# Headers para la autenticación
headers = {
    'Content-Type': 'application/json',
    'X-VTEX-API-AppKey': app_key,
    'X-VTEX-API-AppToken': app_token
}

# Endpoint VTEX
brand_url = f"https://{account_name}.{environment}.com.br/api/catalog_system/pvt/brand/list"

# Obtener marcas de VTEX
print(f"\n🔄 Conectando con VTEX para obtener catálogo de marcas...")
response = requests.get(brand_url, headers=headers)
response.raise_for_status()
vtex_brands = response.json()

# Mapeo nombre normalizado -> id
brand_name_to_id = {normalize(brand['name']): brand['id'] for brand in vtex_brands}

print(f"✓ Cargadas {len(vtex_brands)} marcas desde VTEX API")
print(f"  Ejemplos (normalizados): {list(brand_name_to_id.keys())[:10]}")

# Cargar archivos locales
print(f"\n📂 Cargando archivos locales...")
with open(args.marcas_file, 'r', encoding='utf-8') as f:
    marcas = json.load(f)

with open(args.data_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Crear mapa SKU -> Marca normalizada (soporta tanto "Marca" como "MARCA")
sku_to_marca = {
    item['SKU']: normalize(item.get('Marca', item.get('MARCA', '')))
    for item in marcas
    if 'SKU' in item and (item.get('Marca') or item.get('MARCA'))
}

# Crear mapa SKU -> Marca original (para CSV export)
sku_to_marca_original = {
    item['SKU']: item.get('Marca', item.get('MARCA', '')).strip()
    for item in marcas
    if 'SKU' in item and (item.get('Marca') or item.get('MARCA'))
}

print(f"✓ Cargados {len(sku_to_marca)} mapeos SKU→Marca desde marcas.json")
print(f"  Ejemplos: {list(sku_to_marca.items())[:5]}")
print(f"\n🔄 Procesando {len(data)} productos...")

# Salida y contadores
no_brandid = []
failed_matches = []  # Track primeros 20 fallos para debug
successful_matches = []  # Track primeros 20 éxitos para reporte

# Contadores
total_productos = len(data)
skus_encontrados = 0
skus_no_encontrados = 0
marcas_matched = 0
marcas_no_matched = 0

# Timestamp para el reporte
process_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

for idx, item in enumerate(data, 1):
    # Soportar tanto RefId como SKU (RefId es preferido si existe)
    ref_id = item.get('RefId') or item.get('SKU')
    marca_nombre = sku_to_marca.get(ref_id)  # Normalizada
    marca_original = sku_to_marca_original.get(ref_id)  # Original para CSV

    # Progress indicator cada 500 productos
    if idx % 500 == 0:
        print(f"  Procesados {idx}/{total_productos} productos...")

    if marca_nombre:
        skus_encontrados += 1
        brand_id = brand_name_to_id.get(marca_nombre)
        item['BrandId'] = brand_id if brand_id is not None else None

        if brand_id is None:
            marcas_no_matched += 1
            # Agregar marca original para CSV
            item_with_marca = item.copy()
            item_with_marca['Marca'] = marca_original
            no_brandid.append(item_with_marca)

            # Track primeros 20 fallos para análisis
            if len(failed_matches) < 20:
                failed_matches.append({
                    'RefId': ref_id,
                    'Marca_Original': marca_original,
                    'Marca_Normalized': marca_nombre,
                    'VTEX_Similar': find_similar_brands(marca_nombre, brand_name_to_id.keys())
                })
        else:
            marcas_matched += 1
            # Track primeros 20 éxitos para reporte
            if len(successful_matches) < 20:
                successful_matches.append({
                    'RefId': ref_id,
                    'Marca_Original': marca_original,
                    'Marca_Normalized': marca_nombre,
                    'BrandId': brand_id
                })
    else:
        skus_no_encontrados += 1
        item['BrandId'] = None
        # Agregar indicador de marca no encontrada para CSV
        item_with_marca = item.copy()
        item_with_marca['Marca'] = 'NO_ENCONTRADA'
        no_brandid.append(item_with_marca)

# Imprimir resumen de estadísticas
print(f"\n{'='*60}")
print(f"📊 RESUMEN DE PROCESAMIENTO")
print(f"{'='*60}")
print(f"  Productos procesados: {total_productos}")
print(f"  SKUs encontrados en marcas.json: {skus_encontrados} ({skus_encontrados/total_productos*100:.1f}%)")
print(f"  SKUs NO encontrados: {skus_no_encontrados} ({skus_no_encontrados/total_productos*100:.1f}%)")
print(f"  Marcas matched con VTEX: {marcas_matched} ({marcas_matched/total_productos*100:.1f}%)")
print(f"  Marcas NO matched con VTEX: {marcas_no_matched} ({marcas_no_matched/total_productos*100:.1f}%)")
print(f"  Productos sin BrandId (total): {len(no_brandid)} ({len(no_brandid)/total_productos*100:.1f}%)")
print(f"{'='*60}\n")

# Mostrar primeros fallos para análisis
if failed_matches:
    print(f"⚠️  PRIMEROS {len(failed_matches)} CASOS DE MARCAS NO ENCONTRADAS EN VTEX:")
    print(f"{'-'*60}")
    for fail in failed_matches:
        print(f"  RefId: {fail['RefId']}")
        print(f"    Marca original: '{fail['Marca_Original']}'")
        print(f"    Marca normalizada: '{fail['Marca_Normalized']}'")
        print(f"    Marcas VTEX similares: {fail['VTEX_Similar'][:3]}")
        print()

# Guardar archivo de salida con identación 4 espacios
print(f"💾 Guardando archivos de salida...")
with open(args.output_json, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

# Guardar CSV de los que no se encontró BrandId
if no_brandid:
    with open(args.output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=no_brandid[0].keys())
        writer.writeheader()
        writer.writerows(no_brandid)

# Generar reporte Markdown
with open(args.output_report, 'w', encoding='utf-8') as f:
    f.write(f"# Reporte de Mapeo de BrandId - VTEX\n\n")
    f.write(f"**Generado:** {process_timestamp}\n\n")
    f.write(f"---\n\n")

    # Resumen ejecutivo
    f.write(f"## 📊 Resumen Ejecutivo\n\n")
    f.write(f"| Métrica | Cantidad | Porcentaje |\n")
    f.write(f"|---------|----------|------------|\n")
    f.write(f"| **Total de productos procesados** | {total_productos:,} | 100.0% |\n")
    f.write(f"| ✅ SKUs encontrados en marcas.json | {skus_encontrados:,} | {skus_encontrados/total_productos*100:.1f}% |\n")
    f.write(f"| ❌ SKUs NO encontrados en marcas.json | {skus_no_encontrados:,} | {skus_no_encontrados/total_productos*100:.1f}% |\n")
    f.write(f"| ✅ Marcas matched con VTEX | {marcas_matched:,} | {marcas_matched/total_productos*100:.1f}% |\n")
    f.write(f"| ⚠️  Marcas NO matched con VTEX | {marcas_no_matched:,} | {marcas_no_matched/total_productos*100:.1f}% |\n")
    f.write(f"| **Productos sin BrandId (total)** | {len(no_brandid):,} | {len(no_brandid)/total_productos*100:.1f}% |\n\n")

    # Configuración
    f.write(f"## ⚙️ Configuración\n\n")
    f.write(f"- **Cuenta VTEX:** {account_name}\n")
    f.write(f"- **Ambiente:** {environment}\n")
    f.write(f"- **Archivo marcas:** {args.marcas_file}\n")
    f.write(f"- **Archivo datos:** {args.data_file}\n")
    f.write(f"- **Total marcas en VTEX:** {len(vtex_brands):,}\n")
    f.write(f"- **Total mapeos SKU→Marca:** {len(sku_to_marca):,}\n\n")

    # Ejemplos de matches exitosos
    if successful_matches:
        f.write(f"## ✅ Ejemplos de Matches Exitosos (primeros {len(successful_matches)})\n\n")
        f.write(f"| RefId/SKU | Marca Original | Marca Normalizada | BrandId |\n")
        f.write(f"|-----------|----------------|-------------------|----------|\n")
        for match in successful_matches:
            f.write(f"| {match['RefId']} | {match['Marca_Original']} | `{match['Marca_Normalized']}` | {match['BrandId']} |\n")
        f.write(f"\n")

    # Análisis de fallos
    if failed_matches:
        f.write(f"## ⚠️ Análisis de Marcas No Encontradas en VTEX (primeros {len(failed_matches)})\n\n")
        f.write(f"Estas marcas existen en `marcas.json` pero NO se encontraron en el catálogo VTEX.\n\n")
        for idx, fail in enumerate(failed_matches, 1):
            f.write(f"### {idx}. RefId/SKU: {fail['RefId']}\n\n")
            f.write(f"- **Marca original:** `{fail['Marca_Original']}`\n")
            f.write(f"- **Marca normalizada:** `{fail['Marca_Normalized']}`\n")
            f.write(f"- **Marcas VTEX similares:** {', '.join(f'`{b}`' for b in fail['VTEX_Similar'][:3])}\n\n")

    # SKUs no encontrados
    if skus_no_encontrados > 0:
        f.write(f"## 📋 SKUs No Encontrados en marcas.json\n\n")
        f.write(f"**Total:** {skus_no_encontrados:,} productos ({skus_no_encontrados/total_productos*100:.1f}%)\n\n")
        f.write(f"Estos productos tienen un SKU/RefId que NO aparece en el archivo `marcas.json`.\n")
        f.write(f"Para resolverlo, agrega estos SKUs al archivo de marcas con su respectiva marca.\n\n")

    # Recomendaciones
    f.write(f"## 💡 Recomendaciones\n\n")

    if marcas_no_matched > 0:
        f.write(f"### Marcas no encontradas en VTEX ({marcas_no_matched:,})\n\n")
        f.write(f"Estas marcas existen en tu archivo `marcas.json` pero no están registradas en el catálogo VTEX.\n\n")
        f.write(f"**Acciones sugeridas:**\n")
        f.write(f"1. Revisar la sección \"Análisis de Marcas No Encontradas\" arriba\n")
        f.write(f"2. Verificar si hay errores de tipeo en el archivo `marcas.json`\n")
        f.write(f"3. Crear las marcas faltantes en VTEX antes de subir productos\n")
        f.write(f"4. Usar las \"Marcas VTEX similares\" sugeridas si es apropiado\n\n")

    if skus_no_encontrados > 0:
        f.write(f"### SKUs no encontrados en marcas.json ({skus_no_encontrados:,})\n\n")
        f.write(f"**Acciones sugeridas:**\n")
        f.write(f"1. Revisar el archivo CSV de salida `{args.output_csv}` (filtrar por `Marca = NO_ENCONTRADA`)\n")
        f.write(f"2. Agregar los SKUs faltantes al archivo `marcas.json` con sus marcas correspondientes\n")
        f.write(f"3. Re-ejecutar este script\n\n")

    if marcas_matched == total_productos:
        f.write(f"### ✨ Excelente!\n\n")
        f.write(f"Todos los productos tienen BrandId asignado correctamente. Puedes proceder con la creación de productos en VTEX.\n\n")

    # Archivos generados
    f.write(f"## 📁 Archivos Generados\n\n")
    f.write(f"1. **{args.output_json}** - Todos los productos con campo `BrandId` asignado\n")
    f.write(f"2. **{args.output_csv}** - {len(no_brandid):,} productos sin BrandId (para revisión manual)\n")
    f.write(f"3. **{args.output_report}** - Este reporte\n\n")

    # Footer
    f.write(f"---\n\n")
    f.write(f"*Reporte generado automáticamente por `vtex_brandid_matcher.py`*\n")

print(f"✅ Proceso completado exitosamente!")
print(f"   - JSON generado: {args.output_json}")
print(f"   - CSV sin BrandId: {args.output_csv} ({len(no_brandid)} registros)")
print(f"   - Reporte Markdown: {args.output_report}\n")
