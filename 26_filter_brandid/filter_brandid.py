"""
VTEX Brand ID Filter

Filters JSON product data to include only records with a specific BrandId value.

Usage:
    python3 26_filter_brandid/filter_brandid.py input.json output.json
    python3 26_filter_brandid/filter_brandid.py input.json output.json --indent 2

Examples:
    # Filter products with BrandId = 2000000
    python3 26_filter_brandid/filter_brandid.py productos.json filtered.json

    # Custom indentation
    python3 26_filter_brandid/filter_brandid.py data.json result.json --indent 2

Input Format:
    JSON file containing an array of product records or dict with RefId keys.
    Each record should have a "BrandId" field (numeric).

Output Format:
    JSON file with same structure, containing only records where BrandId = 2000000.
    Uses UTF-8 encoding with 4-space indentation by default.
"""

import json
import argparse
import sys


def read_json_data(file_path):
    """
    Read and parse JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data (list or dict)

    Raises:
        SystemExit on file not found or parse errors
    """
    try:
        print(f"📄 Reading input file: {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Determine record count based on structure
        if isinstance(data, list):
            record_count = len(data)
        elif isinstance(data, dict):
            record_count = len(data)
        else:
            print(f"❌ Error: JSON must be a list or dict, got {type(data).__name__}")
            sys.exit(1)

        print(f"✅ Successfully loaded {record_count} records")
        return data

    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error reading file: {e}")
        sys.exit(1)


def filter_by_brandid(data, brand_id=2000000):
    """
    Filter JSON records where BrandId equals the specified value.

    Args:
        data: JSON data (list of records or dict with RefId keys)
        brand_id: BrandId value to filter by (default: 2000000)

    Returns:
        Filtered data with same structure as input

    Raises:
        ValueError if data is not a list or dict
    """
    print(f"\n🔍 Filtering records with BrandId = {brand_id}...")

    if isinstance(data, list):
        # Filter list of records
        filtered = [record for record in data if record.get('BrandId') == brand_id]

    elif isinstance(data, dict):
        # Filter dict with RefId keys
        filtered = {k: v for k, v in data.items() if v.get('BrandId') == brand_id}

    else:
        raise ValueError(f"JSON must be a list or dict, got {type(data).__name__}")

    # Calculate statistics
    input_count = len(data)
    output_count = len(filtered)
    filtered_out = input_count - output_count
    percentage = (output_count / input_count * 100) if input_count > 0 else 0

    print(f"✅ Found {output_count} matching records ({percentage:.1f}% of total)")

    return filtered, input_count, output_count, filtered_out


def save_json_output(data, output_path, indent=4):
    """
    Save filtered data to JSON file.

    Args:
        data: Filtered JSON data
        output_path: Path to output file
        indent: JSON indentation spaces (default: 4)
    """
    try:
        print(f"\n💾 Saving filtered data to {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

        record_count = len(data)
        print(f"✅ Successfully saved {record_count} records")

    except Exception as e:
        print(f"❌ Error writing output file: {e}")
        sys.exit(1)


def main():
    """Main function to handle command-line arguments and orchestrate filtering."""

    parser = argparse.ArgumentParser(
        description='Filter JSON product data by BrandId value (2000000)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 26_filter_brandid/filter_brandid.py productos.json filtered.json
    python3 26_filter_brandid/filter_brandid.py data.json result.json --indent 2

This script filters JSON product records to include only those with BrandId = 2000000.
Input can be a list of records or a dict with RefId keys.
        """
    )

    parser.add_argument('input_file', help='Path to input JSON file')
    parser.add_argument('output_file', help='Path to output JSON file')
    parser.add_argument('--indent', type=int, default=4,
                        help='JSON output indentation (default: 4)')

    args = parser.parse_args()

    # Read input data
    data = read_json_data(args.input_file)

    # Filter by BrandId
    try:
        filtered_data, input_count, output_count, filtered_out = filter_by_brandid(data, brand_id=2000000)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Save filtered data
    save_json_output(filtered_data, args.output_file, args.indent)

    # Print final statistics
    percentage_kept = (output_count / input_count * 100) if input_count > 0 else 0
    percentage_filtered = (filtered_out / input_count * 100) if input_count > 0 else 0

    print(f"\n📊 Filtering Statistics:")
    print(f"  Input records:    {input_count}")
    print(f"  Output records:   {output_count} ({percentage_kept:.1f}%)")
    print(f"  Filtered out:     {filtered_out} ({percentage_filtered:.1f}%)")
    print(f"\n✅ Filtering completed successfully!")


if __name__ == '__main__':
    main()
