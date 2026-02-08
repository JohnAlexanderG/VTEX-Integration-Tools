#!/usr/bin/env python3
"""
Category-Specification Matcher

Matches products with specifications by CategoryId and generates
output based on FieldTypeId conditions.

Input:
    - productos.csv: Product data with categorieID, _ProductId, VALOR DE UND MEDIDA, UNIDAD DE MEDIDA
    - especificaciones.csv: Specification data with CategoryId, FieldId, FieldTypeId

Output:
    - output.csv: Matches with valid Text values
    - output_empty_text.csv: Matches where Text is empty
    - output_no_match.csv: Products without CategoryId match
    - output_report.md: Statistics report

Usage:
    python3 category_specification_matcher.py productos.csv especificaciones.csv -o output.csv
"""

import csv
import argparse
import sys
import os
from datetime import datetime


def clean_header(header):
    """Clean header by removing extra spaces."""
    return header.strip()


def load_csv(filepath):
    """Load CSV file with UTF-8 encoding and clean headers."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Clean headers
            if reader.fieldnames:
                cleaned_fieldnames = [clean_header(h) for h in reader.fieldnames]
            else:
                print(f"Error: No headers found in {filepath}")
                sys.exit(1)

            rows = []
            for row in reader:
                # Map cleaned headers to values
                cleaned_row = {}
                for orig_header, value in row.items():
                    cleaned_header = clean_header(orig_header)
                    cleaned_row[cleaned_header] = value
                rows.append(cleaned_row)

            return rows, cleaned_fieldnames
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        sys.exit(1)


def save_csv(data, filepath, fieldnames):
    """Save data to CSV file with UTF-8 encoding."""
    if not data:
        return

    try:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"  Saved: {filepath} ({len(data)} rows)")
    except Exception as e:
        print(f"Error writing {filepath}: {e}")


def generate_report(results, empty_text, no_match, output_path, products_count, specs_count):
    """Generate markdown report with statistics."""
    report_path = output_path.replace('.csv', '_report.md')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    total_processed = len(results) + len(empty_text)

    report = f"""# Category-Specification Matcher Report

Generated: {timestamp}

## Input Summary
- Products file: {products_count} records
- Specifications file: {specs_count} records

## Results Summary

| Category | Count | Percentage |
|----------|-------|------------|
| Matches with valid Text | {len(results)} | {len(results)/max(total_processed,1)*100:.1f}% |
| Matches with empty Text | {len(empty_text)} | {len(empty_text)/max(total_processed,1)*100:.1f}% |
| Products without match | {len(no_match)} | - |

## Output Files
- `{os.path.basename(output_path)}`: {len(results)} rows (matches with Text)
- `{os.path.basename(output_path).replace('.csv', '_empty_text.csv')}`: {len(empty_text)} rows (matches without Text)
- `{os.path.basename(output_path).replace('.csv', '_no_match.csv')}`: {len(no_match)} rows (no CategoryId match)
"""

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"  Saved: {report_path}")
    except Exception as e:
        print(f"Error writing report: {e}")


def match_and_transform(products, specs):
    """
    Match products with specifications by CategoryId.

    Returns:
        tuple: (results, empty_text, no_match)
    """
    # Build spec lookup by CategoryId
    spec_by_category = {}
    for spec in specs:
        cat_id = spec.get('CategoryId', '').strip()
        if cat_id:
            if cat_id not in spec_by_category:
                spec_by_category[cat_id] = []
            spec_by_category[cat_id].append(spec)

    # Process products - 3 result lists
    results = []      # Matches with valid Text
    empty_text = []   # Matches with empty Text
    no_match = []     # Products without CategoryId match

    for product in products:
        cat_id = product.get('categorieID', '').strip()
        product_id = product.get('_ProductId', '').strip()

        if cat_id not in spec_by_category:
            # No match - save full product for review
            no_match.append(product)
            continue

        for spec in spec_by_category[cat_id]:
            field_type = spec.get('FieldTypeId', '').strip()
            field_id = spec.get('FieldId', '').strip()

            text_value = ''
            if field_type == '4':
                text_value = product.get('VALOR DE UND MEDIDA', '').strip()
            elif field_type == '1':
                text_value = product.get('UNIDAD DE MEDIDA', '').strip()

            row = {
                '_ProductId': product_id,
                'CategoryId': cat_id,
                'FieldId': field_id,
                'Text': text_value
            }

            if text_value:
                results.append(row)
            else:
                empty_text.append(row)

    return results, empty_text, no_match


def main():
    parser = argparse.ArgumentParser(
        description='Match products with specifications by CategoryId',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 category_specification_matcher.py productos.csv especificaciones.csv -o output.csv
        """
    )
    parser.add_argument('productos', help='Products CSV file (with categorieID)')
    parser.add_argument('especificaciones', help='Specifications CSV file (with CategoryId)')
    parser.add_argument('-o', '--output', default='output.csv', help='Output CSV file (default: output.csv)')

    args = parser.parse_args()

    print("\n=== Category-Specification Matcher ===\n")

    # Load files
    print("Loading files...")
    products, prod_headers = load_csv(args.productos)
    specs, spec_headers = load_csv(args.especificaciones)

    print(f"  Products: {len(products)} records")
    print(f"  Specifications: {len(specs)} records")

    # Validate required columns
    print("\nValidating columns...")

    # Check productos.csv columns
    required_prod_cols = ['categorieID', '_ProductId', 'VALOR DE UND MEDIDA', 'UNIDAD DE MEDIDA']
    missing_prod = [col for col in required_prod_cols if col not in prod_headers]
    if missing_prod:
        print(f"  Error: Missing columns in productos file: {missing_prod}")
        print(f"  Available columns: {prod_headers}")
        sys.exit(1)
    print(f"  productos.csv: OK")

    # Check especificaciones.csv columns
    required_spec_cols = ['CategoryId', 'FieldId', 'FieldTypeId']
    missing_spec = [col for col in required_spec_cols if col not in spec_headers]
    if missing_spec:
        print(f"  Error: Missing columns in especificaciones file: {missing_spec}")
        print(f"  Available columns: {spec_headers}")
        sys.exit(1)
    print(f"  especificaciones.csv: OK")

    # Process matching
    print("\nProcessing matches...")
    results, empty_text, no_match = match_and_transform(products, specs)

    print(f"  Matches with Text: {len(results)}")
    print(f"  Matches without Text: {len(empty_text)}")
    print(f"  Products without match: {len(no_match)}")

    # Save output files
    print("\nSaving output files...")

    output_fieldnames = ['_ProductId', 'CategoryId', 'FieldId', 'Text']

    # Main output - matches with valid Text
    save_csv(results, args.output, output_fieldnames)

    # Empty text matches
    empty_text_path = args.output.replace('.csv', '_empty_text.csv')
    save_csv(empty_text, empty_text_path, output_fieldnames)

    # No match products (save with original headers)
    no_match_path = args.output.replace('.csv', '_no_match.csv')
    if no_match:
        save_csv(no_match, no_match_path, prod_headers)

    # Generate report
    generate_report(results, empty_text, no_match, args.output, len(products), len(specs))

    print("\nDone!")


if __name__ == '__main__':
    main()
