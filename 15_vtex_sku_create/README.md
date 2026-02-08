# 15_vtex_sku_create

## Descripción

Herramienta de creación masiva de SKUs en VTEX usando la API privada del catálogo. Paso fundamental del flujo que crea variantes de productos (SKUs) en el catálogo VTEX. Implementa rate limiting robusto, manejo de errores, reintentos automáticos con backoff exponencial, y genera reportes detallados con estadísticas de éxito y fallos.

Un SKU representa una variante específica de un producto (ej: Zapatos Nike en talla 42, color azul).

## Funcionalidad

- Crea SKUs en VTEX usando endpoint POST `/api/catalog/pvt/stockkeepingunit`
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Implementa control de rate limiting para evitar saturar la API VTEX
- Procesa lista de SKUs desde archivo JSON formateado
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
python3 vtex_sku_create.py skus_vtex.json
```

### Con Configuración Personalizada de Timing

```bash
python3 vtex_sku_create.py skus.json --delay 2 --timeout 45
```

### Con Archivos de Salida Personalizados

```bash
python3 vtex_sku_create.py datos.json --output-prefix custom_batch
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input_file` | Archivo JSON con lista de SKUs para crear | Sí | N/A |
| `--delay` | Delay en segundos entre requests | No | 1.0 |
| `--timeout` | Timeout en segundos por request | No | 30 |
| `--output-prefix` | Prefijo para archivos de salida | No | `vtex_sku_creation` |

## Formato de Entrada

### skus_vtex.json

Archivo JSON con lista de SKUs transformados (salida paso 14):

```json
[
  {
    "ProductId": 1000001,
    "IsActive": false,
    "ActivateIfPossible": true,
    "Name": "Zapatos Nike Azules Talla 42",
    "RefId": "SKU001-T42",
    "Ean": "7891234567890",
    "PackagedHeight": 15.0,
    "PackagedLength": 30.0,
    "PackagedWidth": 12.0,
    "PackagedWeightKg": 0.5
  },
  {
    "ProductId": 1000002,
    "IsActive": false,
    "ActivateIfPossible": true,
    "Name": "Pantalón Adidas Gris Talla M",
    "RefId": "SKU002-TM",
    "PackagedHeight": 40.0,
    "PackagedLength": 80.0,
    "PackagedWidth": 50.0,
    "PackagedWeightKg": 1.2
  }
]
```

**Campos esperados:**
- `ProductId`: ID del producto (obligatorio, del paso 12)
- `IsActive`: Estado (default: false)
- `ActivateIfPossible`: Activar si es posible (default: true)
- `Name`: Nombre del SKU (obligatorio)
- `RefId`: ID de referencia único (obligatorio)
- `Ean`: Código de barras (opcional)
- `PackagedHeight`: Altura en cm (obligatorio)
- `PackagedLength`: Largo en cm (obligatorio)
- `PackagedWidth`: Ancho en cm (obligatorio)
- `PackagedWeightKg`: Peso en kg (obligatorio)

## Formato de Salida

### {timestamp}_vtex_sku_creation_successful.json

Archivo JSON con SKUs creados exitosamente:

```json
[
  {
    "sku_data": {
      "ProductId": 1000001,
      "IsActive": false,
      "ActivateIfPossible": true,
      "Name": "Zapatos Nike Azules Talla 42",
      "RefId": "SKU001-T42",
      "Ean": "7891234567890",
      "PackagedHeight": 15.0,
      ...
    },
    "response": {
      "Id": 2000001,
      "ProductId": 1000001,
      "IsActive": false,
      "ActivateIfPossible": true,
      "Name": "Zapatos Nike Azules Talla 42",
      "RefId": "SKU001-T42",
      "Ean": "7891234567890",
      ...
    },
    "status_code": 200,
    "ref_id": "SKU001-T42",
    "name": "Zapatos Nike Azules Talla 42",
    "product_id": 1000001,
    "timestamp": "2025-01-15T00:28:45.123456"
  }
]
```

**Contenido:**
- `sku_data`: Datos enviados al API
- `response`: Respuesta de VTEX con skuId asignado (en `response.Id`)
- `status_code`: 200 o 201
- `ref_id`, `name`, `product_id`: Metadatos para referencia
- `timestamp`: Cuándo se creó

### {timestamp}_vtex_sku_creation_failed.json

Archivo JSON con SKUs que fallaron:

```json
[
  {
    "sku_data": { ... },
    "error": "API Error: 400",
    "status_code": 400,
    "response": {
      "message": "Invalid ProductId"
    },
    "ref_id": "SKU999",
    "name": "SKU Defectuoso",
    "product_id": 9999999,
    "timestamp": "2025-01-15T00:28:50.123456",
    "retry_count": 0
  }
]
```

### {timestamp}_vtex_sku_creation_report.md

Reporte Markdown con estadísticas y análisis:

```markdown
# Reporte de Creación de SKUs VTEX

