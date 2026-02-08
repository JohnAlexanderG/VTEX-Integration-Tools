# Eliminador de Especificaciones de Producto

Elimina todas las especificaciones de productos en VTEX usando procesamiento concurrente.

## Descripción

Este script lee IDs de productos desde un archivo CSV y elimina todas sus especificaciones utilizando el endpoint `/api/catalog/pvt/product/{productId}/specification` de VTEX con procesamiento paralelo para mayor velocidad.

**Características:**
- Procesamiento concurrente con múltiples workers
- Rate limiting con token bucket compartido
- Manejo adaptativo de errores 429 (Too Many Requests)
- Exponential backoff con jitter
- Dry-run para pruebas seguras

## Requisitos

- Python 3.6+
- Credenciales VTEX en `.env`
- Archivo CSV con IDs de productos

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install requests python-dotenv
```

## Configuración

Archivo `.env` en raíz del proyecto:

```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

### Uso Básico

```bash
python3 delete_product_specifications.py productos.csv
```

### Dry-Run (sin eliminar de verdad)

```bash
python3 delete_product_specifications.py productos.csv --dry-run
```

### Con Workers y RPS Personalizados

```bash
python3 delete_product_specifications.py productos.csv --workers 8 --rps 15
```

### Ejemplo Completo

```bash
# Primero probar sin daño
python3 delete_product_specifications.py productos.csv --dry-run

# Si está bien, ejecutar de verdad
python3 delete_product_specifications.py productos.csv --workers 4 --rps 10
```

### Ver Ayuda

```bash
python3 delete_product_specifications.py --help
```

## Formato de Entrada

### Archivo CSV

Debe contener IDs de productos a procesar.

**Estructura esperada:**
```csv
_ProductId
123
456
789
1000
```

**Columna requerida:**
- `_ProductId`: ID numérico del producto en VTEX

**Ejemplo real:**
- Archivo: `mapping_file.csv`
- Registros: 352,546 productos
- Rango de IDs: Del 1 al 999999

## Formato de Salida

El script genera archivos con timestamp (YYYYMMDD_HHMMSS):

### 1. Eliminaciones Exitosas

**YYYYMMDD_HHMMSS_successful.json**
- Respuestas API para eliminaciones exitosas (status 204)
- Contiene ProductId y detalles de respuesta

**Ejemplo:**
```json
[
  {
    "ProductId": "123",
    "status_code": 204,
    "timestamp": "2026-01-10T21:39:01"
  },
  {
    "ProductId": "456",
    "status_code": 204,
    "timestamp": "2026-01-10T21:39:02"
  }
]
```

### 2. Eliminaciones Fallidas

**YYYYMMDD_HHMMSS_failed.json**
- Errores detallados para eliminaciones que fallaron
- Incluye código de error y mensaje de la API

**Ejemplo:**
```json
[
  {
    "ProductId": "999",
    "error": "Product not found",
    "status_code": 404,
    "timestamp": "2026-01-10T21:39:03"
  }
]
```

### 3. Reporte

**YYYYMMDD_HHMMSS_deletion_report.md**
- Reporte markdown con estadísticas
- Incluye tasa de éxito, errores, tiempo de ejecución

**Contenido típico:**
```markdown
# Product Specifications Deletion Report

**Timestamp:** 2026-01-10 21:39:01

## Summary
- Total Products: 352,546
- Successful: 352,400
- Failed: 146
- Success Rate: 99.96%

## Errors
- 404 Not Found: 100
- 429 Rate Limit: 30
- 500 Server Error: 16

## Performance
- Duration: 45 minutes 32 seconds
- Rate: ~129 requests/second
```

**Ubicación:** Mismo directorio, con sufijo `_deletion_report.md`

## Cómo Funciona

### Fase 1: Carga de Entrada
1. Lee archivo CSV
2. Valida columna `_ProductId`
3. Carga todos los IDs en lista
4. Mostraa estadísticas de carga

### Fase 2: Configuración de Workers
1. Crea token bucket para rate limiting
2. Inicializa pool de workers con ThreadPoolExecutor
3. Configura sesiones HTTP por worker

### Fase 3: Eliminaciones Concurrentes
Para cada ProductId:
1. Worker solicita token del rate limiter
2. Realiza DELETE a la API VTEX
3. Maneja respuestas:
   - 204 (exitoso): Registra en successful
   - 429 (rate limit): Reintenta con exponential backoff
   - Otros errores: Registra en failed

