# 12_vtex_product_create

## Descripción

Herramienta de creación masiva de productos en VTEX usando la API privada del catálogo. Paso final del flujo de transformación de datos que crea productos en el catálogo VTEX. Implementa rate limiting robusto, manejo de errores, reintentos automáticos con backoff exponencial, y genera reportes detallados con estadísticas de éxito y fallos.

## Funcionalidad

- Crea productos en VTEX usando endpoint POST `/api/catalog/pvt/product`
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Implementa control de rate limiting para evitar saturar la API VTEX
- Procesa lista de productos desde archivo JSON formateado
- Exporta respuestas exitosas y errores en archivos JSON separados
- Genera reporte markdown detallado con estadísticas y análisis de resultados
- Maneja todos los errores posibles de la API VTEX con logging comprehensivo
- Implementa reintentos automáticos con backoff exponencial en caso de rate limiting
- Muestra progreso en tiempo real durante la creación

## Requisitos Previos

### Variables de Entorno (.env)

Requiere las siguientes variables en archivo `.env` en la raíz del proyecto:

```
X-VTEX-API-AppKey=<tu_app_key>
X-VTEX-API-AppToken=<tu_app_token>
VTEX_ACCOUNT_NAME=<nombre_cuenta>
VTEX_ENVIRONMENT=vtexcommercestable  # (opcional, por defecto)
```

### Dependencias Python

```
requests
python-dotenv
```

## Uso

### Comando Básico

```bash
python3 vtex_product_create.py productos_vtex.json
```

### Con Configuración Personalizada de Timing

```bash
python3 vtex_product_create.py productos.json --delay 2 --timeout 45
```

### Con Archivos de Salida Personalizados

```bash
python3 vtex_product_create.py datos.json --output-prefix custom_batch
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input_file` | Archivo JSON con lista de productos para crear | Sí | N/A |
| `--delay` | Delay en segundos entre requests | No | 1.0 |
| `--timeout` | Timeout en segundos por request | No | 30 |
| `--output-prefix` | Prefijo para archivos de salida | No | `vtex_creation` |

## Formato de Entrada

### productos_vtex.json

Archivo JSON con lista de productos formateados para VTEX (salida paso 11):

```json
[
  {
    "Name": "Zapatos Nike Azules",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "RefId": "SKU001",
    "IsVisible": true,
    "Description": "Zapatos deportivos de alta calidad",
    "IsActive": true,
    "LinkId": "zapatos-nike-azules-sku001",
    "DescriptionShort": "Zapatos Nike",
    "KeyWords": "nike, zapatos, azules",
    "Title": "Zapatos Nike Azules",
    "MetaTagDescription": "Zapatos Nike",
    "ShowWithoutStock": true
  },
  {
    "Name": "Pantalón Adidas",
    "DepartmentId": 2,
    "CategoryId": 20,
    "BrandId": 2000002,
    "RefId": "SKU002",
    "IsVisible": true,
    "Description": "Pantalón deportivo gris",
    "IsActive": true,
    "LinkId": "pantalon-adidas-sku002",
    "ShowWithoutStock": true
  }
]
```

**Campos esperados:**
- `Name`: Nombre del producto (obligatorio)
- `RefId`: ID de referencia (obligatorio)
- `DepartmentId`: ID de departamento (obligatorio)
- `CategoryId`: ID de categoría (obligatorio)
- `BrandId`: ID de marca (obligatorio)
- `IsVisible`: Visibilidad (opcional, default: true)
- `Description`: Descripción (opcional)
- `IsActive`: Estado activo (opcional, default: true)
- `LinkId`: URL SEO (obligatorio)
- Otros campos opcionales

## Formato de Salida

### {timestamp}_vtex_creation_successful.json

Archivo JSON con productos creados exitosamente:

```json
[
  {
    "product_data": {
      "Name": "Zapatos Nike Azules",
      "DepartmentId": 1,
      "CategoryId": 10,
      "BrandId": 2000001,
      "RefId": "SKU001",
      ...
    },
    "response": {
      "Id": 1000001,
      "Name": "Zapatos Nike Azules",
      "DepartmentId": 1,
      "CategoryId": 10,
      "BrandId": 2000001,
      "RefId": "SKU001",
      "LinkId": "zapatos-nike-azules-sku001",
      ...
    },
    "status_code": 200,
    "ref_id": "SKU001",
    "name": "Zapatos Nike Azules",
    "timestamp": "2025-01-14T19:21:30.123456"
  }
]
```

**Contenido:**
- `product_data`: Datos enviados al API
- `response`: Respuesta completa de VTEX con productId asignado
- `status_code`: 200 o 201
- `ref_id`, `name`: Metadatos para referencia rápida
- `timestamp`: Cuándo se creó

