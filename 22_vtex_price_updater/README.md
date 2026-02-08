# 22_vtex_price_updater

## Descripción

Actualiza precios de SKUs en VTEX de forma masiva usando concurrencia. Lee un archivo JSON con lista de precios y realiza PUT requests concurrentes a la API de precios de VTEX, con soporte para rate limiting adaptativo, manejo robusto de reintentos y exportación de resultados detallados.

## Requisitos

- Python 3.6+
- Dependencias: `requests`
- Instalación: `pip install requests`
- Variables de entorno: `VTEX_ACCOUNT_NAME`, `X-VTEX-API-AppKey`, `X-VTEX-API-AppToken`

### Variables de entorno

```
VTEX_ACCOUNT_NAME=tu_cuenta
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
```

Se pueden cargar desde archivo `.env`:
```
export VTEX_ACCOUNT_NAME=...
export X-VTEX-API-AppKey=...
export X-VTEX-API-AppToken=...
```

## Uso

```bash
python3 vtex_price_updater_cost_optional.py --input <precio_json> [opciones]
```

### Comando básico

```bash
python3 vtex_price_updater_cost_optional.py --input precios.json
```

### Con concurrencia personalizada

```bash
python3 vtex_price_updater_cost_optional.py \
    --input precios.json \
    --concurrency 3 \
    --batch-size 50
```

### Para datasets grandes

```bash
python3 vtex_price_updater_cost_optional.py \
    --input precios_1000.json \
    --batch-size 100 \
    --concurrency 2
```

### Modo dry-run

