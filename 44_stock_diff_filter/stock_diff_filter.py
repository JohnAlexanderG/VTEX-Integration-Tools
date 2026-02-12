#!/usr/bin/env python3
"""
Stock Difference Filter

Compares ERP inventory (complete) against VTEX ecommerce inventory to identify
records that need updating. Optionally filters against a previously-processed file.

Usage:
    # Basic: ERP vs VTEX (recommended)
    python3 stock_diff_filter.py <vtex_file> <complete_file> <vtex_inventory_file> <output_prefix>

    # With optional processed file (extra dedup layer)
    python3 stock_diff_filter.py <vtex_file> <complete_file> <vtex_inventory_file> <output_prefix> --processed <file.csv>

Example:
    python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls output
    python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls output --processed uploaded.csv

    Generates:
    - output_to_update.csv: Records needing VTEX updates
    - output_to_update.ndjson: VTEX-ready records for inventory upload
    - output_REPORT.md: Detailed statistics and analysis
"""

import csv
import json
import sys
import os
import argparse
import logging
from datetime import datetime
from collections import Counter
from typing import Dict, Set, Tuple, Optional, List, Any

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

logger = logging.getLogger(__name__)


class StockFilterError(Exception):
    """Custom exception for stock filter errors."""
    pass


def _is_nan(value: Any) -> bool:
    """Check if value is NaN (pandas-aware)."""
    if value is None:
        return True
    if PANDAS_AVAILABLE and pd.isna(value):
        return True
    return False


def _strip_float_suffix(s: str) -> str:
    """Remove .0 suffix from pandas float->string conversion (e.g., '95.0' -> '95')."""
    if s.endswith('.0'):
        try:
            if float(s) == int(float(s)):
                s = str(int(float(s)))
        except (ValueError, OverflowError):
            pass
    return s


def clean_sku(value: Any) -> str:
    """Normalize SKU codes - strip whitespace, preserve leading zeros."""
    if _is_nan(value):
        return ''
    s = str(value).strip()
    s = _strip_float_suffix(s)
    return s


def clean_warehouse(value: Any) -> str:
    """Normalize warehouse codes.

    - Strips whitespace
    - Removes Excel float artifacts (e.g., '95.0' -> '95')
    - Zero-pads purely numeric codes to 3 digits when length < 3 (e.g., '95' -> '095')
      This matches typical warehouse ids like 001, 021, 095, 140, 220.
    """
    if _is_nan(value):
        return ''
    s = str(value).strip()
    s = _strip_float_suffix(s)
    # Normalize purely numeric warehouses to 3 digits (keep longer ids as-is)
    if s.isdigit() and len(s) < 3:
        s = s.zfill(3)
    return s


def clean_quantity(value: Any) -> str:
    """Normalize quantity - strip whitespace, remove leading zeros and float artifacts."""
    if _is_nan(value):
        return ''
    s = str(value).strip()
    try:
        s = str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def _read_tabular_file(file_path: str) -> 'Tuple[pd.DataFrame, Optional[dict]]':
    """Read a tabular file (.xls, .xlsx, or .csv) and return DataFrame and sheet names.

    Selects the appropriate engine based on file extension:
    - .csv  -> pandas read_csv (no extra engine needed)
    - .xls  -> xlrd
    - .xlsx -> openpyxl

    Returns:
        Tuple of (DataFrame, sheets_dict_or_None). sheets is None for CSV files.
    """
    if not PANDAS_AVAILABLE:
        raise StockFilterError(
            "pandas es requerido para leer archivos tabulares.\n"
            "  Instalalo con: pip install pandas"
        )

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.csv':
        try:
            df = pd.read_csv(file_path, dtype=object, encoding='utf-8')
            logger.info(f"  Archivo CSV leido (total filas={len(df):,})")
            return df, None
        except Exception as e:
            raise StockFilterError(f"Error al leer archivo CSV: {e}")

    if ext == '.xlsx':
        if not OPENPYXL_AVAILABLE:
            raise StockFilterError(
                "openpyxl es requerido para leer archivos .xlsx\n"
                "  Instalalo con: pip install openpyxl"
            )
        engine = 'openpyxl'
    else:
        if not XLRD_AVAILABLE:
            raise StockFilterError(
                "xlrd es requerido para leer archivos .xls\n"
                "  Instalalo con: pip install xlrd"
            )
        engine = 'xlrd'

    try:
        sheets = pd.read_excel(file_path, engine=engine, dtype=object, sheet_name=None)
        if not sheets:
            raise StockFilterError(f"No se encontraron hojas en el archivo: {file_path}")
        df = pd.concat(sheets.values(), ignore_index=True)
        logger.info(f"  Hojas leidas: {', '.join(list(sheets.keys()))} (total filas={len(df):,})")
    except StockFilterError:
        raise
    except Exception as e:
        raise StockFilterError(f"Error al leer archivo Excel: {e}")

    return df, sheets


