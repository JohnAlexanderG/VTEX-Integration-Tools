# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of Python data transformation utilities for VTEX e-commerce platform integration. The project follows a sequential numbered workflow architecture for converting CSV product data to VTEX-ready format with comprehensive API integration and validation.

## Architecture Overview

### Sequential Workflow Design
The codebase implements a microservice-style architecture with numbered directories representing a clear data processing pipeline:

1. **Data Import & Transformation** (01-03): CSV ingestion, field normalization, category processing
2. **Data Unification & Validation** (04-05): Dataset merging, missing record detection  
3. **VTEX API Integration** (06-08): Category mapping, brand ID resolution using VTEX APIs
4. **Validation & Operations** (09-10): Product readiness analysis, bulk updates

### Core Data Flow Pattern
```
CSV Data → JSON Conversion → Field Transformation → Category Processing → 
Data Unification → VTEX API Mapping → Validation → Final Output
```

## Environment Setup

**Required Environment Variables** (root `.env` file):
- `X-VTEX-API-AppKey`: VTEX API application key
- `X-VTEX-API-AppToken`: VTEX API application token  
- `VTEX_ACCOUNT_NAME`: VTEX account name
- `VTEX_ENVIRONMENT`: VTEX environment (default: vtexcommercestable)

**Python Environment**:
- Python 3 with virtual environment in root `venv/` directory
- Individual components may have separate venv for compatibility
- No requirements.txt - dependencies inferred from imports

## Command Reference

### Complete Data Processing Workflow
```bash
# 1. CSV to JSON conversion
python3 01_csv_to_json/csv_to_json.py input.csv data.json --indent 4

# 2. Split composite keys and normalize fields
python3 02_data-transform/transform_json_script.py data.json transformed.json --indent 4

# 3. Process categories and detect problematic entries
python3 03_transform_json_category/transform_json_category.py transformed.json categorized.json

# 4. Unify datasets (old + new data)
python3 04_unificar_json/unificar_json.py old_data.json new_data.json unified.json

# 5. Compare datasets for missing records
python3 05_compare_json_to_csv/compare_json_to_csv.py old_data.json new_data.json missing.csv

# 6. Map VTEX category IDs (uses .env credentials automatically)
python3 06_map_category_ids/map_category_ids.py unified.json categorized.json

# 7. Extract brand mappings from specialized CSV
python3 07_csv_to_json_marca/csv_to_json_marca.py marcas.csv marcas.json

# 8. Match VTEX brand IDs (uses .env credentials automatically)
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json categorized.json

# 9. Generate product readiness report
python3 09_generate_vtex_report/generate_vtex_report.py final_data.json -o report.md

# 10. Bulk update VTEX products
python3 10._update_vtex_products/update_vtex_products.py data.json
```

### Utility Commands
```bash
# Translate Spanish keys to English
python3 translate_keys/translate_keys.py input.json translated.json --indent 4

# Convert JSON back to CSV
python3 json_to_csv/json_to_csv.py input.json output.csv
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
- **Error Resilience**: Comprehensive error reporting with markdown logs and CSV exports
- **Unicode Text Matching**: Accent removal and case normalization for API lookups

### Error Handling & Validation
- **Multi-Format Exports**: Failed cases exported to both JSON and CSV formats
- **Detailed Logging**: Markdown reports with emoji indicators and grouped error analysis  
- **Data Reconciliation**: SKU vs RefId comparison with conflict resolution
- **Product Classification**: Three-tier readiness analysis for VTEX catalog creation

## Data Structure Evolution

### Product Data Lifecycle
1. **Raw CSV**: Spanish field names, composite values, category hierarchies
2. **Normalized JSON**: English fields, split values, cleaned data
3. **Categorized JSON**: Added CategoryPath with "/" separators, problematic entries flagged
4. **Unified JSON**: Merged old/new datasets, duplicate resolution, missing records identified
5. **VTEX-Ready JSON**: DepartmentId, CategoryId, BrandId mapped from VTEX APIs
6. **Final Classification**: Products categorized as ready/requires-creation/cannot-create

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

## File Organization Patterns

### Input/Output Conventions
- **Input files**: `input.csv`, `data.csv`, `marcas.csv`
- **Intermediate files**: `data.json`, `transformed.json`, `categorized.json`
- **Output files**: `final_data.json`, `report.md`, timestamp-based logs
- **Error exports**: `_problematicos.json/csv`, `_no_unificados.csv`, `no_brandid_found.csv`

### Generated Reports
- **Markdown logs**: Emoji indicators, grouped errors, success statistics
- **CSV exports**: All failed cases with original data for manual review
- **JSON exports**: Structured data for programmatic processing

## Working with This Codebase

### Development Patterns
- **CLI-First Design**: All tools expect argparse-based invocation with `--help`
- **Consistent JSON Formatting**: 4-space indentation standard throughout
- **UTF-8 Encoding**: Critical for Spanish character handling
- **Environment-Driven**: VTEX credentials and configuration from root `.env`

### Extension Guidelines
- Add new numbered directories for workflow extensions
- Follow docstring pattern with usage examples in module headers
- Implement comprehensive error handling with CSV/JSON exports
- Generate both data outputs and human-readable reports
- Use Unicode normalization for any text matching operations

### Common Debugging Patterns
- Check `.env` file for VTEX credentials
- Verify Unicode normalization for text matching issues
- Review generated markdown logs for API mapping failures
- Examine CSV exports for problematic data requiring manual review
- Validate JSON indentation and encoding consistency

## Dependencies

**Core Libraries**:
- `json`, `csv`, `argparse`, `sys` (standard library)
- `requests` (VTEX API calls)
- `python-dotenv` (environment management)
- `unicodedata` (text normalization)

Dependencies are imported directly in scripts - no centralized requirements management.