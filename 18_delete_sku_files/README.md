# 18_delete_sku_files

## Descripción

Elimina todos los archivos/imágenes asociados a SKUs en VTEX mediante peticiones DELETE. Lee un archivo JSON con lista de SKU IDs y realiza DELETE a cada uno, con soporte para reintentos, rate limiting y generación de reportes.

## Requisitos

- Python 3.6+
- Dependencias: `requests`, `python-dotenv`, `openpyxl` para leer maestros `.xlsx`
- Instalación: `pip install requests python-dotenv openpyxl`
- Archivo `.env` en el directorio raíz (nivel anterior) con credenciales VTEX

### Variables de entorno (.env)

```
VTEX_ACCOUNT_NAME=tu_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
```

## Uso

### Flujo recomendado: eliminar por código de referencia

Use `delete_sku_files_by_refid.py` cuando el archivo de entrada contiene códigos de referencia y necesita cruzarlos contra un maestro `referenceCode -> skuId`.

```bash
python3 delete_sku_files_by_refid.py <mapping_file> <references_file> [opciones]
```

El script hace primero:

```text
GET /api/catalog/pvt/stockkeepingunit/{skuId}/file
```

Luego elimina cada archivo individualmente con:

```text
DELETE /api/catalog/pvt/stockkeepingunit/{skuId}/file/{skuFileId}
```

Esto es necesario porque VTEX requiere el `skuFileId` para borrar cada archivo específico.

#### Ejecución segura (dry-run)

```bash
python3 delete_sku_files_by_refid.py skus.xlsx referencias.csv --dry-run --delay 1.0
```

En `--dry-run`, el script sí consulta VTEX con `GET` para listar archivos reales, pero no ejecuta ningún `DELETE`. Los archivos encontrados quedan registrados como `result=simulated`.

#### Ejecución real

```bash
python3 delete_sku_files_by_refid.py skus.csv referencias.csv --delay 1.0 --output-prefix borrado_imagenes
```

#### Columnas personalizadas

```bash
python3 delete_sku_files_by_refid.py skus.csv referencias.csv \
  --mapping-ref-column RefId \
  --mapping-sku-column Id \
  --references-column referenceCode \
  --dry-run
```

#### Entradas soportadas

Archivo maestro CSV/XLSX/JSON con `referenceCode` y `skuId`.

Para archivos `.xlsx`, la primera fila puede contener instrucciones o notas; el script toma los encabezados desde la segunda fila. Este formato se detecta automáticamente:

```text
Fila 1: Learn how to fill out this spreadsheet here
Fila 2: Product ID | Product Name | SKU ID | SKU Name | SKU reference code
Fila 3+: datos
```

Ejemplo CSV equivalente:

```csv
referenceCode,skuId
00123,98765
00124,98766
```

También detecta alias comunes como `RefId`, `CODIGO SKU`, `_SKUReferenceCode`, `SKU reference code`, `SkuId`, `Id`, `_SkuId` y `SKU ID`.

Archivo objetivo CSV/JSON con referencias:

```csv
referenceCode
00123
00124
```

O una lista JSON:

```json
[
    "00123",
    "00124"
]
```

Todos los códigos se tratan como strings para preservar ceros a la izquierda.

#### Salidas del flujo por referencia

Con el prefijo por defecto se generan:

- `sku_file_deletion_results_{timestamp}.csv`
- `sku_file_deletion_errors_{timestamp}.csv` si hay errores o referencias sin match
- `sku_file_deletion_report_{timestamp}.md`

El CSV de resultados incluye `referenceCode`, `skuId`, `skuFileId`, `fileName`, `fileUrl`, `action`, `statusCode`, `result`, `error` y `timestamp`.

> Operación irreversible: ejecute primero con `--dry-run` y revise el reporte antes de correr el modo real.

### Script legacy: eliminar por lista de SKU IDs

El comando existente se mantiene para compatibilidad cuando ya tiene un JSON con SKU IDs. Para entradas por código de referencia, use `delete_sku_files_by_refid.py`.

