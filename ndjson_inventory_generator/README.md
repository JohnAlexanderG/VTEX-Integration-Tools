# ndjson_inventory_generator

## Descripción

Generador de registros de inventario VTEX en formato NDJSON. Extrae el campo `_SKUReferenceCode` de un archivo NDJSON y genera registros de inventario listos para upload a VTEX. Soporta dos modos: inventario (warehouse aleatorio) y reset (todos los almacenes con cantidad 0).

## Requisitos

- Python 3.6+ (librerías estándar: json, sys, random, argparse, csv)
- Sin dependencias externas

## Uso

```bash
python3 ndjson_inventory_generator.py <input.ndjson> <output.ndjson> [--mode {inventory|reset}] [--quantity <cantidad>]
```

### Argumentos

- `input.ndjson` - Archivo NDJSON de entrada
- `output.ndjson` - Archivo NDJSON de salida
- `--mode` - Modo de generación: `inventory` o `reset` (default: `inventory`)
- `--quantity` - Cantidad para modo inventario (default: 100, ignorado en reset)

### Ejemplos

```bash
# Modo inventario (default): un registro por SKU, warehouse aleatorio
python3 ndjson_inventory_generator.py input.ndjson output.ndjson --quantity 100

# Modo reset: uno por SKU por warehouse, cantidad 0
python3 ndjson_inventory_generator.py input.ndjson output_reset.ndjson --mode reset

# Con cantidad personalizada
python3 ndjson_inventory_generator.py input.ndjson output.ndjson --mode inventory --quantity 500
```

## Formato de Entrada

NDJSON con objetos conteniendo campo requerido: `_SKUReferenceCode`

**input.ndjson**
```
{"_SkuId":123,"_SKUReferenceCode":"000050","_ProductId":1}
{"_SkuId":124,"_SKUReferenceCode":"000099","_ProductId":2}
```

## Formato de Salida

### Modo inventory
Un registro por SKU con warehouse aleatorio del listado fijo de almacenes.

**output.ndjson (inventory mode)**
```
{"_SKUReferenceCode":"000050","warehouseId":"021","quantity":100,"unlimitedQuantity":false}
{"_SKUReferenceCode":"000099","warehouseId":"001","quantity":100,"unlimitedQuantity":false}
```

### Modo reset
Un registro por SKU por cada warehouse con cantidad 0 (para resetear inventario).

**output.ndjson (reset mode)**
```
{"_SKUReferenceCode":"000050","warehouseId":"021","quantity":0,"unlimitedQuantity":false}
{"_SKUReferenceCode":"000050","warehouseId":"001","quantity":0,"unlimitedQuantity":false}
{"_SKUReferenceCode":"000050","warehouseId":"140","quantity":0,"unlimitedQuantity":false}
...
{"_SKUReferenceCode":"000099","warehouseId":"021","quantity":0,"unlimitedQuantity":false}
...
```

## Almacenes Soportados

Listado fijo de 18 almacenes que se usan en modo reset o para selección aleatoria:

```
"021", "001", "140", "084", "180", "160", "280", "320", "340",
"300", "032", "200", "100", "095", "003", "053", "068", "220"
```

## Archivos Generados

Además del NDJSON de salida, se generan dos archivos adicionales:

### {output_base}.csv
CSV con los mismos datos para revisión/auditoría

```csv
_SKUReferenceCode,warehouseId,quantity,unlimitedQuantity
000050,021,100,False
000099,001,100,False
```

### {output_base}_skipped.log
Log detallado de registros omitidos (si existen)

```
Skipped Records Log
================================================================================

Total skipped: 2
Input file: input.ndjson
Output file: output.ndjson

================================================================================

[1] Line 5
Reason: Missing _SKUReferenceCode
Data: {"_SkuId":125}
...
```

## Lógica de Funcionamiento

1. Lee archivo NDJSON línea por línea
2. Para cada línea:
   - Parsea JSON
   - Extrae `_SKUReferenceCode`
   - Si falta → registra como omitido
3. Según modo:
   - **inventory**: genera un registro con warehouse aleatorio y cantidad especificada
   - **reset**: genera un registro por cada warehouse conocido con cantidad 0
4. Escribe registros NDJSON
5. Genera CSV paralelo
6. Registra cualquier error en log

## Modos de Funcionamiento

### Modo: inventory
- Un registro por SKU encontrado
- warehouse seleccionado aleatoriamente del listado fijo
- quantity establecido por `--quantity` (default 100)
- Útil para inicializar inventario con cantidades presentes

### Modo: reset
- Uno a muchos registros por SKU (1 por warehouse)
- Genera registros para TODOS los almacenes conocidos
- quantity siempre 0
- unlimitedQuantity siempre false
- Útil para resetear inventario completamente

## Notas/Caveats

- Linea NDJSON por SKU encontrado (en inventory) o N×SKUs (en reset, N=almacenes)
- Se omiten registros sin `_SKUReferenceCode` (registrados en .log)
- Modo reset genera muchos más registros (N_SKUs × 18 almacenes)
- warehouse aleatorio puede resultar en mismo warehouse para varios SKUs
- CSV se regenera cada vez (no acumulativo)
- Log se regenera solo si hay registros omitidos
- Buen uso para preparar uploads a VTEX inventory API