def _warn_xls_truncation(df: 'pd.DataFrame', sheets: Optional[dict]) -> None:
    """Emit warning if .xls file appears truncated by legacy 65,536 row limit."""
    if sheets is not None and len(df) in (65535, 65536) and len(sheets) == 1:
        logger.warning(
            "[ADVERTENCIA] El archivo .xls puede estar truncado por limite de filas (65,536).\n"
            "               Considera exportar a .xlsx/CSV o dividir el export."
        )


def _detect_column(df: 'pd.DataFrame', candidates: List[str], description: str, file_path: str) -> str:
    """Find the first matching column name from a list of candidates.

    Raises StockFilterError if none found.
    """
    for col in candidates:
        if col in df.columns:
            return col
    # Also check prefix match (e.g., '_SkuId' matches '_SkuId (...)' )
    for candidate in candidates:
        for col in df.columns:
            if col.startswith(candidate):
                return col
    raise StockFilterError(
        f"Columna {description} no encontrada en {file_path}\n"
        f"  Se busco: {', '.join(candidates)}\n"
        f"  Columnas disponibles: {', '.join(df.columns)}"
    )


def load_vtex_skus(file_path: str) -> Tuple[Set[str], Dict[str, str]]:
    """Load VTEX SKU reference codes from .xls/.xlsx/.csv export.

    Uses vectorized pandas operations for performance.

    Returns:
        Tuple of (set of SKU codes, dict mapping SKU code -> SkuId).
    """
    if not os.path.isfile(file_path):
        raise StockFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"Cargando SKUs VTEX desde: {file_path}")

    df, sheets = _read_tabular_file(file_path)

    # Detect SKU reference column (supports multiple header formats)
    ref_col = _detect_column(df, ['_SKUReferenceCode', 'SKU reference code'], 'referencia SKU', file_path)
    logger.info(f"  Columna de referencia SKU: '{ref_col}'")

    # Vectorized SKU cleaning
    cleaned_refs = df[ref_col].map(clean_sku)
    valid_mask = cleaned_refs != ''
    skipped = int((~valid_mask).sum())
    vtex_skus: Set[str] = set(cleaned_refs[valid_mask].unique())

    # Detect and map SKU ID column
    sku_id_map: Dict[str, str] = {}
    try:
        sku_id_col = _detect_column(df, ['_SkuId', 'SKU ID'], '_SkuId', file_path)
        cleaned_ids = df[sku_id_col].map(clean_sku)
        id_valid = valid_mask & (cleaned_ids != '')
        # Build map: ref_code -> sku_id (vectorized via zip)
        sku_id_map = dict(zip(cleaned_refs[id_valid], cleaned_ids[id_valid]))
        logger.info(f"  {len(sku_id_map):,} SKUs con _SkuId mapeado (columna: '{sku_id_col}')")
    except StockFilterError:
        logger.warning("  Columna '_SkuId' no encontrada, NDJSON no tendra _SkuId")

    logger.info(f"  {len(vtex_skus):,} SKUs unicos cargados ({skipped:,} vacios omitidos)")
    _warn_xls_truncation(df, sheets)
    if vtex_skus:
        sample = list(vtex_skus)[:5]
        logger.debug(f"  Muestra SKUs: {sample}")
    return vtex_skus, sku_id_map


