#!/usr/bin/env python3
"""
refid_to_skuid_mapper.py

Script para mapear RefId a SkuId utilizando un archivo de mapeo local.
Procesa archivos JSON reemplazando valores de RefId por sus correspondientes SkuId.

Funcionalidad:
- Lee archivo de mapeo JSON con campos "Id" y "RefId"
- Lee archivo de datos JSON con RefId como clave o campo
- Compara y mapea RefId a SkuId usando el archivo de mapeo
- Reemplaza RefId por SkuId en la estructura del archivo
- Exporta archivo de salida con los SkuId mapeados
- Genera reportes de éxitos y fallos en múltiples formatos

Uso:
    python3 refid_to_skuid_mapper.py <mapping_json> <input_json> <output_json> [options]

Ejemplo:
    python3 refid_to_skuid_mapper.py mapping.json products.json products_with_skuid.json

Opciones:
    --key-field NAME    Campo que contiene RefId (default: detecta automáticamente)
    --report PREFIX     Prefijo para archivos de reporte

Estructura del archivo de mapeo:
[
    { "Id": "5380", "RefId": "210794" },
    { "Id": "5381", "RefId": "210795" },
    ...
]

Estructura de entrada esperada (archivo de datos):
{
    "210794": { datos... },
    "210795": { datos... }
}

O:
[
    { "RefId": "210794", "otros_datos": ... },
    { "RefId": "210795", "otros_datos": ... }
]

Estructura de salida:
{
    "5380": { datos... },
    "5381": { datos... }
}

O:
[
    { "SkuId": "5380", "otros_datos": ... },
    { "SkuId": "5381", "otros_datos": ... }
]
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime


def load_input_file(file_path, file_description="archivo"):
    """
    Carga el archivo JSON de entrada
    
    Args:
        file_path (str): Ruta al archivo JSON de entrada
        file_description (str): Descripción del archivo para mensajes
        
    Returns:
        dict/list: Datos cargados del archivo
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {file_description} ({file_path}): {e}")
        sys.exit(1)


def load_mapping_file(mapping_file):
    """
    Carga el archivo de mapeo con estructura [{"Id": "...", "RefId": "..."}]
    
    Args:
        mapping_file (str): Ruta al archivo de mapeo
        
    Returns:
        dict: Diccionario {RefId: SkuId}
    """
    print(f"📂 Cargando archivo de mapeo: {mapping_file}")
    mapping_data = load_input_file(mapping_file, "archivo de mapeo")
    
    if not isinstance(mapping_data, list):
        print("❌ El archivo de mapeo debe ser una lista de objetos")
        sys.exit(1)
    
    # Construir diccionario de mapeo RefId -> SkuId
    refid_to_skuid = {}
    invalid_entries = 0
    
    for i, entry in enumerate(mapping_data):
        if not isinstance(entry, dict):
            print(f"⚠️  Entrada {i} no es un objeto, saltando...")
            invalid_entries += 1
            continue
            
        ref_id = entry.get('RefId')
        sku_id = entry.get('Id')
        
        if not ref_id or not sku_id:
            print(f"⚠️  Entrada {i} falta RefId o Id: {entry}")
            invalid_entries += 1
            continue
        
        # Convertir a string para consistencia
        refid_to_skuid[str(ref_id)] = str(sku_id)
    
    valid_mappings = len(refid_to_skuid)
    print(f"✅ Mapeo cargado: {valid_mappings} entradas válidas")
    if invalid_entries > 0:
        print(f"⚠️  {invalid_entries} entradas inválidas saltadas")
    
    return refid_to_skuid


def detect_structure_and_refids(data):
    """
    Detecta la estructura del archivo y extrae los RefId
    
    Args:
        data (dict/list): Datos del archivo JSON
        
    Returns:
        tuple: (structure_type, refids_list, key_field)
    """
    refids = []
    structure_type = None
    key_field = None
    
    if isinstance(data, dict):
        # Estructura de diccionario con RefId como clave
        structure_type = "dict_key"
        refids = list(data.keys())
        print(f"📋 Estructura detectada: Diccionario con RefId como clave")
        print(f"🔍 {len(refids)} RefIds encontrados como claves")
        
    elif isinstance(data, list):
        # Estructura de lista con RefId como campo
        structure_type = "list_field"
        # Detectar campo que contiene RefId
        if data and isinstance(data[0], dict):
            # Buscar campos que podrían contener RefId
            possible_fields = ['RefId', 'refId', 'ref_id', 'refid']
            for field in possible_fields:
                if field in data[0]:
                    key_field = field
                    break
            
            if key_field:
                refids = [item.get(key_field) for item in data if item.get(key_field)]
                print(f"📋 Estructura detectada: Lista con campo '{key_field}'")
                print(f"🔍 {len(refids)} RefIds encontrados en campo '{key_field}'")
            else:
                print("❌ No se pudo detectar el campo RefId en la estructura de lista")
                sys.exit(1)
    else:
        print("❌ Estructura de archivo no soportada")
        sys.exit(1)
    
    return structure_type, refids, key_field


