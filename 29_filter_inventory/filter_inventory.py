#!/usr/bin/env python3
"""
VTEX Inventory Filter

Filters an inventory CSV to include only products that exist in VTEX.
Matches "_SKUReferenceCode" from VTEX products with "CODIGO SKU" from inventory.

IMPORTANT: Inventory data contains multiple rows per SKU (one per warehouse).
All warehouse records for matched SKUs are preserved in the output.

Usage:
    python3 filter_inventory.py <vtex_products> <inventory_csv> <output_prefix>

    vtex_products: CSV or JSON file with VTEX products (must have "_SKUReferenceCode" field)
    inventory_csv: CSV file with inventory data (must have "CODIGO SKU" field)
    output_prefix: Prefix for output files (will generate multiple files)

Example:
    python3 filter_inventory.py vtex_skus.csv inventory_homesentry.csv output

    Generates:
    - output_matched.csv: Inventory records with matching VTEX SKUs
    - output_vtex_without_inventory.csv: VTEX SKUs without inventory
    - output_inventory_without_sku.csv: Inventory records without VTEX SKUs
    - output_REPORT.md: Detailed statistics report

Input Fields:
    VTEX file: "_SKUReferenceCode" (SKU identifier)
    Inventory file: "CODIGO SKU" (SKU identifier)
                   "CODIGO SUCURSAL" (warehouse/store code)
                   "EXISTENCIA" (stock quantity)

Output:
    - 3 CSV files with matched/unmatched data
    - 1 Markdown report with dual statistics (rows + unique SKUs)

Notes:
    - Each SKU can appear multiple times in inventory (once per warehouse)
    - Matched output includes ALL warehouse records for each SKU
    - Report tracks both total records and unique SKU counts
    - Match is exact string match with preserved leading zeros
"""

import json
import csv
import sys
import argparse
from datetime import datetime
from collections import Counter


def load_vtex_data(file_path):
    """
    Load VTEX SKU data from CSV or JSON file.

    Args:
        file_path: Path to VTEX products file (CSV or JSON)

    Returns:
        tuple: (dict of SKU ID -> full row data, fieldnames list)
    """
    vtex_data = {}
    fieldnames = []

    # Determine file type by extension
    if file_path.lower().endswith('.json'):
        # Load from JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # Handle both list and dict formats
            if isinstance(data, list):
                if data:
                    fieldnames = list(data[0].keys())
                for item in data:
                    if '_SKUReferenceCode' in item:
                        sku_id = str(item['_SKUReferenceCode']).strip()
                        if sku_id:
                            vtex_data[sku_id] = item
            elif isinstance(data, dict):
                for item in data.values():
                    if isinstance(item, dict) and '_SKUReferenceCode' in item:
                        if not fieldnames and item:
                            fieldnames = list(item.keys())
                        sku_id = str(item['_SKUReferenceCode']).strip()
                        if sku_id:
                            vtex_data[sku_id] = item

    else:
        # Load from CSV
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Check if required field exists
            if '_SKUReferenceCode' not in fieldnames:
                print(f"Error: Field '_SKUReferenceCode' not found in {file_path}")
                print(f"Available fields: {', '.join(fieldnames)}")
                sys.exit(1)

            for row in reader:
                sku_id = str(row['_SKUReferenceCode']).strip()
                if sku_id:
                    vtex_data[sku_id] = row

    return vtex_data, fieldnames