def load_vtex_inventory(file_path: str) -> Dict[Tuple[str, str], str]:
    """Load current VTEX inventory from .xls/.xlsx/.csv export and build lookup dictionary.

    Uses vectorized pandas operations for performance.

    Returns:
        Dict mapping (ref_id, warehouse_id) -> quantity.
    """
    if not os.path.isfile(file_path):
        raise StockFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"\nCargando inventario VTEX actual desde: {file_path}")

    df, sheets = _read_tabular_file(file_path)

    required_cols = ['RefId', 'WarehouseId', 'TotalQuantity']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise StockFilterError(
            f"Columnas requeridas no encontradas en {file_path}\n"
            f"  Faltantes: {', '.join(missing)}\n"
            f"  Disponibles: {', '.join(df.columns)}"
        )

    # Vectorized cleaning
    ref_ids = df['RefId'].map(clean_sku)
    warehouses = df['WarehouseId'].map(clean_warehouse)
    quantities = df['TotalQuantity'].map(clean_quantity)

    valid_mask = (ref_ids != '') & (warehouses != '')
    skipped = int((~valid_mask).sum())

    # Build lookup dict using vectorized zip
    vtex_inventory: Dict[Tuple[str, str], str] = dict(
        zip(
            zip(ref_ids[valid_mask], warehouses[valid_mask]),
            quantities[valid_mask]
        )
    )

    logger.info(f"  {len(vtex_inventory):,} registros cargados ({skipped:,} incompletos omitidos)")
    _warn_xls_truncation(df, sheets)
    if vtex_inventory:
        sample = list(vtex_inventory.items())[:3]
        logger.debug(f"  Muestra inventario VTEX: {[(k, v) for k, v in sample]}")
    return vtex_inventory


def load_processed_inventory(file_path: str) -> Tuple[Dict[Tuple[str, str], str], int]:
    """Load processed inventory from CSV and build lookup dictionary.

    Returns:
        Tuple of (dict mapping (sku, warehouse) -> quantity, total_records count).
    """
    if not os.path.isfile(file_path):
        raise StockFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"\nCargando inventario procesado desde: {file_path}")

    processed_lookup: Dict[Tuple[str, str], str] = {}
    total_records = 0
    skipped = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        required_cols = ['CODIGO SKU', 'CODIGO SUCURSAL', 'EXISTENCIA']
        if not all(col in (reader.fieldnames or []) for col in required_cols):
            raise StockFilterError(
                f"Columnas requeridas no encontradas en {file_path}\n"
                f"  Requeridas: {', '.join(required_cols)}\n"
                f"  Disponibles: {', '.join(reader.fieldnames or [])}"
            )

        for row in reader:
            total_records += 1
            sku = clean_sku(row.get('CODIGO SKU', ''))
            warehouse = clean_warehouse(row.get('CODIGO SUCURSAL', ''))
            quantity = clean_quantity(row.get('EXISTENCIA', ''))

            if sku and warehouse:
                processed_lookup[(sku, warehouse)] = quantity
            else:
                skipped += 1

    logger.info(
        f"  {len(processed_lookup):,} registros cargados de {total_records:,} filas "
        f"({skipped:,} incompletos omitidos)"
    )
    if processed_lookup:
        sample = list(processed_lookup.items())[:3]
        logger.debug(f"  Muestra procesado: {[(k, v) for k, v in sample]}")
    return processed_lookup, total_records


