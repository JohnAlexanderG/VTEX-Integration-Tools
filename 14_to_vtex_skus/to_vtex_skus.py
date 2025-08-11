#!/usr/bin/env python3
"""
Script: transformar productos con estructura de entrada a SKUs de VTEX.

Uso:
  python3 to_vtex_skus.py input.json dimensions.json ean.json output.json

El input debe ser una lista (array) de objetos con al menos los campos:
  - Id
  - Name
  - RefId

El archivo dimensions.json debe contener datos de dimensiones con campos:
  - sku (para matching con RefId)
  - alto (PackagedHeight)
  - largo (PackagedLength)
  - ancho (PackagedWidth)
  - peso (PackagedWeightKg)

El archivo ean.json debe contener datos de EAN con campos:
  - RefId (para matching)
  - EAN (código de barras)

El output es una lista de SKUs con la forma que requiere VTEX para creación:
      {
        "ProductId": <Id>,
        "IsActive": false,
        "ActivateIfPossible": true,
        "Name": <Name>,
        "RefId": <RefId>,
        "Ean": <EAN (solo si existe)>,
        "PackagedHeight": <alto>,
        "PackagedLength": <largo>,
        "PackagedWidth": <ancho>,
        "PackagedWeightKg": <peso>
      }

Si falta alguno de los campos requeridos, el producto se omite y se emite una advertencia.
Las dimensiones se buscan comparando RefId con el campo 'sku' del archivo de dimensiones.
Los códigos EAN se buscan comparando RefId con el campo 'RefId' del archivo de EAN.
Si no se encuentran dimensiones, se usan valores por defecto (0) y se genera un reporte CSV.
Si no se encuentra EAN, el campo se omite del objeto de salida.

Uso adicional:
  python3 to_vtex_skus.py input.json dimensions.json ean.json output.json --defaults-csv sin_dimensiones.csv --no-ean-csv sin_ean.csv
"""

import json
import argparse
import logging
import sys
import csv

REQUIRED_FIELDS = ["Id", "Name", "RefId"]
skus_with_defaults = []  # Global list to track SKUs using default values
skus_without_ean = []    # Global list to track SKUs without EAN

def find_dimensions(product: dict, dimensions_data: dict) -> dict:
    """Find dimensions for a product by matching RefId with sku field in dimensions."""
    ref_id = product.get("RefId", "")
    
    # Look for dimensions where the sku field matches our RefId
    dimensions = None
    if ref_id and ref_id in dimensions_data:
        dimensions = dimensions_data[ref_id]
    
    if dimensions:
        # Convert string values to appropriate numeric types
        try:
            height = float(dimensions.get("alto", 0)) if dimensions.get("alto") else 0
            length = float(dimensions.get("largo", 0)) if dimensions.get("largo") else 0
            width = float(dimensions.get("ancho", 0)) if dimensions.get("ancho") else 0
            weight = float(dimensions.get("peso", 0)) if dimensions.get("peso") else 0
            
            return {
                "PackagedHeight": height,
                "PackagedLength": length,
                "PackagedWidth": width,
                "PackagedWeightKg": weight,
            }
        except (ValueError, TypeError) as e:
            logging.warning(f"Error converting dimensions for product {ref_id}: {e}, using defaults")
            return {
                "PackagedHeight": 0,
                "PackagedLength": 0,
                "PackagedWidth": 0,
                "PackagedWeightKg": 0,
            }
    else:
        # Default values if no dimensions found
        logging.warning(f"No dimensions found for product {ref_id}, using defaults")
        return {
            "PackagedHeight": 0,
            "PackagedLength": 0,
            "PackagedWidth": 0,
            "PackagedWeightKg": 0,
        }


def transform(product: dict, dimensions_data: dict, ean_data: dict) -> dict | None:
    missing = [f for f in REQUIRED_FIELDS if f not in product]
    if missing:
        logging.warning(
            f"Skipping product because missing required fields {missing}: {product.get('RefId', product.get('Id', '<no-id>'))}"
        )
        return None

    dimensions = find_dimensions(product, dimensions_data)
    ref_id = product.get("RefId", "")
    
    # Get EAN from EAN data or None if not found
    ean = ean_data.get(ref_id, None)
    
    # Check if dimensions are defaults (all zeros)
    is_using_defaults = (
        dimensions["PackagedHeight"] == 0 and
        dimensions["PackagedLength"] == 0 and
        dimensions["PackagedWidth"] == 0 and
        dimensions["PackagedWeightKg"] == 0 and
        ref_id not in dimensions_data
    )
    
    sku = {
        "ProductId": product["Id"],
        "IsActive": False,
        "ActivateIfPossible": True,
        "Name": product["Name"],
        "RefId": product["RefId"],
        **dimensions
    }
    
    # Only add EAN if it exists and is not "0"
    if ean and ean != "0":
        sku["Ean"] = ean
    
    # Track SKUs that used default values
    if is_using_defaults:
        skus_with_defaults.append(sku)
    
    # Track SKUs without EAN (when EAN is None or "0")
    if not ean or ean == "0":
        skus_without_ean.append(sku)
    
    return sku


