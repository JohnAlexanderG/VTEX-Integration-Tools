# 15.2_vtex_sku_ean_create

## Descripción

Herramienta de creación masiva de códigos EAN para SKUs en VTEX. Paso final del flujo de creación de SKUs que asigna códigos de barras a variantes de productos ya creados. Procesa resultados exitosos del paso 15, valida códigos EAN, y asigna mediante la API privada de VTEX. Implementa rate limiting robusto, manejo de errores, reintentos automáticos, y genera reportes detallados con estadísticas.

## Funcionalidad

- Crea valores EAN para SKUs en VTEX usando endpoint POST `/api/catalog/pvt/stockkeepingunit/{skuId}/ean/{ean}`
- Lee credenciales VTEX desde archivo .env en la raíz del proyecto
- Procesa archivo de salida exitoso del paso 15 (SKU creation successful)
- Valida códigos EAN (longitud 8-14 dígitos)
- Implementa control de rate limiting para evitar saturar la API VTEX
- Exporta respuestas exitosas, errores y SKUs saltados en archivos JSON separados
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

### Archivo de Entrada

Requiere salida exitosa del paso 15:
- Archivo: `{timestamp}_vtex_sku_creation_successful.json`

## Uso

### Comando Básico

```bash
python3 vtex_sku_ean_create.py 20250115_002845_vtex_sku_creation_successful.json
```

### Con Configuración Personalizada de Timing

```bash
python3 vtex_sku_ean_create.py \
    successful_skus.json \
    --delay 2 \
    --timeout 45
```

### Con Archivos de Salida Personalizados

```bash
python3 vtex_sku_ean_create.py \
    datos.json \
    --output-prefix custom_batch
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input_file` | Archivo JSON con SKUs creados del paso 15 | Sí | N/A |
| `--delay` | Delay en segundos entre requests | No | 1.0 |
| `--timeout` | Timeout en segundos por request | No | 30 |
| `--output-prefix` | Prefijo para archivos de salida | No | `ean_creation` |

## Formato de Entrada

### {timestamp}_vtex_sku_creation_successful.json

Archivo JSON con respuestas exitosas del paso 15:

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
      "PackagedLength": 30.0,
      "PackagedWidth": 12.0,
      "PackagedWeightKg": 0.5
    },
    "response": {
      "Id": 2000001,
      "ProductId": 1000001,
      "Name": "Zapatos Nike Azules Talla 42",
      "RefId": "SKU001-T42",
      "Ean": "7891234567890",
      ...
    },
    "status_code": 200,
    "ref_id": "SKU001-T42",
    "name": "Zapatos Nike Azules Talla 42",
    "product_id": 1000001,
    "timestamp": "2025-01-15T00:28:45"
  },
  {
    "sku_data": {
      "ProductId": 1000002,
      "Name": "Pantalón Adidas Gris Talla M",
      "RefId": "SKU002-TM",
      "PackagedHeight": 40.0,
      "PackagedLength": 80.0,
      "PackagedWidth": 50.0,
      "PackagedWeightKg": 1.2
    },
    "response": {
      "Id": 2000002,
      "ProductId": 1000002,
      "Name": "Pantalón Adidas Gris Talla M",
      "RefId": "SKU002-TM"
    },
    ...
  }
]
```

**Estructura esperada:**
- Array de objetos con `response` y `sku_data`
- `response.Id` = skuId (obligatorio para crear EAN)
- `sku_data.Ean` = código EAN (será validado)
- Otros campos se preservan en reportes

## Formato de Salida

### {timestamp}_ean_creation_successful.json

Archivo JSON con EANs creados exitosamente:

```json
[
  {
    "sku_id": 2000001,
    "ean": "7891234567890",
    "ref_id": "SKU001-T42",
    "name": "Zapatos Nike Azules Talla 42",
    "product_id": 1000001,
    "status_code": 200,
    "timestamp": "2025-01-15T00:28:46"
  },
  {
    "sku_id": 2000003,
    "ean": "7891234567891",
    "ref_id": "SKU003-T40",
    "name": "Zapatos Nike Negros Talla 40",
    "product_id": 1000001,
    "status_code": 201,
    "timestamp": "2025-01-15T00:28:47"
  }
]
```

### {timestamp}_ean_creation_failed.json

Archivo JSON con EANs que fallaron:

```json
[
  {
    "sku_id": 2000999,
    "ean": "7891234567892",
    "ref_id": "SKU999-T99",
    "name": "SKU Defectuoso",
    "product_id": 9999999,
    "error": "API Error: 409",
    "status_code": 409,
    "response": {
      "message": "EAN already exists"
    },
    "timestamp": "2025-01-15T00:28:50"
  }
]
```

### {timestamp}_ean_creation_skipped.json

Archivo JSON con SKUs saltados (sin EAN válido):

```json
[
  {
    "sku_id": 2000002,
    "ref_id": "SKU002-TM",
    "name": "Pantalón Adidas Gris Talla M",
    "product_id": 1000002,
    "ean_value": null,
    "reason": "Invalid or missing EAN",
    "sku_data": { ... },
    "timestamp": "2025-01-15T00:28:45"
  },
  {
    "sku_id": null,
    "ref_id": "SKU004",
    "name": "Producto Sin SKU ID",
    "reason": "Missing SKU ID",
    "sku_data": { ... },
    "timestamp": "2025-01-15T00:28:46"
  }
]
```

### {timestamp}_vtex_ean_creation_report.md

Reporte Markdown con estadísticas y análisis:

```markdown
# Reporte de Creación de EANs VTEX