### Fase 4: Exportación de Resultados
1. Escribe JSON de exitosos
2. Escribe JSON de fallidos
3. Genera reporte markdown
4. Muestra resumen en consola

## Parámetros de Configuración

### Workers
- **Default:** 4
- **Rango recomendado:** 2-8
- **Impacto:** Más workers = más concurrencia pero potencial 429 errors

### RPS (Requests Per Second)
- **Default:** 10
- **Rango recomendado:** 5-20
- **Impacto:** Más RPS = más rápido pero más errores de rate limit

**Ejemplo:**
- 4 workers @ 10 RPS: ~40 requests/segundo = ~144,000 por hora

## Rate Limiting

El script usa **token bucket** compartido:
- Evita sobrecargar API VTEX
- Comparte tokens entre todos los workers
- Maneja dinámicamente límites de tasa

**Exponential Backoff:**
```
1er intento: inmediato
2do intento: espera 1 segundo
3er intento: espera 2 segundos
4to intento: espera 4 segundos
```

## Argumentos CLI

```
delete_product_specifications.py [-h] [--dry-run] [--workers N] [--rps N]
                                 input_csv

Posicionales:
  input_csv       CSV con _ProductId a eliminar

Opcionales:
  -h, --help      Muestra mensaje de ayuda
  --dry-run       Simula sin hacer eliminaciones reales
  --workers N     Número de workers concurrentes (default: 4)
  --rps N         Requests per second (default: 10)
```

## Ejemplo Completo

```bash
# Paso 1: Probar con dry-run
python3 delete_product_specifications.py mapping_file.csv --dry-run

# Paso 2: Ejecutar eliminación real
python3 delete_product_specifications.py mapping_file.csv --workers 4 --rps 10

# Archivos generados:
# - 20260110_213901_successful.json
# - 20260110_213901_failed.json (si hay errores)
# - 20260110_213901_deletion_report.md
```

## Monitoreo de Ejecución

El script imprime progreso:

```
Processing ProductIds...
[████████████████████░░░░░░░░░░░░░░░] 60%
Processed: 211,500 | Successful: 211,300 | Failed: 200
Rate: ~125 req/sec | Elapsed: 28m | ETA: 18m
```

## Endpoint API

```
DELETE https://{accountName}.{environment}.com.br/api/catalog/pvt/product/{productId}/specification
```

## Códigos de Respuesta Esperados

- **204 No Content**: Eliminación exitosa
- **404 Not Found**: Producto no existe
- **429 Too Many Requests**: Rate limit excedido (se reintenta)
- **500 Server Error**: Error del servidor (se reintenta)

## Performance Típico

| Configuración | Velocidad | Duración (352K items) | Errores |
|---------------|-----------|----------------------|---------|
| 2 workers, 5 RPS | ~10 req/s | ~10 horas | <1% |
| 4 workers, 10 RPS | ~40 req/s | ~2.5 horas | ~2% |
| 8 workers, 20 RPS | ~160 req/s | ~37 minutos | ~5% |

## Solución de Problemas

### Error: "Missing VTEX credentials"
Verifique que `.env` en raíz contiene todas las variables

### Muchos errores 429
- Disminuya RPS: `--rps 5`
- Disminuya workers: `--workers 2`

### Errores 404
- El ProductId no existe en VTEX
- Verifique que los IDs son válidos
- Use archivo de fallos para análisis

### Ejecución muy lenta
- Aumente workers: `--workers 8`
- Aumente RPS: `--rps 20`
- Pero cuidado con rate limits

### Interrupción a mitad del proceso
- Presione Ctrl+C para detener gracefully
- Verifique archivos de salida (pueden estar parciales)
- Reintente o use IDs no procesados

## Seguridad

- **Dry-run obligatorio**: Siempre probar primero sin `--dry-run`
- **Reversión**: No hay forma de restaurar especificaciones eliminadas
- **Backup**: Exporte especificaciones antes de eliminar
- **Validación**: Verifica formato de CSV antes de procesar

## Notas Importantes

- Las especificaciones NO se pueden recuperar una vez eliminadas
- El proceso es irreversible - siempre hacer backup primero
- Dry-run toma igual tiempo pero sin hacer cambios reales
- Los errores 404 son normales si algunos ProductIds no existen
