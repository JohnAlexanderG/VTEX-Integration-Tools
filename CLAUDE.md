# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python data transformation utilities for VTEX e-commerce platform integration. The project follows a sequential numbered workflow architecture for converting CSV product data to VTEX-ready format with comprehensive API integration, validation, and full catalog creation workflows.

## Architecture Overview

### Sequential Workflow Design
The codebase implements a microservice-style architecture with numbered directories representing a complete e-commerce catalog creation pipeline:

1. **Data Import & Transformation** (01-03): CSV ingestion, field normalization, category processing
2. **Data Unification & Validation** (04-05): Dataset merging, missing record detection
3. **VTEX API Integration** (06-08): Category mapping, brand ID resolution using VTEX APIs
4. **Validation & Operations** (09-11): Product readiness analysis, bulk updates, VTEX product formatting
5. **Catalog Creation Workflow** (12-15): Complete product and SKU creation in VTEX
6. **Media & Asset Management** (16-18): SKU image handling, file management, content operations
7. **Utility Operations** (19-23): Data filtering, format conversion, specialized transformations
8. **Category Hierarchy Creation** (24): Automated VTEX category structure creation from flat data

### Extended Data Flow Pattern
```
CSV Data → JSON Conversion → Field Transformation → Category Processing → 
Data Unification → VTEX API Mapping → Validation → Product Creation →
SKU Creation → Media Upload → Asset Management → Final Verification
```

## Quick Start for Claude Code

**Most Common Tasks**:
1. **Create category structure**: Use step 24 to create complete category hierarchy before products
2. **Process new CSV data**: Start at step 01 and follow the numbered sequence
3. **Add new products to VTEX**: Use steps 12-15 for complete catalog creation
4. **Upload images**: Use steps 16-17 for media management
5. **Generate reports**: Use step 09 for product readiness analysis

**Essential Commands**:
- `python3 [script] --help` - Get usage help for any script
- Check `.env` file exists and has VTEX credentials before API operations
- All scripts expect UTF-8 encoding and 4-space JSON indentation

## Environment Setup

**Required Environment Variables** (root `.env` file):
- `X-VTEX-API-AppKey`: VTEX API application key
- `X-VTEX-API-AppToken`: VTEX API application token  
- `VTEX_ACCOUNT_NAME`: VTEX account name
- `VTEX_ENVIRONMENT`: VTEX environment (default: vtexcommercestable)

**Python Environment**:
- Python 3.6+ with virtual environment in root `venv/` directory
- Individual components may have separate venv for compatibility (16, 18)
- Main dependencies: `requests`, `python-dotenv`, `unicodedata`
- Additional system dependencies: `fonttools` and `brotli` for font conversion (19+)
- No requirements.txt - dependencies inferred from imports per script

**Virtual Environment Setup**:
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or venv\Scripts\activate on Windows
pip install requests python-dotenv
```

## Command Reference

### Complete Data Processing Workflow
```bash
# Data Preparation Pipeline (01-05)
python3 01_csv_to_json/csv_to_json.py input.csv data.json --indent 4
python3 02_data-transform/transform_json_script.py data.json transformed.json --indent 4
python3 03_transform_json_category/transform_json_category.py transformed.json categorized.json
python3 04_unificar_json/unificar_json.py old_data.json new_data.json unified.json
python3 05_compare_json_to_csv/compare_json_to_csv.py old_data.json new_data.json missing.csv

# VTEX API Integration (06-08)
python3 06_map_category_ids/map_category_ids.py unified.json categorized.json
python3 07_csv_to_json_marca/csv_to_json_marca.py marcas.csv marcas.json
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json categorized.json

# Validation & Formatting (09-11)
python3 09_generate_vtex_report/generate_vtex_report.py final_data.json -o report.md
python3 10._update_vtex_products/update_vtex_products.py data.json
python3 11_vtex_product_format_create/vtex_product_formatter.py data.json