**Fecha:** 2025-01-15 00:28:45
**Account VTEX:** mitienda
**Environment:** vtexcommercestable
**Duración:** 0:01:30

## 📊 Resumen de Resultados

| Métrica | Valor |
|---------|-------|
| **Total Procesados** | 500 |
| **✅ EANs Creados Exitosamente** | 450 |
| **❌ EANs Fallidos** | 15 |
| **⚠️ SKUs Saltados** | 35 |
| **📈 Tasa de Éxito** | 96.8% |
| **⏱️ Delay entre requests** | 1.0s |
| **⏱️ Timeout por request** | 30s |

## ✅ EANs Creados Exitosamente (450)

| SKU ID | EAN | RefId | Nombre | Product ID | Timestamp |
|--------|-----|-------|--------|------------|-----------|
| 2000001 | 7891234567890 | SKU001-T42 | Zapatos Nike... | 1000001 | 2025-01-15 00:28:46 |
| 2000003 | 7891234567891 | SKU003-T40 | Zapatos Nike... | 1000001 | 2025-01-15 00:28:47 |
| ... | ... | ... | ... | ... | ... |

## ❌ EANs Fallidos (15)

### 📋 Resumen de Errores

- **API Error: 409**: 10 casos (EAN ya existe)
- **API Error: 404**: 5 casos (SKU no encontrado)

### 📝 Detalle de EANs Fallidos

| SKU ID | EAN | RefId | Nombre | Error | Status Code | Timestamp |
|--------|-----|-------|--------|-------|-------------|-----------|
| 2000999 | 7891234567892 | SKU999 | SKU Defectuoso | API Error: 409 | 409 | 2025-01-15 00:28:50 |
| 2001000 | 7891234567893 | SKU1000 | Otro Defectuoso | API Error: 404 | 404 | 2025-01-15 00:28:51 |
| ... | ... | ... | ... | ... | ... | ... |

## ⚠️ SKUs Saltados (35)

### 📋 Resumen de SKUs Saltados

- **Invalid or missing EAN**: 30 SKUs (sin EAN válido)
- **Missing SKU ID**: 5 SKUs (sin skuId)

### 📝 Detalle de SKUs Saltados

| SKU ID | RefId | Nombre | EAN | Razón | Timestamp |
|--------|-------|--------|-----|-------|-----------|
| 2000002 | SKU002-TM | Pantalón Adidas... | (null) | Invalid or missing EAN | 2025-01-15 00:28:45 |
| 2000004 | SKU004 | Producto Sin ID | (null) | Missing SKU ID | 2025-01-15 00:28:46 |
| ... | ... | ... | ... | ... | ... |

## 🔍 Análisis y Recomendaciones

✅ **Excelente tasa de éxito**. La integración funcionó correctamente.

### SKUs Saltados:

- **Invalid or missing EAN**: 30 casos - Agregar EANs en paso 14
- **Missing SKU ID**: 5 casos - Revisar respuestas del paso 15

### Errores más comunes:

