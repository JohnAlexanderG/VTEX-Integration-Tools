#!/usr/bin/env python3
"""
Price Difference Filter

Compares ERP price list against VTEX ecommerce prices to identify
records that need updating. Uses a VTEX SKU reference file to map
ERP product codes (codigo producto) to VTEX SKU IDs.

Usage:
    # Basic: compare ERP prices vs VTEX prices
    python3 price_diff_filter.py <vtex_skus_file> <erp_prices_file> <vtex_prices_file> <output_prefix>

    # Dry-run to analyze without writing output files
    python3 price_diff_filter.py <vtex_skus_file> <erp_prices_file> <vtex_prices_file> <output_prefix> --dry-run

Example:
    python3 price_diff_filter.py vtex_skus.xlsx erp_precios.csv vtex_precios.xlsx output
    python3 price_diff_filter.py vtex_skus.xlsx erp_precios.csv vtex_precios.xlsx output --dry-run

    Generates:
    - output_price_diff.csv:   Records with price differences (ERP vs VTEX side-by-side)
    - output_erp_diff.csv:     Records with differences in ERP format (reimportable)
    - output_to_update.ndjson: VTEX-ready records for pricing API
    - output_REPORT.md:        Detailed statistics and analysis

Field Mapping:
    ERP 'Costo'                            -> VTEX 'Cost Price'
    ERP 'Precio Venta'                     -> VTEX 'Base Price'
    ERP 'Precio Lista o Precio Promocion'  -> VTEX 'List Price'
    ERP '% IVA'                            -> Informational only (not used in comparison)
"""

import csv
import json
import sys
import os
import argparse
import logging
from datetime import datetime
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


# ── Exceptions ────────────────────────────────────────────────────────

class PriceFilterError(Exception):
    """Custom exception for price filter errors."""
    pass


# ── Value Cleaning Helpers ────────────────────────────────────────────

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


