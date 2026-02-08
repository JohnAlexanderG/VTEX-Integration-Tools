# 44_stock_diff_filter

## Descripción

Filtra inventario completo para identificar registros que necesitan actualizarse en VTEX. Compara contra:
1. SKUs válidos en VTEX
2. Inventario ya procesado
3. Inventario actual en VTEX

Genera archivos CSV y NDJSON listos para actualización en VTEX, además de un reporte detallado en Markdown.

## Requisitos

- Python 3.7+
- Dependencias: `pandas`, `xlrd`

Instalar con:
```bash
pip install pandas xlrd
```

## Uso

```bash
python3 stock_diff_filter.py <vtex_file> <processed_file> <complete_file> <vtex_inventory_file> <output_prefix>
```

### Argumentos

- `vtex_file` - Archivo .xls con SKUs VTEX (columna `_SKUReferenceCode`)
- `processed_file` - CSV con inventario ya procesado (columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`)
- `complete_file` - CSV con inventario completo (columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`)
- `vtex_inventory_file` - Archivo .xls con inventario actual VTEX (columnas: `RefId`, `WarehouseId`, `TotalQuantity`)
- `output_prefix` - Prefijo para archivos de salida

### Ejemplo

```bash
python3 stock_diff_filter.py vtex_skus.xls processed.csv complete.csv estoque.xls nivelej__20260205
```

Genera:
- `nivelej__20260205_to_update.csv`
- `nivelej__20260205_to_update.ndjson`
- `nivelej__20260205_REPORT.md`

## Formatos de Entrada

### vtex_file (.xls)
Requiere columnas: `_SKUReferenceCode`, `_SkuId` (opcional)

### processed_file (CSV)
Requiere columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`

### complete_file (CSV)
Requiere columnas: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`

### vtex_inventory_file (.xls)
Requiere columnas: `RefId`, `WarehouseId`, `TotalQuantity`

## Formatos de Salida

### {prefix}_to_update.csv
CSV con todos los registros que necesitan actualización en VTEX.

**Ejemplo:**
```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA,Otros...
000050,095,100,Data1
000099,001,50,Data2
```

### {prefix}_to_update.ndjson
NDJSON listo para upload a VTEX con campos específicos para inventario.

**Ejemplo:**
```json
{"_SkuId":123,"_SKUReferenceCode":"000050","warehouseId":"095","quantity":100,"unlimitedQuantity":false}
{"_SkuId":124,"_SKUReferenceCode":"000099","warehouseId":"001","quantity":50,"unlimitedQuantity":false}
```

### {prefix}_REPORT.md
Reporte markdown detallado con:
- Estadísticas de fuentes de datos
- Análisis de filtrado
- Distribución de almacenes
- Lógica de procesamiento aplicada

## Lógica de Funcionamiento

1. Cargar SKUs válidos desde VTEX (.xls) con opción de mapeo a `_SkuId`
2. Cargar inventario ya procesado (CSV) como lookup (SKU, ALMACEN) → CANTIDAD
3. Cargar inventario VTEX actual (.xls) como lookup (RefId, WarehouseId) → CANTIDAD
4. Para cada registro del inventario completo:
   - Normalizar SKU y ALMACEN (ceros a izquierda para almacenes cortos)
   - Si SKU no existe en VTEX → omitir
   - Si (SKU, ALMACEN, CANTIDAD) idéntico al procesado → omitir
   - Si (SKU, ALMACEN, CANTIDAD) idéntico al inventario VTEX actual → omitir
   - Si es nuevo o cantidad diferente → incluir en salida
5. Generar reporte con estadísticas y análisis

## Normalización de Datos

- **SKU**: Espacios eliminados, ceros a izquierda preservados, .0 removido (ej: 50.0 → 50)
- **ALMACEN**: Espacios eliminados, números cortos (<3 dígitos) rellenados a 3 dígitos (ej: 95 → 095, 1 → 001)
- **CANTIDAD**: Convertida a entero (float → int)

## Notas/Caveats

- Archivos .xls limitados a 65,536 filas (advertencia si alcanza límite)
- NDJSON requiere que `_SkuId` esté disponible; registros sin `_SkuId` se omiten de NDJSON pero se incluyen en CSV
- Soporta múltiples hojas en archivos .xls (se concatenan automáticamente)
- Muestra progreso cada 100,000 registros procesados
- Genera logs detallados de primeras coincidencias y mismatches para debugging