def filter_inventory(vtex_file, inventory_file, output_prefix):
    """
    Filter inventory and generate multiple output files.

    Args:
        vtex_file: Path to VTEX products file (CSV or JSON)
        inventory_file: Path to inventory CSV
        output_prefix: Prefix for output files
    """
    print(f"Loading VTEX SKU data from: {vtex_file}")
    vtex_data, vtex_fieldnames = load_vtex_data(vtex_file)
    print(f"Loaded {len(vtex_data)} unique SKU IDs from VTEX")

    print(f"\nProcessing inventory: {inventory_file}")

    matched_inventory = []
    unmatched_inventory = []
    found_sku_ids = set()
    unmatched_sku_ids = set()

    # Track warehouse counts per SKU
    sku_warehouse_counts = Counter()

    # Read inventory
    with open(inventory_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        inventory_fieldnames = reader.fieldnames

        # Check if required field exists
        if 'CODIGO SKU' not in inventory_fieldnames:
            print(f"Error: Field 'CODIGO SKU' not found in {inventory_file}")
            print(f"Available fields: {', '.join(inventory_fieldnames)}")
            sys.exit(1)

        # Filter rows
        for row in reader:
            sku_code = str(row['CODIGO SKU']).strip()

            if sku_code in vtex_data:
                matched_inventory.append(row)
                found_sku_ids.add(sku_code)
                sku_warehouse_counts[sku_code] += 1
            else:
                unmatched_inventory.append(row)
                unmatched_sku_ids.add(sku_code)

    # Find VTEX SKUs without inventory
    vtex_without_inventory = []
    for sku_id, sku_data in vtex_data.items():
        if sku_id not in found_sku_ids:
            vtex_without_inventory.append(sku_data)

    # Generate output filenames
    matched_file = f"{output_prefix}_matched.csv"
    vtex_no_inventory_file = f"{output_prefix}_vtex_without_inventory.csv"
    inventory_no_sku_file = f"{output_prefix}_inventory_without_sku.csv"
    report_file = f"{output_prefix}_REPORT.md"

    # Write matched inventory
    print(f"\nWriting matched inventory to: {matched_file}")
    with open(matched_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=inventory_fieldnames)
        writer.writeheader()
        writer.writerows(matched_inventory)

    # Write VTEX SKUs without inventory
    print(f"Writing VTEX SKUs without inventory to: {vtex_no_inventory_file}")
    with open(vtex_no_inventory_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=vtex_fieldnames)
        writer.writeheader()
        writer.writerows(vtex_without_inventory)

    # Write inventory without VTEX SKUs
    print(f"Writing inventory without VTEX SKUs to: {inventory_no_sku_file}")
    with open(inventory_no_sku_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=inventory_fieldnames)
        writer.writeheader()
        writer.writerows(unmatched_inventory)

    # Calculate statistics
    total_vtex = len(vtex_data)
    vtex_with_inventory = len(found_sku_ids)
    vtex_without_inventory_count = len(vtex_without_inventory)

    total_inventory_rows = len(matched_inventory) + len(unmatched_inventory)
    matched_inventory_rows = len(matched_inventory)
    unmatched_inventory_rows = len(unmatched_inventory)

    total_unique_inventory_skus = len(found_sku_ids) + len(unmatched_sku_ids)
    unique_matched_skus = len(found_sku_ids)
    unique_unmatched_skus = len(unmatched_sku_ids)

    # Warehouse distribution statistics
    avg_warehouses = matched_inventory_rows / unique_matched_skus if unique_matched_skus > 0 else 0
    max_warehouses = max(sku_warehouse_counts.values()) if sku_warehouse_counts else 0
    min_warehouses = min(sku_warehouse_counts.values()) if sku_warehouse_counts else 0

    # Prepare statistics dictionary
    stats = {
        'total_vtex_skus': total_vtex,
        'vtex_with_inventory': vtex_with_inventory,
        'vtex_without_inventory': vtex_without_inventory_count,
        'total_inventory_rows': total_inventory_rows,
        'matched_inventory_rows': matched_inventory_rows,
        'unmatched_inventory_rows': unmatched_inventory_rows,
        'total_unique_inventory_skus': total_unique_inventory_skus,
        'unique_matched_skus': unique_matched_skus,
        'unique_unmatched_skus': unique_unmatched_skus,
        'avg_warehouses': avg_warehouses,
        'max_warehouses': max_warehouses,
        'min_warehouses': min_warehouses
    }

    # Prepare file paths dictionary
    file_paths = {
        'matched_file': matched_file,
        'vtex_no_inventory_file': vtex_no_inventory_file,
        'inventory_no_sku_file': inventory_no_sku_file
    }

    # Generate report
    print(f"Generating report: {report_file}")
    generate_report(
        report_file,
        vtex_file,
        inventory_file,
        stats,
        file_paths
    )

    # Print statistics
    print(f"\n{'='*70}")
    print(f"INVENTORY FILTERING RESULTS")
    print(f"{'='*70}")
    print(f"VTEX SKUs:")
    print(f"  Total in VTEX:               {total_vtex:,}")
    print(f"  With inventory (matched):    {vtex_with_inventory:,} ({vtex_with_inventory/total_vtex*100:.1f}%)")
    print(f"  Without inventory:           {vtex_without_inventory_count:,} ({vtex_without_inventory_count/total_vtex*100:.1f}%)")

    print(f"\nInventory Records:")
    print(f"  Total records:               {total_inventory_rows:,}")
    print(f"  With VTEX SKU (matched):     {matched_inventory_rows:,} ({matched_inventory_rows/total_inventory_rows*100:.1f}%)")
    print(f"  Without VTEX SKU:            {unmatched_inventory_rows:,} ({unmatched_inventory_rows/total_inventory_rows*100:.1f}%)")

    print(f"\nInventory Unique SKUs:")
    print(f"  Total unique SKUs:           {total_unique_inventory_skus:,}")
    print(f"  Matched with VTEX:           {unique_matched_skus:,} ({unique_matched_skus/total_unique_inventory_skus*100:.1f}%)")
    print(f"  Without VTEX match:          {unique_unmatched_skus:,} ({unique_unmatched_skus/total_unique_inventory_skus*100:.1f}%)")

    print(f"\nWarehouse Distribution:")
    print(f"  Avg warehouses per SKU:      {avg_warehouses:.1f}")
    if max_warehouses > 0:
        print(f"  Max warehouses for SKU:      {max_warehouses}")
        print(f"  Min warehouses for SKU:      {min_warehouses}")

    print(f"{'='*70}")
    print(f"\nOutput Files Generated:")
    print(f"  1. {matched_file}")
    print(f"  2. {vtex_no_inventory_file}")
    print(f"  3. {inventory_no_sku_file}")
    print(f"  4. {report_file}")
    print(f"{'='*70}")


def generate_report(report_file, vtex_file, inventory_file, stats, file_paths):
    """
    Generate a detailed markdown report.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Unpack stats
    total_vtex = stats['total_vtex_skus']
    vtex_with_inv = stats['vtex_with_inventory']
    vtex_without_inv = stats['vtex_without_inventory']

    total_inv_rows = stats['total_inventory_rows']
    matched_rows = stats['matched_inventory_rows']
    unmatched_rows = stats['unmatched_inventory_rows']

    total_unique_inv = stats['total_unique_inventory_skus']
    unique_matched = stats['unique_matched_skus']
    unique_unmatched = stats['unique_unmatched_skus']

    avg_warehouses = stats['avg_warehouses']
    max_warehouses = stats['max_warehouses']
    min_warehouses = stats['min_warehouses']

    # Unpack file paths
    matched_file = file_paths['matched_file']
    vtex_no_inventory_file = file_paths['vtex_no_inventory_file']
    inventory_no_sku_file = file_paths['inventory_no_sku_file']

    # Calculate percentages safely
    vtex_with_inv_pct = vtex_with_inv/total_vtex*100 if total_vtex > 0 else 0
    vtex_without_inv_pct = vtex_without_inv/total_vtex*100 if total_vtex > 0 else 0

    matched_rows_pct = matched_rows/total_inv_rows*100 if total_inv_rows > 0 else 0
    unmatched_rows_pct = unmatched_rows/total_inv_rows*100 if total_inv_rows > 0 else 0

    unique_matched_pct = unique_matched/total_unique_inv*100 if total_unique_inv > 0 else 0
    unique_unmatched_pct = unique_unmatched/total_unique_inv*100 if total_unique_inv > 0 else 0

    report = f"""# VTEX Inventory Filter Report

**Generated:** {timestamp}

## Input Files

- **VTEX Products:** `{vtex_file}`
- **Inventory Data:** `{inventory_file}`

## Summary Statistics

### VTEX SKUs Analysis

| Metric | Count | Percentage |
|--------|-------|------------|
| Total VTEX SKUs | {total_vtex:,} | 100.0% |
| SKUs with inventory (matched) | {vtex_with_inv:,} | {vtex_with_inv_pct:.1f}% |
| SKUs without inventory | {vtex_without_inv:,} | {vtex_without_inv_pct:.1f}% |

### Inventory Records Analysis

| Metric | Count | Percentage |
|--------|-------|------------|
| Total inventory records | {total_inv_rows:,} | 100.0% |
| Records with VTEX SKU (matched) | {matched_rows:,} | {matched_rows_pct:.1f}% |
| Records without VTEX SKU | {unmatched_rows:,} | {unmatched_rows_pct:.1f}% |

### Inventory Unique SKUs Analysis

| Metric | Count | Percentage |
|--------|-------|------------|
| Total unique SKUs in inventory | {total_unique_inv:,} | 100.0% |
| Unique SKUs matched with VTEX | {unique_matched:,} | {unique_matched_pct:.1f}% |
| Unique SKUs without VTEX match | {unique_unmatched:,} | {unique_unmatched_pct:.1f}% |

### Warehouse Distribution

| Metric | Value |
|--------|-------|
| Average warehouses per matched SKU | {avg_warehouses:.1f} |
| Max warehouses for single SKU | {max_warehouses} |
| Min warehouses for matched SKU | {min_warehouses} |

## Output Files

### 1. Matched Inventory Records
**File:** `{matched_file}`
**Description:** Inventory records with corresponding VTEX SKUs
**Records:** {matched_rows:,} rows across {unique_matched:,} unique SKUs

These inventory records can be uploaded to VTEX. Each SKU may appear multiple times (once per warehouse location).

### 2. VTEX SKUs Without Inventory
**File:** `{vtex_no_inventory_file}`
**Description:** VTEX SKUs missing inventory data
**Records:** {vtex_without_inv:,} unique SKUs

Action required: Add inventory data for these SKUs across warehouse locations.

### 3. Inventory Records Without VTEX SKUs
**File:** `{inventory_no_sku_file}`
**Description:** Inventory records for products not in VTEX
**Records:** {unmatched_rows:,} rows across {unique_unmatched:,} unique SKUs

Action required: Create these {unique_unmatched:,} products in VTEX before uploading inventory.

## Recommendations

### If VTEX SKUs Without Inventory > 0
- Review the {vtex_without_inv:,} SKUs in `{vtex_no_inventory_file}`
- Add inventory data for these products
- Ensure all warehouse locations are represented
- Re-run the filter to verify completeness

### If Inventory Records Without VTEX SKUs > 0
- Review the {unique_unmatched:,} unique SKUs in `{inventory_no_sku_file}`
- Create these products in VTEX using the product creation workflow (steps 11-15)
- After creation, re-run the filter to match the new inventory

### Data Quality Checks
- Verify warehouse codes in `CODIGO SUCURSAL` match VTEX warehouse IDs
- Check for negative quantities in `EXISTENCIA` field
- Validate SKU code format (leading zeros preserved)

## Matching Logic

- **Match Field (VTEX):** `_SKUReferenceCode`
- **Match Field (Inventory):** `CODIGO SKU`
- **Match Type:** Exact string match (case-sensitive, whitespace trimmed)
- **Duplicate Handling:** Multiple warehouse records per SKU are preserved

## Notes

- Each SKU in inventory can appear multiple times (one per warehouse)
- Matched records include ALL warehouse locations for each SKU
- Use `unique SKU counts` for product-level analysis
- Use `record counts` for warehouse-level analysis

---

*Generated by VTEX Inventory Filter*
"""

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)


def main():
    parser = argparse.ArgumentParser(
        description='Filter inventory records and generate comprehensive reports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 filter_inventory.py vtex_skus.csv inventory.csv output
  python3 filter_inventory.py vtex_products.json inventory.csv results

Output Files (using prefix "output"):
  - output_matched.csv: Inventory records with matching VTEX SKUs
  - output_vtex_without_inventory.csv: VTEX SKUs without inventory
  - output_inventory_without_sku.csv: Inventory records without VTEX SKUs
  - output_REPORT.md: Detailed statistics report

Input Requirements:
  - VTEX file must have "_SKUReferenceCode" field
  - Inventory file must have "CODIGO SKU" field
  - Both files must be UTF-8 encoded

Notes:
  - Each SKU in inventory can appear multiple times (one per warehouse)
  - All warehouse records for matched SKUs are included in output
  - Report includes both record counts and unique SKU counts
        '''
    )

    parser.add_argument('vtex_file', help='VTEX products file (CSV or JSON)')
    parser.add_argument('inventory_file', help='Inventory CSV file')
    parser.add_argument('output_prefix', help='Prefix for output files')

    args = parser.parse_args()

    # Validate input files exist
    import os
    if not os.path.exists(args.vtex_file):
        print(f"Error: VTEX file not found: {args.vtex_file}")
        sys.exit(1)

    if not os.path.exists(args.inventory_file):
        print(f"Error: Inventory file not found: {args.inventory_file}")
        sys.exit(1)

    # Run filter
    filter_inventory(args.vtex_file, args.inventory_file, args.output_prefix)


if __name__ == '__main__':
    main()