def clean_price(value: Any) -> Optional[float]:
    """Normalize price values - strip whitespace, convert to float.

    Handles comma as decimal separator (common in Latin America).
    Returns None if value is empty/NaN/invalid.
    """
    if _is_nan(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in ('nan', 'none', '', '-'):
        return None
    # Handle comma as decimal separator only if no dot present
    # If both exist, comma is assumed to be thousands separator (e.g., "1,234.56")
    if ',' in s and '.' not in s:
        s = s.replace(',', '.')
    elif ',' in s and '.' in s:
        s = s.replace(',', '')
    try:
        return float(s)
    except (ValueError, OverflowError):
        return None


def prices_equal(a: Optional[float], b: Optional[float]) -> bool:
    """Compare two prices for exact equality (tolerance = 0.00).

    Both None is considered equal. One None and one not-None is different.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Round to 2 decimal places to avoid floating point artifacts
    return round(a, 2) == round(b, 2)


def _fmt_price(value: Optional[float]) -> str:
    """Format price for display. Returns 'N/A' for None."""
    if value is None:
        return 'N/A'
    return f"{value:.2f}"


def _fmt_price_clean(value: Optional[float]) -> str:
    """Format price preserving integer format. Returns 'N/A' for None."""
    if value is None:
        return 'N/A'
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


# ── File I/O Helpers ──────────────────────────────────────────────────

def _read_tabular_file(file_path: str) -> Tuple['pd.DataFrame', Optional[dict]]:
    """Read a tabular file (.xls, .xlsx, .csv, .tsv) and return DataFrame.

    Selects the appropriate engine based on file extension:
    - .csv/.tsv/.txt -> pandas read_csv (auto-detects separator)
    - .xls           -> xlrd
    - .xlsx          -> openpyxl

    Returns:
        Tuple of (DataFrame, sheets_dict_or_None). sheets is None for CSV/TSV.
    """
    if not PANDAS_AVAILABLE:
        raise PriceFilterError(
            "pandas es requerido para leer archivos tabulares.\n"
            "  Instalalo con: pip install pandas"
        )

    ext = os.path.splitext(file_path)[1].lower()

    if ext in ('.csv', '.tsv', '.txt'):
        try:
            # Auto-detect separator by inspecting first line
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            sep = '\t' if '\t' in first_line else ','
            df = pd.read_csv(file_path, dtype=object, encoding='utf-8', sep=sep)
            kind = 'TSV' if sep == '\t' else 'CSV'
            logger.info(f"  Archivo {kind} leido (total filas={len(df):,})")
            return df, None
        except Exception as e:
            raise PriceFilterError(f"Error al leer archivo CSV/TSV: {e}")

    if ext == '.xlsx':
        if not OPENPYXL_AVAILABLE:
            raise PriceFilterError(
                "openpyxl es requerido para leer archivos .xlsx\n"
                "  Instalalo con: pip install openpyxl"
            )
        engine = 'openpyxl'
    else:
        if not XLRD_AVAILABLE:
            raise PriceFilterError(
                "xlrd es requerido para leer archivos .xls\n"
                "  Instalalo con: pip install xlrd"
            )
        engine = 'xlrd'

    try:
        sheets = pd.read_excel(file_path, engine=engine, dtype=object, sheet_name=None)
        if not sheets:
            raise PriceFilterError(f"No se encontraron hojas en el archivo: {file_path}")
        df = pd.concat(sheets.values(), ignore_index=True)
        logger.info(f"  Hojas leidas: {', '.join(list(sheets.keys()))} (total filas={len(df):,})")
    except PriceFilterError:
        raise
    except Exception as e:
        raise PriceFilterError(f"Error al leer archivo Excel: {e}")

    return df, sheets


def _detect_column(df: 'pd.DataFrame', candidates: List[str], description: str, file_path: str) -> str:
    """Find the first matching column name from a list of candidates.

    Also checks prefix matches (e.g., '_SkuId' matches '_SkuId (Not changeable)').
    Raises PriceFilterError if none found.
    """
    for col in candidates:
        if col in df.columns:
            return col
    # Also check prefix match
    for candidate in candidates:
        for col in df.columns:
            if col.startswith(candidate):
                return col
    raise PriceFilterError(
        f"Columna {description} no encontrada en {file_path}\n"
        f"  Se busco: {', '.join(candidates)}\n"
        f"  Columnas disponibles: {', '.join(df.columns)}"
    )


# ── Data Loading ──────────────────────────────────────────────────────

def load_vtex_skus(file_path: str) -> Dict[str, str]:
    """Load VTEX SKU mapping from .xls/.xlsx/.csv export.

    Supports two header formats:
    - Format A: Product ID, Product Name, SKU ID, SKU name, SKU reference code
    - Format B: _SkuId (Not changeable), _SKUReferenceCode, _ProductId (Not changeable)

    Returns:
        Dict mapping SKU reference code -> SKU ID.
    """
    if not os.path.isfile(file_path):
        raise PriceFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"Cargando SKUs VTEX desde: {file_path}")

    df, sheets = _read_tabular_file(file_path)

    # Detect SKU reference column
    ref_col = _detect_column(
        df,
        ['_SKUReferenceCode', 'SKU reference code'],
        'referencia SKU',
        file_path
    )
    logger.info(f"  Columna de referencia SKU: '{ref_col}'")

    # Detect SKU ID column
    sku_id_col = _detect_column(
        df,
        ['_SkuId', 'SKU ID'],
        'SKU ID',
        file_path
    )
    logger.info(f"  Columna de SKU ID: '{sku_id_col}'")

    # Vectorized cleaning
    cleaned_refs = df[ref_col].map(clean_sku)
    cleaned_ids = df[sku_id_col].map(clean_sku)

    valid_mask = (cleaned_refs != '') & (cleaned_ids != '')
    skipped = int((~valid_mask).sum())

    # Build map: ref_code -> sku_id
    ref_to_skuid: Dict[str, str] = dict(
        zip(cleaned_refs[valid_mask], cleaned_ids[valid_mask])
    )

    logger.info(
        f"  {len(ref_to_skuid):,} mapeos SKU ref -> SKU ID cargados "
        f"({skipped:,} vacios omitidos)"
    )

    if ref_to_skuid:
        sample = list(ref_to_skuid.items())[:5]
        logger.debug(f"  Muestra mapeos: {sample}")

    return ref_to_skuid


def load_erp_prices(file_path: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Load ERP price list from CSV/TSV.

    Expected columns:
        codigo producto, Costo, Precio Venta, % IVA, Precio Lista o Precio Promocion

    Column detection is flexible (case-insensitive, partial match).

    Returns:
        Dict mapping codigo_producto -> {cost, base_price, list_price, iva_pct}
    """
    if not os.path.isfile(file_path):
        raise PriceFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"\nCargando precios ERP desde: {file_path}")

    erp_prices: Dict[str, Dict[str, Optional[float]]] = {}
    total = 0
    skipped_empty = 0
    skipped_duplicate = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        # Auto-detect separator
        first_line = f.readline()
        f.seek(0)
        sep = '\t' if '\t' in first_line else ','

        reader = csv.DictReader(f, delimiter=sep)
        fieldnames = [fn for fn in (reader.fieldnames or []) if fn is not None]

        # Detect columns flexibly (case-insensitive partial matching)
        code_col = None
        cost_col = None
        sale_col = None
        iva_col = None
        list_col = None

        for col in fieldnames:
            col_lower = col.strip().lower()
            if 'codigo' in col_lower and 'producto' in col_lower:
                code_col = col
            elif col_lower in ('costo', 'cost'):
                cost_col = col
            elif 'precio' in col_lower and 'venta' in col_lower:
                sale_col = col
            elif 'iva' in col_lower:
                iva_col = col
            elif 'precio' in col_lower and ('lista' in col_lower or 'promoci' in col_lower):
                list_col = col

        if code_col is None:
            raise PriceFilterError(
                f"Columna 'codigo producto' no encontrada en {file_path}\n"
                f"  Columnas disponibles: {', '.join(fieldnames)}"
            )

        logger.info(f"  Columnas detectadas:")
        logger.info(f"    Codigo:       '{code_col}'")
        logger.info(f"    Costo:        '{cost_col or 'NO ENCONTRADA'}'")
        logger.info(f"    Precio Venta: '{sale_col or 'NO ENCONTRADA'}'")
        logger.info(f"    % IVA:        '{iva_col or 'NO ENCONTRADA'}'")
        logger.info(f"    Precio Lista: '{list_col or 'NO ENCONTRADA'}'")

        for row in reader:
            total += 1
            code = clean_sku(row.get(code_col, ''))

            if not code:
                skipped_empty += 1
                continue

            if code in erp_prices:
                skipped_duplicate += 1
                continue

            erp_prices[code] = {
                'cost': clean_price(row.get(cost_col, '')) if cost_col else None,
                'base_price': clean_price(row.get(sale_col, '')) if sale_col else None,
                'list_price': clean_price(row.get(list_col, '')) if list_col else None,
                'iva_pct': clean_price(row.get(iva_col, '')) if iva_col else None,
            }

    logger.info(f"  {len(erp_prices):,} productos cargados de {total:,} filas")
    if skipped_empty:
        logger.info(f"  {skipped_empty:,} filas sin codigo omitidas")
    if skipped_duplicate:
        logger.info(f"  {skipped_duplicate:,} duplicados omitidos (se usa primera aparicion)")

    if erp_prices:
        sample = list(erp_prices.items())[:3]
        logger.debug(f"  Muestra ERP: {sample}")

    return erp_prices


