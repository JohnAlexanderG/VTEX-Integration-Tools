"""
CSV Cleaner Utility

Cleans CSV files by removing trailing whitespace from fields and trailing commas from lines.

Usage:
    python3 27_csv_cleaner/csv_cleaner.py input.csv output.csv
    python3 27_csv_cleaner/csv_cleaner.py input.csv output.csv --encoding utf-8

Examples:
    # Clean a CSV file with default UTF-8 encoding
    python3 27_csv_cleaner/csv_cleaner.py productos.csv productos_clean.csv

    # Specify encoding explicitly
    python3 27_csv_cleaner/csv_cleaner.py data.csv clean.csv --encoding utf-8

Cleaning Operations:
    1. Removes leading and trailing whitespace from each field value
    2. Preserves internal spaces within field values
    3. Removes trailing commas at the end of lines
    4. Removes completely empty rows (all fields empty after cleaning)
    5. Preserves header row and column order

Input Format:
    CSV file with headers in the first row.
    Example input:
        SKU,Precio,Cantidad
        000013    ,280,000000000,
        000014,350,100

Output Format:
    Cleaned CSV file with same structure.
    Example output:
        SKU,Precio,Cantidad
        000013,280,000000000
        000014,350,100
"""

import csv
import argparse
import sys


def clean_field_value(value):
    """
    Clean a single CSV field value by removing leading/trailing whitespace.
    Preserves internal spaces.

    Args:
        value: Field value (string or None)

    Returns:
        Cleaned string value
    """
    if value is None:
        return ''
    return str(value).strip()


def is_empty_row(row):
    """
    Check if a row is completely empty after cleaning.

    Args:
        row: Dictionary representing a CSV row

    Returns:
        True if all fields are empty strings after stripping
    """
    return all(str(v).strip() == '' for v in row.values())


def read_csv_with_headers(file_path, encoding='utf-8'):
    """
    Read CSV file with headers.

    Args:
        file_path: Path to CSV file
        encoding: File encoding (default: utf-8)

    Returns:
        Tuple of (list of rows as dicts, list of header field names)

    Raises:
        SystemExit on file not found or CSV parsing errors
    """
    try:
        print(f"📄 Reading CSV file: {file_path}...")

        with open(file_path, 'r', newline='', encoding=encoding) as f:
            reader = csv.DictReader(f)

            # Get headers
            headers = reader.fieldnames
            if not headers:
                print("❌ Error: CSV file has no headers")
                sys.exit(1)

            # Read all rows
            rows = list(reader)

        print(f"✅ Loaded {len(rows)} rows (+ 1 header row)")
        return rows, headers

    except FileNotFoundError:
        print(f"❌ Error: File '{file_path}' not found")
        sys.exit(1)
    except csv.Error as e:
        print(f"❌ Error parsing CSV file: {e}")
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(f"❌ Error decoding file with {encoding} encoding: {e}")
        print(f"   Try specifying a different encoding with --encoding parameter")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error reading file: {e}")
        sys.exit(1)


def write_cleaned_csv(cleaned_rows, output_path, headers, encoding='utf-8'):
    """
    Write cleaned CSV data to file.

    Args:
        cleaned_rows: List of cleaned row dictionaries
        output_path: Path to output CSV file
        headers: List of header field names
        encoding: File encoding (default: utf-8)

    Raises:
        SystemExit on write errors
    """
    try:
        print(f"\n💾 Writing cleaned CSV to: {output_path}...")

        with open(output_path, 'w', newline='', encoding=encoding) as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(headers)

            # Write data rows
            for row in cleaned_rows:
                # Convert dict to list in header order
                row_values = [row.get(h, '') for h in headers]
                writer.writerow(row_values)

        print(f"✅ Successfully wrote {len(cleaned_rows)} rows")

    except PermissionError:
        print(f"❌ Error: Permission denied writing to '{output_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error writing output file: {e}")
        sys.exit(1)


def main():
    """Main function to handle command-line arguments and orchestrate CSV cleaning."""

    parser = argparse.ArgumentParser(
        description='Clean CSV files by removing whitespace and trailing commas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 27_csv_cleaner/csv_cleaner.py productos.csv productos_clean.csv
    python3 27_csv_cleaner/csv_cleaner.py data.csv clean.csv --encoding utf-8

This script cleans CSV files by:
  - Removing leading/trailing whitespace from field values
  - Preserving internal spaces within values
  - Removing trailing commas from lines (automatic with csv.writer)
  - Removing completely empty rows after cleaning
        """
    )

    parser.add_argument('input_file', help='Path to input CSV file')
    parser.add_argument('output_file', help='Path to output cleaned CSV file')
    parser.add_argument('--encoding', default='utf-8',
                        help='File encoding (default: utf-8)')

    args = parser.parse_args()

    # Read CSV file
    rows, headers = read_csv_with_headers(args.input_file, args.encoding)

    print(f"\n🧹 Cleaning CSV data...")
    print(f"  - Removing leading/trailing whitespace from fields")
    print(f"  - Removing trailing commas from lines")
    print(f"  - Filtering empty rows")

    # Clean and filter rows
    cleaned_rows = []
    empty_rows_removed = 0
    total_fields_cleaned = 0

    for row in rows:
        # Clean all field values
        cleaned_row = {k: clean_field_value(v) for k, v in row.items()}
        total_fields_cleaned += len(cleaned_row)

        # Skip completely empty rows
        if is_empty_row(cleaned_row):
            empty_rows_removed += 1
            continue

        cleaned_rows.append(cleaned_row)

    # Write cleaned CSV
    write_cleaned_csv(cleaned_rows, args.output_file, headers, args.encoding)

    # Print statistics
    input_count = len(rows)
    output_count = len(cleaned_rows)

    print(f"\n📊 Cleaning Statistics:")
    print(f"  Input rows (excluding headers):  {input_count}")
    print(f"  Output rows:                     {output_count}")
    print(f"  Empty rows removed:              {empty_rows_removed}")
    print(f"  Fields cleaned:                  {total_fields_cleaned}")
    print(f"\n✅ CSV cleaning completed successfully!")


if __name__ == '__main__':
    main()
