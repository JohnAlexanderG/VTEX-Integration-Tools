# Creador de Valores de Especificaciones SKU VTEX desde CSV

Este paso crea valores de especificaciones SKU tipo combo en VTEX usando dos CSV:

- CSV exitoso del paso 65, donde `Id` se reutiliza como `FieldId`.
- CSV del paso 61 con especificaciones SKU encontradas por categoria.

El script cruza `CategoryId + Name` del CSV del paso 65 contra `Category ID + Nombre Especificacion` del CSV del paso 61, normaliza los valores desde `Especificacion` y `cantidad`, deduplica por `FieldId + Name`, y hace `POST /api/catalog/pvt/specificationvalue`.

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

El modo `--dry-run` no valida credenciales ni llama a VTEX. Usalo primero para revisar payloads, omitidos y reanudacion.

Por defecto los valores se preparan con `IsActive=false`. Usa `--active` solo cuando quieras crearlos activos en VTEX.

## Columnas de Entrada

CSV exitoso del paso 65:

- `Id`: ID de la especificacion creada en VTEX. Se usa como `FieldId`.
- `CategoryId`: categoria VTEX.
- `Name`: nombre de la especificacion SKU.

CSV del paso 61:

- `Category ID`: categoria VTEX.
- `Nombre Especificacion`: nombre de la especificacion SKU.
- `Especificacion`: valor textual o unidad.
- `cantidad`: valor numerico/textual complementario.

Los nombres de columnas se pueden cambiar con `--field-id-column`, `--field-category-id-column`, `--field-name-column`, `--spec-category-id-column`, `--spec-name-column`, `--spec-value-column` y `--quantity-column`.

## Reglas de Normalizacion

El valor final enviado como `Name` se calcula asi:

- Si `cantidad` y `Especificacion` existen, y `Especificacion` equivale a `Nombre Especificacion` ignorando mayusculas y espacios, usa solo `cantidad`.
- Si `cantidad` y `Especificacion` existen, y son distintos, usa `cantidad + " " + Especificacion`.
- Si solo existe `Especificacion`, usa `Especificacion`.
- Si solo existe `cantidad`, usa `cantidad`.
- Si ambos estan vacios, la fila se omite como `EMPTY_VALUE`.

Ejemplos:

| Nombre Especificacion | Especificacion | cantidad | Name |
|-----------------------|----------------|----------|------|
| Medida Empaque Frente | Medida Empaque Frente | 31.00 | 31.00 |
| Potencia | VATIOS | 1,800.00 | 1,800.00 VATIOS |
| Color | ROSADO |  | ROSADO |

## Uso

### Dry-run con rutas actuales

```bash
python3 66_vtex_specificationvalue_create/vtex_specificationvalue_create.py \
  65_vtex_sku_specification_create/20260602_163212_sku_specification_creation_successful.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --dry-run
```

### Dry-run por lote con reanudacion

El `state file` por defecto es estable: `<output-dir>/<output-prefix>_state.csv`. Si repites el mismo comando, los payloads exitosos previos se saltan como `RESUME_ALREADY_SUCCESSFUL`.

```bash
python3 66_vtex_specificationvalue_create/vtex_specificationvalue_create.py \
  65_vtex_sku_specification_create/20260602_163212_sku_specification_creation_successful.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --dry-run \
  --max-requests 25
```

Tambien puedes sembrar reanudacion desde exitos previos:

```bash
python3 66_vtex_specificationvalue_create/vtex_specificationvalue_create.py \
  65_vtex_sku_specification_create/20260602_163212_sku_specification_creation_successful.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --resume-from-success-csv 66_vtex_specificationvalue_create/20260602_214754_sku_specificationvalue_creation_successful.csv \
  --dry-run
```

### Ejecucion real

Este comando crea valores en VTEX. Ejecutalo solo despues de revisar el dry-run y confirmar que la cuenta del `.env` es la correcta.
Por defecto se crean inactivos; agrega `--active` si intencionalmente necesitas restaurar la creacion activa.

```bash
python3 66_vtex_specificationvalue_create/vtex_specificationvalue_create.py \
  65_vtex_sku_specification_create/20260602_163212_sku_specification_creation_successful.csv \
  61_sku_spec_matcher/resultado_20260602_113828_encontrados.csv \
  --delay 1.0 \
  --timeout 30
```

## Payload VTEX

Cada valor se crea con:

```json
{
  "FieldId": 193,
  "Name": "Metal",
  "IsActive": false,
  "Position": 1
}
```

El script mantiene metadatos internos para reportes (`CategoryId`, `SpecName`, `SourceRows`, `NormalizationRule`, `PayloadKey`), pero no los envia a VTEX.
`IsActive=false` es el comportamiento por defecto; `--active` cambia el payload a `IsActive=true`.

Las posiciones son consecutivas por `FieldId` dentro de la lista deduplicada completa, antes de aplicar skips de reanudacion.

## Salidas

Los archivos se escriben en `--output-dir` (por defecto, este directorio) con timestamp:

- `YYYYMMDD_HHMMSS_sku_specificationvalue_creation_successful.csv`
- `YYYYMMDD_HHMMSS_sku_specificationvalue_creation_failed.csv`
- `YYYYMMDD_HHMMSS_sku_specificationvalue_creation_skipped.csv`
- `YYYYMMDD_HHMMSS_sku_specificationvalue_creation_REPORT.md`

Ademas se mantiene el journal estable:

- `sku_specificationvalue_creation_state.csv`

### CSV Exitoso

Incluye `FieldValueId`, `FieldId`, `Name`, `IsActive`, `Position`, `CategoryId`, `SpecName`, `StatusCode` y `Response`.

### CSV de Fallos

Incluye `FieldId`, `Name`, `Position`, `CategoryId`, `SpecName`, `StatusCode`, `Error`, `Payload` y `SourceRows`.

### CSV de Omitidos

Incluye filas que no se enviaron a VTEX por razones como:

- `MISSING_FIELD_ID`
- `EMPTY_VALUE`
- `EMPTY_CATEGORY_ID`
- `EMPTY_SPEC_NAME`
- `INVALID_FIELD_ID`
- `DUPLICATE_FIELD_MAPPING`
- `RESUME_ALREADY_SUCCESSFUL`

## Seguridad VTEX

- Usa siempre `--dry-run` primero.
- El payload default usa `IsActive=false`; requiere `--active` para crear valores activos.
- El modo real usa `POST https://{VTEX_ACCOUNT_NAME}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt/specificationvalue`.
- El script deduplica dentro del input, pero no consulta valores ya creados previamente en VTEX.
- Si VTEX responde `429`, reintenta hasta 3 veces con backoff exponencial.
- Si el proceso se interrumpe, exporta resultados parciales y conserva exitos ya escritos en el state file.
