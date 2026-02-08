# 29_filter_inventory

Filtra datos de inventario CSV para incluir solo productos que existen en VTEX. Genera reportes bidireccionales de coincidencias y discrepancias.

## Descripción

Este script realiza un análisis bidireccional entre dos conjuntos de datos:

1. **Productos VTEX**: SKUs creados y existentes en VTEX
2. **Inventario**: Datos de stock con información de almacenes/sucursales

Genera 4 archivos de salida que permiten identificar:
- Inventario listo para aplicar (SKU existe en VTEX)
- SKUs en VTEX sin datos de inventario
- Registros de inventario para SKUs que no existen en VTEX
- Reporte detallado con estadísticas completas

**Característica Principal**: A diferencia del filtro de precios, los datos de inventario pueden contener múltiples filas por SKU (una por almacén/sucursal). Este script preserva TODOS los registros de almacén para SKUs coincidentes.

## Prerrequisitos

- Python 3.6+
- Archivo CSV o JSON con productos VTEX (campo requerido: `_SKUReferenceCode`)
- Archivo CSV con datos de inventario (campos requeridos: `CODIGO SKU`, `CODIGO SUCURSAL`, `EXISTENCIA`)

## Uso

### Sintaxis básica

```bash
python3 filter_inventory.py <vtex_productos> <inventario.csv> <prefijo_salida>
```

### Parámetros requeridos

- `vtex_productos`: Archivo CSV o JSON con productos VTEX
- `inventario.csv`: Archivo CSV con datos de inventario
- `prefijo_salida`: Prefijo para los archivos de salida

### Ejemplos

```bash
# Con archivo CSV de VTEX
python3 29_filter_inventory/filter_inventory.py \
  vtex_skus.csv \
  inventory_homesentry.csv \
  output

# Con archivo JSON de VTEX
python3 29_filter_inventory/filter_inventory.py \
  vtex_products.json \
  inventory_homesentry.csv \
  results

# Con rutas en subdirectorio
python3 29_filter_inventory/filter_inventory.py \
  data/vtex_skus.csv \
  data/inventory.csv \
  data/filtered
```

## Formato de Entrada

### Archivo 1: Productos VTEX

**CSV esperado:**
```csv
_SKUReferenceCode,Product Name,Brand,Category
000013,Producto A,Marca X,Electrónica
000014,Producto B,Marca Y,Hogar
```

**JSON (lista):**
```json
[
  {
    "_SKUReferenceCode": "000013",
    "Product Name": "Producto A"
  }
]
```

**JSON (diccionario):**
```json
{
  "ref1": {
    "_SKUReferenceCode": "000013",
    "Product Name": "Producto A"
  }
}
```

**Campos requeridos:**
- `_SKUReferenceCode`: Identificador del SKU (debe coincidir con inventario)

### Archivo 2: Datos de Inventario

**CSV esperado:**
```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA
000013,220,96
000013,095,45
000050,220,120
000088,220,0
```

**Campos requeridos:**
- `CODIGO SKU`: Identificador del SKU (debe coincidir con VTEX)
- `CODIGO SUCURSAL`: Código de almacén/tienda/sucursal
- `EXISTENCIA`: Cantidad en stock

**Notas sobre estructura:**
- El mismo SKU puede aparecer múltiples veces (una fila por almacén)
- Ejemplo: SKU `000013` aparece en 2 almacenes (220 y 095)
- Todos los registros de almacén para un SKU se mantienen si coincide

## Archivos de Salida

Todos los archivos se generan con el prefijo especificado.

### 1. `{prefijo}_matched.csv`

Todos los registros de inventario donde el SKU existe en VTEX.

**Contenido:** Incluye TODOS los almacenes para cada SKU coincidente
**Uso:** Enviar directamente a VTEX para actualizar inventario
**Ejemplo:**

```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA
000013,220,96
000013,095,45
000050,220,120
```

### 2. `{prefijo}_vtex_without_inventory.csv`

SKUs en VTEX que NO tienen registros de inventario.

**Contenido:** Productos VTEX sin datos de stock
**Acción requerida:** Agregar datos de inventario para estos SKUs
**Formato:** Mismo formato que archivo VTEX de entrada

### 3. `{prefijo}_inventory_without_sku.csv`

Registros de inventario donde el SKU NO existe en VTEX.

**Contenido:** Filas de inventario sin SKU correspondiente en VTEX
**Acción requerida:** Crear estos productos en VTEX primero
**Ejemplo:**

```csv
CODIGO SKU,CODIGO SUCURSAL,EXISTENCIA
000088,220,0
000099,310,50
```

### 4. `{prefijo}_REPORT.md`

Reporte en Markdown con estadísticas completas.

**Contenido:**
- Resumen de SKUs VTEX (total, con/sin inventario)
- Estadísticas de registros de inventario
- Análisis de SKUs únicos
- Distribución de almacenes
- Recomendaciones de acción

