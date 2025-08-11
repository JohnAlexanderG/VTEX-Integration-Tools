#!/usr/bin/env python3
"""
CSV to JSON Status Filter

This script compares a CSV file (containing StatusCode and SKU columns) with a JSON file,
filtering JSON records where StatusCode is not 404 or 500 and SKU matches between both files.

Usage:
    python3 csv_json_status_filter.py input.csv data.json output.json

Arguments:
    input.csv   - CSV file with StatusCode and SKU columns
    data.json   - JSON file with data to filter
    output.json - Output file with filtered JSON records

The script will:
1. Read the CSV file and extract StatusCode and SKU columns
2. Filter records where StatusCode is not equal to 404 or 500
3. Read the JSON file and match records by SKU
4. Export matching JSON records to the output file
"""

import csv
import json
import argparse
import sys
from typing import Dict, List, Any, Set


def read_csv_status_sku(csv_file: str) -> Set[str]:
    """
    Read CSV file and extract SKUs where StatusCode is not 404 or 500
    
    Args:
        csv_file: Path to the CSV file
        
    Returns:
        Set of SKUs with valid status codes (not 404 or 500)
    """
    valid_skus = set()
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            # Find StatusCode and SKU columns (case-insensitive)
            status_column = None
            sku_column = None
            
            for col in reader.fieldnames:
                if col.lower() == 'statuscode':
                    status_column = col
                elif col.lower() == 'sku':
                    sku_column = col
            
            if not status_column or not sku_column:
                print(f"Error: CSV file must contain 'StatusCode' and 'SKU' columns (case-insensitive)")
                print(f"Found columns: {reader.fieldnames}")
                sys.exit(1)
            
            for row in reader:
                status_code = row.get(status_column, '').strip()
                sku = row.get(sku_column, '').strip()
                
                if sku and status_code not in ['404', '500']:
                    valid_skus.add(sku)
                    
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)
    
    return valid_skus


def read_json_data(json_file: str) -> List[Dict[str, Any]]:
    """
    Read JSON file and return data as list
    
    Args:
        json_file: Path to the JSON file
        
    Returns:
        List of JSON records
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
            # Return data as is - let filter function handle structure
            return data
            
    except FileNotFoundError:
        print(f"Error: JSON file '{json_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)


def filter_json_by_sku(json_data, valid_skus: Set[str]) -> Dict[str, Any]:
    """
    Filter JSON records by matching SKUs
    
    Args:
        json_data: JSON data (could be list or dict)
        valid_skus: Set of valid SKUs from CSV
        
    Returns:
        Filtered JSON data maintaining original structure
    """
    if isinstance(json_data, list):
        # Handle list format
        filtered_data = []
        for record in json_data:
            sku_value = None
            sku_fields = ['SKU', 'RefId', 'sku', 'refId', 'Sku', 'ref_id']
            
            for field in sku_fields:
                if field in record:
                    sku_value = str(record[field]).strip()
                    break
            
            if sku_value and sku_value in valid_skus:
                filtered_data.append(record)
        return filtered_data
    
    elif isinstance(json_data, dict):
        # Handle dict format where keys are SKUs
        filtered_data = {}
        for sku, records in json_data.items():
            if sku in valid_skus:
                filtered_data[sku] = records
        return filtered_data
    
    else:
        return json_data


def save_json_output(data, output_file: str, indent: int = 4):
    """
    Save filtered data to JSON file
    
    Args:
        data: Data to save
        output_file: Output file path
        indent: JSON indentation
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=indent)
            
        print(f"✅ Filtered data saved to '{output_file}'")
        if isinstance(data, dict):
            print(f"📊 Total filtered SKUs: {len(data)}")
        elif isinstance(data, list):
            print(f"📊 Total filtered records: {len(data)}")
        else:
            print(f"📊 Data filtered and saved")
        
    except Exception as e:
        print(f"Error saving output file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Filter JSON records based on CSV StatusCode and SKU matching',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 csv_json_status_filter.py status.csv products.json filtered_products.json
    python3 csv_json_status_filter.py --indent 2 status.csv data.json output.json
        """
    )
    
    parser.add_argument('csv_file', help='Input CSV file with StatusCode and SKU columns')
    parser.add_argument('json_file', help='Input JSON file with data to filter')
    parser.add_argument('output_file', help='Output JSON file for filtered records')
    parser.add_argument('--indent', type=int, default=4, help='JSON output indentation (default: 4)')
    
    args = parser.parse_args()
    
    print(f"🔍 Reading CSV file: {args.csv_file}")
    valid_skus = read_csv_status_sku(args.csv_file)
    print(f"📋 Found {len(valid_skus)} valid SKUs (StatusCode not 404 or 500)")
    
    print(f"📖 Reading JSON file: {args.json_file}")
    json_data = read_json_data(args.json_file)
    if isinstance(json_data, dict):
        print(f"📊 Total JSON SKUs: {len(json_data)}")
    elif isinstance(json_data, list):
        print(f"📊 Total JSON records: {len(json_data)}")
    else:
        print(f"📊 JSON data loaded")
    
    print("🔄 Filtering JSON records by SKU matching...")
    filtered_data = filter_json_by_sku(json_data, valid_skus)
    
    save_json_output(filtered_data, args.output_file, args.indent)
    
    print(f"✨ Process completed successfully!")
    if isinstance(json_data, dict) and isinstance(filtered_data, dict):
        print(f"📈 Filtering efficiency: {len(filtered_data)}/{len(json_data)} SKUs matched")
    elif isinstance(json_data, list) and isinstance(filtered_data, list):
        print(f"📈 Filtering efficiency: {len(filtered_data)}/{len(json_data)} records matched")
    else:
        print(f"📈 Filtering completed")


if __name__ == "__main__":
    main()