# ndjson_price_generator

## Descripción

Generador de registros de precios VTEX en formato NDJSON. Extrae el campo `_SKUReferenceCode` de un archivo NDJSON y genera registros de precio con valores fijos de costo y precio base, listos para upload a VTEX.

## Requisitos

- Python 3.6+ (librerías estándar: json, sys, argparse, csv)
- Sin dependencias externas

## Uso

```bash
python3 ndjson_price_generator.py <input.ndjson> <output.ndjson> [--cost-price <valor>] [--base-price <valor>]
```

### Argumentos

- `input.ndjson` - Archivo NDJSON de entrada
- `output.ndjson` - Archivo NDJSON de salida
- `--cost-price` - Precio de costo en centavos (default: 9000000 = 90,000 unidades)
- `--base-price` - Precio base de venta en centavos (default: 8999999 = 89,999 unidades)

### Ejemplos

```bash
# Usar precios por defecto
python3 ndjson_price_generator.py input.ndjson output.ndjson

# Con precios personalizados
python3 ndjson_price_generator.py input.ndjson output.ndjson \
  --cost-price 5000000 --base-price 4999999

# Precios diferenciados
python3 ndjson_price_generator.py input.ndjson precios_activos.ndjson \
  --cost-price 10000000 --base-price 9999999
```

## Formato de Entrada

NDJSON con objetos conteniendo campo requerido: `_SKUReferenceCode`

**input.ndjson**
```
{"_SkuId":123,"_SKUReferenceCode":"000050","_ProductId":1}
{"_SkuId":124,"_SKUReferenceCode":"000099","_ProductId":2}
{"_SkuId":125,"_SKUReferenceCode":"000101","_ProductId":3}
```

## Formato de Salida

NDJSON con registros de precio para cada SKU.

**output.ndjson**
```
{"_SKUReferenceCode":"000050","costPrice":9000000,"basePrice":8999999}
{"_SKUReferenceCode":"000099","costPrice":9000000,"basePrice":8999999}
{"_SKUReferenceCode":"000101","costPrice":9000000,"basePrice":8999999}
```

## Unidades Monetarias

VTEX utiliza centavos como unidad base:

| Valor | Centavos | Unidades | Descripción |
|-------|----------|----------|-------------|
| 100.00 | 10000 | 100 | Cien unidades |
| 90,000.00 | 9000000 | 90000 | Noventa mil unidades (default costPrice) |
| 89,999.99 | 8999999 | 89999.99 | Default basePrice |

## Archivos Generados

Además del NDJSON de salida, se generan dos archivos adicionales:

### {output_base}.csv
CSV con los datos de precio para revisión/auditoría

```csv
_SKUReferenceCode,costPrice,basePrice
000050,9000000,8999999
000099,9000000,8999999
000101,9000000,8999999
```

### {output_base}_skipped.log
Log detallado de registros omitidos (si existen)

```
Skipped Records Log
================================================================================

Total skipped: 1
Input file: input.ndjson
Output file: output.ndjson

================================================================================

[1] Line 10
Reason: Missing _SKUReferenceCode
Data: {"_SkuId":199}
```

## Lógica de Funcionamiento

1. Lee archivo NDJSON línea por línea
2. Para cada línea:
   - Parsea JSON
   - Extrae `_SKUReferenceCode`
   - Si falta → registra como omitido
3. Genera registro de precio con:
   - `_SKUReferenceCode` original
   - `costPrice` establecido por `--cost-price`
   - `basePrice` establecido por `--base-price`
4. Escribe registros NDJSON
5. Genera CSV paralelo
6. Registra cualquier error en log

## Campos en Salida

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `_SKUReferenceCode` | string | Código de referencia del SKU |
| `costPrice` | integer | Precio de costo en centavos |
| `basePrice` | integer | Precio base/actual en centavos |

## Notas/Caveats

- Precios en centavos (dividir por 100 para obtener unidades monetarias)
- Un registro por SKU encontrado
- Se omiten registros sin `_SKUReferenceCode` (registrados en .log)
- Todos los registros reciben mismos precios (configurables globalmente)
- CSV se regenera cada vez (no acumulativo)
- Log se regenera solo si hay registros omitidos
- costPrice típicamente debe ser mayor que basePrice (convención VTEX)
- Valores deben ser enteros positivos
- Buen uso para preparar uploads masivos de precios a VTEX
