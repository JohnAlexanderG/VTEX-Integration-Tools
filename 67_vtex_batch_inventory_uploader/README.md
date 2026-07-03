# 67. VTEX Batch Inventory Uploader

Sube inventario ERP Homesentry al endpoint batch de VTEX Logistics.

Este paso recibe el CSV ERP con `CODIGO SKU`, `CODIGO SUCURSAL` y `EXISTENCIA`, cruza `CODIGO SKU` contra un export VTEX para obtener `_SkuId`, genera CSVs batch con el formato esperado por VTEX y procesa cada parte en orden: crear batch, subir CSV a URL prefirmada, commit y consulta de status.

## Requisitos

- Python 3.
- `requests` y `python-dotenv` para ejecucion real.
- `openpyxl` solo si `--sku-map` apunta a un `.xlsx`.
- `.env` en la raiz del proyecto con las credenciales VTEX existentes:
  - `X-VTEX-API-AppKey`
  - `X-VTEX-API-AppToken`
  - `VTEX_ACCOUNT_NAME`
  - `VTEX_ENVIRONMENT`

## Entrada ERP

El CSV ERP debe incluir estas columnas exactas:

```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA
```

`CODIGO SKU` es una referencia, no un SkuId entero. Por eso `--sku-map` es obligatorio y puede apuntar a uno de estos formatos:

CSV con encabezados:

```csv
_SKUReferenceCode,_SkuId
```

XLSX descargado de VTEX `products-and-skus`, con encabezados en la fila 2:

```text
Product ID | Product Name | SKU ID | SKU name | SKU reference code
```

Las columnas del mapa pueden cambiarse con `--sku-ref-column` y `--sku-id-column`.
Para Excel, la fila de encabezados puede cambiarse con `--sku-map-header-row`.

## Normalizacion

- `CODIGO SKU`: se limpia como texto y se remueve el sufijo `.0` de Excel cuando aplica.
- `CODIGO SUCURSAL`: por defecto usa `--warehouse-mode zfill3`, por ejemplo `1 -> 001` y `95 -> 095`.
- `EXISTENCIA`: debe ser entero mayor o igual a cero.
- `unlimited`: por defecto se envia como `false`.
- `lead_time`: por defecto se envia como `1.00:00:00`.
- `supply_date` y `seller_id`: se envian como columnas vacias; VTEX las requiere en el encabezado aunque sean opcionales.

## Uso

Primero correr en dry-run:

```bash
python3 67_vtex_batch_inventory_uploader/vtex_batch_inventory_uploader.py \
  inventario_erp.csv \
  --sku-map products-and-skus_homesentry.xlsx \
  --dry-run
```

Ejecucion real:

```bash
python3 67_vtex_batch_inventory_uploader/vtex_batch_inventory_uploader.py \
  inventario_erp.csv \
  --sku-map products-and-skus_homesentry.xlsx
```

El formato CSV anterior sigue soportado con `--sku-map vtex_sku_export.csv`.
Por defecto, todos los archivos quedan en `67_vtex_batch_inventory_uploader/output/`.

Si `--sku-map` contiene la misma referencia apuntando a distintos SkuId, esas referencias se omiten del mapa para no subir inventario al SKU equivocado. El proceso continua y deja estos diagnosticos en `--output-dir` para corregir el dato en la fuente:

- `YYYYMMDD_HHMMSS_sku_map_conflicts.csv`
- `YYYYMMDD_HHMMSS_sku_map_conflicts_REPORT.md`

## Salidas

El script exporta en `--output-dir`:

- `YYYYMMDD_HHMMSS_batch_inventory_successful.csv`
- `YYYYMMDD_HHMMSS_batch_inventory_failed.csv`
- `YYYYMMDD_HHMMSS_batch_inventory_skipped.csv`
- `YYYYMMDD_HHMMSS_batch_inventory_REPORT.md`
- `batch_inventory_upload_state.csv`
- `parts/`
- `errors/`

El state file es append-only. Con `--resume` se saltan partes que ya quedaron marcadas como `DONE`; con `--no-resume` se reprocesa todo.

## CSV VTEX generado

Cada parte usa encabezado obligatorio:

```csv
item_id,account_name,container_id,quantity,unlimited,lead_time,supply_date,seller_id
```

`supply_date` y `seller_id` se dejan vacias por defecto.

El archivo se divide en partes de maximo `--max-part-mb` MB, por defecto `450`. En modo real, cada parte se renombra con el `batchId` antes de subirse, por ejemplo:

```text
{batchId}_part0001.csv
```

En `--dry-run`, el nombre usa `DRYRUN_part0001.csv` y no se hacen requests a VTEX.

## Filas omitidas

Las filas invalidas quedan en `*_batch_inventory_skipped.csv` con una razon concreta:

- `MISSING_SKU_ID_MAPPING`
- `INVALID_SKU_ID`
- `INVALID_QUANTITY`
- `EMPTY_WAREHOUSE`
- `ROW_TOO_LARGE`

## Seguridad operativa

Ejecutar siempre primero `--dry-run`. En modo real, el script usa las credenciales del `.env`, sube cada parte de forma secuencial y no ejecuta `commit` si falla el upload a la URL prefirmada.
