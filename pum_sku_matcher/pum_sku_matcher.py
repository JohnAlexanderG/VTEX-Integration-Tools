#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUM vs VTEX SKU Matcher - Compara datos PUM contra productos existentes en VTEX

Este script cruza la lista de datos PUM de productos (archivo CSV) contra la lista
de productos existentes en VTEX (otro CSV), usando el campo MECA como clave de
comparación contra SKU reference code.

Genera dos archivos de salida:
1. pum_encontrados.csv: Registros PUM que coinciden con VTEX (MECA renombrado a SKU reference code)
2. pum_no_encontrados.csv: Registros PUM sin coincidencia en VTEX (headers originales)

Uso:
    python3 pum_sku_matcher.py pum_file.csv vtex_file.csv

Ejemplos:
    python3 pum_sku_matcher.py pum_data.csv vtex_products.csv
    python3 pum_sku_matcher.py datos_pum.csv catalogo_vtex.csv
"""

import csv
import sys
import argparse
import os
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        description='Comparar datos PUM contra productos existentes en VTEX usando MECA vs SKU reference code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python3 pum_sku_matcher.py pum_data.csv vtex_products.csv

Archivos de entrada:
  CSV PUM:  Debe contener columnas: MECA, CANTIDAD PUM, UNIDAD MINIMA PUM
  CSV VTEX: Debe contener columna: SKU reference code

Archivos de salida:
  pum_encontrados.csv     - Registros PUM con coincidencia en VTEX
  pum_no_encontrados.csv  - Registros PUM sin coincidencia en VTEX
        """
    )
    parser.add_argument('pum_file', help='Archivo CSV con datos PUM (contiene MECA)')
    parser.add_argument('vtex_file', help='Archivo CSV con productos VTEX (contiene SKU reference code)')

    args = parser.parse_args()

    # Validar que los archivos existan
    if not os.path.exists(args.pum_file):
        print(f"Error: El archivo '{args.pum_file}' no existe")
        sys.exit(1)

    if not os.path.exists(args.vtex_file):
        print(f"Error: El archivo '{args.vtex_file}' no existe")
        sys.exit(1)

    # Headers requeridos
    pum_required = {'MECA', 'CANTIDAD PUM', 'UNIDAD MINIMA PUM'}
    vtex_required = {'SKU reference code'}

    try:
        # Cargar CSV de VTEX y construir set de SKU reference codes
        print(f"Cargando archivo VTEX: {args.vtex_file}")
        vtex_sku_codes = set()
        with open(args.vtex_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            vtex_headers = set(reader.fieldnames) if reader.fieldnames else set()

            if not vtex_required.issubset(vtex_headers):
                missing = vtex_required - vtex_headers
                print(f"Error: El archivo VTEX no contiene las columnas requeridas: {missing}")
                print(f"Columnas disponibles: {reader.fieldnames}")
                sys.exit(1)

            for row in reader:
                code = row.get('SKU reference code', '').strip()
                if code:
                    vtex_sku_codes.add(code)

        print(f"  SKU reference codes en VTEX: {len(vtex_sku_codes)}")

        # Cargar CSV PUM y clasificar registros
        print(f"Cargando archivo PUM: {args.pum_file}")
        encontrados = []
        no_encontrados = []

        with open(args.pum_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pum_headers = set(reader.fieldnames) if reader.fieldnames else set()

            if not pum_required.issubset(pum_headers):
                missing = pum_required - pum_headers
                print(f"Error: El archivo PUM no contiene las columnas requeridas: {missing}")
                print(f"Columnas disponibles: {reader.fieldnames}")
                sys.exit(1)

            for row in reader:
                meca = row.get('MECA', '').strip()
                if meca in vtex_sku_codes:
                    encontrados.append(row)
                else:
                    no_encontrados.append(row)

        total = len(encontrados) + len(no_encontrados)
        print(f"  Registros PUM totales: {total}")

        # Escribir pum_encontrados.csv (MECA renombrado a SKU reference code)
        encontrados_file = 'pum_encontrados.csv'
        if encontrados:
            with open(encontrados_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SKU reference code', 'CANTIDAD PUM', 'UNIDAD MINIMA PUM'])
                for row in encontrados:
                    writer.writerow([
                        row.get('MECA', ''),
                        row.get('CANTIDAD PUM', ''),
                        row.get('UNIDAD MINIMA PUM', '')
                    ])
            print(f"\n  ✓ {encontrados_file}: {len(encontrados)} registros encontrados en VTEX")
        else:
            print(f"\n  ⚠ No se encontraron coincidencias con VTEX")

        # Escribir pum_no_encontrados.csv (headers originales)
        no_encontrados_file = 'pum_no_encontrados.csv'
        if no_encontrados:
            with open(no_encontrados_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['MECA', 'CANTIDAD PUM', 'UNIDAD MINIMA PUM'])
                for row in no_encontrados:
                    writer.writerow([
                        row.get('MECA', ''),
                        row.get('CANTIDAD PUM', ''),
                        row.get('UNIDAD MINIMA PUM', '')
                    ])
            print(f"  ✓ {no_encontrados_file}: {len(no_encontrados)} registros NO encontrados en VTEX")
        else:
            print(f"  ✓ Todos los registros PUM tienen coincidencia en VTEX")

        # Estadísticas
        pct = (len(encontrados) / total) * 100 if total > 0 else 0

        print(f"\n--- Estadísticas ---")
        print(f"  Total PUM:          {total}")
        print(f"  Encontrados:        {len(encontrados)}")
        print(f"  No encontrados:     {len(no_encontrados)}")
        if total > 0:
            print(f"  Cobertura VTEX:     {pct:.1f}%")

        # Generar reporte markdown
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_file = 'pum_sku_matcher_report.md'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# PUM vs VTEX SKU Matcher - Reporte\n\n")
            f.write(f"**Fecha:** {timestamp}\n\n")
            f.write(f"## Archivos de entrada\n\n")
            f.write(f"| Archivo | Ruta |\n")
            f.write(f"|---------|------|\n")
            f.write(f"| PUM | `{args.pum_file}` |\n")
            f.write(f"| VTEX | `{args.vtex_file}` |\n\n")
            f.write(f"## Resumen\n\n")
            f.write(f"| Métrica | Valor |\n")
            f.write(f"|---------|-------|\n")
            f.write(f"| SKU reference codes en VTEX | {len(vtex_sku_codes)} |\n")
            f.write(f"| Registros PUM totales | {total} |\n")
            f.write(f"| Encontrados en VTEX | {len(encontrados)} |\n")
            f.write(f"| No encontrados en VTEX | {len(no_encontrados)} |\n")
            f.write(f"| Cobertura VTEX | {pct:.1f}% |\n\n")
            f.write(f"## Archivos de salida\n\n")
            f.write(f"| Archivo | Registros | Descripción |\n")
            f.write(f"|---------|-----------|-------------|\n")
            if encontrados:
                f.write(f"| `{encontrados_file}` | {len(encontrados)} | Registros PUM con coincidencia en VTEX |\n")
            if no_encontrados:
                f.write(f"| `{no_encontrados_file}` | {len(no_encontrados)} | Registros PUM sin coincidencia en VTEX |\n")
            f.write(f"\n")

            if no_encontrados:
                f.write(f"## Registros no encontrados (MECA)\n\n")
                f.write(f"| # | MECA | CANTIDAD PUM | UNIDAD MINIMA PUM |\n")
                f.write(f"|---|------|--------------|-------------------|\n")
                for i, row in enumerate(no_encontrados, 1):
                    meca = row.get('MECA', '')
                    cantidad = row.get('CANTIDAD PUM', '')
                    unidad = row.get('UNIDAD MINIMA PUM', '')
                    f.write(f"| {i} | {meca} | {cantidad} | {unidad} |\n")
                f.write(f"\n")

        print(f"  ✓ {report_file}: Reporte generado")
        print(f"\n✓ Proceso completado exitosamente")

    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
