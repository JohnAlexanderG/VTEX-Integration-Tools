# 28_filter_price_list

Filtra una lista de precios comparándola con los productos existentes en VTEX y genera reportes completos de coincidencias y discrepancias.

## Propósito

Este script realiza un análisis bidireccional entre dos conjuntos de datos:
1. **Productos VTEX** (archivo 1): SKUs creados y existentes en VTEX
2. **Lista de Precios** (archivo 2): Precios a aplicar

Genera 4 archivos de salida que permiten identificar:
- Precios listos para aplicar (tienen SKU en VTEX)
- SKUs en VTEX sin precio asignado
- Precios de productos que aún no existen en VTEX
- Reporte general con estadísticas completas

## Uso

```bash
python3 filter_price_list.py <vtex_products> <price_list> <output_prefix>
```

### Parámetros

- `vtex_products`: Archivo CSV o JSON con productos de VTEX (campo requerido: `_SkuId (Not changeable)`)
- `price_list`: Archivo CSV con lista de precios (campo requerido: `código producto`)
- `output_prefix`: Prefijo para los archivos de salida

### Ejemplos

```bash
# Generar reportes con prefijo "results"
python3 filter_price_list.py vtex_products.csv prices.csv results

# Usando archivo JSON de VTEX
python3 filter_price_list.py vtex_products.json prices.csv output

# Procesar datos en subdirectorio
python3 filter_price_list.py data/vtex_skus.csv data/precios.csv data/filtered
```

## Formato de Entrada

### Archivo 1: Productos VTEX

**CSV:**
```csv
_SkuId (Not changeable),Product Name,Brand,Category
12345,Product A,Brand X,Electronics
67890,Product B,Brand Y,Home
```

**JSON (lista):**
```json
[
  {
    "_SkuId (Not changeable)": "12345",
    "Product Name": "Product A"
  }
]
```

**JSON (diccionario):**
```json
{
  "sku1": {
    "_SkuId (Not changeable)": "12345",
    "Product Name": "Product A"
  }
}
```

### Archivo 2: Lista de Precios

```csv
código producto,precio,moneda,vigencia
12345,99.99,USD,2025-01-01
67890,49.99,USD,2025-01-01
99999,29.99,USD,2025-01-01
```

## Archivos de Salida

Usando `output` como prefijo, el script genera:

### 1. `output_matched.csv`
**Descripción:** Precios con SKU existente en VTEX
**Contenido:** Entradas de la lista de precios donde `código producto` coincide con un SKU de VTEX
**Uso:** Estos precios pueden aplicarse directamente a VTEX

**Ejemplo:**
```csv
código producto,precio,moneda,vigencia
12345,99.99,USD,2025-01-01
67890,49.99,USD,2025-01-01
```

### 2. `output_vtex_without_price.csv`
**Descripción:** SKUs en VTEX sin precio en la lista
**Contenido:** Productos de VTEX que NO aparecen en la lista de precios
**Uso:** Identificar productos que necesitan precio

**Ejemplo:**
```csv
_SkuId (Not changeable),Product Name,Brand,Category
54321,Product C,Brand Z,Kitchen
```

**Acción Requerida:** Agregar precios para estos SKUs

### 3. `output_prices_without_sku.csv`
**Descripción:** Precios sin SKU en VTEX
**Contenido:** Entradas de precios cuyos productos NO existen en VTEX
**Uso:** Identificar productos que deben crearse primero en VTEX

**Ejemplo:**
```csv
código producto,precio,moneda,vigencia
99999,29.99,USD,2025-01-01
```

**Acción Requerida:** Crear estos productos en VTEX antes de aplicar precios

### 4. `output_REPORT.md`
**Descripción:** Reporte general en formato Markdown
**Contenido:** Estadísticas completas, análisis y recomendaciones

**Estructura del Reporte:**
- Timestamp de generación
- Archivos de entrada utilizados
- Tablas con estadísticas de VTEX SKUs
- Tablas con estadísticas de lista de precios
- Descripción de cada archivo generado
- Recomendaciones basadas en los resultados
- Lógica de matching utilizada

## Ejemplo de Salida en Consola

```
Loading VTEX SKU data from: vtex_products.csv
Loaded 1250 unique SKU IDs from VTEX

Processing price list: prices.csv

Writing matched prices to: output_matched.csv
Writing VTEX SKUs without prices to: output_vtex_without_price.csv
Writing prices without VTEX SKUs to: output_prices_without_sku.csv
Generating report: output_REPORT.md

======================================================================
FILTERING RESULTS
======================================================================
VTEX SKUs:
  Total in VTEX:               1250
  With prices (matched):       980 (78.4%)
  Without prices:              270 (21.6%)

Price List:
  Total prices:                1100
  With VTEX SKU (matched):     980 (89.1%)
  Without VTEX SKU:            120 (10.9%)
======================================================================

Output Files Generated:
  1. output_matched.csv
  2. output_vtex_without_price.csv
  3. output_prices_without_sku.csv
  4. output_REPORT.md
======================================================================
```