def load_vtex_prices(file_path: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Load VTEX price list from .xls/.xlsx/.csv/.tsv export.

    Expected columns:
        SKU ID, Cost Price, Base Price, List Price [, Error Code, Error Message]

    Returns:
        Dict mapping sku_id -> {cost, base_price, list_price}
    """
    if not os.path.isfile(file_path):
        raise PriceFilterError(f"Archivo no encontrado: {file_path}")

    logger.info(f"\nCargando precios VTEX desde: {file_path}")

    df, _ = _read_tabular_file(file_path)

    # Detect SKU ID column
    sku_id_col = _detect_column(
        df,
        ['SKU ID', 'SkuId', '_SkuId', 'skuId'],
        'SKU ID',
        file_path
    )

    # Detect price columns flexibly
    cost_col = None
    base_col = None
    list_col = None

    for col in df.columns:
        col_lower = col.strip().lower()
        if 'cost' in col_lower and 'price' in col_lower:
            cost_col = col
        elif 'base' in col_lower and 'price' in col_lower:
            base_col = col
        elif 'list' in col_lower and 'price' in col_lower:
            list_col = col

    logger.info(f"  Columnas detectadas:")
    logger.info(f"    SKU ID:     '{sku_id_col}'")
    logger.info(f"    Cost Price: '{cost_col or 'NO ENCONTRADA'}'")
    logger.info(f"    Base Price: '{base_col or 'NO ENCONTRADA'}'")
    logger.info(f"    List Price: '{list_col or 'NO ENCONTRADA'}'")

    vtex_prices: Dict[str, Dict[str, Optional[float]]] = {}
    skipped = 0

    for _, row in df.iterrows():
        sku_id = clean_sku(row.get(sku_id_col, ''))
        if not sku_id:
            skipped += 1
            continue

        vtex_prices[sku_id] = {
            'cost': clean_price(row.get(cost_col, '')) if cost_col else None,
            'base_price': clean_price(row.get(base_col, '')) if base_col else None,
            'list_price': clean_price(row.get(list_col, '')) if list_col else None,
        }

    logger.info(
        f"  {len(vtex_prices):,} SKUs con precios cargados "
        f"({skipped:,} vacios omitidos)"
    )

    if vtex_prices:
        sample = list(vtex_prices.items())[:3]
        logger.debug(f"  Muestra VTEX precios: {sample}")

    return vtex_prices


# ── Core Comparison ───────────────────────────────────────────────────

def compare_prices(
    ref_to_skuid: Dict[str, str],
    erp_prices: Dict[str, Dict[str, Optional[float]]],
    vtex_prices: Dict[str, Dict[str, Optional[float]]],
    output_prefix: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Compare ERP prices against VTEX prices and generate output files.

    For each ERP product:
    1. Map 'codigo producto' -> 'SKU ID' via VTEX SKUs file
    2. Look up current VTEX prices by SKU ID
    3. Compare: Costo vs Cost Price, Precio Venta vs Base Price,
       Precio Lista vs List Price
    4. Export differences to CSV (side-by-side), ERP-format CSV, and NDJSON

    Returns:
        Statistics dictionary.
    """
    logger.info(f"\nComparando precios ERP vs VTEX...")

    output_csv = f"{output_prefix}_price_diff.csv"
    erp_csv = f"{output_prefix}_erp_diff.csv"
    ndjson_file = f"{output_prefix}_to_update.ndjson"
    report_file = f"{output_prefix}_REPORT.md"

    # Counters
    total_erp = len(erp_prices)
    mapped_to_vtex = 0
    not_in_vtex_skus = 0
    no_vtex_price = 0
    identical = 0
    different = 0
    ndjson_count = 0

    # Track which fields differ
    cost_diffs = 0
    base_diffs = 0
    list_diffs = 0

    csv_fieldnames = [
        'codigo_producto', 'sku_id',
        'erp_costo', 'vtex_cost_price', 'diff_costo',
        'erp_precio_venta', 'vtex_base_price', 'diff_precio_venta',
        'erp_precio_lista', 'vtex_list_price', 'diff_precio_lista',
        'erp_iva_pct', 'campos_diferentes'
    ]

    erp_fieldnames = [
        'codigo producto', 'Costo', 'Precio Venta',
        '% IVA', 'Precio Lista o Precio Promocion'
    ]

    if dry_run:
        logger.info("[DRY-RUN] Analizando sin escribir archivos de salida...")
        f_csv = None
        csv_writer = None
        ef = None
        erp_writer = None
        nf = None
    else:
        f_csv = open(output_csv, 'w', encoding='utf-8', newline='')
        csv_writer = csv.DictWriter(f_csv, fieldnames=csv_fieldnames)
        csv_writer.writeheader()
        ef = open(erp_csv, 'w', encoding='utf-8', newline='')
        erp_writer = csv.DictWriter(ef, fieldnames=erp_fieldnames)
        erp_writer.writeheader()
        nf = open(ndjson_file, 'w', encoding='utf-8')

    try:
        processed = 0
        for code, erp_data in erp_prices.items():
            processed += 1
            if processed % 50_000 == 0:
                logger.info(
                    f"  ... {processed:,}/{total_erp:,} procesados "
                    f"(vtex={mapped_to_vtex:,} ident={identical:,} diff={different:,})"
                )

            sku_id = ref_to_skuid.get(code)
            if sku_id is None:
                not_in_vtex_skus += 1
                continue

            mapped_to_vtex += 1

            vtex_data = vtex_prices.get(sku_id)
            if vtex_data is None:
                no_vtex_price += 1
                # SKU exists in VTEX but has no pricing record - treat as needing update
                vtex_data = {'cost': None, 'base_price': None, 'list_price': None}

            # Compare each price field
            cost_eq = prices_equal(erp_data['cost'], vtex_data['cost'])
            base_eq = prices_equal(erp_data['base_price'], vtex_data['base_price'])
            list_eq = prices_equal(erp_data['list_price'], vtex_data['list_price'])

            if cost_eq and base_eq and list_eq:
                identical += 1
                continue

            # At least one price differs
            different += 1

            diff_fields = []
            if not cost_eq:
                cost_diffs += 1
                diff_fields.append('Costo')
            if not base_eq:
                base_diffs += 1
                diff_fields.append('PrecioVenta')
            if not list_eq:
                list_diffs += 1
                diff_fields.append('PrecioLista')

            # Calculate numeric differences
            def _diff(a: Optional[float], b: Optional[float]) -> str:
                if a is None or b is None:
                    return 'N/A'
                d = round(a - b, 2)
                return f"{d:+.2f}"

            csv_row = {
                'codigo_producto': code,
                'sku_id': sku_id,
                'erp_costo': _fmt_price(erp_data['cost']),
                'vtex_cost_price': _fmt_price(vtex_data['cost']),
                'diff_costo': _diff(erp_data['cost'], vtex_data['cost']),
                'erp_precio_venta': _fmt_price(erp_data['base_price']),
                'vtex_base_price': _fmt_price(vtex_data['base_price']),
                'diff_precio_venta': _diff(erp_data['base_price'], vtex_data['base_price']),
                'erp_precio_lista': _fmt_price(erp_data['list_price']),
                'vtex_list_price': _fmt_price(vtex_data['list_price']),
                'diff_precio_lista': _diff(erp_data['list_price'], vtex_data['list_price']),
                'erp_iva_pct': _fmt_price(erp_data['iva_pct']),
                'campos_diferentes': '|'.join(diff_fields),
            }

            if csv_writer is not None:
                csv_writer.writerow(csv_row)

            if erp_writer is not None:
                erp_writer.writerow({
                    'codigo producto': code,
                    'Costo': _fmt_price_clean(erp_data['cost']),
                    'Precio Venta': _fmt_price_clean(erp_data['base_price']),
                    '% IVA': _fmt_price_clean(erp_data['iva_pct']),
                    'Precio Lista o Precio Promocion': _fmt_price_clean(erp_data['list_price']),
                })

            # Write NDJSON record for VTEX pricing API
            # Format: PUT /api/pricing/prices/{skuId}
            ndjson_record = {
                "skuId": int(sku_id),
                "markup": 0,
            }
            if erp_data['cost'] is not None:
                ndjson_record["costPrice"] = round(erp_data['cost'], 2)
            if erp_data['base_price'] is not None:
                ndjson_record["basePrice"] = round(erp_data['base_price'], 2)
            if erp_data['list_price'] is not None:
                ndjson_record["listPrice"] = round(erp_data['list_price'], 2)

            if nf is not None:
                nf.write(json.dumps(ndjson_record, ensure_ascii=False) + '\n')
            ndjson_count += 1

            if different == 1:
                logger.debug(
                    f"  [LOG] Primer registro diferente: code='{code}' sku='{sku_id}' "
                    f"diffs={diff_fields}"
                )

    finally:
        if f_csv is not None:
            f_csv.close()
        if ef is not None:
            ef.close()
        if nf is not None:
            nf.close()

    # Build statistics
    stats = {
        'total_erp': total_erp,
        'total_vtex_skus': len(ref_to_skuid),
        'total_vtex_prices': len(vtex_prices),
        'mapped_to_vtex': mapped_to_vtex,
        'not_in_vtex_skus': not_in_vtex_skus,
        'no_vtex_price': no_vtex_price,
        'identical': identical,
        'different': different,
        'cost_diffs': cost_diffs,
        'base_diffs': base_diffs,
        'list_diffs': list_diffs,
        'ndjson_count': ndjson_count,
    }

    if not dry_run:
        generate_report(report_file, stats, output_csv, erp_csv, ndjson_file)
        logger.info(f"\n{different:,} registros con diferencias escritos en: {output_csv}")
        logger.info(f"{different:,} registros ERP en: {erp_csv}")
        logger.info(f"{ndjson_count:,} registros NDJSON en: {ndjson_file}")
    else:
        logger.info(f"\n[DRY-RUN] {different:,} registros con diferencias detectados")

    print_statistics(stats, output_csv, erp_csv, report_file, ndjson_file, dry_run=dry_run)

    return stats


# ── Report Generation ─────────────────────────────────────────────────

def generate_report(
    report_file: str,
    stats: Dict[str, Any],
    output_csv: str,
    erp_csv: str,
    ndjson_file: str
) -> None:
    """Generate detailed markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _pct(num: int, den: int) -> float:
        return num / den * 100 if den > 0 else 0

    mapped_pct = _pct(stats['mapped_to_vtex'], stats['total_erp'])
    not_in_vtex_pct = _pct(stats['not_in_vtex_skus'], stats['total_erp'])
    no_price_pct = _pct(stats['no_vtex_price'], stats['mapped_to_vtex'])
    identical_pct = _pct(stats['identical'], stats['mapped_to_vtex'])
    diff_pct = _pct(stats['different'], stats['mapped_to_vtex'])

    report = f"""# Reporte de Diferencias de Precios (ERP vs VTEX)

**Generado:** {timestamp}
**Tolerancia:** Exacta (0.00)

## Resumen

Precios del ERP comparados contra precios actuales en VTEX.
Solo se exportan registros con diferencias de precio.

## Mapeo de Campos

| ERP | VTEX | Descripcion |
|-----|------|-------------|
| Costo | Cost Price | Precio de costo |
| Precio Venta | Base Price | Precio base de venta |
| Precio Lista o Precio Promocion | List Price | Precio de lista / promocional |
| % IVA | _(no aplica)_ | Informativo, no se usa en comparacion |

## Estadisticas

### Fuentes de Datos

| Fuente | Registros |
|--------|-----------|
| Productos ERP (lista de precios) | {stats['total_erp']:,} |
| Mapeos SKU ref -> SKU ID (VTEX) | {stats['total_vtex_skus']:,} |
| SKUs con precios en VTEX | {stats['total_vtex_prices']:,} |

### Filtrado por SKU VTEX

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Total productos ERP | {stats['total_erp']:,} | 100.0% |
| Mapeados a SKU VTEX | {stats['mapped_to_vtex']:,} | {mapped_pct:.1f}% |
| Sin SKU en VTEX | {stats['not_in_vtex_skus']:,} | {not_in_vtex_pct:.1f}% |

### Comparacion de Precios (sobre productos mapeados)

| Metrica | Cantidad | Porcentaje |
|---------|----------|------------|
| Precios identicos (sin cambios) | {stats['identical']:,} | {identical_pct:.1f}% |
| Sin precio en VTEX (nuevos) | {stats['no_vtex_price']:,} | {no_price_pct:.1f}% |
| Con diferencias de precio | {stats['different']:,} | {diff_pct:.1f}% |

### Desglose por Campo de Precio

| Campo | Diferencias | % de registros diferentes |
|-------|-------------|--------------------------|
| Costo (Cost Price) | {stats['cost_diffs']:,} | {_pct(stats['cost_diffs'], stats['different']):.1f}% |
| Precio Venta (Base Price) | {stats['base_diffs']:,} | {_pct(stats['base_diffs'], stats['different']):.1f}% |
| Precio Lista (List Price) | {stats['list_diffs']:,} | {_pct(stats['list_diffs'], stats['different']):.1f}% |

## Archivos de Salida

- **CSV:** `{output_csv}` - {stats['different']:,} registros con diferencias de precio
- **ERP CSV:** `{erp_csv}` - {stats['different']:,} registros en formato ERP (reimportable)
- **NDJSON:** `{ndjson_file}` - {stats['ndjson_count']:,} registros VTEX-ready para pricing API

## Formato NDJSON (Pricing API)

Cada linea del archivo NDJSON tiene el formato para `PUT /api/pricing/prices/{{skuId}}`:

```json
{{"skuId": 12345, "markup": 0, "costPrice": 50.00, "basePrice": 90.00, "listPrice": 100.00}}
```

## Logica de Procesamiento

1. Cargar mapeo SKU reference code -> SKU ID desde VTEX (.xls/.xlsx/.csv)
2. Cargar lista de precios ERP (.csv/.tsv)
3. Cargar lista de precios VTEX actual (.csv/.tsv)
4. Para cada producto del ERP:
   - Mapear `codigo producto` -> `SKU ID` via archivo VTEX SKUs
   - Si no existe en VTEX -> omitir
   - Buscar precios VTEX actuales por SKU ID
   - Comparar Costo vs Cost Price, Precio Venta vs Base Price, Precio Lista vs List Price
   - Si todos los precios son identicos -> omitir
   - Si hay diferencias (o SKU sin precio en VTEX) -> incluir en salida

---
*Generado por price_diff_filter.py - VTEX Integration Tools*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"Reporte generado: {report_file}")