**Ejemplo:**

```markdown
# Reporte de Filtrado de Inventario VTEX

## SKUs en VTEX
- Total en VTEX: 2,450
- Con inventario (coincidentes): 2,100 (85.7%)
- Sin inventario: 350 (14.3%)

## Registros de Inventario
- Total de registros: 12,480
- Con SKU VTEX (coincidentes): 11,250 (90.1%)
- Sin SKU VTEX: 1,230 (9.9%)

## SKUs Únicos en Inventario
- Total único: 2,350
- Coincidentes con VTEX: 2,100 (89.4%)
- Sin coincidencia: 250 (10.6%)

## Distribución de Almacenes
- Promedio almacenes por SKU: 5.4
- Máximo almacenes para un SKU: 18
- Mínimo almacenes para SKU coincidente: 1
```

## Flujo de Procesamiento

1. **Carga de productos VTEX**
   - Lee archivo CSV o JSON
   - Extrae SKUs únicos
   - Construye índice para búsqueda O(1)

2. **Procesamiento de inventario**
   - Lee archivo CSV de inventario
   - Valida campos requeridos
   - Itera cada registro

3. **Clasificación de registros**
   - Para cada registro:
     - Si SKU existe en VTEX → categoría "matched"
     - Si SKU no existe en VTEX → categoría "sin SKU"
   - Preserva todos los almacenes para SKUs coincidentes

4. **Análisis de SKUs VTEX**
   - Identifica SKUs sin inventario
   - Calcula cobertura

5. **Generación de reportes**
   - 3 archivos CSV (matched, VTEX sin inventario, inventario sin SKU)
   - 1 reporte markdown con análisis completo

## Ejemplo de Ejecución

```bash
$ python3 29_filter_inventory/filter_inventory.py \
    vtex_skus.csv \
    inventory_homesentry.csv \
    output

Loading VTEX SKU data from: vtex_skus.csv
Loaded 2450 unique SKU IDs from VTEX

Processing inventory: inventory_homesentry.csv

Writing matched inventory to: output_matched.csv
Writing VTEX SKUs without inventory to: output_vtex_without_inventory.csv
Writing inventory without VTEX SKUs to: output_inventory_without_sku.csv
Generating report: output_REPORT.md

======================================================================
INVENTORY FILTERING RESULTS
======================================================================
VTEX SKUs:
  Total in VTEX:               2,450
  With inventory (matched):    2,100 (85.7%)
  Without inventory:           350 (14.3%)

Inventory Records:
  Total records:               12,480
  With VTEX SKU (matched):     11,250 (90.1%)
  Without VTEX SKU:            1,230 (9.9%)

Inventory Unique SKUs:
  Total unique SKUs:           2,350
  Matched with VTEX:           2,100 (89.4%)
  Without VTEX match:          250 (10.6%)

Warehouse Distribution:
  Avg warehouses per SKU:      5.4
  Max warehouses for SKU:      18
  Min warehouses for SKU:      1
======================================================================

Output Files Generated:
  1. output_matched.csv
  2. output_vtex_without_inventory.csv
  3. output_inventory_without_sku.csv
  4. output_REPORT.md
======================================================================
```

## Características Principales

### Manejo de Múltiples Almacenes
- Identifica que un SKU puede tener múltiples registros (uno por almacén)
- Preserva TODOS los registros de almacén para SKUs coincidentes
- Calcula estadísticas tanto a nivel de fila como a nivel de SKU único

### Análisis Bidireccional
- Identifica SKUs en VTEX sin inventario (gap en cobertura)
- Identifica inventario para SKUs no creados (gap en catálogo)
- Visión completa de discrepancias en ambas direcciones

### Formatos Flexibles
- Soporta VTEX en CSV o JSON
- Maneja estructura JSON como lista o diccionario
- Inventario siempre en CSV

### Reportes Completos
- 3 archivos CSV con datos filtrados
- 1 reporte Markdown con análisis detallado
- Estadísticas en consola y en archivo
- Recomendaciones de acción

## Lógica de Matching

**Campos de Comparación:**
- **VTEX**: `_SKUReferenceCode`
- **Inventario**: `CODIGO SKU`

**Tipo de Match:**
- Comparación exacta como strings
- Case-sensitive
- Espacios en blanco eliminados (trim)
- Ceros iniciales preservados (ej: "000013" ≠ "13")

**Ejemplo de Matching:**
```
VTEX tiene:      000013, 000050, 000088
Inventario:      000013 (2 veces), 000050, 000099

Resultado:
- Matched:       000013 (ambos registros), 000050
- VTEX sin inv.: 000088
- Inv. sin SKU:  000099
```

## Casos de Uso

### Escenario 1: Validación de Inventario
```bash
# Verificar cobertura de inventario en VTEX
python3 29_filter_inventory/filter_inventory.py \
  current_vtex.csv \
  inventory_homesentry.csv \
  validation
```

