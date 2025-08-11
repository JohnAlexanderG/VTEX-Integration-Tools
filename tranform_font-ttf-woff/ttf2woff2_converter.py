#!/usr/bin/env python3
"""
Script para convertir archivos TTF a WOFF2 usando fonttools y brotli

Flujo del script:
1. Acepta un archivo .ttf individual o un directorio con archivos .ttf
2. Para cada archivo TTF encontrado:
   - Carga la fuente usando fontTools.ttLib
   - Convierte el formato a WOFF2 con compresión brotli
   - Guarda el archivo convertido en el directorio de salida
3. Muestra el progreso y errores en consola

Uso:
    python3 ttf2woff2_converter.py <input> [-o output_dir]

Ejemplos:
    python3 ttf2woff2_converter.py font.ttf
    python3 ttf2woff2_converter.py font.ttf -o ./woff2_fonts
    python3 ttf2woff2_converter.py ./fonts_directory -o ./output

Dependencias requeridas:
    - fonttools: pip install fonttools
    - brotli: pip install brotli

Formatos soportados:
    - Entrada: .ttf (TrueType Font)
    - Salida: .woff2 (Web Open Font Format 2.0)
"""

import os
import sys
import argparse
from fontTools.ttLib import TTFont


def ttf_to_woff2(input_path, output_path):
    """
    Convierte un archivo .ttf a .woff2 usando fontTools con compresión brotli
    
    Args:
        input_path (str): Ruta al archivo .ttf de entrada
        output_path (str): Ruta al archivo .woff2 de salida
        
    Raises:
        Exception: Si falla la conversión o el archivo no existe
    """
    font = TTFont(input_path)       # Carga la fuente TrueType
    font.flavor = 'woff2'           # Ajusta el formato de salida a WOFF2
    font.save(output_path)          # Guarda el archivo convertido

def main():
    """
    Función principal del script
    
    Flujo:
    1. Configurar argumentos de línea de comandos
    2. Validar ruta de entrada (archivo o directorio)
    3. Crear directorio de salida si no existe
    4. Detectar todos los archivos .ttf a procesar
    5. Convertir cada archivo TTF a WOFF2
    6. Mostrar progreso y errores en consola
    """
    parser = argparse.ArgumentParser(
        description="Convertir archivos TTF a WOFF2 de forma masiva o individual.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 ttf2woff2_converter.py font.ttf
  python3 ttf2woff2_converter.py font.ttf -o ./woff2_fonts  
  python3 ttf2woff2_converter.py ./fonts_directory -o ./output

Dependencias:
  pip install fonttools brotli
        """
    )
    parser.add_argument(
        'input',
        help="Ruta a un archivo .ttf o directorio que contenga archivos .ttf"
    )
    parser.add_argument(
        '-o', '--output',
        help="Directorio donde se guardarán los archivos .woff2 (por defecto: directorio actual)",
        default='.'
    )
    args = parser.parse_args()

    print("🔧 Configuración del conversor TTF a WOFF2:")
    print(f"   📁 Entrada: {args.input}")
    print(f"   📂 Salida: {args.output}")
    print()

    # Crear directorio de salida si no existe
    if not os.path.exists(args.output):
        os.makedirs(args.output)
        print(f"✅ Directorio de salida creado: {args.output}")

    # Detectar archivos .ttf para procesar
    paths = []
    if os.path.isdir(args.input):
        print(f"📂 Escaneando directorio: {args.input}")
        for file in os.listdir(args.input):
            if file.lower().endswith('.ttf'):
                paths.append(os.path.join(args.input, file))
    elif os.path.isfile(args.input) and args.input.lower().endswith('.ttf'):
        paths.append(args.input)
    else:
        print(f"❌ Error: ruta de entrada no válida: {args.input}")
        print("   La entrada debe ser un archivo .ttf o directorio con archivos .ttf")
        sys.exit(1)

    if not paths:
        print(f"⚠️  No se encontraron archivos .ttf en: {args.input}")
        sys.exit(1)

    print(f"🚀 Iniciando conversión de {len(paths)} archivo(s) TTF:")
    print("-" * 60)

    # Procesar cada archivo .ttf encontrado
    successful_conversions = 0
    failed_conversions = 0
    
    for index, ttf_path in enumerate(paths, 1):
        base = os.path.basename(ttf_path)
        name = os.path.splitext(base)[0]
        woff2_filename = f"{name}.woff2"
        out_path = os.path.join(args.output, woff2_filename)
        
        print(f"🔄 [{index}/{len(paths)}] Procesando: {base}")
        
        try:
            ttf_to_woff2(ttf_path, out_path)
            successful_conversions += 1
            
            # Calcular reducción de tamaño
            original_size = os.path.getsize(ttf_path)
            woff2_size = os.path.getsize(out_path)
            reduction = ((original_size - woff2_size) / original_size) * 100
            
            print(f"   ✅ Convertido exitosamente")
            print(f"   📊 Tamaño: {original_size:,} bytes → {woff2_size:,} bytes ({reduction:.1f}% reducción)")
            print(f"   💾 Guardado en: {out_path}")
            
        except Exception as e:
            failed_conversions += 1
            print(f"   ❌ Error en conversión: {str(e)}")
        
        print()

    # Resumen final
    print("=" * 60)
    print(f"🏁 PROCESO COMPLETADO")
    print(f"   ✅ Conversiones exitosas: {successful_conversions}")
    print(f"   ❌ Conversiones fallidas: {failed_conversions}")
    print(f"   📂 Directorio de salida: {args.output}")
    print("=" * 60)


if __name__ == '__main__':
    main()
