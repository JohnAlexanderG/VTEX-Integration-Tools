#!/usr/bin/env python3
"""
NDJSON Inventory Generator

Extracts _SKUReferenceCode from input NDJSON file and generates inventory records
with random warehouse assignments.

Usage:
    python3 ndjson_inventory_generator.py input.ndjson output.ndjson

Input format:
    {"_SKUReferenceCode": "value", ...other fields...}

Output format:
    {"_SKUReferenceCode": "value", "warehouseId": "021", "quantity": 1000, "unlimitedQuantity": false}
"""

import json
import sys
import random
import argparse
import csv


WAREHOUSE_IDS = ["021", "001", "140", "084", "180", "160", "280", "320",
                 "340", "300", "032", "200", "100", "095", "003", "053", "068"]


def process_ndjson(input_file, output_file):
    """
    Process NDJSON file and generate inventory records.

    Args:
        input_file: Path to input NDJSON file
        output_file: Path to output NDJSON file
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

                # Generate new record
                inventory_record = {
                    "_SKUReferenceCode": sku_ref,
                    "warehouseId": random.choice(WAREHOUSE_IDS),
                    "quantity": 0,
                    "unlimitedQuantity": False
                }

                # Write to output file
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
    print(f"  Processed: {processed_count} records")
    print(f"  Skipped: {skipped_count} records")
    print(f"  Output NDJSON: {output_file}")
    print(f"  Output CSV: {csv_file}")
    if skipped_records:
        print(f"  Log file: {log_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate VTEX inventory records from NDJSON with random warehouse assignments'
    )
    parser.add_argument('input_file', help='Input NDJSON file')
    parser.add_argument('output_file', help='Output NDJSON file')

    args = parser.parse_args()

    try:
        process_ndjson(args.input_file, args.output_file)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()