def _write_ndjson_record(
    nf, sku: str, warehouse: str, quantity: str, sku_id_map: Dict[str, str]
) -> bool:
    """Write a single NDJSON record to file. Returns True if written, False if skipped (no SkuId)."""
    sku_id = sku_id_map.get(sku)
    if sku_id is None:
        return False
    record = {
        "_SkuId": int(sku_id),
        "_SKUReferenceCode": sku,
        "warehouseId": warehouse,
        "quantity": int(quantity),
        "unlimitedQuantity": False
    }
    nf.write(json.dumps(record, ensure_ascii=False) + '\n')
    return True


def compute_stats(
    vtex_skus: Set[str],
    processed_lookup: Dict[Tuple[str, str], str],
    vtex_inventory_lookup: Dict[Tuple[str, str], str],
    counters: Dict[str, int],
    skus_in_output: Counter
) -> Dict[str, Any]:
    """Compute statistics from filter counters."""
    unique_skus = len(skus_in_output)
    to_update = counters['to_update']
    return {
        'total_vtex_skus': len(vtex_skus),
        'total_processed': len(processed_lookup),
        'total_vtex_inventory': len(vtex_inventory_lookup),
        'total_complete': counters['total_complete'],
        'matched_vtex': counters['matched_vtex'],
        'not_in_vtex': counters['not_in_vtex'],
        'omitted_identical': counters['omitted_identical'],
        'omitted_identical_vtex': counters['omitted_identical_vtex'],
        'to_update': to_update,
        'unique_skus': unique_skus,
        'avg_wh': to_update / unique_skus if unique_skus > 0 else 0,
        'max_wh': max(skus_in_output.values()) if skus_in_output else 0,
        'min_wh': min(skus_in_output.values()) if skus_in_output else 0,
        'ndjson_count': counters['ndjson_count'],
        'no_skuid_count': counters['no_skuid_count'],
    }


