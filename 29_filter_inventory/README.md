# VTEX Inventory Filter

Filters inventory CSV records to include only products that exist in VTEX. Matches VTEX SKUs with inventory data and generates comprehensive reports.

## Key Feature

**Handles Multiple Warehouses**: Unlike price filters, inventory data contains multiple rows per SKU (one per warehouse location). This tool preserves ALL warehouse records for matched SKUs.

## Input Requirements

### 1. VTEX Products File (CSV or JSON)
- **Required field**: `_SKUReferenceCode`
- **Format**: Can be CSV or JSON
- **Example**: `vtex_skus.csv`

### 2. Inventory CSV File
- **Required fields**:
  - `CODIGO SKU` - SKU identifier (matches with `_SKUReferenceCode`)
  - `CODIGO SUCURSAL` - Warehouse/store code
  - `EXISTENCIA` - Stock quantity
- **Format**: CSV with UTF-8 encoding
- **Example**: `inventory_homesentry.csv`

## Output Files

The tool generates 4 files with the specified output prefix:

1. **`{prefix}_matched.csv`**
   - All inventory records where SKU exists in VTEX
   - Includes ALL warehouse locations for each matched SKU
   - Ready for VTEX upload

2. **`{prefix}_vtex_without_inventory.csv`**
   - VTEX SKUs that have no inventory records
   - Action required: Add inventory data for these products

3. **`{prefix}_inventory_without_sku.csv`**
   - Inventory records where SKU not found in VTEX
   - Action required: Create these products in VTEX first

4. **`{prefix}_REPORT.md`**
   - Detailed statistics report with dual metrics:
     - Total records (rows)
     - Unique SKUs
     - Warehouse distribution

## Usage

### Basic Usage

```bash
python3 filter_inventory.py <vtex_file> <inventory_file> <output_prefix>
```

### Examples

```bash
# Using CSV for VTEX data
python3 filter_inventory.py vtex_skus.csv inventory_homesentry.csv output

# Using JSON for VTEX data
python3 filter_inventory.py vtex_products.json inventory.csv results
```

### Output Example

```
Output Files Generated:
  1. output_matched.csv
  2. output_vtex_without_inventory.csv
  3. output_inventory_without_sku.csv
  4. output_REPORT.md
```

## Help

```bash
python3 filter_inventory.py --help
```

## Statistics Tracking

The tool tracks **dual statistics** to provide complete analysis:

### VTEX SKUs (Product-Level)
- Total unique SKUs in VTEX
- SKUs with inventory records
- SKUs without inventory records

### Inventory Records (Row-Level)
- Total inventory rows
- Rows with matching VTEX SKUs
- Rows without VTEX match

### Unique SKUs in Inventory
- Total unique SKUs in inventory file
- Unique SKUs matched with VTEX
- Unique SKUs not in VTEX

### Warehouse Distribution
- Average warehouses per SKU
- Maximum warehouses for a single SKU
- Minimum warehouses for matched SKU

## Example Output

```
======================================================================
INVENTORY FILTERING RESULTS
======================================================================
VTEX SKUs:
  Total in VTEX:               2,450
  With inventory (matched):    2,100 (85.7%)
  Without inventory:           350 (14.3%)

Inventory Records:
  Total records:               12,480
  With VTEX SKU (matched):     11,250 (90.1%)
  Without VTEX SKU:            1,230 (9.9%)

Inventory Unique SKUs:
  Total unique SKUs:           2,350
  Matched with VTEX:           2,100 (89.4%)
  Without VTEX match:          250 (10.6%)

Warehouse Distribution:
  Avg warehouses per SKU:      5.4
  Max warehouses for SKU:      18
  Min warehouses for SKU:      1
======================================================================
```

## Matching Logic

- **Match Type**: Exact string match (case-sensitive)
- **Whitespace**: Trimmed from both sides
- **Leading Zeros**: Preserved (e.g., "000013" ≠ "13")
- **Match Fields**:
  - VTEX: `_SKUReferenceCode`
  - Inventory: `CODIGO SKU`

## Important Notes

1. **Multiple Warehouses**: Each SKU can appear multiple times in the inventory file (once per warehouse). All matching warehouse records are included in the output.

2. **SKU Format**: Leading zeros are preserved during matching. Ensure your SKU codes match exactly between VTEX and inventory files.

3. **UTF-8 Encoding**: Both input files must be UTF-8 encoded.

4. **Statistics Interpretation**:
   - Use **record counts** for warehouse-level analysis
   - Use **unique SKU counts** for product-level analysis

## Integration with VTEX Workflow

This tool fits into the VTEX integration workflow:

```bash
# Step 1: Filter inventory by VTEX SKUs
python3 29_filter_inventory/filter_inventory.py \
    vtex_skus.csv \
    inventory_homesentry.csv \
    filtered_inventory

# Step 2: Review the report
cat filtered_inventory_REPORT.md

# Step 3: Upload matched inventory to VTEX
python3 23_vtex_inventory_uploader/vtex_inventory_uploader.py \
    --input filtered_inventory_matched.csv \
    --failures failures.csv \
    --summary summary.md
```

## Error Handling

The tool validates:
- Input files exist
- Required fields are present in both files
- Files are properly formatted
- UTF-8 encoding is valid

Error messages include:
- Missing files with clear file paths
- Missing required fields with available fields listed
- Clear instructions for resolution

## Example Inventory Data

```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA
000013,220,96
000013,095,45
000050,220,120
000088,220,0
```

In this example:
- SKU `000013` appears twice (warehouses 220 and 095)
- If `000013` exists in VTEX, both rows are included in matched output
- If `000013` doesn't exist in VTEX, both rows go to unmatched output

## Recommendations

### Before Running
1. Ensure VTEX products/SKUs are created (steps 12-15)
2. Verify SKU code format matches between systems
3. Confirm warehouse codes are valid

### After Running
1. Review the markdown report for statistics
2. Check `vtex_without_inventory.csv` for products needing inventory
3. Check `inventory_without_sku.csv` for products to create in VTEX
4. Upload `matched.csv` to VTEX using step 23

### Data Quality Checks
- Verify warehouse codes in `CODIGO SUCURSAL` match VTEX warehouse IDs
- Check for negative quantities in `EXISTENCIA` field
- Validate SKU code format consistency
- Confirm all expected warehouses are represented

## Performance

- **Expected Load**: 100K-300K inventory rows
- **Processing Time**: <30 seconds for large files
- **Memory Usage**: Efficient with O(1) SKU lookups using sets/dictionaries
- **Algorithm**: Single-pass processing for optimal performance

## Related Tools

- **28_filter_price_list**: Similar filter for price data (1:1 relationship)
- **23_vtex_inventory_uploader**: Uploads filtered inventory to VTEX
- **12-15_vtex_product_creation**: Creates products/SKUs before inventory upload

## Troubleshooting

### "Field not found" error
Check that your files have the required fields:
- VTEX file: `_SKUReferenceCode`
- Inventory file: `CODIGO SKU`

### No matches found
Verify SKU format matches exactly, including leading zeros.

### Encoding errors
Ensure both files are UTF-8 encoded. Convert if necessary:
```bash
iconv -f LATIN1 -t UTF-8 input.csv > output.csv
```

## License

Part of VTEX Integration Tools collection.
