# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python data transformation utilities for VTEX e-commerce platform integration. The project focuses on converting CSV data to JSON and processing product information for VTEX catalog management.

## Key Components

### Core Transformation Scripts (Numbered Workflow)
- **01_csv_to_json/csv_to_json.py**: Main CSV to JSON converter with CLI interface
- **02_data-transform/transform_json_script.py**: JSON-to-JSON transformer that splits composite keys (e.g., "Field1, Field2" becomes separate fields)

### VTEX Integration Tools
- **map_category_ids/**: Maps product categories to VTEX department and category IDs using VTEX API
- **vtex_brandid_matcher/**: Matches product brands to VTEX brand IDs
- **generate_vtex_report/**: Generates reports on product readiness for VTEX catalog creation
- **10._update_vtex_products/**: Bulk updates VTEX products (sets IsActive/IsVisible to False)

### Specialized Converters
- **csv_to_json_marca/**: Extracts SKU and brand information from CSV where TIPO == 'MARCA'
- **transform_json_category/**: Category-specific JSON transformations
- **compare_json_to_csv/**: Compares JSON and CSV data to find missing records (SKU vs RefId comparison)
- **unificar_json/**: Merges multiple JSON files with data reconciliation
- **translate_keys/**: Translates JSON keys from Spanish to English with deduplication logic
- **json_to_csv/**: Simple JSON to CSV converter

## Environment Setup

The project uses Python 3 with virtual environment support:
- Main virtual environment in root `venv/` directory (individual components may have their own venv for compatibility)
- VTEX API credentials stored in root `.env` file (not tracked in git)
- Required environment variables: `X-VTEX-API-AppKey`, `X-VTEX-API-AppToken`, `VTEX_ACCOUNT_NAME`, `VTEX_ENVIRONMENT`

## Common Commands

### Complete Data Processing Workflow
```bash
# 1. Convert CSV to JSON (numbered workflow directory)
python3 01_csv_to_json/csv_to_json.py input.csv data.json --indent 4

# 2. Transform JSON with composite keys (numbered workflow directory)
python3 02_data-transform/transform_json_script.py data.json transformed.json --indent 4

# 3. Map category IDs (requires root .env file with VTEX credentials)
python3 map_category_ids/map_category_ids.py transformed.json categorized.json --endpoint vtexcommercestable

# 4. Match brand IDs (requires root .env file and separate marcas.json file)
python3 vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json categorized.json --account ACCOUNT_NAME

# 5. Generate VTEX readiness report
python3 generate_vtex_report/generate_vtex_report.py final_data.json -o report.md
```

### Specialized Processing Tasks
```bash
# Extract brands from CSV where TIPO == 'MARCA'
python3 csv_to_json_marca/csv_to_json_marca.py input.csv brands.json

# Compare datasets to find missing records (SKU vs RefId)
python3 compare_json_to_csv/compare_json_to_csv.py old_data.json new_data.json missing.csv

# Merge multiple JSON files
python3 unificar_json/unificar_json.py file1.json file2.json merged.json

# Translate keys from Spanish to English
python3 translate_keys/translate_keys.py input.json translated.json --indent 4

# Bulk update VTEX products (set inactive)
python3 10._update_vtex_products/update_vtex_products.py data.json --account ACCOUNT_NAME
```

## Architecture Notes

### Data Flow Pattern
1. **Data Import & Initial Transformation**
   - CSV data → JSON conversion (`01_csv_to_json/csv_to_json.py`)
   - JSON transformation for composite fields (`02_data-transform/transform_json_script.py`)

2. **VTEX API Integration & ID Mapping**
   - Category mapping (`map_category_ids/`) → DepartmentId, CategoryId
   - Brand matching (`vtex_brandid_matcher/`) → BrandId

3. **Data Validation & Reporting**
   - VTEX readiness analysis (`generate_vtex_report/`) → Product classification:
     - Ready to create (has DepartmentId, CategoryId, BrandId)
     - Requires category creation (missing CategoryId but has category name)
     - Cannot create (missing BrandId - critical requirement)

4. **Data Management Operations**
   - Dataset comparison (`compare_json_to_csv/`) for data reconciliation
   - JSON file merging (`unificar_json/`) with conflict resolution
   - Bulk product updates (`10._update_vtex_products/`) for inventory management

### VTEX Integration Logic
- **Category Mapping**: Uses hierarchical path format "Department>Category>Subcategory", converts ">" to "/" for CategoryPath
- **Brand Matching**: Maps SKU to brand name, then brand name to VTEX brand ID via API calls
- **Product Readiness**: Requires non-null DepartmentId, CategoryId, and BrandId for VTEX creation
- **Unicode Normalization**: Handles accents and special characters for accurate text matching

### Data Processing Patterns
- **Composite Key Splitting**: Transforms "Lista de Precios 1, Lista de Precios 2" into separate normalized fields
- **Key Normalization**: Converts field names using regex patterns and camelCase formatting
- **Category Formatting**: Standardizes category hierarchies with proper title casing (e.g., "CATEGORIA>SUBCATEGORIA>LINEA")
- **Data Reconciliation**: Merges old and new datasets based on SKU/RefId matching logic

### File Naming Conventions
- Input files typically named `input.csv`, `input.json`, `data.csv`, `data.json`
- Output files use descriptive names like `output.json`, `data_brandid.json`, `reporte.md`
- Generated reports include timestamps and category logs
- Failed matches exported to both JSON and CSV formats

### Error Handling
- Scripts include comprehensive error reporting with detailed stack traces
- Unicode normalization for text comparison (accents removed using unicodedata)
- Detailed logging for category mapping failures with markdown reports
- CSV export for items that couldn't be processed
- Rate limiting and retry logic for VTEX API calls

## Dependencies

The project uses standard Python libraries plus:
- `requests` for VTEX API calls
- `python-dotenv` for environment variable management
- `unicodedata` for text normalization

No requirements.txt file exists, but dependencies can be inferred from import statements in the scripts.