```bash
python3 delete_sku_files.py <input_json> <output_csv> [report_md] [opciones]
```

### Comando básico

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md
```

### Con límite de SKUs

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md --limit 599
```

### Solo con archivos requeridos

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv
```

## Argumentos

| Argumento | Tipo | Descripción |
|-----------|------|-------------|
| `input_json` | str | (posicional) Archivo JSON con lista de SKU IDs |
| `output_csv` | str | (posicional) Archivo CSV para exportar fallos |
| `report_md` | str | (posicional, opcional) Archivo markdown con reporte |
| `--limit` | int | (opcional) Máximo número de SKUs a procesar |

## Formato de entrada

### Archivo JSON (sku_list.json)

**Formato 1: Lista de strings**
```json
[
    "123456",
    "123457",
    "123458",
    "123459"
]
```

**Formato 2: Lista de números**
```json
[
    123456,
    123457,
    123458
]
```

**Formato 3: Diccionario con SKU IDs como claves**
```json
{
    "123456": {},
    "123457": {},
    "123458": {},
    "123459": {}
}
```

## Formato de salida

### Archivo CSV de fallos (failed_deletions.csv)

Contiene todos los SKUs donde la eliminación falló:

```csv
SkuId,StatusCode,ErrorMessage,Timestamp
123456,500,Internal Server Error,2025-02-08 15:30:45
123457,401,Unauthorized,2025-02-08 15:31:12
123460,404,SKU not found,2025-02-08 15:32:05
```

### Archivo de reporte (deletion_report.md)

Documento markdown con estadísticas y análisis de errores:

```markdown
# Informe de Eliminación de Archivos SKU - VTEX

**Fecha de ejecución:** 2025-02-08 15:30:45

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total SKUs procesados** | 600 |
| **Eliminaciones exitosas** | 585 |
| **Fallos totales** | 15 |
| **Tasa de éxito** | 97.50% |

## Análisis de Errores

| Código de Estado | Cantidad |
|------------------|----------|
| **500** | 8 |
| **404** | 5 |
| **401** | 2 |
...
```

## Cómo funciona

1. **Validación de credenciales**: Carga variables de entorno desde `.env`
2. **Carga de datos**: Lee el archivo JSON y detecta automáticamente el formato:
   - Lista de strings/números
   - Diccionario con SKU IDs como claves
3. **Aplicación de límite**: Si se especifica `--limit`, procesa solo los primeros N SKUs
4. **Rate limiting**: Configura límite de 2 requests/segundo para DELETE operations
5. **Procesamiento por lotes**:
   - Procesa en lotes de 20 SKUs
   - Pausa de 3 segundos entre lotes
6. **Eliminación de archivos**:
   - DELETE a `/api/catalog/pvt/stockkeepingunit/{skuId}/file`
   - Elimina TODOS los archivos/imágenes asociados al SKU
7. **Manejo de errores**:
   - Registra errores HTTP con código de estado
   - Reintenta en caso de timeouts
8. **Reportes**:
   - CSV con SKUs donde la eliminación falló
   - Markdown con estadísticas y análisis de errores

## Notas y caveats

- **Operación irreversible**: Este script elimina permanentemente archivos/imágenes de SKUs en VTEX
- **Rate limiting más agresivo**: 2 requests/segundo (vs 1 en upload) porque DELETE es menos pesado
- **Procesamiento en lotes**: Pausa de 3 segundos cada 20 SKUs para respetar límites de VTEX
- **Conversión a strings**: Todos los SKU IDs se convierten a strings internamente
- **Límite temporal**: El parámetro `--limit` es útil para testing o procesamiento gradual (ej: `--limit 599` para evitar límites diarios)
- **Sin reintentos automáticos**: A diferencia del upload, las eliminaciones fallan inmediatamente sin reintentos
- **Fallos registrados**: Solo los SKUs que fallaron se escriben en el CSV
- **Formato de diccionario**: Si el JSON es un diccionario, se usan los keys como SKU IDs (útiles para datos complejos)