def load_input(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load input JSON '{path}': {e}")
        sys.exit(1)
    if not isinstance(data, list):
        logging.error("Input JSON must be a list (array) of product objects.")
        sys.exit(1)
    return data


def load_dimensions(path: str):
    """Load dimensions data and create lookup dictionary by sku field."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load dimensions JSON '{path}': {e}")
        sys.exit(1)
    
    # Convert to lookup dictionary using 'sku' field as key
    lookup = {}
    if isinstance(data, list):
        for item in data:
            # Use the 'sku' field (lowercase) as the key for lookup
            if "sku" in item:
                lookup[item["sku"]] = item
    elif isinstance(data, dict):
        # If it's already a dict, use it directly
        lookup = data
    else:
        logging.error("Dimensions JSON must be a list or dictionary.")
        sys.exit(1)
    
    logging.info(f"Created dimensions lookup with {len(lookup)} entries")
    return lookup


def load_ean_data(path: str):
    """Load EAN data and create lookup dictionary by RefId field."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load EAN JSON '{path}': {e}")
        sys.exit(1)
    
    # Convert to lookup dictionary using 'RefId' field as key
    lookup = {}
    if isinstance(data, list):
        for item in data:
            # Use the 'RefId' field as the key for lookup
            if "RefId" in item:
                lookup[item["RefId"]] = item.get("EAN", None)
    elif isinstance(data, dict):
        # If it's already a dict, use it directly
        lookup = data
    else:
        logging.error("EAN JSON must be a list or dictionary.")
        sys.exit(1)
    
    logging.info(f"Created EAN lookup with {len(lookup)} entries")
    return lookup


def write_output(skus: list, path: str):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(skus, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to write output JSON '{path}': {e}")
        sys.exit(1)


def write_defaults_csv(skus: list, path: str):
    """Write SKUs that used default dimensions to CSV file."""
    if not skus:
        logging.info("No SKUs used default dimensions - no CSV report needed")
        return
    
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            if skus:
                fieldnames = skus[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(skus)
        logging.info(f"Wrote {len(skus)} SKUs with default dimensions to '{path}'")
    except Exception as e:
        logging.error(f"Failed to write defaults CSV '{path}': {e}")
        sys.exit(1)


def write_no_ean_csv(skus: list, path: str):
    """Write SKUs that don't have EAN codes to CSV file."""
    if not skus:
        logging.info("All SKUs have EAN codes - no CSV report needed")
        return
    
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            if skus:
                fieldnames = skus[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(skus)
        logging.info(f"Wrote {len(skus)} SKUs without EAN codes to '{path}'")
    except Exception as e:
        logging.error(f"Failed to write no-EAN CSV '{path}': {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Transform product list into VTEX SKU JSON format with dimensions and EAN codes."
    )
    parser.add_argument("input", help="Path to input JSON file (list of products).")
    parser.add_argument("dimensions", help="Path to dimensions JSON file.")
    parser.add_argument("ean", help="Path to EAN JSON file.")
    parser.add_argument("output", help="Path to output JSON file (VTEX SKUs).")
    parser.add_argument("--defaults-csv", help="Path to CSV file for products with default dimensions (optional).")
    parser.add_argument("--no-ean-csv", help="Path to CSV file for products without EAN codes (optional).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Clear the global lists at the start
    global skus_with_defaults, skus_without_ean
    skus_with_defaults = []
    skus_without_ean = []

    products = load_input(args.input)
    dimensions_data = load_dimensions(args.dimensions)
    ean_data = load_ean_data(args.ean)
    
    logging.info(f"Loaded {len(products)} products, {len(dimensions_data)} dimension entries, and {len(ean_data)} EAN entries")
    
    skus = []
    for p in products:
        sku = transform(p, dimensions_data, ean_data)
        if sku:
            skus.append(sku)

    write_output(skus, args.output)
    logging.info(f"Converted {len(skus)} SKUs and wrote to '{args.output}'")
    
    # Generate CSV report of SKUs with default dimensions
    if args.defaults_csv:
        write_defaults_csv(skus_with_defaults, args.defaults_csv)
    elif skus_with_defaults:
        # Auto-generate CSV filename if not provided
        csv_path = args.output.replace('.json', '_sin_dimensiones.csv')
        write_defaults_csv(skus_with_defaults, csv_path)
    
    # Generate CSV report of SKUs without EAN codes
    if args.no_ean_csv:
        write_no_ean_csv(skus_without_ean, args.no_ean_csv)
    elif skus_without_ean:
        # Auto-generate CSV filename if not provided
        csv_path = args.output.replace('.json', '_sin_ean.csv')
        write_no_ean_csv(skus_without_ean, csv_path)


if __name__ == "__main__":
    main()
