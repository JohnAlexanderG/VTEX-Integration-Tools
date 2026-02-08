# extract_refid_ean

## Descripción

Extrae los campos `RefId` y `UPC` (renombrado a `EAN`) de un archivo JSON y crea un nuevo archivo JSON simplificado conteniendo solo estos dos campos.

## Requisitos

- Python 3.6+ (librerías estándar: json, argparse, sys, os)
- Sin dependencias externas

## Uso

```bash
python3 extract_refid_ean.py <input.json> <output.json> [--indent <espacios>]
```

### Argumentos

- `input.json` - Archivo JSON de entrada
- `output.json` - Archivo JSON de salida
- `--indent <número>` - Espacios de indentación (default: 4)

### Ejemplos

```bash
python3 extract_refid_ean.py data.json refid_ean.json
python3 extract_refid_ean.py data.json refid_ean.json --indent 2
```

## Formato de Entrada

Archivo JSON con array de objetos que contienen al menos uno de estos campos: `RefId` o `UPC`

**input.json**
```json
[
  {
    "RefId": "000050",
    "UPC": "1234567890",
    "Name": "Producto A",
    "Price": 99.99
  },
  {
    "RefId": "000099",
    "UPC": "0987654321",
    "Name": "Producto B",
    "Price": 49.99
  }
]
```

## Formato de Salida

Archivo JSON con array de objetos simplificados conteniendo:
- `RefId` (si estaba presente en entrada)
- `EAN` (renombrado de `UPC`)

Solo se incluyen objetos que tengan al menos uno de estos campos.

**output.json**
```json
[
  {
    "RefId": "000050",
    "EAN": "1234567890"
  },
  {
    "RefId": "000099",
    "EAN": "0987654321"
  }
]
```

## Lógica de Funcionamiento

1. Lee el archivo JSON de entrada
2. Para cada elemento del array:
   - Busca el campo `RefId` (si existe, lo incluye)
   - Busca el campo `UPC` (si existe, lo renombra a `EAN`)
   - Solo incluye el objeto si tiene al menos uno de estos campos
3. Exporta el array simplificado a JSON con formato especificado

## Notas/Caveats

- Solo extrae `RefId` y `UPC` (renombrado a `EAN`)
- Los objetos sin ninguno de estos campos se descartan
- El renombramiento de `UPC` a `EAN` es intencional (normalización de nomenclatura)
- Mantiene codificación UTF-8 en la salida
- Indentación por defecto es 4 espacios (configurable)
- Buen uso para preparar datos para procesos de precio y inventario