**Fecha:** 2025-01-15 00:28:45
**Account VTEX:** mitienda
**Environment:** vtexcommercestable
**Duración:** 0:02:15

## 📊 Resumen de Resultados

| Métrica | Valor |
|---------|-------|
| **Total Procesados** | 500 |
| **✅ Exitosos** | 480 |
| **❌ Fallidos** | 20 |
| **📈 Tasa de Éxito** | 96.0% |
| **⏱️ Delay entre requests** | 1.0s |
| **⏱️ Timeout por request** | 30s |

## ✅ SKUs Creados Exitosamente (480)

| RefId | Nombre | Product ID | SKU ID | Timestamp |
|-------|--------|------------|--------|-----------|
| SKU001-T42 | Zapatos Nike... | 1000001 | 2000001 | 2025-01-15 00:28:46 |
| SKU002-TM | Pantalón Adidas... | 1000002 | 2000002 | 2025-01-15 00:28:47 |
| ... | ... | ... | ... | ... |

## ❌ SKUs Fallidos (20)

### 📋 Resumen de Errores

- **API Error: 400**: 15 SKUs
- **Request timeout**: 5 SKUs

### 📝 Detalle de SKUs Fallidos

| RefId | Nombre | Product ID | Error | Status Code | Timestamp |
|-------|--------|------------|-------|-------------|-----------|
| SKU999-T99 | SKU Defectuoso | 9999999 | API Error: 400 | 400 | 2025-01-15 00:28:50 |
| ... | ... | ... | ... | ... | ... |

## 🔍 Análisis y Recomendaciones

✅ **Excelente tasa de éxito**. La integración funcionó correctamente.

### Errores más comunes:

- **API Error: 400**: 15 casos - Revisar ProductIds válidos
- **Request timeout**: 5 casos - Aumentar timeout
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
3. **Timeout/Error:** Registra y continúa

## Cómo Funciona

### Proceso de Creación de SKUs

1. **Validación de credenciales:** Verifica que existan en .env
2. **Carga de archivo JSON:** Lee SKUs desde archivo
3. **Para cada SKU:**
   - Pausa de `--delay` segundos
   - POST request al API VTEX
   - Maneja respuesta (exitosa o error)
   - Reintentar si es rate limiting (429)
   - Registra resultado
4. **Exporta resultados:**
   - JSON con SKUs exitosos
   - JSON con SKUs fallidos
   - Markdown con reporte
5. **Muestra resumen:** Estadísticas finales

### Endpoint API Utilizado

```
POST https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit

Headers:
  Content-Type: application/json
  Accept: application/json
  X-VTEX-API-AppKey: {app_key}
  X-VTEX-API-AppToken: {app_token}

Body: JSON del SKU
```

### Respuesta Exitosa

```json
{
  "Id": 2000001,
  "ProductId": 1000001,
  "IsActive": false,
  "ActivateIfPossible": true,
  "Name": "Zapatos Nike Azules Talla 42",
  "RefId": "SKU001-T42",
  ...
}
```

La respuesta incluye el `Id` asignado por VTEX (skuId).

## Ejemplos de Ejecución

### Ejemplo 1: Creación Básica

```bash
python3 15_vtex_sku_create/vtex_sku_create.py input.json
```

