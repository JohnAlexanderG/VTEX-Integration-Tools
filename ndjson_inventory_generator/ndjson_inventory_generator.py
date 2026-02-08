#!/usr/bin/env python3
"""
NDJSON Inventory Generator

Extracts _SKUReferenceCode from input NDJSON file and generates inventory records.
Supports two modes: inventory (random warehouse) and reset (all warehouses with quantity 0).

Usage:
    # Inventory mode (default): one record per SKU with random warehouse
    python3 ndjson_inventory_generator.py input.ndjson output.ndjson --mode inventory --quantity 100

    # Reset mode: one record per SKU per warehouse with quantity 0
    python3 ndjson_inventory_generator.py input.ndjson output.ndjson --mode reset

Input format:
    {"_SKUReferenceCode": "value", ...other fields...}

Output format (inventory mode):
    {"_SKUReferenceCode": "value", "warehouseId": "021", "quantity": 100, "unlimitedQuantity": false}

Output format (reset mode - generates N_SKUs x N_warehouses records):
    {"_SKUReferenceCode": "value", "warehouseId": "021", "quantity": 0, "unlimitedQuantity": false}
    {"_SKUReferenceCode": "value", "warehouseId": "001", "quantity": 0, "unlimitedQuantity": false}
    ... (one record per warehouse)
"""

import json
import sys
import random
import argparse
import csv


WAREHOUSE_IDS = ["021", "001", "140", "084", "180", "160", "280", "320", "340", "300", "032", "200", "100", "095", "003", "053", "068", "220"]

def process_ndjson(input_file, output_file, mode='inventory', quantity=100):
    """
    Process NDJSON file and generate inventory records.

    Args:
        input_file: Path to input NDJSON file
        output_file: Path to output NDJSON file
        mode: 'inventory' (one record per SKU, random warehouse) or 'reset' (all warehouses, quantity 0)
        quantity: Quantity for inventory mode (ignored in reset mode)
    """
    processed_count = 0
    skipped_count = 0
    skipped_records = []
    inventory_records = []

    # Generate log file name based on output file
    log_file = output_file.replace('.ndjson', '_skipped.log')
    csv_file = output_file.replace('.ndjson', '.csv')

    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:

        for line_number, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)

                # Extract _SKUReferenceCode
                sku_ref = record.get('_SKUReferenceCode')

                if not sku_ref:
                    error_msg = f"Line {line_number}: Missing _SKUReferenceCode"
                    print(f"Warning: {error_msg}")
                    skipped_records.append({
                        'line': line_number,
                        'reason': 'Missing _SKUReferenceCode',
                        'data': record
                    })
                    skipped_count += 1
                    continue

                # Generate records based on mode
                if mode == 'reset':
                    # Reset mode: one record per warehouse with quantity 0
                    for warehouse_id in WAREHOUSE_IDS:
                        inventory_record = {
                            "_SKUReferenceCode": sku_ref,
                            "warehouseId": warehouse_id,
                            "quantity": 0,
                            "unlimitedQuantity": False
                        }
                        outfile.write(json.dumps(inventory_record, ensure_ascii=False) + '\n')
                        inventory_records.append(inventory_record)
                    processed_count += 1
                else:
                    # Inventory mode: one record per SKU with random warehouse
                    inventory_record = {
                        "_SKUReferenceCode": sku_ref,
                        "warehouseId": random.choice(WAREHOUSE_IDS),
                        "quantity": quantity,
                        "unlimitedQuantity": False
                    }
                    outfile.write(json.dumps(inventory_record, ensure_ascii=False) + '\n')
                    inventory_records.append(inventory_record)
                    processed_count += 1

            except json.JSONDecodeError as e:
                error_msg = f"Line {line_number}: Invalid JSON - {e}"
                print(f"Error: {error_msg}")
                skipped_records.append({
                    'line': line_number,
                    'reason': f'Invalid JSON: {str(e)}',
                    'data': line
                })
                skipped_count += 1
                continue

    # Write CSV file
    if inventory_records:
        with open(csv_file, 'w', encoding='utf-8', newline='') as csvfile:
            fieldnames = ['_SKUReferenceCode', 'warehouseId', 'quantity', 'unlimitedQuantity']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(inventory_records)

    # Write skipped records log
    if skipped_records:
        with open(log_file, 'w', encoding='utf-8') as logfile:
            logfile.write(f"Skipped Records Log\n")
            logfile.write(f"{'='*80}\n\n")
            logfile.write(f"Total skipped: {skipped_count}\n")
            logfile.write(f"Input file: {input_file}\n")
            logfile.write(f"Output file: {output_file}\n\n")
            logfile.write(f"{'='*80}\n\n")

            for idx, record in enumerate(skipped_records, 1):
                logfile.write(f"[{idx}] Line {record['line']}\n")
                logfile.write(f"Reason: {record['reason']}\n")
                logfile.write(f"Data: {json.dumps(record['data'], ensure_ascii=False, indent=2)}\n")
                logfile.write(f"{'-'*80}\n\n")

    print(f"\n✓ Processing complete")
    print(f"  Mode: {mode}")
    print(f"  SKUs processed: {processed_count}")
    print(f"  Records generated: {len(inventory_records)}")
    if mode == 'reset':
        print(f"  Warehouses: {len(WAREHOUSE_IDS)}")
    else:
        print(f"  Quantity per record: {quantity}")
    print(f"  Skipped: {skipped_count} records")
    print(f"  Output NDJSON: {output_file}")
    print(f"  Output CSV: {csv_file}")
    if skipped_records:
        print(f"  Log file: {log_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate VTEX inventory records from NDJSON'
    )
    parser.add_argument('input_file', help='Input NDJSON file')
    parser.add_argument('output_file', help='Output NDJSON file')
    parser.add_argument('--mode', choices=['inventory', 'reset'], default='inventory',
                        help='inventory: one record per SKU with random warehouse. reset: one record per SKU per warehouse with quantity 0 (default: inventory)')
    parser.add_argument('--quantity', type=int, default=100,
                        help='Quantity for inventory mode, ignored in reset mode (default: 100)')

    args = parser.parse_args()

    try:
        process_ndjson(args.input_file, args.output_file, args.mode, args.quantity)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()