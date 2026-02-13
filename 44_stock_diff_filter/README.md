# 44_stock_diff_filter

## Descripcion

Compara inventario ERP contra inventario VTEX (ecommerce) para identificar registros desactualizados que necesitan actualizarse. Genera archivos CSV y NDJSON listos para actualizacion, ademas de un reporte detallado en Markdown.

**Logica central:** el inventario VTEX debe ser espejo del ERP. Este script detecta las diferencias.

## Requisitos

- Python 3.7+
- Dependencias: `pandas`, `xlrd` (para .xls), `openpyxl` (para .xlsx)

```bash
pip install pandas xlrd openpyxl
```

## Uso

```bash
# Basico: ERP vs VTEX (recomendado)
python3 stock_diff_filter.py <vtex_file> <complete_file> <vtex_inventory_file> <output_prefix>

# Con archivo procesado como capa extra de dedup (opcional)
python3 stock_diff_filter.py <vtex_file> <complete_file> <vtex_inventory_file> <output_prefix> --processed <file.csv>
```

### Argumentos

| Argumento | Tipo | Descripcion |
|-----------|------|-------------|
| `vtex_file` | Posicional | Archivo .xls/.xlsx/.csv con SKUs VTEX (columna `_SKUReferenceCode` o `SKU reference code`) |
| `complete_file` | Posicional | CSV con inventario completo ERP (columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`) |
| `vtex_inventory_file` | Posicional | Archivo .xls/.xlsx/.csv con inventario VTEX actual (columnas: `RefId`, `WarehouseId`, `TotalQuantity`) |
| `output_prefix` | Posicional | Prefijo para archivos de salida |
| `--processed`, `-p` | Opcional | CSV con inventario ya procesado para dedup extra |
| `--dry-run` | Flag | Analizar sin escribir archivos de salida |
| `--verbose`, `-v` | Flag | Logs detallados de debug |
| `--quiet`, `-q` | Flag | Solo errores y resultado final |

### Ejemplos

```bash
# Comparacion directa ERP vs VTEX
python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls nivelej_20260212

# Con dedup extra contra archivo procesado
python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls nivelej_20260212 --processed uploaded.csv

# Dry-run para analizar sin generar archivos
python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls nivelej_20260212 --dry-run

# Verbose para debugging
python3 stock_diff_filter.py vtex_skus.xlsx complete.csv estoque.xls nivelej_20260212 --dry-run -v
```

Genera:
- `nivelej_20260212_to_update.csv`
- `nivelej_20260212_to_update.ndjson`
- `nivelej_20260212_REPORT.md`

## Formatos de Entrada

### vtex_file (.xls/.xlsx/.csv)
Requiere columnas: `_SKUReferenceCode` (o `SKU reference code`), `_SkuId` (o `SKU ID`, opcional para NDJSON)

### complete_file (CSV)
Inventario completo del ERP. Requiere columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`

### vtex_inventory_file (.xls/.xlsx/.csv)
Inventario actual de VTEX. Requiere columnas: `RefId`, `WarehouseId`, `TotalQuantity`

### --processed (CSV, opcional)
Inventario ya enviado previamente. Requiere columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`

## Formatos de Salida

### {prefix}_to_update.csv
CSV con todos los registros que necesitan actualizacion en VTEX.

```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA,Otros...
000050,095,100,Data1
000099,001,50,Data2
```

### {prefix}_to_update.ndjson
NDJSON listo para upload a VTEX con campos especificos para inventario.

```json
{"_SkuId":123,"_SKUReferenceCode":"000050","warehouseId":"095","quantity":100,"unlimitedQuantity":false}
{"_SkuId":124,"_SKUReferenceCode":"000099","warehouseId":"001","quantity":50,"unlimitedQuantity":false}
```

### {prefix}_REPORT.md
Reporte markdown con estadisticas, analisis de filtrado y distribucion de almacenes.

## Logica de Funcionamiento

1. Cargar SKUs validos desde VTEX (.xls/.xlsx/.csv) con opcion de mapeo a `_SkuId`
2. Cargar inventario VTEX actual (.xls/.xlsx/.csv) como lookup (RefId, WarehouseId) -> CANTIDAD
3. (Opcional) Cargar inventario ya procesado (CSV) como lookup extra de dedup
4. Para cada registro del inventario ERP completo:
   - Normalizar SKU y ALMACEN (ceros a izquierda para almacenes cortos)
   - Si SKU no existe en VTEX -> omitir
   - Si (SKU, ALMACEN, CANTIDAD) identico al inventario VTEX actual -> omitir
   - (Si --processed) Si identico al procesado -> omitir
   - Si es nuevo o cantidad diferente -> incluir en salida
5. Generar reporte con estadisticas y analisis

## Por que processed es opcional

El archivo `processed.csv` era una capa extra de deduplicacion para evitar re-enviar actualizaciones. Sin embargo, si `estoque.xls` (inventario VTEX) es un export reciente, ya refleja todo lo procesado anteriormente. Ademas, usar processed puede causar inconsistencias: si el ERP cambio un valor durante la ventana de tiempo entre el ultimo upload y el nuevo export, el processed saltaria ese registro pensando que "ya se proceso", cuando en realidad el ERP tiene un valor mas reciente.

**Recomendacion:** usar el modo directo (sin --processed) para garantizar que VTEX siempre sea espejo del ERP.

## Normalizacion de Datos

- **SKU**: Espacios eliminados, ceros a izquierda preservados, .0 removido (ej: 50.0 -> 50)
- **ALMACEN**: Espacios eliminados, numeros cortos (<3 digitos) rellenados a 3 digitos (ej: 95 -> 095, 1 -> 001)
- **CANTIDAD**: Convertida a entero (float -> int), NaN manejado correctamente

## Notas/Caveats

- Archivos .xls limitados a 65,536 filas (advertencia automatica si alcanza limite)
- NDJSON requiere que `_SkuId` este disponible; registros sin `_SkuId` se omiten de NDJSON pero se incluyen en CSV
- Soporta multiples hojas en archivos .xls/.xlsx (se concatenan automaticamente)
- Muestra progreso cada 100,000 registros procesados
- Streaming write: CSV y NDJSON se escriben registro por registro (bajo uso de memoria)
- `--dry-run` analiza sin escribir archivos de salida
- `--verbose` muestra primeros matches, muestras de datos y logs de debug
