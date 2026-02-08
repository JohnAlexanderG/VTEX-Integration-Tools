# 43_dynamodb_to_json

## Descripción

Convierte archivos CSV que contienen datos en formato DynamoDB AttributeValue JSON a archivos JSON planos. Deserializa recursivamente todos los tipos DynamoDB (S, N, BOOL, NULL, L, M, SS, NS, BS) y fusiona los campos de forma plana con las demás columnas del CSV.

## Requisitos

- Python 3.6+ (solo librería estándar: csv, json, argparse, sys)
- Sin dependencias externas

## Uso

```bash
python3 dynamodb_to_json.py <input.csv> <output.json> [-i <indent>] [--vtex-data-column <column>]
```

### Argumentos

- `input.csv` - Archivo CSV de entrada con datos DynamoDB
- `output.json` - Archivo JSON de salida plano
- `-i, --indent <número>` - Nivel de indentación (default: ninguno/compacto)
- `--vtex-data-column <nombre>` - Columna que contiene datos DynamoDB (default: `vtex_data`)

### Ejemplos

```bash
# Conversión básica
python3 dynamodb_to_json.py input.csv output.json --indent 4

# Usando stdin/stdout
cat input.csv | python3 dynamodb_to_json.py - - -i 4

# Columna personalizada
python3 dynamodb_to_json.py input.csv output.json --vtex-data-column my_custom_column
```

## Formato de Entrada

### input.csv

Requiere una columna con datos en formato DynamoDB AttributeValue JSON. Las demás columnas se copian tal como están.

**Ejemplo:**
```csv
id,nombre,vtex_data
001,Producto A,"{""S"":""valor"",""N"":""123""}"
002,Producto B,"{""M"":{""field1"":{""S"":""test""},""field2"":{""N"":""99""}}}"
```

## Formato de Salida

Archivo JSON con array de objetos. Cada objeto tiene:
- Todas las columnas CSV originales (excepto la columna DynamoDB)
- Todos los campos deserializados de la columna DynamoDB fusionados de forma plana

**output.json**
```json
[
  {
    "id": "001",
    "nombre": "Producto A",
    "S": "valor",
    "N": 123
  },
  {
    "id": "002",
    "nombre": "Producto B",
    "field1": "test",
    "field2": 99
  }
]
```

## Tipos DynamoDB Soportados

| Tipo | Ejemplo | Resultado |
|------|---------|-----------|
| S (String) | `{"S":"value"}` | `"value"` |
| N (Number) | `{"N":"123"}` | `123` o `123.45` |
| BOOL (Boolean) | `{"BOOL":true}` | `true` |
| NULL | `{"NULL":true}` | `null` |
| L (List) | `{"L":[...]}` | Array (recursivo) |
| M (Map) | `{"M":{...}}` | Objeto (recursivo) |
| SS (String Set) | `{"SS":[...]}` | Array de strings |
| NS (Number Set) | `{"NS":[...]}` | Array de números |
| BS (Binary Set) | `{"BS":[...]}` | Array de binarios |

## Lógica de Funcionamiento

1. Lee el CSV usando csv.DictReader
2. Para cada fila:
   - Copia todas las columnas excepto la columna DynamoDB especificada
   - Lee la columna DynamoDB como JSON string
   - Deserializa todos los tipos DynamoDB recursivamente
   - Fusiona los campos deserializados con el resto de la fila
3. Exporta array JSON con todos los registros procesados

## Notas/Caveats

- Solo librería estándar, sin dependencias externas
- Soporta pipelines stdin/stdout usando `-` como nombre de archivo
- JSON malformado en la columna DynamoDB se copia tal como está (con advertencia a stderr)
- Valores NULL se convierten a `null` en JSON (no strings vacías)
- Numbers se convierten a int o float según corresponda
- Recursividad total soportada para Maps y Lists anidados
- Resumen de procesamiento se envía a stderr
