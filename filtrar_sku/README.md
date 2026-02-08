# filtrar_sku

## Descripción

Compara dos archivos JSON utilizando el campo `_SKUReferenceCode` como clave. Genera dos archivos de salida:
1. Datos del archivo 2 que coinciden en archivo 1 (con campos específicos según tipo)
2. Datos del archivo 1 que NO tienen coincidencia en archivo 2

Soporta dos tipos de datos: precios e inventario, con transformaciones específicas para cada tipo.

## Requisitos

- Python 3.6+ (librerías estándar: json, sys, argparse, os, csv, datetime)
- Sin dependencias externas

## Uso

```bash
python3 filtrar_sku.py <archivo1.json> <archivo2.json> --tipo {precios|inventario} [--salida-coincidencias <archivo>] [--salida-no-encontrados <archivo>]
```

### Argumentos

- `archivo1` - JSON de referencia (contiene SKUs existentes)
- `archivo2` - JSON a filtrar (se extraen coincidencias)
- `--tipo` - Tipo de archivo: `precios` o `inventario` (requerido)
- `--salida-coincidencias` - Archivo de salida para coincidencias JSON (default: `{tipo}_{fecha}.json`)
- `--salida-no-encontrados` - Archivo de salida para no encontrados CSV (default: `no_encontrados_{fecha}.csv`)

### Ejemplos

```bash
# Filtrar precios
python3 filtrar_sku.py productos_vtex.json precios_nuevos.json --tipo precios

# Filtrar inventario con nombres personalizados
python3 filtrar_sku.py productos_vtex.json inventario_nuevos.json --tipo inventario \
  --salida-coincidencias precios_filtrados.json \
  --salida-no-encontrados productos_sin_datos.csv
```

## Formatos de Entrada

### archivo1 (productos VTEX)
Array JSON con campo requerido: `_SKUReferenceCode`

```json
[
  {
    "_SkuId (Not changeable)": 123,
    "_SKUReferenceCode": "000050",
    "_ProductId": 1
  }
]
```

### archivo2 (datos a filtrar - precios)
Array JSON con campos requeridos para tipo `precios`:
- `_SKUReferenceCode`
- `_SkuId (Not changeable)` (opcional, se usa del archivo1 si falta)
- `Costo`
- `Precio Venta`

```json
[
  {
    "_SkuId (Not changeable)": 123,
    "_SKUReferenceCode": "000050",
    "Costo": 50000,
    "Precio Venta": 99999
  }
]
```

### archivo2 (datos a filtrar - inventario)
Array JSON con campos requeridos para tipo `inventario`:
- `_SKUReferenceCode`
- `_SkuId (Not changeable)` (opcional, se usa del archivo1 si falta)
- `Codigo Sucursal`
- `Existencia`

```json
[
  {
    "_SkuId (Not changeable)": 123,
    "_SKUReferenceCode": "000050",
    "Codigo Sucursal": "095",
    "Existencia": "100"
  }
]
```

## Formatos de Salida

### {tipo}_{fecha}.json (coincidencias)
JSON array con campos transformados según tipo.

**Tipo precios:**
```json
[
  {
    "_SkuId": 123,
    "_SKUReferenceCode": "000050",
    "costPrice": 50000,
    "basePrice": 99999
  }
]
```

**Tipo inventario:**
```json
[
  {
    "_SkuId": 123,
    "_SKUReferenceCode": "000050",
    "warehouseId": "095",
    "quantity": 100,
    "unlimitedQuantity": false
  }
]
```

### no_encontrados_{fecha}.csv (sin coincidencias)
CSV con todos los campos del archivo 1 que no tuvieron coincidencia en archivo 2

## Lógica de Funcionamiento

1. Carga ambos archivos JSON validando que sean arrays
2. Verifica que exista `_SKUReferenceCode` en ambos archivos
3. Construye conjunto de SKUs únicos de ambos archivos
4. Identifica SKUs que coinciden entre ambos archivos
5. Filtra archivo 2 manteniendo solo registros coincidentes:
   - Para precios: mapea a `costPrice` y `basePrice`
   - Para inventario: mapea a `warehouseId`, `quantity`, `unlimitedQuantity`
   - Agrega `_SkuId` desde archivo 1 si está disponible
6. Extrae registros de archivo 1 sin coincidencia en archivo 2
7. Exporta coincidencias como JSON y no-encontrados como CSV

## Transformaciones por Tipo

### Tipo: precios
| Campo Entrada | Campo Salida |
|---|---|
| `_SkuId (Not changeable)` | `_SkuId` |
| `_SKUReferenceCode` | `_SKUReferenceCode` |
| `Costo` | `costPrice` |
| `Precio Venta` | `basePrice` |

### Tipo: inventario
| Campo Entrada | Campo Salida |
|---|---|
| `_SkuId (Not changeable)` | `_SkuId` |
| `_SKUReferenceCode` | `_SKUReferenceCode` |
| `Codigo Sucursal` | `warehouseId` |
| `Existencia` | `quantity` (convertido a int) |
| N/A | `unlimitedQuantity` (siempre false) |

## Notas/Caveats

- Comparación de SKU es case-sensitive y sensible a espacios
- Se omiten valores vacíos y strings "None" en comparación de SKUs
- Tipo inventario siempre establece `unlimitedQuantity` a `false` (regla de negocio)
- Cantidad se convierte a entero (errores de conversión se tratan como 0)
- Nombres de archivo de salida incluyen fecha actual si no se especifican
- No-encontrados se exportan como CSV (todos los campos originales)
- Solo las coincidencias exactas de SKU generan registros en salida