```bash
python3 vtex_price_updater_cost_optional.py --input precios.json --dry-run
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `--input` | str | (requerido) Archivo JSON con datos de precios | (requerido) |
| `--concurrency` | int | Número de workers concurrentes | `1` |
| `--batch-size` | int | Tamaño del lote para actualización | `1` |
| `--infer-cost-from-base` | flag | Forzar costPrice = basePrice si falta | (desactivado) |
| `--dry-run` | flag | Simular sin realizar cambios reales | (desactivado) |

## Formato de entrada

### Archivo JSON (precios.json)

Array de objetos con precios de SKU:

```json
[
    {
        "_SkuId": 1,
        "_SKUReferenceCode": "000050",
        "basePrice": 17950
    },
    {
        "_SkuId": 2,
        "_SKUReferenceCode": "000051",
        "costPrice": 7917,
        "basePrice": 17950
    },
    {
        "_SkuId": 3,
        "_SKUReferenceCode": "000052",
        "costPrice": 5000,
        "basePrice": 25000
    }
]
```

**Campos soportados:**
- `_SkuId` (requerido): ID del SKU
- `_SKUReferenceCode` (requerido): Código de referencia del SKU
- `basePrice` (requerido): Precio base/lista (entero o string con formato precio)
- `costPrice` (opcional): Precio de costo (se omite si no está presente)

**Formato de precios:**
- Enteros: `17950`
- Floats: `179.50`
- Strings con símbolo: `"$ 17,950"` → `17950`
- Strings con comas decimales: `"179,50"` → `17950` (nota: coma como decimal)

## Formato de salida

### Archivo de éxitos (price-update-success-{timestamp}.json)

Reporte detallado de todas las actualizaciones exitosas:

```json
{
    "metadata": {
        "execution_date": "2025-02-08T15:30:45.123456Z",
        "total_processed": 1000,
        "successful": 950,
        "failed": 50,
        "success_rate_percent": 95.0
    },
    "successful_updates": [
        {
            "sku_id": 1,
            "reference_code": "000050",
            "base_price": 17950,
            "cost_price": null,
            "http_status": 200,
            "response_time_ms": 145
        },
        {
            "sku_id": 2,
            "reference_code": "000051",
            "base_price": 17950,
            "cost_price": 7917,
            "http_status": 200,
            "response_time_ms": 132
        }
    ]
}
```

### Archivo de errores (price-update-errors-{timestamp}.json)

Reporte categorizado de errores:

```json
{
    "summary": {
        "total_errors": 50,
        "by_category": {
            "http_errors": {
                "400": 10,
                "404": 15,
                "500": 5
            },
            "validation_errors": 15,
            "network_errors": 5
        }
    },
    "errors": [
        {
            "sku_id": 100,
            "reference_code": "000100",
            "error_type": "http_error",
            "status_code": 404,
            "message": "SKU not found"
        },
        {
            "sku_id": 101,
            "reference_code": "000101",
            "error_type": "validation_error",
            "message": "basePrice is required"
        }
    ]
}
```

### Archivo de errores CSV (price-update-errors-{timestamp}.csv)

Formato tabular de errores para análisis:

```csv
SkuId,ReferenceCode,ErrorType,StatusCode,ErrorMessage
100,000100,http_error,404,SKU not found
101,000101,validation_error,,basePrice is required
102,000102,network_error,,Connection timeout
```

## Cómo funciona

1. **Inicialización**:
   - Carga credenciales de variables de entorno
   - Valida que todos los parámetros requeridos estén presentes
   - Carga el archivo JSON de precios
   - Inicializa rate limiter (600 RPS por defecto)

2. **Rate Limiting**:
   - Límite global: 600 requests/minuto (10 por segundo)
   - Implementa ventana deslizante (sliding window)
   - Detección adaptativa de 429: incrementa delay si necesario
   - Backoff automático: reduce RPS temporal cuando se detectan 429s

3. **Procesamiento concurrente**:
   - Crea N workers (threads) configurables
   - Distribuye items entre workers
   - Cada worker tiene su propia sesión HTTP para evitar contención
   - Workers operan en paralelo respetando rate limit global

4. **Para cada item de precio**:
   - Validación: verifica campos requeridos (SkuId, basePrice)
   - Normalización: convierte precios a enteros (maneja múltiples formatos)
   - Construcción de payload:
     - Siempre: `basePrice`
     - Condicional: `costPrice` (si existe en entrada o `--infer-cost-from-base`)
   - PUT a `/pricing/prices/{itemId}` (API de Pricing de VTEX)
   - Reintentos: máximo 3 intentos con exponential backoff
   - Timeouts: 10 segundos por defecto

5. **Manejo de 429 (Rate Limit)**:
   - Incrementa delay adaptativo (+0.5s cada 429, máx 5s)
   - Reintenta automáticamente después del delay
   - Reduce delay gradualmente después de requests exitosos

6. **Exportación de resultados**:
   - JSON detallado de éxitos con metadata
   - JSON categorizado de errores
   - CSV de errores para análisis rápido
   - Timestamp en nombre de archivo

## Notas y caveats

- **costPrice es opcional**: Si no está presente en entrada, solo se envía basePrice (VTEX derivará costPrice)
- **Formato de precios flexible**: Soporta enteros, floats, strings con símbolos, comas decimales
- **Concurrencia adaptada**: Por defecto 1 worker; aumentar para datasets grandes (3-8 workers típico)
- **Rate limiting global**: Respeta límite de 600 RPS compartido entre todos los workers
- **Adaptación a 429**: Detecta automáticamente cuando se excede límite y aplica backoff
- **Reintentos con backoff**: Máximo 3 intentos por item con delay creciente
- **Dry-run útil**: Valida formato sin realizar cambios
- **Timestamps ISO**: Fechas en formato ISO 8601 con zona horaria
- **Thread-safe**: Las operaciones de stats son thread-safe
- **Pausa entre lotes**: Configurable con `--batch-size` para control de memoria

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| 404 Not Found | SKU no existe | Verificar SkuId en VTEX |
| 400 Bad Request | Precio inválido | Verificar formato de basePrice |
| 429 Too Many Requests | Exceso de rate limit | Reducir concurrency, aumentar delay |
| Connection timeout | Red lenta | Aumentar timeout o reducir concurrency |
