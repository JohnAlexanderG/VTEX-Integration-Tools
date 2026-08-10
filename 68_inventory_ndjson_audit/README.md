# 68_inventory_ndjson_audit

## Descripcion

Compara el CSV de inventario **origen** (fuente del cliente/ERP, lo que se quiso enviar) contra el **NDJSON** generado por el middleware (una linea = una peticion enviada a VTEX) para detectar que bodegas y que registros puntuales no se estan enviando en las actualizaciones diarias de inventario.

**Caso de uso:** el cliente reporta que "no se estan enviando en su totalidad" las bodegas de inventario. Este script responde con datos concretos: que bodegas tienen cobertura completa, cuales estan parcialmente cubiertas, y cuales faltan por completo del NDJSON.

## Requisitos

- Python 3.6+
- Solo libreria estandar (`csv`, `json`, `argparse`, `logging`) — no requiere dependencias externas.

## Uso

```bash
python3 inventory_ndjson_audit.py <source_csv> <ndjson_file> <output_prefix>
```

### Argumentos

| Argumento | Tipo | Descripcion |
|-----------|------|-------------|
| `source_csv` | Posicional | CSV de origen del cliente/ERP con el inventario a enviar |
| `ndjson_file` | Posicional | NDJSON generado por el middleware (una linea = una peticion a VTEX) |
| `output_prefix` | Posicional | Prefijo para archivos de salida |
| `--sku-column` | Opcional | Nombre de columna SKU en el CSV origen (default: `CODIGO SKU`) |
| `--warehouse-column` | Opcional | Nombre de columna bodega en el CSV origen (default: `CODIGO SUCURSAL`) |
| `--quantity-column` | Opcional | Nombre de columna cantidad en el CSV origen (default: `EXISTENCIA`) |
| `--dry-run` | Flag | Analizar sin escribir archivos de salida |
| `--verbose`, `-v` | Flag | Logs detallados de debug (lineas invalidas, duplicados) |
| `--quiet`, `-q` | Flag | Solo errores y resultado final |

### Ejemplos

```bash
# Basico
python3 inventory_ndjson_audit.py inventario_erp.csv nivelej_to_update.ndjson bodega_audit

# Con columnas personalizadas (otro cliente/formato)
python3 inventory_ndjson_audit.py origen.csv salida.ndjson audit \
    --sku-column "SKU" --warehouse-column "BODEGA" --quantity-column "STOCK"

# Dry-run para analizar sin generar archivos
python3 inventory_ndjson_audit.py inventario_erp.csv nivelej_to_update.ndjson bodega_audit --dry-run

# Verbose para debugging (lineas NDJSON invalidas o duplicadas)
python3 inventory_ndjson_audit.py inventario_erp.csv nivelej_to_update.ndjson bodega_audit -v
```

Genera:
- `bodega_audit_bodega_coverage.csv`
- `bodega_audit_missing_records.csv`
- `bodega_audit_extra_in_ndjson.csv`
- `bodega_audit_REPORT.md`

## Formatos de Entrada

### source_csv (CSV)
CSV de origen del cliente. Requiere columnas (nombres configurables): `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`.

### ndjson_file (NDJSON)
Salida del middleware, una peticion por linea:

```json
{"_SkuId": 123, "_SKUReferenceCode": "000050", "warehouseId": "095", "quantity": 100, "unlimitedQuantity": false}
```

Campos usados: `_SKUReferenceCode`, `warehouseId`, `quantity`.

## Formatos de Salida

### {prefix}_bodega_coverage.csv

Una fila por bodega detectada en cualquiera de los dos archivos:

```csv
warehouseId,en_csv,en_ndjson,enviados,faltantes,pct_cobertura,estado
021,150,0,0,150,0.0,FALTANTE
095,200,180,180,20,90.0,PARCIAL
001,100,100,100,0,100.0,OK
340,0,5,0,0,,EXTRA
```

Estados:
- `OK`: todos los registros de la bodega en el CSV origen aparecen en el NDJSON.
- `PARCIAL`: solo una parte de los registros de la bodega llegaron al NDJSON.
- `FALTANTE`: la bodega esta en el CSV origen pero **ningun** registro llego al NDJSON (el caso reportado por el cliente).
- `EXTRA`: la bodega aparece en el NDJSON pero no tiene registros en el CSV origen (anomalia a revisar).

### {prefix}_missing_records.csv

Filas del CSV origen (columnas originales intactas) cuyo `(SKU, BODEGA)` no aparece en el NDJSON.

### {prefix}_extra_in_ndjson.csv

Registros del NDJSON (`_SkuId,_SKUReferenceCode,warehouseId,quantity,unlimitedQuantity`) sin fila de origen correspondiente en el CSV.

### {prefix}_REPORT.md

Reporte markdown con:
- Alertas: bodegas `FALTANTE`, `PARCIAL` y `EXTRA` listadas primero.
- Estadisticas generales: totales, cobertura global, duplicados y lineas invalidas del NDJSON, mismatches de cantidad.
- Tabla completa de cobertura por bodega.

## Logica de Funcionamiento

1. Cargar CSV origen y normalizar (SKU, BODEGA, CANTIDAD) — misma normalizacion que `44_stock_diff_filter` (bodegas numericas cortas se rellenan a 3 digitos, ej. `95 -> 095`).
2. Cargar NDJSON del middleware linea por linea, normalizando `_SKUReferenceCode`/`warehouseId`/`quantity` con el mismo criterio, para que ambos lados sean comparables. Lineas con JSON invalido o campos faltantes se cuentan y se omiten sin abortar el proceso.
3. Calcular cobertura por bodega: cuantos registros del CSV llegaron al NDJSON vs cuantos se esperaban.
4. Exportar registros faltantes (en CSV, no en NDJSON) y registros extra (en NDJSON, no en CSV).
5. Generar reporte con las bodegas problematicas destacadas primero.

## Normalizacion de Datos

- **SKU**: espacios eliminados, `.0` removido (ej. `50.0 -> 50`).
- **BODEGA**: espacios eliminados, numeros cortos (<3 digitos) rellenados a 3 digitos (ej. `95 -> 095`, `1 -> 001`). Se aplica igual a `CODIGO SUCURSAL` (CSV) y `warehouseId` (NDJSON).
- **CANTIDAD**: convertida a entero (float -> int).

## Notas/Caveats

- El match de columnas del CSV origen ignora espacios sobrantes al inicio/final del encabezado (ej. `"CODIGO SUCURSAL "` con typo humano se reconoce igual que `"CODIGO SUCURSAL"`), asi no hace falta editar cada archivo fuente para corregir un encabezado con espacios de mas.
- No requiere dependencias externas (sin pandas/openpyxl), a diferencia de `44_stock_diff_filter`.
- El NDJSON ya representa "lo que se envio con exito a VTEX" (o al menos lo que el middleware armo para enviar); este script no vuelve a duplicar esos registros en un archivo aparte, solo reporta faltantes y extra.
- `--dry-run` calcula y muestra estadisticas por consola sin escribir archivos.
- `--verbose` muestra el primer duplicado detectado y el detalle de lineas NDJSON invalidas.
- Si el `output_prefix` incluye una carpeta, esta debe existir previamente (el script no crea directorios).
