# Creador de Especificaciones SKU VTEX desde CSV

Este paso crea especificaciones SKU tipo combo en VTEX usando dos CSV:

- CSV de grupos de especificacion SKU ya creados y validados por categoria.
- CSV de especificaciones SKU encontradas, con `Category ID` y `Nombre Especificacion`.

El script cruza `CategoryId` del CSV de grupos contra `Category ID` del CSV de specs, deduplica por categoria + nombre de especificacion, y hace `POST /api/catalog/pvt/specification`.

## Requisitos

- Python 3.
- Para modo real: `requests` y `python-dotenv`.
- Archivo `.env` en la raiz del proyecto con:

```bash
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

El modo `--dry-run` no llama a VTEX y puede usarse para validar entradas y salidas antes de mutar la cuenta.

## Columnas de Entrada

CSV de grupos:

- `CategoryId`: categoria VTEX validada.
- `GroupId`: ID del grupo de especificaciones SKU que se usara como `FieldGroupId`.

CSV de specs:

- `Category ID`: categoria VTEX donde debe crearse la especificacion.
- `Nombre Especificacion`: nombre de la especificacion SKU.

Los nombres de columnas se pueden cambiar con `--category-id-column`, `--group-id-column`, `--spec-category-id-column` y `--spec-name-column`.

## Uso

### Dry-run con archivos dentro del paso 65

Si moviste los CSV al directorio de este paso con los nombres por defecto:

```bash
python3 65_vtex_sku_specification_create/vtex_sku_specification_create.py --dry-run
```

### Dry-run con rutas actuales

```bash
python3 65_vtex_sku_specification_create/vtex_sku_specification_create.py \
  64_vtex_specificationgroup_category_validator/resultado_20260602_122525_categoryid_tercer_nivel_correctos.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --dry-run
```

### Ejecucion real

Este comando crea especificaciones en VTEX. Ejecutalo solo despues de revisar el dry-run y confirmar que la cuenta del `.env` es la correcta.

```bash
python3 65_vtex_sku_specification_create/vtex_sku_specification_create.py \
  64_vtex_specificationgroup_category_validator/resultado_20260602_122525_categoryid_tercer_nivel_correctos.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --delay 1.0 \
  --timeout 30
```

## Payload VTEX

Cada especificacion se crea con:

```json
{
  "FieldTypeId": 5,
  "CategoryId": 893,
  "FieldGroupId": 123,
  "Name": "Color",
  "Position": 1,
  "IsFilter": true,
  "IsRequired": false,
  "IsOnProductDetails": true,
  "IsStockKeepingUnit": true,
  "IsActive": true,
  "IsTopMenuLinkActive": false,
  "IsSideMenuLinkActive": false,
  "DefaultValue": ""
}
```

Las posiciones son consecutivas por categoria dentro del lote de entrada. El script no consulta especificaciones ya existentes en VTEX antes de hacer POST.

## Salidas

Los archivos se escriben en `--output-dir` (por defecto, este directorio) con timestamp:

- `YYYYMMDD_HHMMSS_sku_specification_creation_successful.csv`
- `YYYYMMDD_HHMMSS_sku_specification_creation_failed.csv`
- `YYYYMMDD_HHMMSS_sku_specification_creation_skipped.csv`
- `YYYYMMDD_HHMMSS_sku_specification_creation_REPORT.md`

### CSV Exitoso

El CSV exitoso incluye estas columnas para reutilizar el `Id` como referencia de `FieldId`:

- `Id`
- `FieldTypeId`
- `CategoryId`
- `FieldGroupId`
- `Name`
- `Description`
- `Position`
- `IsFilter`
- `IsRequired`
- `IsOnProductDetails`
- `IsStockKeepingUnit`
- `IsWizard`
- `IsActive`
- `IsTopMenuLinkActive`
- `IsSideMenuLinkActive`
- `DefaultValue`
- `StatusCode`

### CSV de Fallos

Incluye `CategoryId`, `FieldGroupId`, `Name`, `Position`, `StatusCode` y `Error`.

### CSV de Omitidos

Incluye filas que no se enviaron a VTEX por razones como:

- `CATEGORY_WITHOUT_GROUP`
- `EMPTY_CATEGORY_ID`
- `EMPTY_SPEC_NAME`
- `INVALID_GROUP_CATEGORY_ID`
- `INVALID_GROUP_ID`
- `DUPLICATE_GROUP_CATEGORY`

## Seguridad VTEX

- Usa siempre `--dry-run` primero.
- El modo real usa `POST https://{VTEX_ACCOUNT_NAME}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt/specification`.
- El script deduplica dentro del input, pero no detecta especificaciones ya creadas previamente en VTEX.
- Si VTEX responde `429`, reintenta hasta 3 veces con backoff exponencial.
