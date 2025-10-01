#!/usr/bin/env python3
"""
NDJSON Price Generator

Extracts _SKUReferenceCode from input NDJSON file and generates price records
with fixed cost and base prices.

Usage:
    python3 ndjson_price_generator.py input.ndjson output.ndjson

Input format:
    {"_SkuId (Not changeable)":1,"_SKUReferenceCode":"000050","_ProductId (Not changeable)":1}

Output format:
    {"_SKUReferenceCode": "000050", "costPrice": 9000000, "basePrice": 8999999}

Note: In VTEX pricing:
    - costPrice: Cost of the product (typically higher reference price)
    - basePrice: Selling price (current/active price)
"""

import json
import sys
import argparse
import csv


def process_ndjson(input_file, output_file, cost_price=9000000, base_price=8999999):
    """
    Process NDJSON file and generate price records.

    Args:
        input_file: Path to input NDJSON file
        output_file: Path to output NDJSON file
        cost_price: Cost price value (default: 9000000)
        base_price: Base selling price value (default: 8999999)
    """
    processed_count = 0
    skipped_count = 0
    skipped_records = []
    price_records = []

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

                # Generate new price record
                price_record = {
                    "_SKUReferenceCode": sku_ref,
                    "costPrice": cost_price,
                    "basePrice": base_price
                }

                # Write to output file
                outfile.write(json.dumps(price_record, ensure_ascii=False) + '\n')
                price_records.append(price_record)
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
    if price_records:
        with open(csv_file, 'w', encoding='utf-8', newline='') as csvfile:
            fieldnames = ['_SKUReferenceCode', 'costPrice', 'basePrice']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(price_records)

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
        description='Generate VTEX price records from NDJSON with fixed cost and base prices'
    )
    parser.add_argument('input_file', help='Input NDJSON file')
    parser.add_argument('output_file', help='Output NDJSON file')
    parser.add_argument('--cost-price', type=int, default=9000000,
                        help='Cost price value (default: 9000000)')
    parser.add_argument('--base-price', type=int, default=8999999,
                        help='Base selling price value (default: 8999999)')

    args = parser.parse_args()

    try:
        process_ndjson(args.input_file, args.output_file, args.cost_price, args.base_price)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
