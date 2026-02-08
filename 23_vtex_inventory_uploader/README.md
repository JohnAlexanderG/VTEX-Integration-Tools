# 23_vtex_inventory_uploader

## Descripción

Actualiza inventario de SKUs por bodega (warehouse) en VTEX usando procesamiento concurrente. Lee un archivo JSON o NDJSON con datos de inventario y realiza PUT requests concurrentes a la API de logística de VTEX, con rate limiting global, manejo robusto de errores y exportación de reportes.

## Requisitos

- Python 3.6+
- Dependencias: `requests`
- Instalación: `pip install requests`
- Archivo `.env` en el directorio padre (../.env) con credenciales VTEX

### Variables de entorno (.env)

```
VTEX_ACCOUNT_NAME=tu_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
```

## Uso

```bash
python3 vtex_inventory_uploader.py --input <inventario> [opciones]
```

### Comando básico

```bash
python3 vtex_inventory_uploader.py --input inventario.json
```

### Con opciones de concurrencia

```bash
python3 vtex_inventory_uploader.py \
    --input inventario.json \
    --failures fallos.csv \
    --summary resumen.md \
    --rps 30 \
    --workers 8
```

### Para datasets grandes en NDJSON

```bash
python3 vtex_inventory_uploader.py \
    --input inventario.ndjson \
    --batch-size 100 \
    --workers 8 \
    --rps 30
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `--input` | str | (requerido) Archivo JSON o NDJSON con datos de inventario | (requerido) |
| `--failures` | str | Archivo CSV para fallos | `failures_{timestamp}.csv` |
| `--summary` | str | Archivo markdown con resumen | `summary_{timestamp}.md` |
| `--rps` | int | Requests per second (rate limit) | `10` |
| `--workers` | int | Número de workers concurrentes | `4` |
| `--batch-size` | int | Registros por lote para progreso | `100` |
| `--timeout` | int | Timeout en segundos por request | `30` |

## Formato de entrada

### Archivo JSON (inventario.json)

Array de objetos con datos de inventario:

```json
[
    {
        "_SkuId": 1,
        "_SKUReferenceCode": "000050",
        "warehouseId": "220",
        "quantity": 96,
        "unlimitedQuantity": false
    },
    {
        "_SkuId": 2,
        "_SKUReferenceCode": "000051",
        "warehouseId": "220",
        "quantity": 150,
        "unlimitedQuantity": false
    },
    {
        "_SkuId": 3,
        "_SKUReferenceCode": "000052",
        "warehouseId": "221",
        "quantity": 50,
        "unlimitedQuantity": true
    }
]
```

### Archivo NDJSON (inventario.ndjson)

Formato de línea a línea (1 objeto JSON por línea):

```ndjson
{"_SkuId": 1, "_SKUReferenceCode": "000050", "warehouseId": "220", "quantity": 96, "unlimitedQuantity": false}
{"_SkuId": 2, "_SKUReferenceCode": "000051", "warehouseId": "220", "quantity": 150, "unlimitedQuantity": false}
{"_SkuId": 3, "_SKUReferenceCode": "000052", "warehouseId": "221", "quantity": 50, "unlimitedQuantity": true}
```

**Campos de entrada:**
- `_SkuId` (requerido): ID del SKU
- `_SKUReferenceCode` (requerido): Código de referencia
- `warehouseId` (requerido): ID de la bodega
- `quantity` (requerido): Cantidad disponible
- `unlimitedQuantity` (requerido): Booleano para inventario ilimitado

## Formato de salida

### Archivo CSV de fallos (failures_{timestamp}.csv)

Contiene registros que fallaron:

```csv
SkuId,WarehouseId,Quantity,HttpStatus,ErrorMessage,Timestamp
1,220,96,404,SKU not found,2025-02-08 15:30:45
2,221,150,400,Invalid warehouse ID,2025-02-08 15:30:46
3,220,50,429,Too many requests,2025-02-08 15:30:47
```

### Archivo markdown de resumen (summary_{timestamp}.md)

Reporte detallado de la ejecución:

```markdown
# Resumen de Actualización de Inventario - VTEX

**Fecha de ejecución:** 2025-02-08 15:30:45.123456Z

## Estadísticas Generales