def map_refids_using_mapping(refids, refid_to_skuid_mapping):
    """
    Mapea una lista de RefIds a SkuIds usando el diccionario de mapeo
    
    Args:
        refids (list): Lista de RefIds a mapear
        refid_to_skuid_mapping (dict): Diccionario de mapeo RefId -> SkuId
        
    Returns:
        tuple: (successful_mappings, failed_mappings)
    """
    print(f"🚀 Iniciando mapeo de RefId a SkuId:")
    print(f"   📦 Total RefIds: {len(refids)}")
    print(f"   📋 Mapeos disponibles: {len(refid_to_skuid_mapping)}")
    print("-" * 60)
    
    successful_mappings = {}
    failed_mappings = []
    
    for i, refid in enumerate(refids, 1):
        refid_str = str(refid)  # Convertir a string para comparación
        print(f"🔍 [{i}/{len(refids)}] Buscando RefId: {refid_str}")
        
        if refid_str in refid_to_skuid_mapping:
            skuid = refid_to_skuid_mapping[refid_str]
            successful_mappings[refid] = skuid
            print(f"   ✅ Mapeado: RefId {refid_str} → SkuId {skuid}")
        else:
            failed_mappings.append({
                'refid': refid,
                'error': f"RefId {refid_str} not found in mapping file"
            })
            print(f"   ❌ RefId {refid_str} no encontrado en archivo de mapeo")
        
        # Mostrar progreso cada 10 elementos
        if i % 10 == 0:
            progress_pct = (i / len(refids)) * 100
            print(f"📊 Progreso: {i}/{len(refids)} ({progress_pct:.1f}%) - ✅ {len(successful_mappings)} exitosos, ❌ {len(failed_mappings)} fallos")
    
    print("\n" + "=" * 60)
    print(f"🏁 MAPEO COMPLETADO")
    print(f"   ✅ Exitosos: {len(successful_mappings)}")
    print(f"   ❌ Fallos: {len(failed_mappings)}")
    print(f"   📈 Tasa de éxito: {(len(successful_mappings)/len(refids)*100):.2f}%")
    print("=" * 60)
    
    return successful_mappings, failed_mappings


def transform_data_structure(data, structure_type, key_field, mappings):
    """
    Transforma la estructura de datos reemplazando RefId por SkuId
    
    Args:
        data (dict/list): Datos originales
        structure_type (str): Tipo de estructura detectada
        key_field (str): Campo que contiene RefId (para listas)
        mappings (dict): Mapeo RefId → SkuId
        
    Returns:
        dict/list: Datos transformados
    """
    transformed_data = None
    
    if structure_type == "dict_key":
        # Transformar diccionario: claves RefId → SkuId
        transformed_data = {}
        for refid, value in data.items():
            if refid in mappings:
                skuid = mappings[refid]
                transformed_data[skuid] = value
            else:
                # Mantener RefId original si no se pudo mapear
                transformed_data[refid] = value
                
    elif structure_type == "list_field":
        # Transformar lista: campo RefId → SkuId
        transformed_data = []
        for item in data:
            if isinstance(item, dict):
                new_item = item.copy()
                refid = item.get(key_field)
                if refid and refid in mappings:
                    skuid = mappings[refid]
                    # Reemplazar campo RefId por SkuId
                    new_item.pop(key_field, None)
                    new_item['SkuId'] = skuid
                transformed_data.append(new_item)
            else:
                transformed_data.append(item)
    
    return transformed_data