- **API Error: 409**: 10 casos - EANs ya asignados a otros SKUs
- **API Error: 404**: 5 casos - SKUs no encontrados en VTEX
```

## Validación de EAN

El script valida códigos EAN automáticamente:

### Criterios de Validez

```
Válido si:
  - NO es null, vacío, "null", "none"
  - Longitud entre 8 y 14 dígitos
  - Es convertible a string

Ejemplo:
  "7891234567890" ✓ (13 dígitos, válido)
  "123456789" ✓ (9 dígitos, válido)
  "123" ✗ (3 dígitos, muy corto)
  "12345678901234567890" ✗ (20 dígitos, muy largo)
  "" ✗ (vacío)
  "null" ✗ (string "null")
  "0" ✗ (cero)
```

### SKUs Saltados vs Fallidos

**Saltados (⚠️):** SKU sin EAN válido, se omite sin intentar
- No genera error en API
- Se registra para revisión
- Razones: EAN vacío, inválido, muy corto/largo

**Fallidos (❌):** EAN válido pero API rechaza
- Error de VTEX (409 = ya existe, 404 = no encontrado)
- Requiere investigación
- Posible: EAN duplicado, skuId incorrecto

## Cómo Funciona

### Proceso de Creación de EANs

1. **Validación de credenciales:** Verifica que existan en .env
2. **Carga de archivo JSON:** Lee SKUs con EANs del paso 15
3. **Para cada SKU:**
   - Valida que tenga skuId (response.Id)
   - Valida que EAN sea válido (8-14 dígitos)
   - Si EAN inválido: Salta con razón registrada
   - Si EAN válido: Intenta crear
     - Pausa de `--delay` segundos
     - POST request al API VTEX
     - Maneja respuesta
     - Reintenta si rate limiting (429)
     - Registra resultado
4. **Exporta resultados:**
   - JSON exitosos
   - JSON fallidos
   - JSON saltados
   - Markdown con reporte
5. **Muestra resumen:** Estadísticas finales

### Endpoint API Utilizado

```
POST https://{VTEX_ACCOUNT}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt/stockkeepingunit/{skuId}/ean/{ean}

Headers:
  Content-Type: application/json
  Accept: application/json
  X-VTEX-API-AppKey: {app_key}
  X-VTEX-API-AppToken: {app_token}

Body: (vacío según documentación VTEX)
```

### Respuesta Exitosa

Status 200 o 201, sin body específico.

## Control de Rate Limiting

El script implementa control automático:

### Configuración

```
DEFAULT_DELAY = 1.0        # Segundos entre requests
DEFAULT_TIMEOUT = 30       # Timeout por request
MAX_RETRIES = 3            # Intentos máximos
BACKOFF_FACTOR = 2         # Multiplicador de espera
```

### Estrategia de Reintento

1. **Request exitoso (200/201):** Continúa
2. **Rate limit (429):** Espera y reintenta
3. **Timeout/Error:** Registra y continúa

## Ejemplos de Ejecución

### Ejemplo 1: Creación Básica

```bash
python3 15.2_vtex_sku_ean_create/vtex_sku_ean_create.py \
    20250115_002845_vtex_sku_creation_successful.json
```

**Salida:**
```
✅ Credenciales VTEX configuradas para cuenta: mitienda
✅ Base URL: https://mitienda.vtexcommercestable.com.br

📂 Cargando datos de SKUs desde: 20250115_002845_vtex_sku_creation_successful.json
✅ Cargados 500 registros de SKU para procesar

🚀 Iniciando creación de EANs para 500 SKUs en VTEX...
⏱️ Delay entre requests: 1.0s
⏱️ Timeout por request: 30s

[1/500] Procesando SKU 2000001 - RefId: SKU001-T42
✅ EAN creado: SKU 2000001 - EAN 7891234567890 - RefId SKU001-T42

[2/500] Procesando SKU 2000002 - RefId: SKU002-TM
⚠️ Saltado: EAN inválido o faltante - SKU 2000002 - EAN: 'None'

[3/500] Procesando SKU 2000003 - RefId: SKU003-T40
✅ EAN creado: SKU 2000003 - EAN 7891234567891 - RefId SKU003-T40

📊 Progreso: 10/500 (2.0%) - Éxito: 80.0%