def print_statistics(
    stats: Dict[str, Any],
    output_csv: str,
    erp_csv: str,
    report_file: str,
    ndjson_file: str,
    dry_run: bool = False
) -> None:
    """Print statistics to console."""
    te = stats['total_erp']
    mv = stats['mapped_to_vtex']

    def _with_pct(value: int, total: int) -> str:
        if total > 0:
            return f"{value:,} ({value/total*100:.1f}%)"
        return f"{value:,}"

    sep = '=' * 60
    prefix = "[DRY-RUN] " if dry_run else ""

    logger.info(f"\n{sep}")
    logger.info(f"{prefix}RESULTADOS DE COMPARACION DE PRECIOS (ERP vs VTEX)")
    logger.info(sep)
    logger.info(f"Productos ERP:          {te:,}")
    logger.info(f"Mapeos SKU VTEX:        {stats['total_vtex_skus']:,}")
    logger.info(f"Precios VTEX:           {stats['total_vtex_prices']:,}")
    logger.info(sep)
    logger.info(f"Mapeados a VTEX:        {_with_pct(mv, te)}")
    logger.info(f"Sin SKU en VTEX:        {_with_pct(stats['not_in_vtex_skus'], te)}")
    logger.info(sep)
    logger.info(f"Precios identicos:      {_with_pct(stats['identical'], mv)}")
    logger.info(f"Sin precio VTEX:        {_with_pct(stats['no_vtex_price'], mv)}")
    logger.info(f"Con diferencias:        {_with_pct(stats['different'], mv)}")
    logger.info(f"  Costo diffs:          {stats['cost_diffs']:,}")
    logger.info(f"  Precio Venta diffs:   {stats['base_diffs']:,}")
    logger.info(f"  Precio Lista diffs:   {stats['list_diffs']:,}")
    logger.info(sep)
    logger.info(f"NDJSON:                 {stats['ndjson_count']:,} registros")
    logger.info(sep)
    if not dry_run:
        logger.info(f"\nArchivos generados:")
        logger.info(f"  {output_csv}")
        logger.info(f"  {erp_csv}")
        logger.info(f"  {ndjson_file}")
        logger.info(f"  {report_file}")
    else:
        logger.info(f"\n[DRY-RUN] No se generaron archivos de salida")
    logger.info(sep)