def write_output_files(transformed_data, output_file, failed_mappings, report_prefix=None):
    """
    Escribe archivos de salida: datos transformados, fallos y reporte
    
    Args:
        transformed_data (dict/list): Datos transformados
        output_file (str): Archivo de salida principal
        failed_mappings (list): Lista de mapeos fallidos
        report_prefix (str): Prefijo para archivos de reporte
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Archivo principal de salida
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(transformed_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Archivo principal guardado: {output_file}")
    except Exception as e:
        print(f"❌ Error escribiendo archivo principal: {e}")
        return
    
    # Archivo de fallos (CSV)
    if failed_mappings:
        prefix = report_prefix or output_file.replace('.json', '')
        failed_csv = f"{prefix}_failed_mappings_{timestamp}.csv"
        
        try:
            with open(failed_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['refid', 'error'])
                writer.writeheader()
                for failure in failed_mappings:
                    writer.writerow(failure)
            print(f"📄 Fallos exportados: {failed_csv}")
        except Exception as e:
            print(f"❌ Error escribiendo archivo de fallos: {e}")
    
    # Archivo de fallos (JSON)
    if failed_mappings:
        prefix = report_prefix or output_file.replace('.json', '')
        failed_json = f"{prefix}_failed_mappings_{timestamp}.json"
        
        try:
            with open(failed_json, 'w', encoding='utf-8') as f:
                json.dump(failed_mappings, f, indent=2, ensure_ascii=False)
            print(f"📄 Fallos JSON: {failed_json}")
        except Exception as e:
            print(f"❌ Error escribiendo JSON de fallos: {e}")


def main():
    """
    Función principal del script
    """
    parser = argparse.ArgumentParser(description='Mapea RefId a SkuId usando archivo de mapeo local')
    parser.add_argument('mapping_file', help='Archivo JSON de mapeo con Id y RefId')
    parser.add_argument('input_file', help='Archivo JSON de entrada con datos')
    parser.add_argument('output_file', help='Archivo JSON de salida')
    parser.add_argument('--key-field', type=str,
                       help='Campo que contiene RefId (para estructuras de lista)')
    parser.add_argument('--report', type=str,
                       help='Prefijo para archivos de reporte')
    
    args = parser.parse_args()
    
    print("🔧 Configuración del proceso:")
    print(f"   📋 Archivo de mapeo: {args.mapping_file}")
    print(f"   📁 Archivo de entrada: {args.input_file}")
    print(f"   📄 Archivo de salida: {args.output_file}")
    print()
    
    # 1. Cargar archivo de mapeo
    refid_to_skuid_mapping = load_mapping_file(args.mapping_file)
    
    # 2. Cargar archivo de datos
    print(f"📂 Cargando archivo de datos: {args.input_file}")
    data = load_input_file(args.input_file, "archivo de datos")
    
    # 3. Detectar estructura y extraer RefIds
    structure_type, refids, key_field = detect_structure_and_refids(data)
    
    # Usar key_field del argumento si se especificó
    if args.key_field:
        key_field = args.key_field
        print(f"🔧 Usando campo personalizado: {key_field}")
    
    # 4. Mapear RefIds a SkuIds usando el archivo de mapeo
    successful_mappings, failed_mappings = map_refids_using_mapping(
        refids, refid_to_skuid_mapping
    )
    
    # 5. Transformar estructura de datos
    print("\n🔄 Transformando estructura de datos...")
    transformed_data = transform_data_structure(
        data, structure_type, key_field, successful_mappings
    )
    
    # 6. Escribir archivos de salida
    print("\n💾 Escribiendo archivos de salida...")
    write_output_files(transformed_data, args.output_file, failed_mappings, args.report)
    
    print(f"\n🎉 PROCESO COMPLETADO")
    print(f"   ✅ {len(successful_mappings)} RefIds mapeados exitosamente")
    print(f"   ❌ {len(failed_mappings)} RefIds fallaron")
    print(f"   📄 Archivo principal: {args.output_file}")
    
    # Mostrar algunos ejemplos de mapeo si hay éxitos
    if successful_mappings and len(successful_mappings) > 0:
        print(f"\n📋 Ejemplos de mapeos exitosos:")
        examples = list(successful_mappings.items())[:3]
        for refid, skuid in examples:
            print(f"   RefId '{refid}' → SkuId '{skuid}'")
        if len(successful_mappings) > 3:
            print(f"   ... y {len(successful_mappings) - 3} más")


if __name__ == '__main__':
    main()