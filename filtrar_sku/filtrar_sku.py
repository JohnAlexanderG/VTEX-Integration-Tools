#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filtrador de SKUs - Compara dos archivos JSON usando _SKUReferenceCode

Este script compara dos archivos JSON que contienen el campo _SKUReferenceCode
y genera dos archivos de salida:
1. Un archivo con los datos del archivo 2 que tienen coincidencias en archivo 1,
   agregando el campo _SkuId del archivo 1 a cada coincidencia
2. Un archivo con los datos del archivo 1 que NO tienen coincidencias en archivo 2

Uso:
    python3 filtrar_sku.py archivo1.json archivo2.json --tipo {precios|inventario}

Ejemplos:
    python3 filtrar_sku.py productos_existentes.json precios_nuevos.json --tipo precios
    python3 filtrar_sku.py productos_existentes.json inventario_nuevos.json --tipo inventario

Tipos de archivo soportados:
- precios: Contiene campos Costo, Precio Venta
- inventario: Contiene campos Codigo Sucursal, Existencia
"""

import json
import sys
import argparse
import os
import csv
from datetime import datetime

def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Filtrar archivos JSON usando _SKUReferenceCode')
    parser.add_argument('archivo1', help='Archivo JSON de referencia (contiene SKUs existentes)')
    parser.add_argument('archivo2', help='Archivo JSON a filtrar (se extraen los datos coincidentes)')
    parser.add_argument('--tipo', choices=['precios', 'inventario'], required=True, 
                       help='Tipo de archivo del segundo archivo: precios o inventario')
    parser.add_argument('--salida-coincidencias', 
                       help='Archivo de salida para datos coincidentes del archivo 2 (default: {tipo}_{fecha}.json)')
    parser.add_argument('--salida-no-encontrados', 
                       help='Archivo de salida para datos no encontrados del archivo 1 (default: no_encontrados_{fecha}.csv)')
    
    args = parser.parse_args()
    
    # Generar nombres de archivo por defecto con fecha y tipo
    fecha_actual = datetime.now().strftime('%Y%m%d')
    if args.salida_coincidencias is None:
        args.salida_coincidencias = f'{args.tipo}_{fecha_actual}.json'
    if args.salida_no_encontrados is None:
        args.salida_no_encontrados = f'no_encontrados_{fecha_actual}.csv'
    
    # Validar que los archivos existan
    if not os.path.exists(args.archivo1):
        print(f"Error: El archivo '{args.archivo1}' no existe")
        sys.exit(1)
    
    if not os.path.exists(args.archivo2):
        print(f"Error: El archivo '{args.archivo2}' no existe")
        sys.exit(1)
    
    try:
        # Cargar archivos JSON
        print(f"Cargando archivo 1: {args.archivo1}")
        with open(args.archivo1, 'r', encoding='utf-8') as f:
            data1 = json.load(f)
        
        print(f"Cargando archivo 2: {args.archivo2}")
        with open(args.archivo2, 'r', encoding='utf-8') as f:
            data2 = json.load(f)
        
        # Validar que los datos sean listas
        if not isinstance(data1, list):
            print(f"Error: El archivo '{args.archivo1}' no contiene una lista JSON")
            sys.exit(1)
        
        if not isinstance(data2, list):
            print(f"Error: El archivo '{args.archivo2}' no contiene una lista JSON")
            sys.exit(1)
        
        # Validar que los objetos tengan la columna _SKUReferenceCode
        if not data1 or '_SKUReferenceCode' not in data1[0]:
            print(f"Error: El archivo '{args.archivo1}' no contiene la clave '_SKUReferenceCode'")
            if data1:
                print(f"Claves disponibles: {list(data1[0].keys())}")
            sys.exit(1)
        
        if not data2 or '_SKUReferenceCode' not in data2[0]:
            print(f"Error: El archivo '{args.archivo2}' no contiene la clave '_SKUReferenceCode'")
            if data2:
                print(f"Claves disponibles: {list(data2[0].keys())}")
            sys.exit(1)
        
        # Mostrar información de los archivos
        print(f"\nInformación de archivos:")
        print(f"  Archivo 1: {len(data1)} registros")
        print(f"  Archivo 2: {len(data2)} registros")
        
        # Función para limpiar SKUs
        def limpiar_sku(valor):
            if valor is None:
                return ''
            # Convertir a string y eliminar espacios
            sku = str(valor).strip()
            return sku
        
        # Obtener códigos SKU únicos (limpios)
        skus_archivo1 = set()
        for item in data1:
            sku = limpiar_sku(item.get('_SKUReferenceCode'))
            if sku and sku != '' and sku != 'None':
                skus_archivo1.add(sku)
        
        skus_archivo2 = set()
        for item in data2:
            sku = limpiar_sku(item.get('_SKUReferenceCode'))
            if sku and sku != '' and sku != 'None':
                skus_archivo2.add(sku)
        
        print(f"\nAnálisis de SKUs:")
        print(f"  SKUs únicos en archivo 1: {len(skus_archivo1)}")
        print(f"  SKUs únicos en archivo 2: {len(skus_archivo2)}")
        
        # Encontrar coincidencias
        skus_coincidentes = skus_archivo1.intersection(skus_archivo2)
        print(f"  SKUs que coinciden: {len(skus_coincidentes)}")
        
        # Debug específico para SKU 000050
        sku_test = '000050'
        print(f"\nDebug para SKU {sku_test}:")
        print(f"  Está en archivo 1: {sku_test in skus_archivo1}")
        print(f"  Está en archivo 2: {sku_test in skus_archivo2}")
        
        # Debug detallado - buscar SKUs que contengan "000050"
        skus_archivo1_con_000050 = [sku for sku in skus_archivo1 if '000050' in sku]
        skus_archivo2_con_000050 = [sku for sku in skus_archivo2 if '000050' in sku]
        
        print(f"  SKUs en archivo 1 que contienen '000050': {skus_archivo1_con_000050}")
        print(f"  SKUs en archivo 2 que contienen '000050': {skus_archivo2_con_000050}")
        
        # Mostrar representación de los SKUs encontrados
        if skus_archivo1_con_000050:
            for sku in skus_archivo1_con_000050:
                print(f"  Archivo 1 - SKU '{sku}' - len: {len(sku)}")
        
        if skus_archivo2_con_000050:
            for sku in skus_archivo2_con_000050:
                print(f"  Archivo 2 - SKU '{sku}' - len: {len(sku)}")
        
        # Mostrar algunos SKUs de ejemplo
        print(f"\nPrimeros 5 SKUs archivo 1: {list(skus_archivo1)[:5]}")
        print(f"Primeros 5 SKUs archivo 2: {list(skus_archivo2)[:5]}")
        
        # Crear un diccionario de mapeo SKU -> datos completos del archivo 1
        mapeo_archivo1 = {}
        for item in data1:
            sku = limpiar_sku(item.get('_SKUReferenceCode'))
            if sku and sku != '' and sku != 'None':
                mapeo_archivo1[sku] = item
        
        
        # Filtrar archivo 2 - solo registros que existan en archivo 1
        # Agregar el campo _SkuId (Not changeable) del archivo 1
        # Solo mantener campos específicos y renombrar según requerimientos
        coincidencias = []
        for item in data2:
            sku = limpiar_sku(item.get('_SKUReferenceCode'))
            if sku in skus_archivo1:
                # Crear objeto con solo los campos requeridos según el tipo
                if args.tipo == 'precios':
                    item_filtrado = {
                        '_SkuId': item.get('_SkuId (Not changeable)'),
                        '_SKUReferenceCode': item.get('_SKUReferenceCode'),
                        'costPrice': item.get('Costo'),
                        'basePrice': item.get('Precio Venta')
                    }
                elif args.tipo == 'inventario':
                    # Convertir Existencia a entero
                    existencia = item.get('Existencia', '0')
                    try:
                        quantity = int(str(existencia).strip()) if existencia else 0
                    except ValueError:
                        quantity = 0
                    
                    # Siempre usar unlimitedQuantity=false como regla de negocio
                    unlimited_quantity = False
                    
                    item_filtrado = {
                        '_SkuId': item.get('_SkuId (Not changeable)'),
                        '_SKUReferenceCode': item.get('_SKUReferenceCode'),
                        'warehouseId': item.get('Codigo Sucursal'),
                        'quantity': quantity,
                        'unlimitedQuantity': unlimited_quantity
                    }
                    
                    # Agregar campos opcionales si están disponibles
                    if item.get('dateUtcOnBalanceSystem'):
                        item_filtrado['dateUtcOnBalanceSystem'] = item.get('dateUtcOnBalanceSystem')
                    
                    if item.get('leadTime'):
                        item_filtrado['leadTime'] = item.get('leadTime')
                
                # Agregar el _SkuId del archivo 1 si existe
                if sku in mapeo_archivo1:
                    sku_id = mapeo_archivo1[sku].get('_SkuId (Not changeable)')
                    if sku_id is not None:
                        item_filtrado['_SkuId'] = sku_id
                coincidencias.append(item_filtrado)
        
        # Encontrar registros de archivo 1 que NO están en archivo 2
        no_encontrados = []
        for item in data1:
            sku = limpiar_sku(item.get('_SKUReferenceCode'))
            if sku not in skus_archivo2:
                no_encontrados.append(item)
        
        # Función para exportar datos
        def exportar_datos(datos, archivo, formato):
            if formato == 'json':
                with open(archivo, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, indent=4, ensure_ascii=False)
            elif formato == 'csv':
                if datos:
                    # Obtener todas las claves únicas de todos los objetos
                    claves = set()
                    for item in datos:
                        claves.update(item.keys())
                    claves = sorted(list(claves))
                    
                    with open(archivo, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=claves)
                        writer.writeheader()
                        for item in datos:
                            writer.writerow(item)
        
        # Exportar resultados
        print(f"\nGenerando archivos de salida:")
        
        # Archivo de coincidencias (siempre JSON)
        if len(coincidencias) > 0:
            exportar_datos(coincidencias, args.salida_coincidencias, 'json')
            print(f"  ✓ {args.salida_coincidencias}: {len(coincidencias)} registros coincidentes del archivo 2 (JSON)")
        else:
            print(f"  ⚠ No se encontraron coincidencias para exportar")
        
        # Archivo de no encontrados (siempre CSV)
        if len(no_encontrados) > 0:
            exportar_datos(no_encontrados, args.salida_no_encontrados, 'csv')
            print(f"  ✓ {args.salida_no_encontrados}: {len(no_encontrados)} registros del archivo 1 sin coincidencia (CSV)")
        else:
            print(f"  ✓ Todos los registros del archivo 1 tienen coincidencia en archivo 2")
        
        print(f"\n✓ Proceso completado exitosamente")
        
    except FileNotFoundError as e:
        print(f"Error: Archivo no encontrado - {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Archivo JSON inválido - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()