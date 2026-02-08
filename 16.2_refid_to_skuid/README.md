# 16.2_refid_to_skuid

## Descripción

Mapea valores de `RefId` a `SkuId` utilizando un archivo de mapeo local en formato JSON. Procesa archivos de datos JSON reemplazando referencias de `RefId` por sus correspondientes `SkuId` de VTEX, manteniendo la estructura original del documento.

## Requisitos

- Python 3.6+
- Dependencias: ninguna (solo librerías estándar)

## Uso

```bash
python3 refid_to_skuid_mapper.py <archivo_mapeo> <archivo_entrada> <archivo_salida> [opciones]
```

### Comando básico

```bash
python3 refid_to_skuid_mapper.py mapping.json products.json products_with_skuid.json
```

### Con opciones adicionales

```bash
python3 refid_to_skuid_mapper.py mapping.json products.json products_with_skuid.json --key-field RefId --report reporte_mapeo
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `mapping_file` | str | Archivo JSON de mapeo (RefId → SkuId) | (posicional, requerido) |
| `input_file` | str | Archivo JSON de entrada con datos | (posicional, requerido) |
| `output_file` | str | Archivo JSON de salida con mapeo aplicado | (posicional, requerido) |
| `--key-field` | str | Campo que contiene RefId (para listas) | `RefId` (auto-detectado) |
| `--report` | str | Prefijo para archivos de reporte de fallos | (sin prefijo) |

## Formato de entrada

### Archivo de mapeo (mapping.json)

**Formato simple:**
```json
[
    {"Id": "5380", "RefId": "210794"},
    {"Id": "5381", "RefId": "210795"},
    {"Id": "5382", "RefId": "210796"}
]
```

**Formato anidado (con response):**
```json
[
    {
        "sku_data": {...},
        "response": {
            "Id": 5380,
            "RefId": "210794",
            "...": "..."
        },
        "status_code": 200
    },
    {
        "response": {
            "Id": 5381,
            "RefId": "210795"
        }
    }
]
```

### Archivo de datos de entrada (products.json)

**Formato 1: Diccionario con RefId como claves**
```json
{
    "210794": {
        "name": "Producto A",
        "category": "Electrónica",
        "price": 99.99
    },
    "210795": {
        "name": "Producto B",
        "category": "Ropa",
        "price": 49.99
    }
}
```

**Formato 2: Lista con campo RefId**
```json
[
    {"RefId": "210794", "Name": "Producto A", "Category": "Electrónica"},
    {"RefId": "210795", "Name": "Producto B", "Category": "Ropa"},
    {"RefId": "210796", "Name": "Producto C", "Category": "Deportes"}
]
```

## Formato de salida

### Archivo principal (products_with_skuid.json)

**Formato transformado (diccionario):**
```json
{
    "5380": {
        "name": "Producto A",
        "category": "Electrónica",
        "price": 99.99
    },
    "5381": {
        "name": "Producto B",
        "category": "Ropa",
        "price": 49.99
    }
}
```

**Formato transformado (lista):**
```json
[
    {"SkuId": "5380", "Name": "Producto A", "Category": "Electrónica"},
    {"SkuId": "5381", "Name": "Producto B", "Category": "Ropa"},
    {"SkuId": "5382", "Name": "Producto C", "Category": "Deportes"}
]
```

### Archivos de reporte de fallos

**CSV de mapeos fallidos:** `{prefix}_failed_mappings_{timestamp}.csv`
```csv
refid,error
210799,RefId 210799 not found in mapping file
210800,RefId 210800 not found in mapping file
```

**JSON de mapeos fallidos:** `{prefix}_failed_mappings_{timestamp}.json`
```json
[
    {"refid": "210799", "error": "RefId 210799 not found in mapping file"},
    {"refid": "210800", "error": "RefId 210800 not found in mapping file"}
]
```

## Cómo funciona

1. **Carga del archivo de mapeo**: Lee el archivo JSON de mapeo y detecta automáticamente si es formato simple o anidado
2. **Construcción del diccionario de mapeo**: Crea un diccionario Python con `RefId → SkuId` para búsqueda rápida
3. **Detección de estructura**: Analiza el archivo de datos y detecta si es:
   - Diccionario con RefId como claves
   - Lista con campo RefId
4. **Mapeo de RefIds**: Compara cada RefId del archivo de datos con el diccionario de mapeo
5. **Transformación**: Reemplaza los RefId por los SkuId correspondientes manteniendo la estructura
6. **Exportación**: Genera:
   - Archivo principal con datos transformados
   - CSV de mapeos fallidos (si los hay)
   - JSON de mapeos fallidos (si los hay)
7. **Reporte en consola**: Muestra estadísticas detalladas incluyendo:
   - Mapeos exitosos
   - Mapeos fallidos
   - Porcentaje de éxito
   - Ejemplos de mapeos realizados

## Notas y caveats

- Los valores RefId y SkuId se convierten a strings para comparación consistente
- Si un RefId no tiene mapeo en el archivo de mapeo, se mantiene el RefId original en el JSON de salida
- El script detecta automáticamente el formato del archivo de mapeo en la primera entrada válida
- El campo que contiene RefId en estructuras de lista se detecta automáticamente buscando: `RefId`, `refId`, `ref_id`, `refid`
- Los archivos de reporte de fallos se generan solo si hay mapeos fallidos
- El timestamp en los nombres de archivo es UNIX epoch (segundos desde 1970)
- La tasa de éxito se calcula solo sobre los RefIds que se intentaron mapear (no incluye vacíos)
