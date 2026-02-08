# 14_to_vtex_skus

## Descripción

Herramienta de transformación que convierte productos con estructura de entrada a SKUs en formato requerido por VTEX. Realiza matching de tres fuentes (productos base, dimensiones, códigos EAN) para crear objetos SKU completos con información física y códigos de barras. Genera archivos CSV de reportes para productos con valores por defecto o sin códigos EAN.

## Funcionalidad

- Transforma lista de productos a SKUs formato VTEX
- Realiza matching de productos con datos de dimensiones por campo 'sku'
- Realiza matching de EAN codes por field 'RefId'
- Asigna valores por defecto (0) si dimensiones no encontradas
- Filtra y valida códigos EAN (longitud 8-14 dígitos)
- Genera SKU con estructura requerida por VTEX
- Exporta reportes CSV de productos sin dimensiones
- Exporta reportes CSV de productos sin EAN codes
- Logging detallado de advertencias y transformaciones

## Requisitos Previos

No requiere variables de entorno ni credenciales VTEX.

### Dependencias Python

```
(dependencias estándar de Python)
```

## Uso

### Comando Básico

```bash
python3 to_vtex_skus.py input.json dimensions.json ean.json output.json
```

### Con Reportes CSV

```bash
python3 to_vtex_skus.py \
    input.json \
    dimensions.json \
    ean.json \
    output.json \
    --defaults-csv sin_dimensiones.csv \
    --no-ean-csv sin_ean.csv
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input` | Archivo JSON con productos (array) | Sí | N/A |
| `dimensions` | Archivo JSON con datos de dimensiones | Sí | N/A |
| `ean` | Archivo JSON con códigos EAN | Sí | N/A |
| `output` | Archivo JSON de salida con SKUs | Sí | N/A |
| `--defaults-csv` | CSV de SKUs con dimensiones por defecto | No | Auto-generado |
| `--no-ean-csv` | CSV de SKUs sin EAN codes | No | Auto-generado |

## Formato de Entrada

### input.json

Archivo JSON con lista de productos base:

```json
[
  {
    "Id": 1000001,
    "Name": "Zapatos Nike Azules",
    "RefId": "SKU001"
  },
  {
    "Id": 1000002,
    "Name": "Pantalón Adidas",
    "RefId": "SKU002"
  }
]
```

**Campos requeridos:**
- `Id`: Identificador único del producto (productId de VTEX)
- `Name`: Nombre del producto
- `RefId`: ID de referencia/SKU del producto

### dimensions.json

Archivo JSON con datos de dimensiones (array o dict):

```json
[
  {
    "sku": "SKU001",
    "alto": "15",
    "largo": "30",
    "ancho": "12",
    "peso": "0.5"
  },
  {
    "sku": "SKU002",
    "alto": "40",
    "largo": "80",
    "ancho": "50",
    "peso": "1.2"
  }
]
```

**Campos esperados:**
- `sku`: Identificador para matching con product RefId (obligatorio)
- `alto`: Altura en cm (PackagedHeight) - convertido a float
- `largo`: Largo en cm (PackagedLength) - convertido a float
- `ancho`: Ancho en cm (PackagedWidth) - convertido a float
- `peso`: Peso en kg (PackagedWeightKg) - convertido a float

**Notas:**
- Los nombres de campos son exactos (minúsculas en español)
- Se aceptan valores como strings o números
- Si faltan, se usan por defecto 0
- Si conversion a float falla, se usa 0

### ean.json

Archivo JSON con códigos EAN (array o dict):

```json
[
  {
    "RefId": "SKU001",
    "EAN": "7891234567890"
  },
  {
    "RefId": "SKU002",
    "EAN": "7891234567891"
  }
]
```

**Campos esperados:**
- `RefId`: Identificador para matching con producto RefId (obligatorio)
- `EAN`: Código de barras (obligatorio)

**Formato EAN válido:**
- Longitud: 8 a 14 dígitos
- Si es "0" o está vacío, se omite
- Valores inválidos (< 8 o > 14 dígitos) se omiten con advertencia

## Formato de Salida

### output.json

Archivo JSON con SKUs transformados para VTEX:

```json
[
  {
    "ProductId": 1000001,
    "IsActive": false,
    "ActivateIfPossible": true,
    "Name": "Zapatos Nike Azules",
    "RefId": "SKU001",
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
    "Name": "Pantalón Adidas",
    "RefId": "SKU002",
    "PackagedHeight": 40.0,
    "PackagedLength": 80.0,
    "PackagedWidth": 50.0,
    "PackagedWeightKg": 1.2
  }
]
```

**Estructura SKU para VTEX:**
- `ProductId`: ID del producto (del campo 'Id' input)
- `IsActive`: Siempre false (para activar después)
- `ActivateIfPossible`: Siempre true
- `Name`: Nombre del producto
- `RefId`: ID de referencia
- `Ean`: Código de barras (SOLO si existe y válido)
- `PackagedHeight`: Altura en cm (float)
- `PackagedLength`: Largo en cm (float)
- `PackagedWidth`: Ancho en cm (float)
- `PackagedWeightKg`: Peso en kg (float)

