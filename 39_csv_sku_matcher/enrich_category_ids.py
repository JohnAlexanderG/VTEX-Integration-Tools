#!/usr/bin/env python3
"""
Enrich CSV with missing category IDs using a category lookup table.

This script fills in missing categorieID values by matching the category path
(Categoria>Subcategoria>Linea) against a lookup table from categorias.csv.

Uses prefix matching to handle truncated category names.

Usage:
    python3 enrich_category_ids.py <input.csv> <categories.csv> <output.csv>

Examples:
    python3 enrich_category_ids.py filtered_specs_v2_matched.csv categorias.csv enriched.csv
"""

import argparse
import csv
import sys
import os
import unicodedata


def normalize(text):
    """Normalize text by removing accents, special chars, and converting to lowercase."""
    if not text:
        return ''
    # Replace degree symbol variations
    text = text.replace('°', ' ').replace('�', ' ').replace('\ufffd', ' ')
    # Normalize unicode
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    # Collapse multiple spaces
    text = ' '.join(text.split())
    return text.lower().strip()


def load_category_lookup(file_path):
    """
    Load categorias.csv and create lookup dictionaries.

    Returns:
        tuple: (exact_lookup, prefix_lookup)
        - exact_lookup: dict mapping normalized path -> category ID
        - prefix_lookup: dict mapping prefix (Cat>Subcat) -> list of (full_path, id)
    """
    exact_lookup = {}
    prefix_lookup = {}

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = normalize(row.get('Path', ''))
            if not path:
                continue

            # Get the most specific ID available
            cat_id = (row.get('SubcategorieID', '').strip() or
                     row.get('categorieID', '').strip() or
                     row.get('DepartamentID', '').strip())

            if cat_id:
                exact_lookup[path] = cat_id

                # Also index by prefix (Categoria>Subcategoria)
                parts = path.split('>')
                if len(parts) >= 2:
                    prefix = '>'.join(parts[:2])
                    if prefix not in prefix_lookup:
                        prefix_lookup[prefix] = []
                    prefix_lookup[prefix].append((path, cat_id))

    return exact_lookup, prefix_lookup


def find_category_id(row, exact_lookup, prefix_lookup):
    """
    Find category ID for a row using exact or prefix matching.

    Returns:
        tuple: (category_id, match_type) where match_type is 'exact', 'prefix', or None
    """
    cat = row.get('Categoria', '')
    subcat = row.get('Subcategoria', '')
    linea = row.get('Linea', '')

    # Build normalized path
    full_path = normalize(f'{cat}>{subcat}>{linea}')
    prefix = normalize(f'{cat}>{subcat}')

    # Try exact match first
    if full_path in exact_lookup:
        return exact_lookup[full_path], 'exact'

    # Try prefix match for truncated names
    if prefix in prefix_lookup:
        norm_linea = normalize(linea)
        for lookup_path, cat_id in prefix_lookup[prefix]:
            # Check if the lookup path starts with our path (truncation case)
            lookup_linea = lookup_path.split('>')[-1] if '>' in lookup_path else lookup_path

            # Match if linea is a prefix of lookup_linea (truncated name)
            if lookup_linea.startswith(norm_linea) or norm_linea.startswith(lookup_linea):
                return cat_id, 'prefix'

    return None, None


def make_unique_fieldnames(fieldnames):
    """Handle duplicate column names by appending numeric suffixes."""
    seen = {}
    unique = []

    for name in fieldnames:
        if name in seen:
            seen[name] += 1
            unique.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            unique.append(name)

    return unique


def process_file(input_file, categories_file, output_file):
    """Process input file and enrich with category IDs."""

    # Load category lookup
    print(f"\n   Loading categories from: {categories_file}")
    exact_lookup, prefix_lookup = load_category_lookup(categories_file)
    print(f"   Loaded {len(exact_lookup):,} category paths")

    # Process input file
    print(f"\n   Processing: {input_file}")

    output_rows = []
    stats = {
        'total': 0,
        'already_has_id': 0,
        'enriched_exact': 0,
        'enriched_prefix': 0,
        'not_found': 0
    }
    not_found_paths = set()

    with open(input_file, 'r', encoding='utf-8') as f:
        # Handle duplicate column names
        csv_reader = csv.reader(f)
        original_fieldnames = next(csv_reader)
        fieldnames = make_unique_fieldnames(original_fieldnames)

        reader = csv.DictReader(f, fieldnames=fieldnames)

        for row in reader:
            stats['total'] += 1

            current_id = row.get('categorieID', '').strip()

            if current_id:
                # Already has category ID
                stats['already_has_id'] += 1
                output_rows.append(row)
            else:
                # Try to find category ID
                cat_id, match_type = find_category_id(row, exact_lookup, prefix_lookup)

                if cat_id:
                    row['categorieID'] = cat_id
                    if match_type == 'exact':
                        stats['enriched_exact'] += 1
                    else:
                        stats['enriched_prefix'] += 1
                else:
                    stats['not_found'] += 1
                    cat = row.get('Categoria', '')
                    subcat = row.get('Subcategoria', '')
                    linea = row.get('Linea', '')
                    not_found_paths.add(f'{cat}>{subcat}>{linea}')

                output_rows.append(row)

    # Write output file
    print(f"\n   Writing: {output_file}")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return stats, not_found_paths


def main():
    parser = argparse.ArgumentParser(
        description='Enrich CSV with missing category IDs using a lookup table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 enrich_category_ids.py filtered_specs_v2_matched.csv categorias.csv enriched.csv
        """
    )
    parser.add_argument('input_csv', help='Input CSV file with missing categorieID values')
    parser.add_argument('categories_csv', help='Categories lookup CSV (Path,DepartamentID,categorieID,SubcategorieID)')
    parser.add_argument('output_csv', help='Output CSV file with enriched category IDs')

    args = parser.parse_args()

    # Validate files
    if not os.path.exists(args.input_csv):
        print(f"Error: File '{args.input_csv}' not found")
        sys.exit(1)

    if not os.path.exists(args.categories_csv):
        print(f"Error: File '{args.categories_csv}' not found")
        sys.exit(1)

    print("=" * 70)
    print("Enrich Category IDs")
    print("=" * 70)

    try:
        stats, not_found_paths = process_file(args.input_csv, args.categories_csv, args.output_csv)
    except Exception as e:
        print(f"\n   Error: {e}")
        sys.exit(1)

    # Print summary
    print("\n" + "=" * 70)
    print("   Summary")
    print("=" * 70)
    print(f"   Total rows:              {stats['total']:,}")
    print(f"   Already had categorieID: {stats['already_has_id']:,}")
    print(f"   Enriched (exact match):  {stats['enriched_exact']:,}")
    print(f"   Enriched (prefix match): {stats['enriched_prefix']:,}")
    print(f"   Not found:               {stats['not_found']:,}")
    print("=" * 70)

    if not_found_paths:
        print(f"\n   Paths not found in lookup ({len(not_found_paths)} unique):")
        for path in sorted(not_found_paths)[:5]:
            print(f"      - {path}")
        if len(not_found_paths) > 5:
            print(f"      ... and {len(not_found_paths) - 5} more")

    print(f"\n   Output: {args.output_csv}")
    print("   Done!")


if __name__ == '__main__':
    main()