✅ Procesamiento completado en 0:08:30
✅ EANs creados exitosamente: 450
❌ EANs fallidos: 15
⚠️ SKUs saltados: 35
📊 Tasa de éxito: 96.8%

✅ EANs exitosos exportados a: 20250115_002846_ean_creation_successful.json
❌ EANs fallidos exportados a: 20250115_002846_ean_creation_failed.json
⚠️ SKUs saltados exportados a: 20250115_002846_ean_creation_skipped.json
📋 Reporte generado: 20250115_002846_vtex_ean_creation_report.md

🎉 Proceso completado exitosamente!
```

### Ejemplo 2: Con Delay Mayor

```bash
python3 15.2_vtex_sku_ean_create/vtex_sku_ean_create.py \
    successful_skus.json \
    --delay 2 \
    --timeout 45
```

### Ejemplo 3: Con Prefijo Personalizado

```bash
python3 15.2_vtex_sku_ean_create/vtex_sku_ean_create.py \
    datos.json \
    --output-prefix batch_enero
```

## Archivos Generados

El script genera hasta 4 archivos (con timestamp):

1. **{timestamp}_ean_creation_successful.json** - EANs creados exitosamente
2. **{timestamp}_ean_creation_failed.json** - EANs que fallaron (si hay)
3. **{timestamp}_ean_creation_skipped.json** - SKUs saltados (sin EAN válido)
4. **{timestamp}_vtex_ean_creation_report.md** - Reporte detallado

## Notas Importantes

- **SkuId requerido:** Debe venir del paso 15 (response.Id)
- **EAN validado:** Se valida longitud 8-14 dígitos
- **Rate limiting:** Maneja automáticamente 429 (rate limit)
- **Reintentos:** Máximo 3 intentos con backoff exponencial
- **Timeout:** 30 segundos por request (configurable)
- **SKUs saltados:** No se consideran errores, solo omisiones
- **Progreso:** Se muestra cada 10 registros

## Troubleshooting

### Error: "Credenciales VTEX faltantes"

Completa todas las variables en `.env`.

### Error: "El archivo debe contener un array"

El archivo debe ser un array de SKUs (salida directa del paso 15).

### Error: "No se encontraron registros de SKU"

El archivo está vacío o es un array vacío.

### Muchos SKUs saltados (sin EAN)

Si > 50% sin EAN:
1. Verifica que paso 14 generó EANs correctamente
2. Verifica que `ean.json` tenía datos
3. Revisa archivo `_skipped.json` para detalles

### Muchos EANs fallidos con 409 (conflict)

Causas:
1. EAN ya asignado a otro SKU
2. EAN duplicado en archivo entrada
3. SKU generado dos veces

Verifica en `_failed.json` los EANs duplicados.

### Muchos EANs fallidos con 404 (not found)

Causas:
1. SkuId del paso 15 es incorrecto
2. SKU no fue creado exitosamente en VTEX
3. SKU fue eliminado entre pasos

Verifica que `_successful.json` del paso 15 tiene skuIds válidos.

## Integración en Pipeline

Este paso se ubica al final:
- **Entrada:** SKUs creados exitosos del paso 15
- **Entrada auxiliar:** EANs asignados en paso 14
- **Salida:** SKUs con EANs asignados

### Flujo Completo

```
Paso 11: vtex_product_format_create.py
    ↓ (formatea productos)
Paso 12: vtex_product_create.py
    ↓ (crea productos)
Paso 13: extract_json_response.py
    ↓ (extrae respuestas)
Paso 14: to_vtex_skus.py
    ↓ (transforma a SKUs)
Paso 15: vtex_sku_create.py
    ↓ (crea SKUs)
Paso 15.2: vtex_sku_ean_create.py ← FINAL
    ↓ (asigna EANs)
✅ Catálogo completamente creado
```

## Mejores Prácticas

1. **Validar EANs antes:** Asegura que paso 14 generó datos válidos
2. **Revisar saltados:** Antes de terminar, completa EANs faltantes
3. **Revisar fallidos:** Investiga 409 y 404 antes de reintentar
4. **Mantener orden:** Procesa siempre en orden: 12 → 13 → 14 → 15 → 15.2
5. **Documentar:** Nota de dónde vinieron EANs
6. **Backups:** Guarda archivos `_successful.json` como respaldo
7. **Procesamiento en lotes:** Para miles de SKUs, divide en lotes
