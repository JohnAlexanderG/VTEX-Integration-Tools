#!/usr/bin/env python3
"""
Split DynamoDB batch-write JSON into smaller batches (max 25 items each).

Usage:
    python3 split_dynamo_batch.py sku-vtex.json --batch-size 25
"""

import json
import argparse
import os
import math

def main():
    parser = argparse.ArgumentParser(description='Split DynamoDB batch-write JSON into smaller batches')
    parser.add_argument('input_file', help='Input JSON file')
    parser.add_argument('--batch-size', type=int, default=25, help='Items per batch (max 25 for DynamoDB)')
    parser.add_argument('--output-prefix', default='batch', help='Output file prefix')

    args = parser.parse_args()

    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Get table name and items
    table_name = list(data.keys())[0]
    items = data[table_name]

    total_items = len(items)
    total_batches = math.ceil(total_items / args.batch_size)

    print(f"Total items: {total_items}")
    print(f"Batch size: {args.batch_size}")
    print(f"Total batches: {total_batches}")

    base_name = os.path.splitext(args.input_file)[0]

    # Create batches
    for i in range(total_batches):
        start_idx = i * args.batch_size
        end_idx = min(start_idx + args.batch_size, total_items)

        batch_items = items[start_idx:end_idx]
        batch_data = {table_name: batch_items}

        # Zero-padded batch number
        batch_num = str(i + 1).zfill(len(str(total_batches)))
        output_file = f"{base_name}_{args.output_prefix}_{batch_num}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Created {output_file} ({len(batch_items)} items)")

    print(f"\n🚀 To upload all batches:")
    for i in range(total_batches):
        batch_num = str(i + 1).zfill(len(str(total_batches)))
        batch_file = f"{base_name}_{args.output_prefix}_{batch_num}.json"
        print(f"aws dynamodb batch-write-item --request-items file://{batch_file}")

if __name__ == '__main__':
    main()