# VTEX Catalog Creation (12-15)
python3 12_vtex_product_create/vtex_product_create.py formatted_products.json
python3 13_extract_json_response/extract_response.py successful_products.json
python3 14_to_vtex_skus/to_vtex_skus.py response_data.json sku_data.json
python3 15_vtex_sku_create/vtex_sku_create.py vtex_skus.json

# Media & Asset Management (16-18)
python3 16_merge_sku_images/merge_sku_images.py products.json images.csv
python3 17_upload_sku_images/upload_sku_images.py sku_images.json
python3 18_delete_sku_files/delete_sku_files.py sku_list.json

# Category Hierarchy Creation (24)
python3 24_vtex_category_creator/vtex_category_creator.py category_data.json --dry-run  # Test first
python3 24_vtex_category_creator/vtex_category_creator.py category_data.json  # Create for real
```

### Utility Commands
```bash
# Data conversion utilities
python3 01_csv_to_json/xlsb_to_csv.py input.xlsb output.csv
python3 translate_keys/translate_keys.py input.json translated.json --indent 4
python3 json_to_csv/json_to_csv.py input.json output.csv
python3 19_csv_json_status_filter/csv_json_status_filter.py input.csv output.json

# Specialized extraction and mapping
python3 extract_refid_ean/extract_refid_ean.py data.json sku_ean.json
python3 16.2_refid_to_skuid/refid_to_skuid_mapper.py data.json mapping.json

# Font conversion utility
python3 tranform_font-ttf-woff/ttf2woff2_converter.py fonts/ woff2-fonts/

# SKU filtering utility
python3 filtrar_sku/filtrar_sku.py archivo1.json archivo2.json  # Filters pricing data based on existing SKU references

# DynamoDB CSV to JSON conversion
python3 43_dynamodb_to_json/dynamodb_to_json.py input.csv output.json --indent 4
python3 43_dynamodb_to_json/dynamodb_to_json.py input.csv output.json --vtex-data-column my_column  # Custom column name
cat export.csv | python3 43_dynamodb_to_json/dynamodb_to_json.py - - -i 4  # Pipeline mode
```

### Testing and Validation
```bash
# Test single image upload before batch processing
python3 17_upload_sku_images/test_single_upload.py sku_id image_url

# Validate environment setup
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✓ Environment loaded' if all([os.getenv('X-VTEX-API-AppKey'), os.getenv('X-VTEX-API-AppToken'), os.getenv('VTEX_ACCOUNT_NAME')]) else '✗ Missing VTEX credentials')"

