#!/usr/bin/env python3
"""
csv_to_json_marca.py

Script especializado para extraer información de marcas desde archivos CSV.
Procesa archivos con estructura de opciones donde las marcas están identificadas 
por TIPO='MARCA'.

Funcionalidad:
- Lee archivo CSV completo línea por línea
- Filtra registros donde campo TIPO contiene 'MARCA' (case-insensitive)
- Extrae SKU desde columna 'SKU' 
- Extrae nombre de marca desde columna 'OPCIONES'
- Genera archivo JSON con mapeo SKU → Marca para uso posterior
- Mantiene codificación UTF-8 para caracteres especiales en nombres de marca

Campos de Salida:
- SKU: Identificador único del producto
- Marca: Nombre de la marca extraído del campo OPCIONES

Ejecución:
    # Extracción básica de marcas
    python3 csv_to_json_marca.py input.csv marcas.json
    
    # Procesamiento típico de archivo de opciones
    python3 csv_to_json_marca.py opciones_productos.csv marcas_extraidas.json

Ejemplo:
    python3 csv_to_json_marca/csv_to_json_marca.py datos_opciones.csv marcas.json

Casos de Uso:
- Generar archivo de marcas para vtex_brandid_matcher
- Extraer mapeo SKU-Marca desde archivos de configuración de productos
"""
import csv
import json
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='Convierte un CSV a JSON extrayendo SKU y Marca'
    )
    parser.add_argument('input_csv', help='Ruta al archivo CSV de entrada')
    parser.add_argument('output_json', help='Ruta al archivo JSON de salida')
    args = parser.parse_args()

    resultados = []
    with open(args.input_csv, mode='r', encoding='utf-8', newline='') as csvfile:
        lector = csv.DictReader(csvfile)
        for fila in lector:
            tipo = fila.get('TIPO', '').strip().lower()
            if tipo == 'marca':
                sku = fila.get('SKU', '').strip()
                marca = fila.get('OPCIONES', '').strip()
                resultados.append({
                    'SKU': sku,
                    'Marca': marca
                })

    with open(args.output_json, mode='w', encoding='utf-8') as jsonfile:
        json.dump(resultados, jsonfile, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