- **Total registros procesados:** 10,000
- **Actualizaciones exitosas:** 9,950
- **Fallos totales:** 50
- **Tasa de éxito:** 99.50%

## Detalles Técnicos

### Configuración
- **Workers concurrentes:** 8
- **Rate limit:** 30 RPS (Requests Per Second)
- **Timeout por request:** 30 segundos
- **Batch size:** 100 registros

### Performance
- **Tiempo total:** 5 minutos 32 segundos
- **RPS promedio actual:** 29.8
- **Latencia promedio:** 145ms

## Análisis de Errores

| Tipo de Error | Cantidad |
|---------------|----------|
| HTTP 404 | 25 |
| HTTP 400 | 15 |
| HTTP 429 | 5 |
| Network Timeout | 5 |

...
```

## Cómo funciona

1. **Inicialización**:
   - Carga credenciales desde `.env` (directorio padre)
   - Valida parámetros
   - Inicializa rate limiter tipo token bucket

2. **Lectura de entrada**:
   - Detecta automáticamente formato (JSON array o NDJSON)
   - JSON: carga array completo (útil para archivos < 100MB)
   - NDJSON: procesa línea a línea (ideal para archivos grandes > 300MB)
   - Memoria eficiente para datasets masivos

3. **Rate limiting**:
   - Token bucket implementation: tokens = RPS
   - Límite global compartido entre workers
   - Refresca tokens cada segundo
   - Espera si se excede límite

4. **Procesamiento concurrente**:
   - ThreadPoolExecutor con N workers
   - Cada worker mantiene sesión HTTP reutilizable
   - Distribución automática de trabajo
   - Progreso actualizado en tiempo real

5. **Para cada registro de inventario**:
   - Validación: verifica campos requeridos
   - Obtiene token del rate limiter
   - Construye URL: `/api/logistics/pvt/inventory/skus/{skuId}/warehouses/{warehouseId}`
   - Payload: `{ "quantity": ..., "unlimitedQuantity": ... }`
   - PUT request con timeout
   - Reintentos: máximo 3 intentos con exponential backoff si falla

6. **Manejo de errores**:
   - 429: Backoff adaptativo, no cuenta como fallo final
   - 5xx: Reintentos con exponential backoff
   - Timeouts: Reintentos automáticos
   - Otros errores: Registra y continúa

7. **Exportación de resultados**:
   - CSV con solo registros fallidos
   - Markdown con estadísticas completas
   - Timestamps ISO 8601
   - Análisis de rendimiento y errores

## Notas y caveats

- **NDJSON recomendado para grandes volúmenes**: Mejor consumo de memoria
- **Concurrencia adaptada a datos**: 4-8 workers típicamente óptimo
- **RPS configurable**: 10-30 típico según límites de VTEX
- **Rate limiting global**: Respeta límite compartido entre workers
- **Reintentos automáticos**: Máximo 3 intentos con backoff exponencial
- **Session reuse**: Cada worker reutiliza conexión HTTP
- **Thread-safe**: Operaciones de estadísticas protegidas con locks
- **Progreso en tiempo real**: Actualizaciones cada lote procesado
- **ETA estimada**: Se calcula basada en velocidad actual
- **Fallos thread-safe**: Escritura concurrente a CSV sincronizada
- **Formato de fechas**: ISO 8601 con zona horaria UTC

## Ejemplos de casos de uso

**Caso 1: Actualización pequeña (< 100MB)**
```bash
python3 vtex_inventory_uploader.py --input inventario.json --workers 4 --rps 20
```

**Caso 2: Dataset grande en NDJSON**
```bash
python3 vtex_inventory_uploader.py \
    --input inventario_300k.ndjson \
    --workers 8 \
    --rps 30 \
    --batch-size 200
```

**Caso 3: Actualización lenta (bajo impacto)**
```bash
python3 vtex_inventory_uploader.py \
    --input inventario.json \
    --workers 2 \
    --rps 5
```

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| Muchos 429s | Rate limit excedido | Reducir `--rps` o `--workers` |
| Out of memory | Archivo JSON muy grande | Convertir a NDJSON |
| Fallos altos | SKUs/bodegas inválidos | Validar datos de entrada |
| Ejecución lenta | Rate limiting muy conservador | Aumentar `--rps` gradually |
