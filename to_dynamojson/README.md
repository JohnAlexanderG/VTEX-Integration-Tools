# to_dynamojson

## Descripción

Suite de herramientas para convertir datos tabulares (CSV/XLSX/XLS) a formato JSON de DynamoDB y cargar en AWS DynamoDB. Incluye:
1. `dynamojson_from_tabular.py` - Convierte archivos tabulares a DynamoDB JSON
2. `split_dynamo_batch.py` - Divide batches grandes en lotes de máximo 25 items (límite DynamoDB)
3. `upload_dynamo_batches.sh` - Script bash para cargar todos los lotes a DynamoDB

## Requisitos

### Para conversión (Python)
- Python 3.7+
- Dependencia opcional: `pandas`, `openpyxl` (solo para archivos Excel)

```bash
pip install pandas openpyxl
```

### Para upload (Bash)
- AWS CLI configurado con credenciales
- Acceso a DynamoDB en AWS

## Uso General

### Paso 1: Convertir datos tabulares a DynamoDB JSON

```bash
python3 dynamojson_from_tabular.py <input_file> \
  --table-name <table_name> \
  [-o <output.json>] \
  [opciones]
```

**Ejemplo básico:**
```bash
python3 dynamojson_from_tabular.py productos.xlsx \
  --table-name ProductTable \
  -o productos_dynamo.json
```

**Con opciones avanzadas:**
```bash
python3 dynamojson_from_tabular.py data.csv \
  --table-name MyTable \
  --all-as-string \
  --string-cols "_SkuId (Not changeable),RefId" \
  -o output.json
```

### Paso 2: Dividir en batches (si es necesario)

```bash
python3 split_dynamo_batch.py <batch_input.json> \
  [--batch-size 25] \
  [--output-prefix batch]
```

**Ejemplo:**
```bash
python3 split_dynamo_batch.py productos_dynamo.json --batch-size 25
```

Genera: `productos_dynamo_batch_001.json`, `productos_dynamo_batch_002.json`, etc.

### Paso 3: Cargar a DynamoDB

```bash
bash upload_dynamo_batches.sh
```

O manualmente con AWS CLI:
```bash
aws dynamodb batch-write-item --request-items file://batch_001.json
```

## Argumentos Detallados

### dynamojson_from_tabular.py

| Argumento | Descripción | Default |
|-----------|-------------|---------|
| `input` | Archivo CSV/XLSX/XLS | Requerido |
| `-o, --output` | Archivo JSON de salida | `{input_base}.json` |
| `--table-name` | Nombre tabla DynamoDB (envuelve en batch-write format) | Opcional |
| `--ndjson` | Salida NDJSON (Items solo, sin PutRequest) | Falso |
| `--all-as-string` | Fuerza todos valores a tipo String (S) | Falso |
| `--no-empty-as-null` | No convierte strings vacíos a NULL | Falso |
| `--string-cols` | Columnas a forzar como String (ej: `col1,col2`) | Vacío |

### split_dynamo_batch.py

| Argumento | Descripción | Default |
|-----------|-------------|---------|
| `input_file` | Archivo JSON con tabla | Requerido |
| `--batch-size` | Items por batch (máx 25) | 25 |
| `--output-prefix` | Prefijo para archivos de salida | `batch` |

### upload_dynamo_batches.sh

Script sin argumentos. Carga automáticamente todos los archivos `{table}_batch_*.json`

## Formatos

### Entrada

**CSV:**
```csv
_SkuId (Not changeable),_SKUReferenceCode,Name,Price
123,000050,Producto A,99.99
124,000099,Producto B,49.99
```

**XLSX/XLS:**
Similar a CSV, con soporte para múltiples hojas

### Salida: DynamoDB JSON (batch-write format)

