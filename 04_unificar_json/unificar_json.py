#!/usr/bin/env python3
"""
unificar_json.py

Script de unificación de datasets que combina datos antiguos y nuevos 
resolviendo conflictos y actualizando información. Utilizado para 
sincronización de datos entre diferentes fuentes.

Funcionalidad:
- Combina dos archivos JSON usando claves de identificación diferentes
- Archivo antiguo usa "SKU" como clave de identificación
- Archivo nuevo usa "MECA" como clave de identificación
- Actualiza registros existentes con información nueva
- Preserva registros únicos de ambos datasets
- Aplica transformaciones de formato y normalización de nombres
- Exporta registros no unificados a CSV para revisión manual

Lógica de Unificación:
1. **Registros Comunes** (SKU existe en ambos archivos):
   - Renombra "SKU" → "RefId"
   - Actualiza "Categoría" con formato Title Case desde "CATEGORIA" nuevo
   - Agrega "Name" desde "DESCRIPCION" del archivo nuevo
   - Renombra "Descripción" → "Description" preservando valor antiguo
   - Mantiene todos los demás campos del registro antiguo

2. **Registros Solo en Archivo Nuevo** (MECA no existe en archivo antiguo):
   - Crea registro mínimo con RefId, Categoría formateada, Name y Description vacía

3. **Registros Solo en Archivo Antiguo**: Se exportan a CSV para revisión manual

Transformaciones Aplicadas:
- Formato Title Case: "cuidado personal>cuidado del pelo" → "Cuidado Personal>Cuidado Del Pelo"
- Normalización de campos: SKU → RefId, Descripción → Description
- Adición de campos: Name desde DESCRIPCION (formateado de UPPERCASE a camelCase)

Ejecución:
    python3 unificar_json.py old_data.json new_data.json output.json

Ejemplo:
    python3 unificar_json/unificar_json.py productos_antiguos.json productos_nuevos.json productos_unificados.json
"""

import json
import sys
import csv

from pathlib import Path

def title_case_segment(segment: str) -> str:
    """
    Convierte un segmento de texto a Title Case.
    
    Args:
        segment: Segmento de texto a convertir
        
    Returns:
        Segmento con cada palabra capitalizada
    """
    return " ".join(word.capitalize() for word in segment.split())

def format_categoria(cat: str) -> str:
    """
    Formatea una categoría jerárquica aplicando Title Case a cada segmento.
    
    Args:
        cat: Categoría con formato "segmento1>segmento2>segmento3"
        
    Returns:
        Categoría formateada con Title Case
    """
    return ">".join(title_case_segment(seg) for seg in cat.split(">"))

def format_descripcion(descripcion: str) -> str:
    """
    Convierte texto de UPPERCASE a formato camelCase conservando espacios.
    
    Args:
        descripcion: Texto en UPPERCASE
        
    Returns:
        Texto formateado en camelCase con espacios preservados
    """
    if not descripcion:
        return descripcion
    
    # Convertir a lowercase y luego capitalizar solo la primera letra de cada palabra
    return " ".join(word.capitalize() for word in descripcion.lower().split())

def export_to_csv(items, csv_path):
    """
    Exporta una lista de elementos JSON a un archivo CSV.
    
    Args:
        items: Lista de diccionarios a exportar
        csv_path: Ruta del archivo CSV de salida
    """
    if not items:
        return
    
    # Obtener todas las claves únicas de todos los elementos
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    
    # Ordenar las claves para tener un orden consistente
    fieldnames = sorted(all_keys)
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)

def main(old_path: str, new_path: str, out_path: str):
    """
    Función principal que unifica los dos archivos JSON.
    
    Args:
        old_path: Ruta al archivo JSON antiguo (con claves SKU)
        new_path: Ruta al archivo JSON nuevo (con claves MECA)
        out_path: Ruta al archivo JSON de salida unificado
    """
    # Cargar archivos JSON
    old_data = json.loads(Path(old_path).read_text(encoding='utf-8'))
    new_data = json.loads(Path(new_path).read_text(encoding='utf-8'))

    # Construir mapas para acceso rápido
    new_map = {item['MECA']: item for item in new_data}
    old_map = {item['SKU']: item for item in old_data}
    result = []
    no_unificados = []

    # Procesar registros comunes y actualizar
    for sku, old_rec in old_map.items():
        if sku in new_map:
            upd = new_map[sku]
            merged = old_rec.copy()
            merged['RefId'] = sku
            # Actualizar categoría con formato Title Case
            merged['Categoría'] = format_categoria(upd['CATEGORIA'])
            # Agregar campo Name desde DESCRIPCION del archivo nuevo (formateado)
            merged['Name'] = format_descripcion(upd['DESCRIPCION'])
            # Renombrar Descripción a Description manteniendo el valor del archivo viejo
            if 'Descripción' in merged:
                merged['Description'] = merged.pop('Descripción')
            # Eliminar campo SKU original
            merged.pop('SKU', None)
            result.append(merged)
        else:
            # Si no existe en new_map, agregarlo a la lista de no unificados
            no_unificados.append(old_rec)

    # Incluir nuevos registros no presentes en old_data
    for meca, new_rec in new_map.items():
        if meca not in old_map:
            minimal = {
                'RefId': meca,
                'Categoría': format_categoria(new_rec['CATEGORIA']),
                'Name': format_descripcion(new_rec['DESCRIPCION']),
                'Description': ''
            }
            result.append(minimal)

    # Escribir JSON de salida con indentación de 4 espacios
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=4), encoding='utf-8')
    print(f"Archivo unificado generado: {out_path} ({len(result)} registros)")
    
    # Exportar registros no unificados a CSV si existen
    if no_unificados:
        csv_path = out_path.rsplit('.', 1)[0] + '_no_unificados.csv'
        export_to_csv(no_unificados, csv_path)
        print(f"Registros no unificados exportados a: {csv_path} ({len(no_unificados)} registros)")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f"Uso: {sys.argv[0]} <old_data.json> <new_data.json> <output.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])