### {output}_sin_dimensiones.csv

Reporte CSV de SKUs que usaron valores por defecto (0):

```csv
ProductId,IsActive,ActivateIfPossible,Name,RefId,PackagedHeight,PackagedLength,PackagedWidth,PackagedWeightKg
1000003,False,True,Producto Sin Dims,SKU003,0,0,0,0
1000004,False,True,Otro Sin Dims,SKU004,0,0,0,0
```

**Cuándo se incluye:**
- Cuando todas las dimensiones son 0
- Indica que no se encontró entrada en `dimensions.json`
- Requiere revisión y adición manual de datos

### {output}_sin_ean.csv

Reporte CSV de SKUs sin código EAN:

```csv
ProductId,IsActive,ActivateIfPossible,Name,RefId,PackagedHeight,PackagedLength,PackagedWidth,PackagedWeightKg
1000001,False,True,Zapatos Nike,SKU001,15.0,30.0,12.0,0.5
1000005,False,True,Producto Sin EAN,SKU005,20.0,50.0,15.0,0.8
```

**Cuándo se incluye:**
- Cuando EAN es None, vacío, "0", "null" o "none"
- Indica que no se encontró entrada en `ean.json`
- Requiere revisión y adición manual de EANs

## Cómo Funciona

### Proceso de Transformación

1. **Carga archivos:**
   - Input: Lista de productos base
   - Dimensions: Crea lookup dict por 'sku'
   - EAN: Crea lookup dict por 'RefId'

2. **Para cada producto:**
   - Valida campos requeridos (Id, Name, RefId)
   - Busca dimensiones por matching RefId == sku en dimensions
   - Busca EAN por matching RefId en ean data
   - Valida longitud EAN (8-14 dígitos)
   - Crea objeto SKU con estructura VTEX
   - Registra en listas de tracking (defaults, sin-ean)

3. **Exporta resultados:**
   - JSON principal con todos los SKUs
   - CSV de SKUs con dimensiones por defecto
   - CSV de SKUs sin EAN codes

### Matching de Dimensiones

```
product.RefId = "SKU001"
    ↓
Busca en dimensions donde sku == "SKU001"
    ↓
Si encuentra:
  - altura = dimensions.alto
  - largo = dimensions.largo
  - ancho = dimensions.ancho
  - peso = dimensions.peso
Si NO encuentra:
  - altura = 0
  - largo = 0
  - ancho = 0
  - peso = 0
  - Se agrega a lista sin_dimensiones para CSV
```

### Matching de EAN

```
product.RefId = "SKU001"
    ↓
Busca en ean data donde RefId == "SKU001"
    ↓
Si encuentra y longitud válida (8-14):
  - EAN = valor encontrado
Si NO encuentra O inválido:
  - Se omite campo EAN
  - Se agrega a lista sin_ean para CSV
```

## Ejemplos de Ejecución

### Ejemplo 1: Transformación Básica

```bash
python3 14_to_vtex_skus/to_vtex_skus.py \
    productos.json \
    dimensiones.json \
    ean.json \
    output.json
```

**Genera:**
- `output.json` - SKUs principales
- `output_sin_dimensiones.csv` - Si hay sin dimensiones
- `output_sin_ean.csv` - Si hay sin EAN

### Ejemplo 2: Con Reportes CSV Específicos

```bash
python3 14_to_vtex_skus/to_vtex_skus.py \
    productos.json \
    dimensiones.json \
    ean.json \
    productos_skus.json \
    --defaults-csv productos_revisar_dims.csv \
    --no-ean-csv productos_revisar_ean.csv
```

### Ejemplo 3: Desde Paso Anterior

```bash
python3 14_to_vtex_skus/to_vtex_skus.py \
    20260114_142531_vtex_creation_successful-responsed.json \
    dimensiones.json \
    ean.json \
    skus_transformados.json
```

## Validaciones

### Campos Requeridos

Se valida que cada producto tenga:
- `Id` (obligatorio)
- `Name` (obligatorio)
- `RefId` (obligatorio)

Si falta alguno, se omite con advertencia.

### Validación de EAN

```
Válido si:
  - No es vacío, None, "null", "none"
  - Longitud entre 8 y 14 dígitos

Ejemplo:
  "7891234567890" ✓ (13 dígitos, válido)
  "123" ✗ (3 dígitos, muy corto)
  "" ✗ (vacío)
  "null" ✗(string "null")
  "0" ✗ (cero)
```

### Conversión de Dimensiones

```
Alto, Largo, Ancho, Peso se convierten a float
Si conversión falla → se usa 0
Si valor es vacío → se usa 0

Ejemplo:
  "15.5" → 15.5 ✓
  "20" → 20.0 ✓
  "abc" → 0 (falla conversión)
  "" → 0
```

