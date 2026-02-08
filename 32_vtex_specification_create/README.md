# VTEX Specification Creator

Creates VTEX specifications within specification groups via API.

## Overview

This script reads a JSON file with specification group creation responses (from step 31) and creates specifications within those groups using the VTEX Catalog API endpoint `/api/catalog/pvt/specification`.

## Prerequisites

- Python 3.6+
- VTEX credentials configured in root `.env` file
- Specification groups already created (output from step 31)
- Specification definitions prepared in JSON format

## Installation

```bash
# From project root
source venv/bin/activate
pip install requests python-dotenv
```

## Usage

### Basic Usage

```bash
python3 vtex_specification_create.py groups.json specs.json
```

### Dry-Run Mode (Test without creating)

```bash
python3 vtex_specification_create.py groups.json specs.json --dry-run
```

### Custom Delay and Timeout

```bash
python3 vtex_specification_create.py groups.json specs.json --delay 2.0 --timeout 60
```

### Full Example

```bash
# Test first with dry-run
python3 vtex_specification_create.py \
  20260108_023307_specificationgroup_creation_successful.json \
  specifications_template.json \
  --dry-run

# If everything looks good, run for real
python3 vtex_specification_create.py \
  20260108_023307_specificationgroup_creation_successful.json \
  specifications_template.json
```

## Input File Formats

### Groups JSON (from step 31)

```json
[
  {
    "group_data": {
      "CategoryId": 118,
      "Name": "PUM_CAT",
      "line_number": 2
    },
    "response": {
      "Id": 168,
      "CategoryId": 118,
      "Name": "PUM_CAT",
      "Position": null
    },
    "status_code": 200
  }
]
```

The script extracts:
- `response.Id` → `FieldGroupId`
- `response.CategoryId` → `CategoryId`

### Specifications JSON

```json
[
  {
    "Name": "VALOR UNIDAD DE MEDIDA",
    "FieldTypeId": 4,
    "IsFilter": false,
    "IsRequired": false,
    "IsOnProductDetails": true,
    "IsStockKeepingUnit": true,
    "IsActive": true,
    "IsTopMenuLinkActive": false,
    "IsSideMenuLinkActive": false
  }
]
```

You can define multiple specifications in the array, and they will be created for ALL specification groups.

### VTEX FieldTypeId Reference

Common field types:
- `1`: Text (short)
- `2`: Text (large/multiline)
- `4`: Number
- `5`: Combo (dropdown)
- `6`: Radio button
- `7`: Checkbox

## Output Files

The script generates several output files with timestamps:

1. **`YYYYMMDD_HHMMSS_specification_creation_successful.json`**
   - Full API responses for successful creations
   - Includes all extracted fields and complete response data

2. **`YYYYMMDD_HHMMSS_specification_creation_successful.csv`**
   - Summary table with key fields:
     - `FieldId`: VTEX specification field ID
     - `CategoryId`: Category ID
     - `FieldGroupId`: Specification group ID
     - `Name`: Specification name
     - `FieldTypeId`: Field type (1=Text, 4=Number, 5=Combo, etc.)
     - `Position`: Display position
     - `IsRequired`: Whether field is required
     - `IsFilter`: Whether field is filterable
     - `IsActive`: Whether field is active

3. **`YYYYMMDD_HHMMSS_specification_creation_failed.json`**
   - Detailed error information for failed creations

4. **`YYYYMMDD_HHMMSS_specification_creation_failed.csv`**
   - Error summary for manual review

5. **`YYYYMMDD_HHMMSS_specification_creation_REPORT.md`**
   - Comprehensive markdown report with statistics and recommendations
   - Enhanced table format showing all key specification properties

## Features

- **Rate Limiting**: Configurable delay between requests (default: 1s)
- **Exponential Backoff**: Automatic retry with increasing delays for rate limits (429 errors)
- **Dry-Run Mode**: Test the process without making actual API calls
- **Error Handling**: Comprehensive error tracking with detailed exports
- **Progress Tracking**: Real-time progress updates every 10 groups
- **Batch Processing**: Creates specifications for all groups × all spec definitions

## API Endpoint

```
POST https://{accountName}.{environment}.com.br/api/catalog/pvt/specification
```

### Request Body

```json
{
  "FieldTypeId": 4,
  "CategoryId": 118,
  "FieldGroupId": 168,
  "Name": "VALOR UNIDAD DE MEDIDA",
  "IsFilter": false,
  "IsRequired": false,
  "IsOnProductDetails": true,
  "IsStockKeepingUnit": true,
  "IsActive": true,
  "IsTopMenuLinkActive": false,
  "IsSideMenuLinkActive": false
}
```

## Common Workflows

### Create Single Specification for All Groups

1. Prepare your specification in `specifications_template.json`
2. Run dry-run: `python3 vtex_specification_create.py groups.json specifications_template.json --dry-run`
3. Review the output
4. Run for real: `python3 vtex_specification_create.py groups.json specifications_template.json`

### Create Multiple Specifications for All Groups

1. Edit `specifications_template.json` to include multiple specifications:
```json
[
  {
    "Name": "VALOR UNIDAD DE MEDIDA",
    "FieldTypeId": 4,
    ...
  },
  {
    "Name": "COLOR",
    "FieldTypeId": 1,
    ...
  },
  {
    "Name": "MATERIAL",
    "FieldTypeId": 5,
    ...
  }
]
```

2. Run the script - it will create all 3 specifications for each group

## Troubleshooting

### "Missing VTEX credentials in .env"
- Ensure your root `.env` file contains:
  - `X-VTEX-API-AppKey`
  - `X-VTEX-API-AppToken`
  - `VTEX_ACCOUNT_NAME`

### "Rate limit exceeded"
- Increase delay: `--delay 2.0`
- The script automatically retries with exponential backoff

### "CategoryId or FieldGroupId not found"
- Verify your groups JSON file structure
- Ensure specification groups were created successfully in step 31

### Some specifications fail to create
- Check the failed CSV export for error patterns
- Verify CategoryId and FieldGroupId exist in VTEX
- Review error messages in the markdown report

## Performance

- **Processing time**: ~1 second per specification (with default delay)
- **Example**: 58 groups × 1 specification = ~58 seconds
- **Example**: 58 groups × 5 specifications = ~290 seconds (~5 minutes)

## Exit Codes

- `0`: All specifications created successfully
- `1`: Some specifications failed to create (check exports)

## Related Scripts

- **Step 31**: `31_vtex_specificationgroup_create` - Creates specification groups
- **Next Step**: Create specification values for combo/radio/checkbox fields