## Características

### Análisis Bidireccional
- Identifica SKUs en VTEX sin precios (gap en lista de precios)
- Identifica precios sin SKUs (gap en catálogo VTEX)
- Genera vista completa de coincidencias y discrepancias

### Formatos Flexibles
- Soporta VTEX en CSV o JSON
- Maneja estructuras JSON como lista o diccionario
- Lista de precios siempre en CSV

### Validación Robusta
- Verifica existencia de campos requeridos
- Mensajes de error descriptivos con campos disponibles
- Validación de archivos de entrada

### Reportes Completos
- 3 archivos CSV con datos filtrados
- 1 reporte Markdown con análisis completo
- Estadísticas en consola y en archivo
- Recomendaciones de acción

## Lógica de Matching

**Campo de Comparación:**
- **VTEX:** `_SkuId (Not changeable)`
- **Precios:** `código producto`

**Tipo de Match:**
- Comparación exacta como strings
- Case-sensitive
- Espacios en blanco eliminados (trim)

**Proceso:**
1. Cargar todos los SKU IDs de VTEX
2. Comparar cada entrada de precios con los SKU IDs
3. Clasificar en 3 categorías: matched, VTEX sin precio, precio sin SKU
4. Generar archivos separados para cada categoría

## Casos de Uso

### Escenario 1: Actualización de Precios
```bash
python3 filter_price_list.py current_vtex_catalog.csv new_prices.csv update
```
**Resultado:**
- `update_matched.csv`: Aplicar estos precios a VTEX
- `update_vtex_without_price.csv`: Solicitar precios para estos productos
- `update_prices_without_sku.csv`: Crear productos antes de aplicar precios

### Escenario 2: Auditoría de Catálogo
```bash
python3 filter_price_list.py vtex_export.json pricing_database.csv audit
```
**Resultado:**
- Identificar productos en VTEX sin información de precio
- Detectar precios huérfanos (sin producto asociado)
- Generar reporte de discrepancias

### Escenario 3: Migración de Datos
```bash
python3 filter_price_list.py migrated_products.csv legacy_prices.csv migration
```
**Resultado:**
- Validar que todos los productos migrados tienen precio
- Identificar precios del sistema legacy que necesitan productos nuevos

## Troubleshooting

### Error: Field not found
```
Error: Field '_SkuId (Not changeable)' not found in vtex_products.csv
Available fields: SkuId, ProductName, Brand
```
**Solución:** Verificar que el archivo VTEX tenga exactamente el campo `_SkuId (Not changeable)`

### Error: Field 'código producto' not found
```
Error: Field 'código producto' not found in prices.csv
Available fields: codigo, price, currency
```
**Solución:** Renombrar la columna del SKU en el CSV de precios a `código producto`

### 100% de precios sin SKU
**Causa:** Los códigos no coinciden (diferentes formatos, prefijos, etc.)
**Solución:**
- Verificar formato de SKU IDs en ambos archivos
- Revisar si hay prefijos/sufijos diferentes
- Comparar algunos valores manualmente

## Notas Técnicas

- **Encoding:** UTF-8 obligatorio para todos los archivos
- **Performance:** Eficiente con conjuntos grandes (usa diccionarios para O(1) lookups)
- **Memory:** Carga ambos archivos completos en memoria
- **Duplicados:** Si hay SKU IDs duplicados, solo se mantiene el último
- **Valores vacíos:** SKU IDs vacíos o solo espacios se ignoran

## Integración con Workflow VTEX

Este script se integra en el workflow de integración VTEX:

**Antes de ejecutar:**
- Paso 15: Crear SKUs en VTEX → genera archivo con SKU IDs
- Paso 23: Generar inventario → prepara datos de stock

**Este script (28):**
- Filtrar lista de precios basada en SKUs existentes

**Después de ejecutar:**
- Paso 29+: Aplicar precios a VTEX (usar `*_matched.csv`)
- Paso requerido: Crear productos faltantes (usar `*_prices_without_sku.csv`)
- Paso requerido: Completar precios (usar `*_vtex_without_price.csv`)

## Ayuda

Ver ayuda completa del script:
```bash
python3 filter_price_list.py --help
```