### {timestamp}_vtex_creation_failed.json

Archivo JSON con productos que fallaron:

```json
[
  {
    "product_data": { ... },
    "error": "API Error: 400",
    "status_code": 400,
    "response": {
      "message": "The requested URL returned error: 400 Bad Request"
    },
    "ref_id": "SKU999",
    "name": "Producto Defectuoso",
    "timestamp": "2025-01-14T19:21:35.123456"
  }
]
```

**Contenido:**
- `product_data`: Datos que se intentaron enviar
- `error`: Descripción del error
- `status_code`: Código HTTP de error
- `response`: Respuesta del API con detalles del error
- `retry_count`: Número de reintentos realizados (si aplica)

### {timestamp}_vtex_creation_report.md

Reporte Markdown con estadísticas y análisis:

```markdown
# Reporte de Creación de Productos VTEX

**Fecha:** 2025-01-14 19:21:30
**Account VTEX:** mitienda
**Environment:** vtexcommercestable
**Duración:** 0:05:32

## 📊 Resumen de Resultados

| Métrica | Valor |
|---------|-------|
| **Total Procesados** | 1000 |
| **✅ Exitosos** | 950 |
| **❌ Fallidos** | 50 |
| **📈 Tasa de Éxito** | 95.0% |
| **⏱️ Delay entre requests** | 1.0s |
| **⏱️ Timeout por request** | 30s |

## ✅ Productos Creados Exitosamente (950)

| RefId | Nombre | Product ID | Timestamp |
|-------|--------|------------|-----------|
| SKU001 | Zapatos Nike Azules | 1000001 | 2025-01-14 19:21:31 |
| SKU002 | Pantalón Adidas | 1000002 | 2025-01-14 19:21:32 |
| ... | ... | ... | ... |

## ❌ Productos Fallidos (50)

### 📋 Resumen de Errores

- **API Error: 400**: 30 productos
- **Request timeout**: 15 productos
- **Rate limit exceeded**: 5 productos

### 📝 Detalle de Productos Fallidos

| RefId | Nombre | Error | Status Code | Timestamp |
|-------|--------|-------|-------------|-----------|
| SKU999 | Producto Defectuoso | API Error: 400 | 400 | 2025-01-14 19:21:35 |
| SKU998 | Otro Producto | Request timeout | 0 | 2025-01-14 19:21:40 |
| ... | ... | ... | ... | ... |

## 🔍 Análisis y Recomendaciones

✅ **Excelente tasa de éxito**. La integración funcionó correctamente.

### Errores más comunes:

- **API Error: 400**: 30 casos - Revisar datos de entrada
- **Request timeout**: 15 casos - Aumentar timeout en reintentos
- **Rate limit exceeded**: 5 casos - Aumentar delay entre requests
```

## Control de Rate Limiting

El script implementa control automático de rate limiting:

### Configuración

```
DEFAULT_DELAY = 1.0        # Segundos entre requests
DEFAULT_TIMEOUT = 30       # Timeout por request
MAX_RETRIES = 3            # Intentos máximos
BACKOFF_FACTOR = 2         # Multiplicador de espera
```

### Estrategia de Reintento

1. **Request exitoso (200/201):** Continúa al siguiente
2. **Rate limit (429):** Espera y reintenta
   - Intento 1: Espera 1s * 2^0 = 1s
   - Intento 2: Espera 1s * 2^1 = 2s
   - Intento 3: Espera 1s * 2^2 = 4s
3. **Timeout/Error:** Registra y continúa al siguiente

## Cómo Funciona

### Proceso de Creación

1. **Validación de credenciales:** Verifica que existan en .env
2. **Carga de archivo JSON:** Lee productos desde archivo
3. **Para cada producto:**
   - Pausa de `--delay` segundos
   - POST request al API VTEX
   - Maneja respuesta (exitosa o error)
   - Reintentar si es rate limiting (429)
   - Registra resultado
4. **Exporta resultados:**
   - JSON con productos exitosos
   - JSON con productos fallidos
   - Markdown con reporte
5. **Muestra resumen:** Estadísticas finales en consola

### Endpoint API Utilizado

```
POST https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt/product

Headers:
  Content-Type: application/json
  Accept: application/json
  X-VTEX-API-AppKey: {app_key}
  X-VTEX-API-AppToken: {app_token}

Body: JSON del producto
```

### Respuesta Exitosa

```json
{
  "Id": 1000001,
  "Name": "Zapatos Nike Azules",
  "DepartmentId": 1,
  "CategoryId": 10,
  "BrandId": 2000001,
  "RefId": "SKU001",
  ...
}
```

La respuesta incluye el `Id` asignado por VTEX (productId).

## Ejemplos de Ejecución