```json
{
  "ProductTable": [
    {
      "PutRequest": {
        "Item": {
          "_SkuId": {"N": "123"},
          "_SKUReferenceCode": {"S": "000050"},
          "Name": {"S": "Producto A"},
          "Price": {"N": "99.99"}
        }
      }
    },
    {
      "PutRequest": {
        "Item": {
          "_SkuId": {"N": "124"},
          "_SKUReferenceCode": {"S": "000099"},
          "Name": {"S": "Producto B"},
          "Price": {"N": "49.99"}
        }
      }
    }
  ]
}
```

### Salida: NDJSON (Items solo)

```json
{"_SkuId":{"N":"123"},"_SKUReferenceCode":{"S":"000050"},"Name":{"S":"Producto A"},"Price":{"N":"99.99"}}
{"_SkuId":{"N":"124"},"_SKUReferenceCode":{"S":"000099"},"Name":{"S":"Producto B"},"Price":{"N":"49.99"}}
```

## Tipos de Datos DynamoDB

| Entrada Python | DynamoDB Type | Ejemplo |
|---|---|---|
| número (int/float) | N (Number) | `{"N":"123"}` |
| string | S (String) | `{"S":"value"}` |
| bool | BOOL | `{"BOOL":true}` |
| null | NULL | `{"NULL":true}` |
| lista | L (List) | `{"L":[...]}` |
| dict | M (Map) | `{"M":{...}}` |
| vacío | NULL (predeterminado) | `{"NULL":true}` |

## Limpieza de Nombres de Columna

Automáticamente se eliminan comentarios entre paréntesis:

```
Entrada:                    Salida:
_SkuId (Not changeable)  →  _SkuId
_ProductId (Not changeable) →  _ProductId
Name                     →  Name
```

## Lógica de Procesamiento

1. Detección automática de formato (CSV/XLSX/XLS)
2. Lectura de datos tabulares
3. Para cada fila:
   - Limpia nombres de columna
   - Convierte valores a tipos DynamoDB
   - Genera PutRequest si hay tabla-name, Items solo si NDJSON
4. Validación: omite items con `_SKUReferenceCode` NULL
5. Genera archivo JSON/NDJSON

## Notas/Caveats

- **Límite DynamoDB**: 25 items máximo por batch-write
- **Nombres columna**: Paréntesis se limpian automáticamente
- **_SKUReferenceCode**: Items sin este campo se omiten automáticamente
- **Tipos numéricos**: Strings que parecen números se convierten a N
- **Strings con ceros**: "000050" se mantiene como string (no number)
- **Archivos Excel**: Requiere pandas y openpyxl
- **UTF-8**: Se preserva codificación UTF-8
- **Rate limiting**: upload_dynamo_batches.sh incluye delay de 1s entre requests
- **Batch-write JSON**: Está optimizado para AWS CLI batch-write-item

## Ejemplos Prácticos

### Convertir y subir CSV a DynamoDB

```bash
# Convertir CSV
python3 dynamojson_from_tabular.py productos.csv --table-name Products -o prod.json

# Dividir si es necesario
python3 split_dynamo_batch.py prod.json --batch-size 25

# Cargar todos
bash upload_dynamo_batches.sh
```

### Usar NDJSON para procesamiento streaming

```bash
# Generar NDJSON
python3 dynamojson_from_tabular.py data.csv --ndjson -o data.ndjson

# Procesar línea por línea
while IFS= read -r line; do
  # Procesar cada Item DynamoDB
  echo "$line"
done < data.ndjson
```

### Forzar columnas específicas como strings

```bash
python3 dynamojson_from_tabular.py data.xlsx \
  --table-name MyTable \
  --string-cols "_SkuId,RefId,ZipCode" \
  -o output.json
```

## Archivos Generados

- `{input_base}.json` - JSON batch-write listo para DynamoDB
- `{input_base}_batch_001.json` - Primer lote si se divide
- `dynamo_upload_success_*.log` - Log de uploads exitosos
- `dynamo_upload_errors_*.log` - Log de errores
