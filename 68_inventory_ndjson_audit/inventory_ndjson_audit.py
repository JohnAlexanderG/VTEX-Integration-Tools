#!/usr/bin/env python3
"""
Inventory NDJSON Audit

Compara el CSV de inventario origen (fuente del cliente/ERP) contra el NDJSON
generado por el middleware (una linea = una peticion enviada a VTEX) para
detectar que bodegas y que registros puntuales no se estan enviando.

Usage:
    python3 inventory_ndjson_audit.py <source_csv> <ndjson_file> <output_prefix>
    python3 inventory_ndjson_audit.py source.csv middleware.ndjson output --dry-run

Example:
    python3 inventory_ndjson_audit.py inventario_erp.csv nivelej_to_update.ndjson bodega_audit

    Genera:
    - bodega_audit_bodega_coverage.csv: cobertura de envio por bodega
    - bodega_audit_missing_records.csv: registros del CSV que no llegaron al NDJSON
    - bodega_audit_extra_in_ndjson.csv: registros del NDJSON sin fila de origen en el CSV
    - bodega_audit_REPORT.md: resumen ejecutivo con tabla de cobertura por bodega
"""

import csv
import json
import sys
import os
import argparse
import logging
from datetime import datetime
from collections import Counter
from typing import Dict, Tuple, Optional, List, Any

logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Custom exception for audit errors."""
    pass


def _strip_float_suffix(s: str) -> str:
    """Remove .0 suffix from Excel-style float conversion (e.g. '95.0' -> '95')."""
    if s.endswith('.0'):
        try:
            if float(s) == int(float(s)):
                s = str(int(float(s)))
        except (ValueError, OverflowError):
            pass
    return s


def clean_sku(value: Any) -> str:
    """Normalize SKU codes - strip whitespace, preserve leading zeros."""
    if value is None:
        return ''
    s = str(value).strip()
    s = _strip_float_suffix(s)
    return s


def clean_warehouse(value: Any) -> str:
    """Normalize warehouse/bodega codes.

    - Strips whitespace
    - Removes Excel float artifacts (e.g. '95.0' -> '95')
    - Zero-pads purely numeric codes to 3 digits when length < 3 (e.g. '95' -> '095')
      This matches typical warehouse ids like 001, 021, 095, 140, 220.
    """
    if value is None:
        return ''
    s = str(value).strip()
    s = _strip_float_suffix(s)
    if s.isdigit() and len(s) < 3:
        s = s.zfill(3)
    return s


def clean_quantity(value: Any) -> str:
    """Normalize quantity - strip whitespace, remove float artifacts."""
    if value is None:
        return ''
    s = str(value).strip()
    try:
        s = str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def _find_column(fieldnames: List[str], target: str) -> Optional[str]:
    """Find a column name tolerating stray leading/trailing whitespace in headers.

    Real-world ERP exports sometimes have typos like 'CODIGO SUCURSAL ' (trailing
    space). Matching is done by stripped comparison so callers don't need to edit
    every source file just to fix a header typo.
    """
    target_norm = target.strip()
    for fn in fieldnames:
        if fn.strip() == target_norm:
            return fn
    return None


def load_source_csv(
    file_path: str, sku_col: str, warehouse_col: str, quantity_col: str
) -> Tuple[Dict[Tuple[str, str], str], Counter, List[dict], List[str]]:
    """Load source CSV and build lookup dictionary.

    Returns:
        Tuple of:
        - dict mapping (sku, warehouse) -> quantity
        - Counter of rows per warehouse
        - list of original rows (dicts) keyed by (sku, warehouse) order, for missing-records export
        - fieldnames of the CSV
    """
    if not os.path.isfile(file_path):
        raise AuditError(f"Archivo no encontrado: {file_path}")

    logger.info(f"Cargando CSV origen desde: {file_path}")

    lookup: Dict[Tuple[str, str], str] = {}
    rows_by_key: Dict[Tuple[str, str], dict] = {}
    per_warehouse: Counter = Counter()
    total_rows = 0
    skipped = 0

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = [fn for fn in (reader.fieldnames or []) if fn is not None]

        sku_actual = _find_column(fieldnames, sku_col)
        warehouse_actual = _find_column(fieldnames, warehouse_col)
        quantity_actual = _find_column(fieldnames, quantity_col)
        missing_cols = [
            requested for requested, actual in
            [(sku_col, sku_actual), (warehouse_col, warehouse_actual), (quantity_col, quantity_actual)]
            if actual is None
        ]
        if missing_cols:
            raise AuditError(
                f"Columnas requeridas no encontradas en {file_path}\n"
                f"  Faltantes: {', '.join(missing_cols)}\n"
                f"  Disponibles: {', '.join(fieldnames)}"
            )

        for row in reader:
            total_rows += 1
            sku = clean_sku(row.get(sku_actual, ''))
            warehouse = clean_warehouse(row.get(warehouse_actual, ''))
            quantity = clean_quantity(row.get(quantity_actual, ''))

            if not sku or not warehouse:
                skipped += 1
                continue

            key = (sku, warehouse)
            clean_row = {k: v for k, v in row.items() if k is not None}
            lookup[key] = quantity
            rows_by_key[key] = clean_row
            per_warehouse[warehouse] += 1

    logger.info(
        f"  {len(lookup):,} registros unicos cargados de {total_rows:,} filas "
        f"({skipped:,} incompletos omitidos)"
    )
    return lookup, per_warehouse, rows_by_key, fieldnames


def load_ndjson(file_path: str, verbose: bool = False) -> Tuple[Dict[Tuple[str, str], str], Counter, List[dict], int, int]:
    """Load middleware NDJSON output and build lookup dictionary.

    Returns:
        Tuple of:
        - dict mapping (ref_code, warehouse) -> quantity (last value wins)
        - Counter of lines per warehouse
        - list of raw records (dicts) for extra-record export
        - count of duplicate (ref_code, warehouse) lines
        - count of invalid/skipped lines
    """
    if not os.path.isfile(file_path):
        raise AuditError(f"Archivo no encontrado: {file_path}")

    logger.info(f"Cargando NDJSON del middleware desde: {file_path}")

    lookup: Dict[Tuple[str, str], str] = {}
    records_by_key: Dict[Tuple[str, str], dict] = {}
    per_warehouse: Counter = Counter()
    seen_keys: set = set()
    total_lines = 0
    duplicate_count = 0
    invalid_count = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                invalid_count += 1
                if verbose:
                    logger.debug(f"  [LOG] Linea {line_number} invalida (JSON malformado): {e}")
                continue

            ref_code = clean_sku(record.get('_SKUReferenceCode'))
            warehouse = clean_warehouse(record.get('warehouseId'))
            quantity = clean_quantity(record.get('quantity'))

            if not ref_code or not warehouse:
                invalid_count += 1
                if verbose:
                    logger.debug(
                        f"  [LOG] Linea {line_number} sin _SKUReferenceCode/warehouseId validos: {record}"
                    )
                continue

            key = (ref_code, warehouse)
            if key in seen_keys:
                duplicate_count += 1
                if verbose and duplicate_count == 1:
                    logger.debug(f"  [LOG] Primer duplicado detectado: key={key}")
            seen_keys.add(key)

            lookup[key] = quantity
            records_by_key[key] = record
            per_warehouse[warehouse] += 1

    logger.info(
        f"  {len(lookup):,} registros unicos cargados de {total_lines:,} lineas "
        f"({duplicate_count:,} duplicados, {invalid_count:,} invalidas/incompletas omitidas)"
    )
    return lookup, per_warehouse, list(records_by_key.values()), duplicate_count, invalid_count


def compute_bodega_coverage(
    csv_per_warehouse: Counter, ndjson_per_warehouse: Counter,
    csv_lookup: Dict[Tuple[str, str], str], ndjson_lookup: Dict[Tuple[str, str], str]
) -> List[dict]:
    """Compute per-warehouse coverage stats.

    Returns a list of dicts sorted with FALTANTE/PARCIAL warehouses first.
    """
    all_warehouses = sorted(set(csv_per_warehouse) | set(ndjson_per_warehouse))
    coverage: List[dict] = []

    for warehouse in all_warehouses:
        en_csv = csv_per_warehouse.get(warehouse, 0)
        en_ndjson = ndjson_per_warehouse.get(warehouse, 0)
        enviados = sum(
            1 for (sku, wh) in csv_lookup if wh == warehouse and (sku, wh) in ndjson_lookup
        )
        faltantes = en_csv - enviados

        if en_csv == 0 and en_ndjson > 0:
            estado = 'EXTRA'
            pct = None
        elif en_csv > 0 and enviados == 0:
            estado = 'FALTANTE'
            pct = 0.0
        elif en_csv > 0 and enviados < en_csv:
            estado = 'PARCIAL'
            pct = enviados / en_csv * 100
        else:
            estado = 'OK'
            pct = 100.0 if en_csv > 0 else None

        coverage.append({
            'warehouseId': warehouse,
            'en_csv': en_csv,
            'en_ndjson': en_ndjson,
            'enviados': enviados,
            'faltantes': faltantes,
            'pct_cobertura': pct,
            'estado': estado,
        })

    # FALTANTE first, then PARCIAL, then EXTRA, then OK; each group sorted by warehouseId
    order = {'FALTANTE': 0, 'PARCIAL': 1, 'EXTRA': 2, 'OK': 3}
    coverage.sort(key=lambda r: (order.get(r['estado'], 9), r['warehouseId']))
    return coverage


def write_bodega_coverage_csv(coverage: List[dict], output_file: str) -> None:
    fieldnames = ['warehouseId', 'en_csv', 'en_ndjson', 'enviados', 'faltantes', 'pct_cobertura', 'estado']
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in coverage:
            out_row = dict(row)
            out_row['pct_cobertura'] = (
                f"{row['pct_cobertura']:.1f}" if row['pct_cobertura'] is not None else ''
            )
            writer.writerow(out_row)
    logger.info(f"Cobertura por bodega escrita en: {output_file}")


def write_missing_records_csv(
    csv_lookup: Dict[Tuple[str, str], str], ndjson_lookup: Dict[Tuple[str, str], str],
    rows_by_key: Dict[Tuple[str, str], dict], fieldnames: List[str], output_file: str
) -> int:
    count = 0
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key in csv_lookup:
            if key not in ndjson_lookup:
                writer.writerow(rows_by_key[key])
                count += 1
    logger.info(f"{count:,} registros faltantes escritos en: {output_file}")
    return count


def write_extra_in_ndjson_csv(
    ndjson_lookup: Dict[Tuple[str, str], str], csv_lookup: Dict[Tuple[str, str], str],
    ndjson_records: List[dict], output_file: str
) -> int:
    count = 0
    fieldnames = ['_SkuId', '_SKUReferenceCode', 'warehouseId', 'quantity', 'unlimitedQuantity']
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for record in ndjson_records:
            ref_code = clean_sku(record.get('_SKUReferenceCode'))
            warehouse = clean_warehouse(record.get('warehouseId'))
            key = (ref_code, warehouse)
            if key not in csv_lookup:
                writer.writerow(record)
                count += 1
    logger.info(f"{count:,} registros extra (sin origen en CSV) escritos en: {output_file}")
    return count


def compute_quantity_mismatches(
    csv_lookup: Dict[Tuple[str, str], str], ndjson_lookup: Dict[Tuple[str, str], str]
) -> int:
    return sum(
        1 for key, qty in csv_lookup.items()
        if key in ndjson_lookup and ndjson_lookup[key] != qty
    )


def generate_report(
    report_file: str,
    coverage: List[dict],
    stats: Dict[str, Any],
    coverage_file: str,
    missing_file: str,
    extra_file: str,
) -> None:
    """Generate detailed markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _pct(numerator: int, denominator: int) -> float:
        return numerator / denominator * 100 if denominator > 0 else 0

    global_pct = _pct(stats['csv_total'] - stats['missing_count'], stats['csv_total'])

    faltantes = [r for r in coverage if r['estado'] == 'FALTANTE']
    parciales = [r for r in coverage if r['estado'] == 'PARCIAL']
    extras = [r for r in coverage if r['estado'] == 'EXTRA']

    coverage_rows = ""
    for r in coverage:
        pct_str = f"{r['pct_cobertura']:.1f}%" if r['pct_cobertura'] is not None else "N/A"
        coverage_rows += (
            f"| {r['warehouseId']} | {r['en_csv']:,} | {r['en_ndjson']:,} | "
            f"{r['enviados']:,} | {r['faltantes']:,} | {pct_str} | {r['estado']} |\n"
        )

    alert_section = ""
    if faltantes:
        bodegas_faltantes = ', '.join(r['warehouseId'] for r in faltantes)
        alert_section += (
            f"\n**Bodegas totalmente ausentes del NDJSON "
            f"({len(faltantes)}):** {bodegas_faltantes}\n"
        )
    if parciales:
        bodegas_parciales = ', '.join(r['warehouseId'] for r in parciales)
        alert_section += (
            f"\n**Bodegas con envio parcial ({len(parciales)}):** {bodegas_parciales}\n"
        )
    if extras:
        bodegas_extras = ', '.join(r['warehouseId'] for r in extras)
        alert_section += (
            f"\n**Bodegas en NDJSON sin fila de origen en el CSV "
            f"({len(extras)}):** {bodegas_extras}\n"
        )
    if not alert_section:
        alert_section = "\nTodas las bodegas del CSV origen tienen cobertura completa en el NDJSON.\n"

    report = f"""# Reporte de Auditoria de Bodegas en NDJSON

**Generado:** {timestamp}

## Resumen

Compara el CSV de inventario origen contra el NDJSON generado por el middleware
(una linea = una peticion enviada a VTEX) para identificar bodegas y registros
que no se estan enviando en su totalidad.

## Alertas
{alert_section}
## Estadisticas Generales

| Metrica | Cantidad |
|---------|----------|
| Registros unicos en CSV origen | {stats['csv_total']:,} |
| Registros unicos en NDJSON | {stats['ndjson_total']:,} |
| Registros del CSV enviados (presentes en NDJSON) | {stats['csv_total'] - stats['missing_count']:,} |
| Registros del CSV faltantes en NDJSON | {stats['missing_count']:,} |
| Registros del NDJSON sin origen en CSV | {stats['extra_count']:,} |
| Cobertura global de registros | {global_pct:.1f}% |
| Lineas NDJSON duplicadas (misma SKU+bodega) | {stats['duplicate_count']:,} |
| Lineas NDJSON invalidas/incompletas omitidas | {stats['invalid_count']:,} |
| Registros con cantidad distinta CSV vs NDJSON | {stats['mismatch_count']:,} |

## Cobertura por Bodega

| Bodega | En CSV | En NDJSON | Enviados | Faltantes | % Cobertura | Estado |
|--------|--------|-----------|----------|-----------|--------------|--------|
{coverage_rows}
## Archivos de Salida

- **Cobertura por bodega:** `{coverage_file}`
- **Registros faltantes:** `{missing_file}` - {stats['missing_count']:,} registros del CSV origen que no llegaron al NDJSON
- **Registros extra:** `{extra_file}` - {stats['extra_count']:,} registros del NDJSON sin fila de origen en el CSV

## Logica de Procesamiento

1. Cargar CSV origen y normalizar (SKU, BODEGA, CANTIDAD)
2. Cargar NDJSON del middleware linea por linea y normalizar (_SKUReferenceCode, warehouseId, quantity)
3. Para cada bodega presente en CSV y/o NDJSON, calcular cobertura (registros enviados vs esperados)
4. Clasificar cada bodega: `OK` (100%), `PARCIAL` (parcial), `FALTANTE` (0% de lo esperado), `EXTRA` (en NDJSON sin origen en CSV)
5. Exportar registros CSV sin correspondencia en NDJSON (faltantes) y registros NDJSON sin correspondencia en CSV (extra)

---
*Generado por inventory_ndjson_audit.py - VTEX Integration Tools*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"Reporte generado: {report_file}")


def print_statistics(stats: Dict[str, Any], coverage: List[dict], dry_run: bool = False) -> None:
    sep = '=' * 60
    prefix = "[DRY-RUN] " if dry_run else ""

    faltantes = [r for r in coverage if r['estado'] == 'FALTANTE']
    parciales = [r for r in coverage if r['estado'] == 'PARCIAL']

    logger.info(f"\n{sep}")
    logger.info(f"{prefix}RESULTADOS DE LA AUDITORIA (CSV origen vs NDJSON middleware)")
    logger.info(sep)
    logger.info(f"Registros CSV:          {stats['csv_total']:,}")
    logger.info(f"Registros NDJSON:       {stats['ndjson_total']:,}")
    logger.info(f"Faltantes en NDJSON:    {stats['missing_count']:,}")
    logger.info(f"Extra en NDJSON:        {stats['extra_count']:,}")
    logger.info(f"Mismatches cantidad:    {stats['mismatch_count']:,}")
    logger.info(sep)
    logger.info(f"Bodegas totales:        {len(coverage):,}")
    logger.info(f"Bodegas FALTANTE:       {len(faltantes):,}")
    logger.info(f"Bodegas PARCIAL:        {len(parciales):,}")
    if faltantes:
        logger.info(f"  -> {', '.join(r['warehouseId'] for r in faltantes)}")
    logger.info(sep)


def run_audit(
    source_csv: str, ndjson_file: str, output_prefix: str,
    sku_col: str, warehouse_col: str, quantity_col: str,
    dry_run: bool = False, verbose: bool = False
) -> Dict[str, Any]:
    csv_lookup, csv_per_warehouse, rows_by_key, fieldnames = load_source_csv(
        source_csv, sku_col, warehouse_col, quantity_col
    )
    ndjson_lookup, ndjson_per_warehouse, ndjson_records, duplicate_count, invalid_count = load_ndjson(
        ndjson_file, verbose=verbose
    )

    coverage = compute_bodega_coverage(csv_per_warehouse, ndjson_per_warehouse, csv_lookup, ndjson_lookup)
    mismatch_count = compute_quantity_mismatches(csv_lookup, ndjson_lookup)
    missing_count = sum(1 for key in csv_lookup if key not in ndjson_lookup)
    extra_count = sum(1 for key in ndjson_lookup if key not in csv_lookup)

    stats = {
        'csv_total': len(csv_lookup),
        'ndjson_total': len(ndjson_lookup),
        'missing_count': missing_count,
        'extra_count': extra_count,
        'duplicate_count': duplicate_count,
        'invalid_count': invalid_count,
        'mismatch_count': mismatch_count,
    }

    coverage_file = f"{output_prefix}_bodega_coverage.csv"
    missing_file = f"{output_prefix}_missing_records.csv"
    extra_file = f"{output_prefix}_extra_in_ndjson.csv"
    report_file = f"{output_prefix}_REPORT.md"

    if not dry_run:
        write_bodega_coverage_csv(coverage, coverage_file)
        write_missing_records_csv(csv_lookup, ndjson_lookup, rows_by_key, fieldnames, missing_file)
        write_extra_in_ndjson_csv(ndjson_lookup, csv_lookup, ndjson_records, extra_file)
        generate_report(report_file, coverage, stats, coverage_file, missing_file, extra_file)
    else:
        logger.info("[DRY-RUN] No se escriben archivos de salida")

    print_statistics(stats, coverage, dry_run=dry_run)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Compara el CSV de inventario origen contra el NDJSON generado por el '
                     'middleware para detectar bodegas y registros que no se estan enviando a VTEX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  python3 inventory_ndjson_audit.py source.csv middleware.ndjson bodega_audit
  python3 inventory_ndjson_audit.py source.csv middleware.ndjson bodega_audit --dry-run
  python3 inventory_ndjson_audit.py source.csv middleware.ndjson bodega_audit -v

Archivos de Salida (usando prefijo "bodega_audit"):
  - bodega_audit_bodega_coverage.csv   Cobertura de envio por bodega
  - bodega_audit_missing_records.csv   Registros del CSV que no llegaron al NDJSON
  - bodega_audit_extra_in_ndjson.csv   Registros del NDJSON sin fila de origen en el CSV
  - bodega_audit_REPORT.md             Reporte de estadisticas

Logica:
  1. Cargar CSV origen (columnas: CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA por defecto)
  2. Cargar NDJSON del middleware (_SKUReferenceCode, warehouseId, quantity)
  3. Calcular cobertura por bodega: OK / PARCIAL / FALTANTE / EXTRA
  4. Exportar registros faltantes y extra, y un reporte con la bodega(s) que el cliente reporto como ausente
        '''
    )

    parser.add_argument('source_csv',
                        help='CSV de origen del cliente/ERP con el inventario a enviar')
    parser.add_argument('ndjson_file',
                        help='NDJSON generado por el middleware (una linea = una peticion a VTEX)')
    parser.add_argument('output_prefix',
                        help='Prefijo para archivos de salida')
    parser.add_argument('--sku-column', default='CODIGO SKU',
                        help='Nombre de columna SKU en el CSV origen (default: "CODIGO SKU")')
    parser.add_argument('--warehouse-column', default='CODIGO SUCURSAL',
                        help='Nombre de columna bodega en el CSV origen (default: "CODIGO SUCURSAL")')
    parser.add_argument('--quantity-column', default='EXISTENCIA',
                        help='Nombre de columna cantidad en el CSV origen (default: "EXISTENCIA")')
    parser.add_argument('--dry-run', action='store_true',
                        help='Analizar sin escribir archivos de salida')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar logs detallados de debug (lineas invalidas, duplicados)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Solo mostrar errores y resultado final')

    args = parser.parse_args()

    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    try:
        for label, path in [('CSV origen', args.source_csv), ('NDJSON middleware', args.ndjson_file)]:
            if not os.path.exists(path):
                raise AuditError(f"Archivo {label} no encontrado: {path}")

        sep = '=' * 60
        logger.info(sep)
        logger.info("AUDITORIA DE BODEGAS EN NDJSON (CSV origen vs middleware)")
        if args.dry_run:
            logger.info("[DRY-RUN MODE]")
        logger.info(sep)

        run_audit(
            args.source_csv, args.ndjson_file, args.output_prefix,
            args.sku_column, args.warehouse_column, args.quantity_column,
            dry_run=args.dry_run, verbose=args.verbose
        )

    except AuditError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("\nOperacion cancelada por el usuario")
        sys.exit(130)


if __name__ == '__main__':
    main()
