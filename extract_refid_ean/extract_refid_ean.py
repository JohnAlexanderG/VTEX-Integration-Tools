#!/usr/bin/env python3
"""
Extrae RefId y UPC de un archivo JSON y crea un nuevo archivo con solo estos campos.

Uso:
    python3 extract_refid_ean.py input.json output.json [--indent 4]

Argumentos:
    input.json  - Archivo JSON de entrada
    output.json - Archivo JSON de salida 
    --indent    - Espacios de indentación para el JSON de salida (opcional, default: 4)

Ejemplo:
    python3 extract_refid_ean.py data.json refid_ean.json --indent 4
"""

import json
import argparse
import sys
import os

def extract_refid_ean(input_file, output_file, indent=4):
    """
    Extrae RefId y UPC de un JSON y crea un nuevo archivo con solo estos campos.
    
    Args:
        input_file (str): Ruta del archivo JSON de entrada
        output_file (str): Ruta del archivo JSON de salida
        indent (int): Espacios de indentación para el JSON de salida
    """
    try:
        # Leer archivo JSON de entrada
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        extracted_data = []
        
        # Procesar cada elemento del JSON
        for item in data:
            if isinstance(item, dict):
                # Extraer RefId y UPC si existen
                extracted_item = {}
                
                if 'RefId' in item:
                    extracted_item['RefId'] = item['RefId']
                
                if 'UPC' in item:
                    extracted_item['EAN'] = item['UPC']  # Renombrar UPC a EAN
                
                # Solo agregar si tiene al menos uno de los campos
                if extracted_item:
                    extracted_data.append(extracted_item)
        
        # Escribir archivo JSON de salida
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=indent)
        
        print(f"✅ Extracción completada: {len(extracted_data)} registros procesados")
        print(f"📄 Archivo de salida: {output_file}")
        
    except FileNotFoundError:
        print(f"❌ Error: El archivo {input_file} no existe")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error al leer JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Extrae RefId y UPC de un JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python3 extract_refid_ean.py data.json output.json
    python3 extract_refid_ean.py data.json output.json --indent 2
        """
    )
    
    parser.add_argument('input_file', help='Archivo JSON de entrada')
    parser.add_argument('output_file', help='Archivo JSON de salida')
    parser.add_argument('--indent', type=int, default=4, 
                       help='Espacios de indentación para el JSON de salida (default: 4)')
    
    args = parser.parse_args()
    
    # Verificar que el archivo de entrada existe
    if not os.path.exists(args.input_file):
        print(f"❌ Error: El archivo {args.input_file} no existe")
        sys.exit(1)
    
    extract_refid_ean(args.input_file, args.output_file, args.indent)

if __name__ == "__main__":
    main()