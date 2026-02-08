# Añadidor de Especificaciones de Producto

Asigna especificaciones a productos en VTEX mediante procesamiento concurrente.

## Descripción

Este script lee un CSV con especificaciones de producto y las asigna a productos en VTEX usando el endpoint `/api/catalog/pvt/product/{productId}/specification` con procesamiento paralelo para mejor velocidad.

**Características:**
- Procesamiento concurrente con múltiples workers
- Rate limiting compartido con token bucket
- Manejo dinámico de errores 429 (Too Many Requests)
- Exponential backoff con jitter
- Dry-run mode para validación segura

## Requisitos

- Python 3.6+
- Credenciales VTEX en `.env`
- Archivo CSV con especificaciones de producto

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install requests python-dotenv
```

## Configuración

Archivo `.env` en raíz:

```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

### Uso Básico

```bash
python3 add_product_specifications.py input.csv
```

### Dry-Run (sin asignar de verdad)

```bash
python3 add_product_specifications.py input.csv --dry-run
```

### Con Workers y RPS Personalizados

```bash
python3 add_product_specifications.py input.csv --workers 8 --rps 15
```

### Ejemplo Completo

```bash
# Paso 1: Probar sin daño
python3 add_product_specifications.py input.csv --dry-run

# Paso 2: Ejecutar de verdad
python3 add_product_specifications.py input.csv --workers 4 --rps 10
```

### Ver Ayuda

```bash
python3 add_product_specifications.py --help
```

## Formato de Entrada

### Archivo CSV

Debe contener especificaciones a asignar a productos.

**Estructura esperada:**
```csv
_ProductId,CategoryId,FieldId,Text
100,118,1001,5
200,200,2001,10
300,118,1002,metro
```

**Columnas requeridas:**
- `_ProductId`: ID del producto en VTEX
- `CategoryId`: ID de la categoría
- `FieldId`: ID del campo de especificación
- `Text`: Valor de la especificación

**Características:**
- Una fila por especificación a asignar
- Un producto puede tener múltiples especificaciones
- FieldValueId NO se envía a la API

**Ejemplo real:**
- Archivo: `input.csv`
- Registros: 66,902 especificaciones a asignar

## Formato de Salida

El script genera archivos con timestamp (YYYYMMDD_HHMMSS):

### 1. Asignaciones Exitosas

**YYYYMMDD_HHMMSS_successful.json**

Contiene respuestas API completas para asignaciones exitosas.

**Estructura:**
```json
[
  {
    "productId": "100",
    "fieldId": "1001",
    "fieldValueId": 101,
    "value": "5",
    "status_code": 200,
    "timestamp": "2026-01-13T21:45:05"
  }
]
```

**Ejemplo real:**
- Archivo: `20260113_164505_successful.json`
- Registros: 66,902 asignaciones exitosas

### 2. Asignaciones Fallidas

**YYYYMMDD_HHMMSS_failed.json**

Contiene errores detallados para asignaciones que fallaron.

**Estructura:**
```json
[
  {
    "productId": "999",
    "fieldId": "9999",
    "error": "Product not found",
    "status_code": 404,
    "timestamp": "2026-01-13T21:45:06"
  }
]
```

**Formato CSV también disponible:**

**YYYYMMDD_HHMMSS_failed.csv**
- Para análisis rápido de errores
- Una fila por error

### 3. Reporte

**YYYYMMDD_HHMMSS_spec_add_report.md**

Reporte markdown con estadísticas.

**Contenido típico:**
```markdown
# Product Specifications Addition Report

**Timestamp:** 2026-01-13 21:45:05

## Summary
- Total Specifications: 66,902
- Successful: 66,850
- Failed: 52
- Success Rate: 99.92%

## Errors
- 404 Not Found: 30
- 400 Bad Request: 15
- 429 Rate Limit: 7

## Performance
- Duration: 45 minutes 30 seconds
- Rate: ~24 req/sec
```

## Cómo Funciona

### Fase 1: Carga de Entrada
1. Lee archivo CSV
2. Valida columnas requeridas
3. Carga especificaciones en lista
4. Imprime estadísticas

### Fase 2: Configuración de Workers
1. Crea token bucket para rate limiting
2. Inicializa ThreadPoolExecutor con N workers
3. Configura sesión HTTP por worker

### Fase 3: Asignaciones Concurrentes
Para cada especificación:
1. Worker solicita token del rate limiter
2. Construye request body (FieldId, Text)
3. Realiza POST a API VTEX
4. Procesa respuesta:
   - 200 (exitoso): Registra en successful
   - 429 (rate limit): Reintenta con backoff
   - Otros errores: Registra en failed

### Fase 4: Exportación
1. Escribe JSON de exitosos
2. Escribe JSON/CSV de fallidos
3. Genera reporte markdown

## Body de Solicitud API

```json
{
  "FieldId": 1001,
  "Text": "5"
}
```

**Notas:**
- FieldValueId NO se envía
- Text es obligatorio
- Se auto-genera FieldValueId en VTEX

## Configuración de Procesamiento