# ── CLI Entry Point ───────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Compara precios ERP contra VTEX para identificar diferencias de precio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Ejemplos:
  # Basico: comparar precios ERP vs VTEX
  python3 price_diff_filter.py vtex_skus.xlsx erp_precios.csv vtex_precios.csv output

  # Dry-run para analizar sin escribir archivos
  python3 price_diff_filter.py vtex_skus.xlsx erp_precios.csv vtex_precios.csv output --dry-run

Archivos de Salida (usando prefijo "output"):
  - output_price_diff.csv      Registros con diferencias de precio (ERP vs VTEX)
  - output_erp_diff.csv        Registros con diferencias en formato ERP (reimportable)
  - output_to_update.ndjson    Registros VTEX-ready para pricing API
  - output_REPORT.md           Reporte de estadisticas

Mapeo de Campos:
  ERP 'Costo'                            -> VTEX 'Cost Price'
  ERP 'Precio Venta'                     -> VTEX 'Base Price'
  ERP 'Precio Lista o Precio Promocion'  -> VTEX 'List Price'

Formatos soportados:
  - Archivo VTEX SKUs: .xls, .xlsx, .csv
  - Archivo ERP precios: .csv, .tsv
  - Archivo VTEX precios: .xls, .xlsx, .csv, .tsv