def filter_complete_inventory(
    vtex_skus: Set[str],
    processed_lookup: Dict[Tuple[str, str], str],
    vtex_inventory_lookup: Dict[Tuple[str, str], str],
    complete_file: str,
    output_prefix: str,
    sku_id_map: Optional[Dict[str, str]] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Filter complete inventory to identify records needing updates.

    Streams matching records directly to CSV and NDJSON files to minimize memory usage.

    Returns:
        Statistics dictionary.
    """
    if not os.path.isfile(complete_file):
        raise StockFilterError(f"Archivo no encontrado: {complete_file}")

    has_processed = bool(processed_lookup)
    logger.info(f"\nProcesando inventario ERP: {complete_file}")
    if has_processed:
        logger.info("Filtrando por SKUs VTEX y comparando con inventario VTEX + procesado...")
    else:
        logger.info("Filtrando por SKUs VTEX y comparando con inventario VTEX...")
    logger.info("Nota: CODIGO SUCURSAL/WarehouseId se normaliza a 3 digitos (ej: 95->095, 1->001).")

    if sku_id_map is None:
        sku_id_map = {}

    output_file = f"{output_prefix}_to_update.csv"
    ndjson_file = f"{output_prefix}_to_update.ndjson"
    report_file = f"{output_prefix}_REPORT.md"

    # Counters
    total_complete = 0
    matched_vtex = 0
    omitted_identical = 0
    omitted_identical_vtex = 0
    not_in_vtex = 0
    update_count = 0
    ndjson_count = 0
    no_skuid_count = 0
    skus_in_output: Counter = Counter()
    logged_first_vtex_mismatch = False

    with open(complete_file, 'r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        # Filter None fieldnames that can appear in malformed CSVs with trailing commas
        fieldnames = [fn for fn in (reader.fieldnames or []) if fn is not None]

        required_cols = ['CODIGO SKU', 'CODIGO SUCURSAL', 'EXISTENCIA']
        if not all(col in fieldnames for col in required_cols):
            raise StockFilterError(
                f"Columnas requeridas no encontradas en {complete_file}\n"
                f"  Requeridas: {', '.join(required_cols)}\n"
                f"  Disponibles: {', '.join(fieldnames)}"
            )

        if dry_run:
            logger.info("[DRY-RUN] Analizando sin escribir archivos de salida...")
            csv_writer = None
            nf = None
        else:
            f_csv = open(output_file, 'w', encoding='utf-8', newline='')
            csv_writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
            csv_writer.writeheader()
            nf = open(ndjson_file, 'w', encoding='utf-8')

        try:
            for row in reader:
                total_complete += 1
                sku = clean_sku(row.get('CODIGO SKU', ''))
                warehouse = clean_warehouse(row.get('CODIGO SUCURSAL', ''))
                quantity = clean_quantity(row.get('EXISTENCIA', ''))

                if total_complete % 100_000 == 0:
                    logger.info(
                        f"  ... {total_complete:,} registros procesados "
                        f"(vtex={matched_vtex:,} omit_proc={omitted_identical:,} "
                        f"omit_vtex={omitted_identical_vtex:,} update={update_count:,})"
                    )

                if not sku or not warehouse:
                    continue

                if sku not in vtex_skus:
                    not_in_vtex += 1
                    continue

                matched_vtex += 1
                key = (sku, warehouse)

                if key in processed_lookup and processed_lookup[key] == quantity:
                    omitted_identical += 1
                    if omitted_identical == 1:
                        logger.debug(f"  [LOG] Primer identico procesado: key={key} qty='{quantity}'")
                    continue

                if key in vtex_inventory_lookup and vtex_inventory_lookup[key] == quantity:
                    omitted_identical_vtex += 1
                    if omitted_identical_vtex == 1:
                        logger.debug(
                            f"  [LOG] Primer identico VTEX: key={key} "
                            f"complete_qty='{quantity}' vtex_qty='{vtex_inventory_lookup[key]}'"
                        )
                    continue

                if not logged_first_vtex_mismatch and key in vtex_inventory_lookup:
                    logger.debug(
                        f"  [LOG] Primer mismatch VTEX: key={key} "
                        f"complete_qty='{quantity}' vtex_qty='{vtex_inventory_lookup[key]}'"
                    )
                    logged_first_vtex_mismatch = True

                # Stream-write: write immediately to CSV and NDJSON (no memory accumulation)
                clean_row = {k: v for k, v in row.items() if k is not None}
                if csv_writer is not None:
                    csv_writer.writerow(clean_row)
                if nf is not None:
                    if _write_ndjson_record(nf, sku, warehouse, quantity, sku_id_map):
                        ndjson_count += 1
                    else:
                        no_skuid_count += 1
                else:
                    # dry-run: still count NDJSON stats
                    if sku_id_map.get(sku) is not None:
                        ndjson_count += 1
                    else:
                        no_skuid_count += 1

                update_count += 1
                skus_in_output[sku] += 1
                if update_count == 1:
                    logger.debug(f"  [LOG] Primer registro a actualizar: sku='{sku}' wh='{warehouse}' qty='{quantity}'")

        finally:
            if not dry_run:
                f_csv.close()
                nf.close()

    logger.info(f"  ... {total_complete:,} registros procesados (completo)")

    logger.info(
        f"\n  Ecuacion: {matched_vtex:,} matched - {omitted_identical:,} ident_proc"
        f" - {omitted_identical_vtex:,} ident_vtex = {update_count:,} a actualizar"
    )

    if not dry_run:
        logger.info(f"\n{update_count:,} registros escritos en: {output_file}")
        logger.info(f"{ndjson_count:,} registros NDJSON en: {ndjson_file}")
        if no_skuid_count > 0:
            logger.info(f"  {no_skuid_count:,} registros omitidos del NDJSON (sin _SkuId)")
    else:
        logger.info(f"\n[DRY-RUN] {update_count:,} registros se habrian escrito")

    # Compute and report statistics
    counters = {
        'total_complete': total_complete,
        'matched_vtex': matched_vtex,
        'not_in_vtex': not_in_vtex,
        'omitted_identical': omitted_identical,
        'omitted_identical_vtex': omitted_identical_vtex,
        'to_update': update_count,
        'ndjson_count': ndjson_count,
        'no_skuid_count': no_skuid_count,
    }
    stats = compute_stats(vtex_skus, processed_lookup, vtex_inventory_lookup, counters, skus_in_output)

    if not dry_run:
        generate_report(report_file, stats, output_file, ndjson_file)
    print_statistics(stats, output_file, report_file, ndjson_file, dry_run=dry_run)

    return stats


def generate_report(
    report_file: str,
    stats: Dict[str, Any],
    output_file: str,
    ndjson_file: str
) -> None:
    """Generate detailed markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _pct(numerator: int, denominator: int) -> float:
        return numerator / denominator * 100 if denominator > 0 else 0

    matched_pct = _pct(stats['matched_vtex'], stats['total_complete'])
    not_vtex_pct = _pct(stats['not_in_vtex'], stats['total_complete'])
    omitted_pct = _pct(stats['omitted_identical'], stats['matched_vtex'])
    omitted_vtex_pct = _pct(stats['omitted_identical_vtex'], stats['matched_vtex'])
    update_pct = _pct(stats['to_update'], stats['matched_vtex'])

    has_processed = stats['total_processed'] > 0
    mode_desc = "Inventario ERP comparado contra inventario VTEX actual"
    if has_processed:
        mode_desc += " y registros ya procesados"
    mode_desc += ".\nSolo se exportan registros nuevos o con cantidades modificadas."

    # Build data sources table dynamically
    sources_rows = f"| SKUs en VTEX | {stats['total_vtex_skus']:,} |\n"
    if has_processed:
        sources_rows += f"| Inventario procesado | {stats['total_processed']:,} |\n"
    sources_rows += f"| Inventario VTEX actual | {stats['total_vtex_inventory']:,} |\n"
    sources_rows += f"| Inventario ERP completo | {stats['total_complete']:,} |"

    # Build diff analysis rows dynamically
    diff_rows = ""
    if has_processed:
        diff_rows += f"| Identicos al procesado (omitidos) | {stats['omitted_identical']:,} | {omitted_pct:.1f}% |\n"
    diff_rows += f"| Identicos al inventario VTEX (omitidos) | {stats['omitted_identical_vtex']:,} | {omitted_vtex_pct:.1f}% |\n"
    diff_rows += f"| A actualizar (nuevos/modificados) | {stats['to_update']:,} | {update_pct:.1f}% |"

    report = f"""# Reporte de Filtrado de Diferencias de Inventario

**Generado:** {timestamp}
**Modo:** {'ERP vs VTEX + dedup procesado' if has_processed else 'ERP vs VTEX (directo)'}

## Resumen

{mode_desc}

## Estadisticas

### Fuentes de Datos

| Fuente | Registros |
|--------|-----------|
{sources_rows}

### Filtrado por SKU VTEX

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Total registros analizados | {stats['total_complete']:,} | 100.0% |
| Con SKU valido en VTEX | {stats['matched_vtex']:,} | {matched_pct:.1f}% |
| SKU no encontrado en VTEX | {stats['not_in_vtex']:,} | {not_vtex_pct:.1f}% |

### Analisis de Diferencias (sobre registros con SKU VTEX)

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
{diff_rows}

### Distribucion de Almacenes en Salida

| Metrica | Valor |
|---------|-------|
| SKUs unicos a actualizar | {stats['unique_skus']:,} |
| Promedio almacenes/SKU | {stats['avg_wh']:.1f} |
| Maximo almacenes para un SKU | {stats['max_wh']} |
| Minimo almacenes para un SKU | {stats['min_wh']} |

## Archivos de Salida

- **CSV:** `{output_file}` - {stats['to_update']:,} registros ({stats['unique_skus']:,} SKUs unicos)
- **NDJSON:** `{ndjson_file}` - {stats['ndjson_count']:,} registros VTEX-ready ({stats['no_skuid_count']:,} omitidos sin _SkuId)

## Logica de Procesamiento

1. Cargar SKUs validos desde VTEX (.xls/.xlsx/.csv)
2. Cargar inventario VTEX actual (.xls/.xlsx/.csv) como lookup
{"3. Cargar inventario ya procesado (.csv) como lookup extra de dedup" if has_processed else "3. (Sin archivo procesado - comparacion directa ERP vs VTEX)"}
4. Para cada registro del inventario ERP completo:
   - Si SKU no existe en VTEX -> omitir
   - Si (SKU, ALMACEN, CANTIDAD) identico al inventario VTEX actual -> omitir
{"   - Si (SKU, ALMACEN, CANTIDAD) identico al procesado -> omitir" if has_processed else ""}
   - Si es nuevo o cantidad diferente -> incluir en salida

---
*Generado por stock_diff_filter.py - VTEX Integration Tools*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"Reporte generado: {report_file}")


def print_statistics(
    stats: Dict[str, Any],
    output_file: str,
    report_file: str,
    ndjson_file: str,
    dry_run: bool = False
) -> None:
    """Print statistics to console."""
    tc = stats['total_complete']
    mv = stats['matched_vtex']

    def _with_pct(value: int, total: int) -> str:
        if total > 0:
            return f"{value:,} ({value/total*100:.1f}%)"
        return f"{value:,}"

    sep = '=' * 60
    prefix = "[DRY-RUN] " if dry_run else ""

    has_processed = stats['total_processed'] > 0

    logger.info(f"\n{sep}")
    logger.info(f"{prefix}RESULTADOS DEL FILTRADO (ERP vs VTEX{'+ procesado' if has_processed else ''})")
    logger.info(sep)
    logger.info(f"SKUs VTEX:              {stats['total_vtex_skus']:,}")
    if has_processed:
        logger.info(f"Inventario procesado:   {stats['total_processed']:,} registros")
    logger.info(f"Inventario VTEX actual: {stats['total_vtex_inventory']:,} registros")
    logger.info(f"Inventario ERP:         {tc:,} registros")
    logger.info(sep)
    logger.info(f"Con SKU VTEX:           {_with_pct(mv, tc)}")
    logger.info(f"Sin SKU VTEX:           {_with_pct(stats['not_in_vtex'], tc)}")
    logger.info(sep)
    if has_processed:
        logger.info(f"Identicos proc (omit): {_with_pct(stats['omitted_identical'], mv)}")
    logger.info(f"Identicos VTEX (omit): {_with_pct(stats['omitted_identical_vtex'], mv)}")
    logger.info(f"A actualizar:           {_with_pct(stats['to_update'], mv)}")
    logger.info(f"  SKUs unicos:          {stats['unique_skus']:,}")
    if stats['unique_skus'] > 0:
        logger.info(f"  Almacenes/SKU:        {stats['avg_wh']:.1f} prom, {stats['max_wh']} max, {stats['min_wh']} min")
    logger.info(sep)
    logger.info(f"NDJSON:                 {stats['ndjson_count']:,} registros")
    if stats['no_skuid_count'] > 0:
        logger.info(f"  Sin _SkuId (omitidos): {stats['no_skuid_count']:,}")
    logger.info(sep)
    if not dry_run:
        logger.info(f"\nArchivos generados:")
        logger.info(f"  {output_file}")
        logger.info(f"  {ndjson_file}")
        logger.info(f"  {report_file}")
    else:
        logger.info(f"\n[DRY-RUN] No se generaron archivos de salida")
    logger.info(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Compara inventario ERP contra VTEX para identificar registros desactualizados',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  # Basico: ERP vs VTEX (recomendado)
  python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls output

  # Con archivo procesado como capa extra de dedup
  python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls output --processed uploaded.csv

  # Dry-run para analizar sin escribir archivos
  python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls output --dry-run

Archivos de Salida (usando prefijo "output"):
  - output_to_update.csv      Registros que necesitan actualizacion
  - output_to_update.ndjson    Registros VTEX-ready para upload
  - output_REPORT.md           Reporte de estadisticas

Formatos soportados:
  - Archivos VTEX: .xls, .xlsx, .csv
  - Archivos ERP/procesado: .csv

Logica:
  1. Cargar SKUs validos desde VTEX (columna _SKUReferenceCode o SKU reference code)
  2. Cargar inventario VTEX actual (columnas RefId, WarehouseId, TotalQuantity)
  3. (Opcional) Cargar inventario ya procesado como capa extra de dedup
  4. Del inventario completo ERP, extraer solo registros donde:
     - El SKU existe en VTEX
     - Y el (SKU, ALMACEN, CANTIDAD) NO es identico al inventario VTEX actual
     - Y (si --processed) NO es identico al ya procesado
        '''
    )

    parser.add_argument('vtex_file',
                        help='Archivo .xls/.xlsx/.csv con SKUs VTEX (columna _SKUReferenceCode o SKU reference code)')
    parser.add_argument('complete_file',
                        help='CSV con inventario completo ERP (CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)')
    parser.add_argument('vtex_inventory_file',
                        help='Archivo .xls/.xlsx/.csv con inventario VTEX actual (RefId, WarehouseId, TotalQuantity)')
    parser.add_argument('output_prefix',
                        help='Prefijo para archivos de salida')
    parser.add_argument('--processed', '-p', dest='processed_file', default=None,
                        help='(Opcional) CSV con inventario ya procesado para dedup extra (CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular procesamiento sin escribir archivos de salida')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar logs detallados de debug (primeros matches, muestras, etc.)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Solo mostrar errores y resultado final')

    args = parser.parse_args()

    # Configure logging based on verbosity flags
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
        # Validate required files exist
        for label, path in [('VTEX SKUs', args.vtex_file),
                            ('Inventario ERP', args.complete_file),
                            ('Inventario VTEX', args.vtex_inventory_file)]:
            if not os.path.exists(path):
                raise StockFilterError(f"Archivo {label} no encontrado: {path}")

        if args.processed_file and not os.path.exists(args.processed_file):
            raise StockFilterError(f"Archivo Procesado no encontrado: {args.processed_file}")

        sep = '=' * 60
        logger.info(sep)
        logger.info("FILTRO DE DIFERENCIAS DE INVENTARIO (ERP vs VTEX)")
        if args.dry_run:
            logger.info("[DRY-RUN MODE]")
        if not args.processed_file:
            logger.info("Modo: ERP vs VTEX (sin archivo procesado)")
        else:
            logger.info("Modo: ERP vs VTEX + dedup procesado")
        logger.info(sep)

        vtex_skus, sku_id_map = load_vtex_skus(args.vtex_file)

        # Load processed inventory only if provided
        processed_lookup: Dict[Tuple[str, str], str] = {}
        if args.processed_file:
            processed_lookup, _ = load_processed_inventory(args.processed_file)
        else:
            logger.info("\nSin archivo procesado (--processed no proporcionado), comparando directo ERP vs VTEX")

        vtex_inventory_lookup = load_vtex_inventory(args.vtex_inventory_file)
        filter_complete_inventory(
            vtex_skus, processed_lookup, vtex_inventory_lookup,
            args.complete_file, args.output_prefix,
            sku_id_map=sku_id_map, dry_run=args.dry_run
        )

    except StockFilterError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("\nOperacion cancelada por el usuario")
        sys.exit(130)


if __name__ == '__main__':
    main()