### Ejemplo 1: Creación Básica

```bash
python3 12_vtex_product_create/vtex_product_create.py vtex_ready.json
```

**Salida:**
```
🚀 Iniciando creación de 100 productos en VTEX...
⏱️ Delay entre requests: 1.0s
⏱️ Timeout por request: 30s
================================================================================

[1/100] Procesando producto...
✅ Producto creado: SKU001 - Zapatos Nike Azules
[2/100] Procesando producto...
✅ Producto creado: SKU002 - Pantalón Adidas
...
📊 Progreso: 10/100 (10.0%) - Éxito: 100.0%

✅ Procesamiento completado en 0:01:45
✅ Productos exitosos: 100
❌ Productos fallidos: 0
📊 Tasa de éxito: 100.0%

✅ Productos exitosos exportados a: 20250114_192130_vtex_creation_successful.json
📋 Reporte generado: 20250114_192130_vtex_creation_report.md
```

### Ejemplo 2: Con Delay Mayor

```bash
python3 12_vtex_product_create/vtex_product_create.py \
    productos.json \
    --delay 2 \
    --timeout 45
```

**Útil cuando:** API VTEX está cerca del límite de rate limiting

### Ejemplo 3: Con Prefijo Personalizado

```bash
python3 12_vtex_product_create/vtex_product_create.py \
    datos.json \
    --output-prefix batch_enero_2025
```

**Genera:**
- `20250114_192130_batch_enero_2025_successful.json`
- `20250114_192130_batch_enero_2025_failed.json`
- `20250114_192130_batch_enero_2025_report.md`

## Archivos Generados

El script genera 3 archivos (con timestamp):

1. **{timestamp}_vtex_creation_successful.json** - Productos creados exitosamente
2. **{timestamp}_vtex_creation_failed.json** - Productos que fallaron (si hay)
3. **{timestamp}_vtex_creation_report.md** - Reporte detallado

## Notas Importantes

- **Delay mínimo:** 1 segundo es recomendado para respetar rate limits de VTEX
- **Timeout recomendado:** 30 segundos por request
- **Orden de creación:** Se respeta el orden del archivo JSON
- **Reintentos automáticos:** Maneja 429 (rate limit) y 5xx automáticamente
- **Credenciales:** Válidas durante todo el procesamiento
- **Progreso:** Se muestra cada 10 productos
- **Archivos grandes:** Funciona con cientos o miles de productos

## Troubleshooting

### Error: "Credenciales VTEX faltantes"

```
Error de configuración: Credenciales VTEX faltantes en .env: X-VTEX-API-AppKey
```

Solución: Completa todas las variables en `.env`:

```
X-VTEX-API-AppKey=...
X-VTEX-API-AppToken=...
VTEX_ACCOUNT_NAME=...
```

### Error: "Archivo JSON no encontrado"

```
Error: Archivo 'productos.json' no encontrado
```

Solución: Verifica ruta del archivo:

```bash
ls -la productos.json  # Verifica existencia
```

### Error: "JSON inválido"

```
Error: JSON inválido en archivo de entrada: ...
```

Solución: Valida JSON:

```bash
python3 -m json.tool productos.json
```

### Muchos productos fallidos (status 400)

Posibles causas:
1. Campos obligatorios faltantes o vacíos
2. Datos mal formateados
3. Categoría/Brand/Department no existen en VTEX

Verifica el archivo `_failed.json` para detalles.

### Rate limiting frecuente (429)

Si ves muchos 429:
1. Aumenta `--delay` a 2 o 3 segundos
2. Reduce cantidad de productos por lote
3. Ejecuta en horarios de menor carga

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** Productos formateados del paso 11
- **Salida:** Productos creados en VTEX (JSON con productIds)
- **Seguimiento:** Paso 14 (extracción) o Paso 15 (SKUs)

### Flujo Recomendado

```
Paso 11: vtex_product_format_create.py
    ↓ (productos VTEX ready)
Paso 12: vtex_product_create.py
    ↓ (productos creados con ID)
Paso 14: extract_json_response.py (extrae IDs)
    ↓
Paso 15: vtex_sku_create.py (crea SKUs)
    ↓
Paso 15.2: vtex_sku_ean_create.py (asigna EANs)
```

## Mejores Prácticas

1. **Validar datos:** Antes de crear, valida con paso 09 (report)
2. **Usar dry-run:** No es disponible, pero puedes ejecutar con pocos productos primero
3. **Monitorear tasa:** Si es < 90%, investiga errores antes de continuar
4. **Mantener backups:** Guarda archivos `_successful.json` para referencia
5. **Revisar errores:** Analiza `_failed.json` antes de reintentar
6. **Ajustar timing:** Si hay rate limits, aumenta delay