Logica:
  1. Cargar mapeo SKU ref -> SKU ID desde archivo VTEX SKUs
  2. Cargar lista de precios ERP (por codigo producto)
  3. Cargar lista de precios VTEX (por SKU ID)
  4. Mapear codigo producto ERP -> SKU ID -> precios VTEX
  5. Comparar cada campo de precio y exportar diferencias
        '''
    )

    parser.add_argument(
        'vtex_skus_file',
        help='Archivo .xls/.xlsx/.csv con SKUs VTEX '
             '(columnas: _SKUReferenceCode + _SkuId, o SKU reference code + SKU ID)'
    )
    parser.add_argument(
        'erp_prices_file',
        help='CSV/TSV con lista de precios ERP '
             '(columnas: codigo producto, Costo, Precio Venta, %% IVA, '
             'Precio Lista o Precio Promocion)'
    )
    parser.add_argument(
        'vtex_prices_file',
        help='Archivo .xls/.xlsx/.csv/.tsv con lista de precios VTEX '
             '(columnas: SKU ID, Cost Price, Base Price, List Price)'
    )
    parser.add_argument(
        'output_prefix',
        help='Prefijo para archivos de salida '
             '(genera: {prefix}_price_diff.csv, {prefix}_erp_diff.csv, '
             '{prefix}_to_update.ndjson, {prefix}_REPORT.md)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Simular procesamiento sin escribir archivos de salida'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Mostrar logs detallados de debug (muestras, primer match, etc.)'
    )
    parser.add_argument(
        '--quiet', '-q', action='store_true',
        help='Solo mostrar errores y resultado final'
    )

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
        for label, path in [('VTEX SKUs', args.vtex_skus_file),
                            ('Precios ERP', args.erp_prices_file),
                            ('Precios VTEX', args.vtex_prices_file)]:
            if not os.path.exists(path):
                raise PriceFilterError(f"Archivo {label} no encontrado: {path}")

        sep = '=' * 60
        logger.info(sep)
        logger.info("FILTRO DE DIFERENCIAS DE PRECIOS (ERP vs VTEX)")
        if args.dry_run:
            logger.info("[DRY-RUN MODE]")
        logger.info(sep)

        # Step 1: Load VTEX SKU mapping (ref code -> sku id)
        ref_to_skuid = load_vtex_skus(args.vtex_skus_file)

        # Step 2: Load ERP prices
        erp_prices = load_erp_prices(args.erp_prices_file)

        # Step 3: Load VTEX current prices
        vtex_prices = load_vtex_prices(args.vtex_prices_file)

        # Step 4: Compare and generate output
        compare_prices(
            ref_to_skuid, erp_prices, vtex_prices,
            args.output_prefix, dry_run=args.dry_run
        )

    except PriceFilterError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("\nOperacion cancelada por el usuario")
        sys.exit(130)


if __name__ == '__main__':
    main()