# Check JSON file structure
python3 -c "import json, sys; data=json.load(open(sys.argv[1])); print(f'Records: {len(data)}, Keys: {list(data[0].keys()) if data else []}')" file.json
```

## Key Architectural Patterns

### Data Transformation Patterns
- **Composite Key Splitting**: `"Field1, Field2": "Value1, Value2"` → separate normalized fields
- **Unicode Normalization**: Removes accents using unicodedata for accurate matching
- **Field Name Normalization**: Spanish → English with camelCase and regex patterns
- **Category Path Transformation**: `"Category>Subcategory"` → `"Category/Subcategory"` for VTEX format

### API Integration Architecture
- **Centralized Credentials**: All VTEX API tools read from root `.env` automatically
- **Endpoint Construction**: Dynamic URLs using account name and environment variables
- **Rate Limiting Control**: 1-second delays, exponential backoff, retry mechanisms
- **Error Resilience**: Comprehensive error reporting with markdown logs and CSV exports
- **Unicode Text Matching**: Accent removal and case normalization for API lookups

### VTEX Catalog Creation Pipeline
- **Product Creation**: `/api/catalog/pvt/product` endpoint with formatted product data
- **Response Extraction**: Parse successful creation responses for Product IDs
- **SKU Generation**: Transform product responses into VTEX SKU format
- **SKU Creation**: `/api/catalog/pvt/stockkeepingunit` endpoint for individual SKUs
- **Media Upload**: `/api/catalog/pvt/stockkeepingunit/{sku}/file` for image associations

### Error Handling & Validation
- **Multi-Format Exports**: Failed cases exported to both JSON and CSV formats
- **Timestamped Reports**: Markdown logs with creation timestamps and batch tracking
- **Detailed Logging**: Emoji indicators, grouped error analysis, success statistics
- **Data Reconciliation**: SKU vs RefId comparison with conflict resolution
- **Product Classification**: Three-tier readiness analysis for VTEX catalog creation
- **Graceful Failures**: Scripts continue processing after individual record failures
- **Retry Logic**: Exponential backoff for API rate limiting and temporary failures

## Data Structure Evolution

### Product Data Lifecycle
1. **Raw CSV**: Spanish field names, composite values, category hierarchies
2. **Normalized JSON**: English fields, split values, cleaned data
3. **Categorized JSON**: Added CategoryPath with "/" separators, problematic entries flagged
4. **Unified JSON**: Merged old/new datasets, duplicate resolution, missing records identified
5. **VTEX-Ready JSON**: DepartmentId, CategoryId, BrandId mapped from VTEX APIs
6. **Classification Report**: Products categorized as ready/requires-creation/cannot-create
7. **VTEX Product Format**: Formatted for VTEX product creation API endpoint
8. **Created Products**: VTEX API responses with ProductId assignments
9. **SKU Generation**: Product responses transformed to SKU creation format
10. **Created SKUs**: VTEX SKU creation responses with SkuId assignments
11. **Media Integration**: SKU images merged and uploaded to VTEX catalog

### Key Field Mappings
- `SKU` → `RefId` (VTEX product identifier)
- `Categoría` → `CategoryPath` (hierarchical path with "/" separators)
- `Descripción` → `Description` + `Name` (formatted from UPPERCASE to Title Case)
- Category hierarchy → `DepartmentId` + `CategoryId` (via VTEX API)
- Brand name → `BrandId` (via VTEX API)

## VTEX Integration Logic

### Category Mapping Process
- Input format: `"Department>Category>Subcategory"`
- Unicode normalization for matching with VTEX catalog
- ID assignment priority: Subcategory ID > Category ID > Department ID
- Output format: `"Department/Category/Subcategory"` with existing "/" → "|"

### Brand Matching Process  
1. `RefId` → lookup SKU in marcas.json
2. SKU → extract brand name
3. Brand name → match with VTEX brand catalog (case-insensitive, normalized)
4. VTEX brand → assign BrandId or null if not found

### Product Readiness Classification
- **Ready to Create**: Has DepartmentId, CategoryId, and BrandId (all non-null)
- **Requires Category Creation**: Missing CategoryId but has category name
- **Cannot Create**: Missing BrandId (critical VTEX requirement)

## Extended Workflow Operations

### Category Hierarchy Creation (24)
- **Automated 3-Level Structure**: Creates Departments → Categories → Subcategories/Lines from flat JSON
- **Idempotent Design**: Re-executions skip existing categories without errors
- **Pre-Verification**: Fetches existing VTEX category tree before creating to avoid duplicates
- **Sequential Processing**: Creates level 1 (departments) first, then level 2, then level 3 to ensure parent categories exist
- **Unicode Normalization**: Robust name matching by removing accents (e.g., "Decoración" matches "decoracion")
- **Dry-Run Mode**: Test mode that simulates operations without making actual API calls
- **Comprehensive Reporting**: Exports created/skipped/failed categories with detailed markdown reports
- **Rate Limiting**: 1-second delays between creations, no delays for skipped categories
- **Input Format**: Flat JSON with `CATEGORIA` (dept), `SUBCATEGORIA` (cat), `LINEA` (subcat) fields
- **Use Case**: Run BEFORE product creation to establish complete category structure in VTEX
- **Performance**: ~27 minutes for 1632 new categories, ~3 minutes if all exist (idempotent re-run)

### Catalog Creation Workflow (12-15)
- **Product Formatting** (11): Transform classified products to VTEX API format
- **Product Creation** (12): Batch create products via VTEX API with rate limiting
- **Response Extraction** (13): Parse successful creation responses for Product IDs
- **SKU Transformation** (14): Convert product data to SKU format with dimensions and EAN
- **SKU Creation** (15): Batch create SKUs via VTEX API with comprehensive error handling

### Media & Asset Management (16-18)
- **SKU Image Merging** (16): Combine product data with image URLs from external sources
- **Media Validation** (16.2): RefId to SkuId mapping for accurate image associations
- **Image Upload** (17): Batch upload images to VTEX SKUs with URL validation
- **File Cleanup** (18): Remove obsolete SKU files and manage catalog assets

### Data Processing Extensions (19+)
- **Status Filtering** (19): Filter datasets based on status conditions and criteria
- **RefId-EAN Extraction**: Extract SKU and EAN mappings from unified datasets
- **Font Conversion**: TTF to WOFF2 conversion for web optimization
- **SKU Filtering** (filtrar_sku): Compare two JSON files by _SKUReferenceCode, outputs matches as JSON with _SkuId field, non-matches as CSV

## File Organization Patterns

### Input/Output Conventions
- **Input files**: `input.csv`, `data.csv`, `marcas.csv`, `images.csv`
- **Intermediate files**: `data.json`, `transformed.json`, `categorized.json`, `sku_images.json`
- **Output files**: `final_data.json`, `report.md`, timestamp-based creation logs
- **Error exports**: `_problematicos.json/csv`, `_no_unificados.csv`, `no_brandid_found.csv`
- **Creation outputs**: `{timestamp}_vtex_creation_successful.json`, `{timestamp}_vtex_creation_failed.json`
- **API responses**: `responses.json` files organized by date folders

### Generated Reports & Logs
- **Creation Reports**: Timestamped markdown reports with batch statistics and error analysis
- **Upload Reports**: Media upload logs with success rates and failure details
- **API Response Logs**: Comprehensive logging of VTEX API interactions
- **Markdown logs**: Emoji indicators, grouped errors, success statistics
- **CSV exports**: All failed cases with original data for manual review
- **JSON exports**: Structured data for programmatic processing

## Working with This Codebase

### Development Patterns
- **CLI-First Design**: All tools expect argparse-based invocation with `--help`
- **Consistent JSON Formatting**: 4-space indentation standard throughout
- **UTF-8 Encoding**: Critical for Spanish character handling
- **Environment-Driven**: VTEX credentials and configuration from root `.env`

### Testing & Validation
- **Single Upload Testing**: Use `test_single_upload.py` (17) for media upload validation
- **Rate Limiting Testing**: Scripts include `--delay` and `--timeout` parameters
- **API Response Validation**: Check timestamped JSON logs for successful operations
- **Error Tracking**: Failed operations exported to CSV for manual inspection

### Extension Guidelines
- Add new numbered directories for workflow extensions
- Follow docstring pattern with usage examples in module headers
- Implement comprehensive error handling with CSV/JSON exports
- Generate both data outputs and human-readable reports
- Use Unicode normalization for any text matching operations
- Include rate limiting for VTEX API operations (1-second minimum delays)
- Provide timestamped outputs for batch operation tracking

### Common Debugging Patterns
- **Environment Issues**: Check `.env` file for VTEX credentials and proper variable names
- **Text Matching**: Verify Unicode normalization for text matching issues  
- **API Failures**: Review generated markdown logs for API mapping and creation failures
- **Data Problems**: Examine CSV exports for problematic data requiring manual review
- **Format Issues**: Validate JSON indentation and encoding consistency (UTF-8, 4-space indent)
- **Rate Limiting**: Monitor API rate limits and adjust delays if necessary
- **Batch Operations**: Check timestamp folders for organized batch operation results
- **File Not Found**: Ensure input files exist and paths are correct (scripts don't create missing directories)
- **Permission Errors**: Verify venv activation and package installation in correct environment

## Dependencies

**Core Libraries**:
- `json`, `csv`, `argparse`, `sys` (standard library)
- `requests` (VTEX API calls)
- `python-dotenv` (environment management)
- `unicodedata` (text normalization)

Dependencies are imported directly in scripts - no centralized requirements management.