**Salida:**
```
✅ Credenciales VTEX configuradas para cuenta: mitienda
✅ Endpoint: https://mitienda.vtexcommercestable.com.br/api/catalog/pvt/stockkeepingunit

📂 Cargando SKUs desde: input.json
✅ Cargados 500 SKUs para procesar

🚀 Iniciando creación de 500 SKUs en VTEX...
⏱️ Delay entre requests: 1.0s
⏱️ Timeout por request: 30s

[1/500] Procesando SKU...
✅ SKU creado: SKU001-T42 - Zapatos Nike...
[2/500] Procesando SKU...
✅ SKU creado: SKU002-TM - Pantalón Adidas...
...
📊 Progreso: 10/500 (2.0%) - Éxito: 100.0%

✅ Procesamiento completado en 0:08:45
✅ SKUs exitosos: 500
❌ SKUs fallidos: 0
📊 Tasa de éxito: 100.0%

✅ SKUs exitosos exportados a: 20250115_002845_vtex_sku_creation_successful.json
📋 Reporte generado: 20250115_002845_vtex_sku_creation_report.md

🎉 Proceso completado exitosamente!
```

### Ejemplo 2: Con Delay Mayor

```bash
python3 15_vtex_sku_create/vtex_sku_create.py \
    skus.json \
    --delay 2 \
    --timeout 45
```

### Ejemplo 3: Con Prefijo Personalizado

```bash
python3 15_vtex_sku_create/vtex_sku_create.py \
    datos.json \
    --output-prefix batch_enero
```

## Archivos Generados

El script genera hasta 3 archivos (con timestamp):

1. **{timestamp}_vtex_sku_creation_successful.json** - SKUs creados exitosamente
2. **{timestamp}_vtex_sku_creation_failed.json** - SKUs que fallaron (si hay)
3. **{timestamp}_vtex_sku_creation_report.md** - Reporte detallado

## Notas Importantes

- **ProductId requerido:** Debe existir en VTEX (creado en paso 12)
- **RefId único:** Cada SKU debe tener RefId único
- **Dimensiones obligatorias:** Height, Length, Width, Weight deben ser números válidos
- **EAN opcional:** Si no existe, se omite (VTEX permite)
- **IsActive = false:** SKUs se crean desactivados inicialmente
- **Reintento automático:** Maneja 429 (rate limit) automáticamente
- **Progreso:** Se muestra cada 10 SKUs

## Troubleshooting

### Error: "Credenciales VTEX faltantes"

Completa todas las variables en `.env`:

```
X-VTEX-API-AppKey=...
X-VTEX-API-AppToken=...
VTEX_ACCOUNT_NAME=...
VTEX_ENVIRONMENT=vtexcommercestable
```

### Error: "Archivo JSON no encontrado"

Verifica ruta del archivo:

```bash
ls -la input.json
```

### Error: "JSON inválido"

Valida JSON:

```bash
python3 -m json.tool input.json | head -20
```

### Muchos SKUs fallidos con status 400

Causas posibles:
1. ProductId no existe en VTEX
2. Dimensiones inválidas
3. RefId duplicado o inválido

Verifica en archivo `_failed.json`.

### Rate limiting frecuente (429)

Si ves muchos 429:
1. Aumenta `--delay` a 2 o 3 segundos
2. Reduce cantidad de SKUs por lote
3. Ejecuta en horarios de menor carga

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** SKUs transformados del paso 14
- **Salida:** SKUs creados en VTEX
- **Seguimiento:** Paso 15.2 (asignar EANs)

### Flujo Recomendado

```
Paso 14: to_vtex_skus.py
    ↓ (transforma a SKUs)
Paso 15: vtex_sku_create.py ← AQUÍ
    ↓ (crea SKUs en VTEX)
Paso 15.2: vtex_sku_ean_create.py
    ↓ (asigna EANs)
```

## Diferencia Entre Productos y SKUs

- **Producto:** Artículo general (ej: "Zapatos Nike")
- **SKU:** Variante específica (ej: "Zapatos Nike Talla 42 Azules")

Ejemplo:
```
Producto: "Zapatos Nike" (Id=1000001)
  ├─ SKU: "SKU001-T40" (Id=2000001, Talla 40)
  ├─ SKU: "SKU001-T42" (Id=2000002, Talla 42)
  └─ SKU: "SKU001-T44" (Id=2000003, Talla 44)
```

## Mejores Prácticas

1. **Validar antes:** Asegura que ProductIds existan
2. **Revisar errores:** Analiza `_failed.json` antes de continuar
3. **Mantener backups:** Guarda archivos `_successful.json`
4. **Nombres descriptivos:** Usa prefijos que indiquen contenido
5. **Ajustar timing:** Aumenta delay si hay rate limits frecuentes
6. **Procesar por lotes:** Para miles de SKUs, divide en lotes más pequeños
