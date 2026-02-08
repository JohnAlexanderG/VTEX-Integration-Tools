# 19_csv_json_status_filter

## Descripción

Filtra registros JSON basándose en códigos de estado en un archivo CSV. Lee un CSV con columnas `StatusCode` y `SKU`, extrae los SKUs con estados válidos (excluyendo 404 y 500), y filtra un archivo JSON para mantener solo los registros que coincidan con esos SKUs válidos.

## Requisitos

- Python 3.6+
- Dependencias: ninguna (solo librerías estándar)

## Uso

```bash
python3 csv_json_status_filter.py <input_csv> <input_json> <output_json> [opciones]
```

### Comando básico

```bash
python3 csv_json_status_filter.py input.csv data.json output.json
```

### Con indentación personalizada

```bash
python3 csv_json_status_filter.py input.csv data.json output.json --indent 2
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `csv_file` | str | (posicional) Archivo CSV con StatusCode y SKU | (requerido) |
| `json_file` | str | (posicional) Archivo JSON a filtrar | (requerido) |
| `output_file` | str | (posicional) Archivo JSON de salida filtrado | (requerido) |
| `--indent` | int | Indentación JSON en la salida | `4` |

## Formato de entrada

### Archivo CSV (input.csv)

Columnas requeridas: `StatusCode` y `SKU` (búsqueda case-insensitive)

```csv
StatusCode,SKU,Name,ProductId
200,000013,Candado 40ml,5380
404,000014,Producto no encontrado,5381
500,000015,Error interno,5382
201,000016,Barre Puerta,5383
200,000017,Producto válido,5384
400,000018,Bad request,5385
```

**Comportamiento:**
- Se extraen SKUs con StatusCode que NO sea 404 o 500
- En el ejemplo anterior: 000013, 000016, 000017 son válidos
- SKUs 000014 (404), 000015 (500), 000018 (400) se descartan

### Archivo JSON (data.json)

**Formato 1: Diccionario con SKU como claves**
```json
{
    "000013": {
        "name": "Candado 40ml",
        "category": "Seguridad",
        "price": 99.99
    },
    "000014": {
        "name": "Producto no encontrado",
        "category": "Otro",
        "price": 50.00
    },
    "000016": {
        "name": "Barre Puerta",
        "category": "Construcción",
        "price": 29.99
    }
}
```

**Formato 2: Lista con campo SKU**
```json
[
    {
        "SKU": "000013",
        "Name": "Candado 40ml",
        "Category": "Seguridad",
        "Price": 99.99
    },
    {
        "SKU": "000014",
        "Name": "Producto no encontrado",
        "Category": "Otro",
        "Price": 50.00
    },
    {
        "RefId": "000016",
        "Name": "Barre Puerta",
        "Category": "Construcción",
        "Price": 29.99
    }
]
```

Los campos detectados automáticamente para SKU: `SKU`, `RefId`, `sku`, `refId`, `Sku`, `ref_id`

## Formato de salida

### Archivo JSON filtrado (output.json)

Solo contiene registros cuyo SKU coincida con los SKUs válidos del CSV:

**Formato diccionario (si entrada es diccionario):**
```json
{
    "000013": {
        "name": "Candado 40ml",
        "category": "Seguridad",
        "price": 99.99
    },
    "000016": {
        "name": "Barre Puerta",
        "category": "Construcción",
        "price": 29.99
    }
}
```

**Formato lista (si entrada es lista):**
```json
[
    {
        "SKU": "000013",
        "Name": "Candado 40ml",
        "Category": "Seguridad",
        "Price": 99.99
    },
    {
        "RefId": "000016",
        "Name": "Barre Puerta",
        "Category": "Construcción",
        "Price": 29.99
    }
]
```

## Cómo funciona

1. **Lectura del CSV**:
   - Abre el archivo CSV
   - Busca columnas `StatusCode` y `SKU` (case-insensitive)
   - Valida que ambas columnas existan
2. **Extracción de SKUs válidos**:
   - Itera sobre cada fila del CSV
   - Extrae el StatusCode (removiendo espacios)
   - Extrae el SKU (removiendo espacios)
   - Valida que StatusCode ≠ "404" y ≠ "500"
   - Agrega el SKU a un conjunto (set) de SKUs válidos
3. **Lectura del JSON**:
   - Lee el archivo JSON completo
   - Detecta automáticamente el formato (diccionario o lista)
4. **Filtrado del JSON**:
   - Si es diccionario: mantiene solo keys que estén en el conjunto de SKUs válidos
   - Si es lista: mantiene solo registros cuyo campo SKU esté en el conjunto válido
5. **Escritura de salida**:
   - Guarda el JSON filtrado con indentación especificada
   - Muestra estadísticas en consola

## Notas y caveats

- **Búsqueda case-insensitive para columnas**: Las columnas `StatusCode` y `SKU` se detectan sin importar mayúsculas/minúsculas
- **Valores case-sensitive para StatusCode**: Los valores "404" y "500" se comparan como strings exactos
- **Mantiene estructura original**: El JSON de salida mantiene la estructura del original (diccionario o lista)
- **Campos SKU detectados automáticamente**: En listas, busca varios nombres posibles: `SKU`, `RefId`, `sku`, `refId`, `Sku`, `ref_id`
- **Trim de espacios**: Los valores del CSV se limpian de espacios al inicio y final
- **Estadísticas útiles**: Se muestran SKUs válidos encontrados vs total procesados
- **Indentación personalizable**: Por defecto 4 espacios, pero se puede ajustar con `--indent`
- **Preserva orden en listas**: Los registros filtrados mantienen el orden original
- **Descarta SKUs duplicados**: Si el CSV tiene el mismo SKU múltiples veces, se trata como un único SKU válido
