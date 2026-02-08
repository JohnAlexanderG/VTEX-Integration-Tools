#!/usr/bin/env python3
"""
Compare ERP SKUs vs VTEX SKUs — Find Missing SKUs.

Reads SKU codes from an ERP CSV file (column 'CODIGO SKU') and a VTEX
.xls export (column '_SKUReferenceCode'), then outputs the ERP SKUs
that do NOT exist in VTEX. Matching is exact string comparison after
stripping whitespace (leading zeros are preserved).

Usage:
    python3 generate_sku_range.py <vtex_file.xls> <erp_file.csv> <output.csv>

    # Find ERP SKUs missing from VTEX
    python3 generate_sku_range.py vtex_export.xls erp_inventory.csv missing_skus.csv

Input Formats:
    - VTEX .xls file with column '_SKUReferenceCode'
    - ERP .csv file with column 'CODIGO SKU'

Output Format:
    CSV file with a single column 'CODIGO SKU' containing ERP SKU codes
    not found in the VTEX export.

Dependencies:
    pip install pandas xlrd
"""

import argparse
import csv
import os
import sys

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def load_vtex_skus(file_path):
    """Read a VTEX .xls export and extract _SKUReferenceCode values as strings.

    Args:
        file_path: Path to the .xls file.

    Returns:
        A set of stripped strings representing VTEX SKU reference codes.
    """
    if not PANDAS_AVAILABLE:
        print("Error: pandas and xlrd are required to read .xls files.")
        print("   Install them with: pip install pandas xlrd")
        sys.exit(1)

    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"  Reading VTEX file: {file_path}...")
    df = pd.read_excel(file_path, engine='xlrd', dtype=object)

    if '_SKUReferenceCode' not in df.columns:
        print(f"Error: Column '_SKUReferenceCode' not found in {file_path}")
        print(f"   Available columns: {list(df.columns)}")
        sys.exit(1)

    vtex_skus = set()
    skipped = 0

    for val in df['_SKUReferenceCode']:
        if pd.isna(val):
            skipped += 1
            continue
        stripped = str(val).strip()
        if stripped:
            vtex_skus.add(stripped)
        else:
            skipped += 1

    print(f"  Loaded {len(vtex_skus):,} VTEX SKU codes ({skipped:,} empty values omitted)")
    return vtex_skus


def load_erp_skus(file_path):
    """Read an ERP CSV file and extract unique 'CODIGO SKU' values as strings.

    Args:
        file_path: Path to the .csv file.

    Returns:
        A set of stripped strings representing unique ERP SKU codes.
    """
    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"  Reading ERP file: {file_path}...")

    erp_skus = set()
    skipped = 0
    total_rows = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        if 'CODIGO SKU' not in (reader.fieldnames or []):
            print(f"Error: Column 'CODIGO SKU' not found in {file_path}")
            print(f"   Available columns: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            total_rows += 1
            val = row.get('CODIGO SKU', '').strip()
            if val:
                erp_skus.add(val)
            else:
                skipped += 1

    print(f"  Loaded {len(erp_skus):,} unique ERP SKU codes from {total_rows:,} rows ({skipped:,} empty values omitted)")
    return erp_skus


def save_csv(data, output_path):
    """Write a list of SKU code strings to a CSV file with column 'CODIGO SKU'.

    Args:
        data: List of strings to write.
        output_path: Path to the output CSV file.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"  Created output directory: {output_dir}")

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['CODIGO SKU'])
        writer.writeheader()
        for code in data:
            writer.writerow({'CODIGO SKU': code})

    print(f"  Saved {len(data):,} SKU codes to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Find ERP SKU codes that do not exist in a VTEX export. Exact string matching (leading zeros preserved).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 generate_sku_range.py vtex_export.xls erp_inventory.csv missing_skus.csv
        """
    )
    parser.add_argument('vtex_file', help='.xls file with VTEX SKUs (column "_SKUReferenceCode")')
    parser.add_argument('erp_file', help='.csv file with ERP SKUs (column "CODIGO SKU")')
    parser.add_argument('output_file', help='Output CSV file with ERP SKUs not found in VTEX')

    args = parser.parse_args()

    # Banner
    print(f"{'=' * 70}")
    print(f"  ERP vs VTEX SKU COMPARATOR")
    print(f"{'=' * 70}")
    print(f"  VTEX file:   {args.vtex_file}")
    print(f"  ERP file:    {args.erp_file}")
    print(f"  Output file: {args.output_file}")
    print(f"{'=' * 70}")
    print()

    # Load SKUs from both sources
    vtex_skus = load_vtex_skus(args.vtex_file)
    erp_skus = load_erp_skus(args.erp_file)

    # Compute difference: ERP SKUs not in VTEX
    missing = sorted(erp_skus - vtex_skus)
    already_in_vtex = len(erp_skus) - len(missing)

    # Save output
    print()
    save_csv(missing, args.output_file)

    # Statistics
    print()
    print(f"{'=' * 70}")
    print(f"  STATISTICS")
    print(f"{'=' * 70}")
    print(f"  ERP SKUs (unique):      {len(erp_skus):,}")
    print(f"  VTEX SKUs:              {len(vtex_skus):,}")
    print(f"  Already in VTEX:        {already_in_vtex:,}")
    print(f"  Missing from VTEX:      {len(missing):,}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