### Workers
- **Default:** 4
- **Rango:** 2-8
- **Impacto:** Más = más concurrencia pero más 429s

### RPS (Requests Per Second)
- **Default:** 10
- **Rango:** 5-20
- **Impacto:** Más = más rápido pero más errores

**Combinación típica:**
```bash
4 workers @ 10 RPS = ~40 req/segundo = 144,000/hora
```

## Rate Limiting

Usa **token bucket** compartido entre workers:

```
Inicial: bucket.tokens = capacity
Cada segundo: bucket.tokens += rate

Cuando consumen token:
- Si hay token: consume, continúa
- Si no hay: espera (sleep)
- Luego: consume, continúa
```

**Exponential Backoff (para 429):**
```
Intento 1: inmediato
Intento 2: espera 1s
Intento 3: espera 2s
Intento 4: espera 4s
```

## Argumentos CLI

```
add_product_specifications.py [-h] [--dry-run] [--workers N] [--rps N]
                              input_csv

Posicionales:
  input_csv       CSV con especificaciones a asignar

Opcionales:
  -h, --help      Muestra mensaje de ayuda
  --dry-run       Simula sin hacer asignaciones reales
  --workers N     Número de workers concurrentes (default: 4)
  --rps N         Requests per second (default: 10)
```

## Ejemplo Completo

```bash
# Paso 1: Validar con dry-run
python3 add_product_specifications.py input.csv --dry-run

# Paso 2: Ejecutar asignación real
python3 add_product_specifications.py input.csv --workers 4 --rps 10

# Archivos generados:
# - 20260113_164505_successful.json
# - 20260113_165141_successful.json (si se ejecuta nuevamente)
# - 20260113_165141_spec_add_report.md
```

## Progreso y Monitoreo

El script imprime progreso en tiempo real:

```
Processing Specifications...
[████████████████░░░░░░░░░░░░░░░░░░] 45%
Processed: 30,000 | Successful: 29,800 | Failed: 200
Rate: ~22 req/sec | Elapsed: 22m | ETA: 27m
```

## Endpoint API

```
POST https://{accountName}.{environment}.com.br/api/catalog/pvt/product/{productId}/specification
```

**Request Body:**
```json
{
  "FieldId": <int>,
  "Text": "<string>"
}
```

**Response (200 OK):**
```json
{
  "Id": 1001,
  "ProductId": 100,
  "FieldId": 1001,
  "Text": "5",
  "FieldValueId": 101
}
```

## Códigos de Respuesta

- **200 OK**: Especificación asignada exitosamente
- **400 Bad Request**: Datos inválidos (FieldId no existe, etc.)
- **404 Not Found**: Producto no existe
- **429 Too Many Requests**: Rate limit excedido (se reintenta)
- **500 Server Error**: Error del servidor VTEX (se reintenta)

## Performance Típico

| Config | Velocidad | Duración (66K items) | Tasa Error |
|--------|-----------|----------------------|-----------|
| 2w, 5 RPS | ~10 req/s | ~1.8 horas | <1% |
| 4w, 10 RPS | ~40 req/s | ~27 minutos | ~2% |
| 8w, 20 RPS | ~160 req/s | ~6.8 minutos | ~5% |

## Solución de Problemas

### Error: "Missing VTEX credentials"
Verifique `.env` en raíz con todas las variables

### Muchos errores 404
- ProductId no existe en VTEX
- Revise que los IDs sean válidos
- Consulte archivo de fallos

### Muchos errores 400
- FieldId puede no existir para esa categoría
- Verifique estructura de especificaciones
- Revise reporte de errores

### Errores 429 frecuentes
- Disminuya RPS: `--rps 5`
- Disminuya workers: `--workers 2`

### Ejecución lenta
- Aumente workers: `--workers 8`
- Aumente RPS: `--rps 20`

### Interrupción a mitad
- Presione Ctrl+C para parar gracefully
- Archivos de salida pueden estar parciales
- Reintente con especificaciones no procesadas

## Validación Pre-ejecución

Con dry-run, se valida:
- Formato del CSV
- Existencia de columnas
- Credenciales VTEX
- Conectividad a API

Sin hacer ningún cambio en VTEX.

## Notas Importantes

- **Irreversible:** Una vez asignadas, revise antes de continuar
- **Dry-run obligatorio:** Siempre probar primero
- **Errors son normales:** 1-5% de errores es típico
- **Reintentos:** El script reintenta automáticamente 429s
- **Performance:** Varía con latencia de VTEX

## Casos de Uso

### 1. Asignar especificaciones por lotes
```bash
python3 add_product_specifications.py especificaciones_lote1.csv
python3 add_product_specifications.py especificaciones_lote2.csv
```

### 2. Recuperación de fallos
```bash
# Después de un fallo, reintente solo especificaciones no asignadas
python3 add_product_specifications.py especificaciones_fallidas.csv
```

### 3. Actualización lenta (sin sobrecargar)
```bash
# Procesar lentamente para no afectar tráfico
python3 add_product_specifications.py input.csv --workers 2 --rps 5
```