## Archivos Generados

El script genera hasta 3 archivos:

1. **output.json** - SKUs transformados (siempre)
2. **output_sin_dimensiones.csv** - Solo si hay SKUs con defaults
3. **output_sin_ean.csv** - Solo si hay SKUs sin EAN

## Logging y Advertencias

El script genera advertencias para:

```
INFO: Loaded X products, Y dimension entries, Z EAN entries
WARNING: No dimensions found for product SKU001, using defaults
WARNING: Error converting dimensions for product SKU002: invalid value, using defaults
WARNING: Skipping product because missing required fields ['Name']: SKU003
INFO: Converted X SKUs and wrote to 'output.json'
INFO: Wrote Y SKUs with default dimensions to 'output_sin_dimensiones.csv'
INFO: Wrote Z SKUs without EAN codes to 'output_sin_ean.csv'
```

## Casos de Uso

### Caso 1: Transformación Completa

```
Productos creados (paso 12)
    ↓
Extraer respuestas (paso 13)
    ↓
Transformar a SKUs (paso 14) ← AQUÍ
    ↓
Crear SKUs en VTEX (paso 15)
```

### Caso 2: Reparar Datos Faltantes

1. Ejecutar transformación
2. Revisar CSV con faltantes
3. Completar datos en archivos origen
4. Re-ejecutar transformación

### Caso 3: Múltiples Lotes

```bash
# Lote 1
python3 to_vtex_skus.py lote1_productos.json dims.json eans.json lote1_skus.json

# Lote 2
python3 to_vtex_skus.py lote2_productos.json dims.json eans.json lote2_skus.json

# Combinar
python3 -c "
import json
lote1 = json.load(open('lote1_skus.json'))
lote2 = json.load(open('lote2_skus.json'))
combined = lote1 + lote2
json.dump(combined, open('todos_skus.json', 'w'), indent=2)"
```

## Notas Importantes

- **Campos de dimensiones:** Nombres exactos (alto, largo, ancho, peso en minúsculas)
- **Matching por RefId:** Tanto productos como EAN/dims usan RefId para búsqueda
- **Valores por defecto:** Si falta dimension, se usa 0 (requiere revisión)
- **EAN opcional:** Si falta, se omite el campo en output (VTEX permite)
- **IsActive siempre false:** SKUs se crean desactivados
- **Orden preservado:** Se mantiene orden de entrada en output
- **Sin deduplicación:** Si hay RefIds duplicados, se procesan ambos

## Troubleshooting

### Error: "Input JSON must be a list"

El archivo input.json debe ser un array:

```json
[
  { "Id": 1, ... },
  { "Id": 2, ... }
]
```

No un objeto individual:

```json
{
  "Id": 1,
  ...
}
```

### Error: "Dimensions JSON must be a list or dictionary"

El archivo dimensions.json debe ser array o dict, no otra estructura.

Válido:
```json
[
  { "sku": "SKU001", ... }
]
```

O:
```json
{
  "SKU001": { "alto": "15", ... }
}
```

### Productos sin dimensiones

Si ves muchos en CSV sin_dimensiones:
1. Verifica que 'sku' en dimensions.json coincida exactamente con RefId
2. Agrega faltantes al archivo dimensions
3. Re-ejecuta transformación

### Productos sin EAN

Si ves muchos en CSV sin_ean:
1. Verifica que 'RefId' en ean.json coincida exactamente
2. Agrega EANs faltantes al archivo ean
3. Re-ejecuta transformación

### Valores de dimensiones incorrectos

Si se usan por defecto (0) cuando no deberían:
1. Verifica typos en 'sku' field
2. Verifica que nombres de campos sean exactos: alto, largo, ancho, peso
3. Verifica que valores sean convertibles a float

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** Productos creados + respuestas extraídas (pasos 12-13)
- **Entrada auxiliar:** Dimensiones + EAN (archivos de datos)
- **Salida:** SKUs transformados para paso 15

### Flujo Recomendado

```
Paso 12: vtex_product_create.py
    ↓ (crea productos)
Paso 13: extract_json_response.py
    ↓ (extrae respuestas)
Paso 14: to_vtex_skus.py ← AQUÍ
    ↓ (transforma a SKUs)
Paso 15: vtex_sku_create.py
    ↓ (crea SKUs en VTEX)
Paso 15.2: vtex_sku_ean_create.py
    ↓ (asigna EANs)
```

## Mejores Prácticas

1. **Validar datos antes:** Verifica dimensiones y EANs completos
2. **Revisar CSV de faltantes:** Antes de paso 15, completa datos
3. **Mantener archivos auxiliares:** Guarda dims.json y ean.json actualizados
4. **Nombres descriptivos:** Usa nombres que indiquen contenido
5. **Documentar fuentes:** Nota de dónde vienen dimensiones y EANs
