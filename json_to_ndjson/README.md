# json_to_ndjson

## Descripción

Convertidor streaming de JSON (array) a NDJSON. Transforma archivos JSON con grandes arrays de objetos en NDJSON (newline delimited JSON) para procesamiento eficiente en memoria. Soporta detección automática de formato, selección de campos, validación y exclusión por warehouse.

## Requisitos

- Python 3.6+ (librerías estándar: argparse, json, os, sys, time, typing)
- Sin dependencias externas

## Uso

```bash
python3 json_to_ndjson.py -i <input.json> [-o <output.ndjson>] [opciones]
```

### Argumentos

- `-i, --input` - Archivo de entrada (JSON array o NDJSON) - requerido
- `-o, --output` - Archivo de salida NDJSON (default: `{input_base}.ndjson`)
- `--keep` - Lista de campos a conservar (ej: `_SkuId,warehouseId,quantity`)
- `--drop` - Lista de campos a eliminar (ej: `foo,bar,baz`)
- `--require` - Campos obligatorios; líneas sin ellos se descartan
- `--exclude-warehouse` - Valor de `warehouseId` a excluir
- `--no-progress` - Desactiva mensajes de progreso

### Ejemplos

```bash
# Conversión simple (auto-detecta formato)
python3 json_to_ndjson.py -i inventory.json -o inventory.ndjson

# Mantener solo ciertos campos
python3 json_to_ndjson.py -i inventory.json -o inv_clean.ndjson \
  --keep _SkuId,warehouseId,quantity,unlimitedQuantity

# Excluir campos específicos
python3 json_to_ndjson.py -i data.json -o data_clean.ndjson \
  --drop internal_field,debug_data

# Campos obligatorios
python3 json_to_ndjson.py -i data.json -o data_required.ndjson \
  --require _SkuId,warehouseId,quantity

# Excluir warehouse específico
python3 json_to_ndjson.py -i inventory.json -o inventory_no220.ndjson \
  --exclude-warehouse 220

# Sin mensajes de progreso
python3 json_to_ndjson.py -i inventory.json --no-progress
```

## Formato de Entrada

### JSON Array
```json
[
  {"_SkuId": 123, "warehouseId": "001", "quantity": 100},
  {"_SkuId": 124, "warehouseId": "021", "quantity": 50}
]
```

### NDJSON (también soportado)
```
{"_SkuId": 123, "warehouseId": "001", "quantity": 100}
{"_SkuId": 124, "warehouseId": "021", "quantity": 50}
```

## Formato de Salida

NDJSON - un objeto JSON por línea, sin corchetes ni comas entre elementos.

**output.ndjson**
```
{"_SkuId":123,"warehouseId":"001","quantity":100,"unlimitedQuantity":false}
{"_SkuId":124,"warehouseId":"021","quantity":50,"unlimitedQuantity":false}
```

## Características

- **Auto-detección**: Detecta automáticamente si entrada es JSON array o NDJSON
- **Streaming**: No carga todo el archivo en memoria
- **Tolerante**: Si ya es NDJSON, normaliza/sanea automáticamente (idempotente)
- **Selección de campos**: `--keep` o `--drop` para control granular
- **Validación**: `--require` para descartar líneas incompletas
- **Filtrado**: `--exclude-warehouse` para excluir almacenes específicos
- **Reporte**: Muestra progreso y estadísticas cada 10,000 elementos

## Lógica de Funcionamiento

1. Detecta formato de entrada: si comienza con `[` → JSON array, sino → NDJSON
2. Para JSON arrays:
   - Parsea character-by-character respetando strings y escapes
   - Emite objetos completamente parseados
3. Para NDJSON: itera línea por línea
4. Para cada objeto:
   - Valida que tenga campos requeridos (si `--require` se especificó)
   - Verifica que no esté excluido por warehouse (si `--exclude-warehouse` se especificó)
   - Aplica filtro `--keep` o `--drop`
   - Escribe línea NDJSON
5. Genera reporte con conteos

## Estadísticas de Salida

Se muestra información cada 10,000 elementos:
```
[progreso] escritos=10000 descartados=50 filtrados=5 total_leidos=10055 rate~2000 lps
[fin] escritos=50000 descartados=200 filtrados=25 total_leidos=50225 tiempo=25.5s rate~1960 lps
```

## Notas/Caveats

- **Streaming**: Ideal para archivos 300k+ registros (bajo uso de memoria)
- **Idempotente**: Puede procesar tanto JSON como NDJSON sin cambios
- **Lineal**: Tiempo O(n) con respecto al número de registros
- **Campos faltantes**: Con `--keep`, si campo no existe se omite (no error)
- **Warehouse**: Comparación como string (maneja números y strings)
- **JSON inválido**: Líneas inválidas se ignoran (no fallan el proceso)
- **Progreso**: Se muestra cada 10,000 elementos (configurable con `--no-progress`)
- **Control-C**: Presionar Ctrl+C interrumpe y finaliza correctamente