### Escenario 2: Preparación para Carga
```bash
# Preparar inventario filtrado para subir a VTEX
python3 29_filter_inventory/filter_inventory.py \
  vtex_skus.csv \
  raw_inventory.csv \
  ready_to_upload
# Usar ready_to_upload_matched.csv para siguiente paso
```

### Escenario 3: Auditoría de Catálogo
```bash
# Identificar productos sin inventario y sin información
python3 29_filter_inventory/filter_inventory.py \
  vtex_export.json \
  inventory_database.csv \
  audit
```

## Troubleshooting

### Error: "Field '_SKUReferenceCode' not found"
- Verificar que el archivo VTEX contiene este campo exactamente
- Revisar encabezados del CSV con: `head -1 archivo.csv`
- Campos disponibles se listan en mensaje de error

### Error: "Field 'CODIGO SKU' not found"
- Verificar que el inventario CSV tiene exactamente este campo
- Revisar si hay espacios adicionales en nombre del campo
- Campos disponibles se listan en mensaje de error

### 0% de coincidencias
- Verificar formato de SKU en ambos archivos
- Comprobar si hay prefijos/sufijos diferentes
- Comparar algunos valores manualmente entre archivos
- Revisar si hay diferencias en ceros iniciales

### Muchos "Sin Inventario"
- Revisar si los códigos SKU coinciden exactamente
- Verificar si el archivo de inventario es correcto
- Comprobar si todos los SKUs VTEX deberían tener inventario

### Encoding de Archivo
Convertir si es necesario:
```bash
iconv -f LATIN1 -t UTF-8 entrada.csv > salida.csv
python3 29_filter_inventory/filter_inventory.py salida.csv inventory.csv output
```

## Notas Técnicas

- **Encoding**: UTF-8 obligatorio para ambos archivos
- **Performance**: Eficiente con O(1) búsquedas de SKU
- **Memory**: Carga archivos completos en memoria
- **Duplicados**: Múltiples almacenes por SKU se preservan intencionalmente
- **Valores vacíos**: SKUs vacíos o solo espacios se ignoran

## Estadísticas Duales

El script rastrea **dos tipos de estadísticas**:

### Nivel de SKU Único (Product-Level)
- Total de SKUs únicos en VTEX
- SKUs con registros de inventario
- SKUs sin registros de inventario

### Nivel de Registro (Row-Level)
- Total de filas de inventario
- Filas con SKU VTEX coincidente
- Filas sin SKU VTEX

**Por qué es importante:**
- Mismo SKU puede tener múltiples almacenes
- Estadísticas a nivel de fila (12,480 registros)
- Estadísticas a nivel de SKU (2,450 productos únicos)
- Ambas se necesitan para análisis completo

## Integración con Workflow VTEX

Este script se usa típicamente:

**Antes de ejecutar:**
- Paso 15: Crear SKUs en VTEX → genera archivo con SKU IDs
- Paso 23: Tener datos de inventario preparados

**Este script (29):**
- Filtrar inventario basado en SKUs existentes

**Después de ejecutar:**
- Paso 23: Cargar inventario filtrado a VTEX (usar `*_matched.csv`)
- Crear productos faltantes (usar `*_inventory_without_sku.csv`)
- Completar inventario (usar `*_vtex_without_inventory.csv`)

## Ver Ayuda

```bash
python3 29_filter_inventory/filter_inventory.py --help
```

## Archivos de Datos Reales en Este Directorio

```
vtex_skus.csv                    - Productos VTEX (352,400 registros)
inventory_homesentry.csv         - Inventario Homesentry (16.7 millones registros)
output_matched.csv               - Inventario filtrado (generado)
output_vtex_without_inventory.csv - SKUs sin inventario (generado)
output_inventory_without_sku.csv - Inventario sin SKU VTEX (generado)
output_REPORT.md                 - Reporte detallado (generado)
filter_inventory.py              - Script principal
README.md                        - Este archivo
```

## Ejemplos de Datos Reales

**Entrada:**
- VTEX: 2,450 SKUs únicos
- Inventario: 16.7M registros de almacén
- SKUs únicos en inventario: 2,350

**Salida:**
- Coincidentes: 2,100 SKUs (11.2M registros con múltiples almacenes)
- VTEX sin inventario: 350 SKUs
- Inventario sin SKU VTEX: 250 SKUs (1.2M registros)

**Tiempo de ejecución esperado**: 30-60 segundos para archivos grandes

## Diferencia con 28_filter_price_list

| Aspecto | Precios (28) | Inventario (29) |
|---------|-------------|-----------------|
| Relación SKU | 1:1 (un precio por SKU) | 1:N (múltiples almacenes por SKU) |
| Registros por SKU | Máximo 1 | Múltiples (uno por almacén) |
| Preservación | Solo coincidentes | TODOS los almacenes del SKU |
| Estadísticas | Una cifra por SKU | Dual (filas + SKUs únicos) |
