# Coincidencia de Especificaciones

Compara y combina especificaciones de categoría y producto basándose en SKU.

## Descripción

Este script compara dos archivos CSV de especificaciones:
1. Especificaciones de categoría (estructura de especificaciones definidas por categoría)
2. Especificaciones de producto (datos específicos de los productos)

Genera archivos de salida con:
- Registros combinados donde los SKUs coinciden
- Registros de productos sin categoría correspondiente
- Opcionalmente, registros únicos sin duplicados por ID

## Requisitos

- Python 3.6+
- Archivos CSV codificados en UTF-8
- Ambos archivos deben tener una columna SKU

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Matching básico

```bash
python3 match_specifications.py specs_cat.csv specs_prod.csv
```

### Con deduplicación por ID

```bash
python3 match_specifications.py specs_cat.csv specs_prod.csv --deduplicate
```

### Con columna SKU personalizada

```bash
python3 match_specifications.py specs_cat.csv specs_prod.csv --sku-column "CODIGO"
```

### Con deduplicación y ID personalizado

```bash
python3 match_specifications.py specs_cat.csv specs_prod.csv \
    --deduplicate --id-column "ProductID"
```

### Ver ayuda completa

```bash
python3 match_specifications.py --help
```

## Formato de Entrada

### Archivo de Especificaciones de Categoría (specs_cat.csv)

Ejemplo de estructura:
```csv
SKU,NombreEspecificacion,TipoField,OtrosCampos
001,Color,1,valor1
002,Tamaño,2,valor2
```

**Columnas requeridas:**
- `SKU`: Identificador único a comparar (nombre configurable con `--sku-column`)

**Ejemplo real:**
- `specs_cat.csv`: Contiene 19,051,116 registros

### Archivo de Especificaciones de Producto (specs_prod.csv)

Ejemplo de estructura:
```csv
SKU,_ProductId,VALOR DE UND MEDIDA,Especificacion
001,123,5,especificación1
002,456,10,especificación2
```

**Columnas requeridas:**
- `SKU`: Identificador a coincidir (nombre configurable)
- `_ProductId`: ID del producto (se preserva en salida)
- Otros campos: Se copian tal cual en los resultados

**Ejemplo real:**
- `specs_prod.csv`: Contiene 322,080 registros

## Formato de Salida

El script genera automáticamente archivos con timestamp (YYYYMMDD):

### Sin deduplicación

1. **matched_specs_YYYYMMDD.csv**
   - Registros donde SKU de producto coincide con SKU de categoría
   - Combina todas las columnas de ambos archivos
   - Contiene el campo `_ProductId`
   - Ejemplo: `matched_specs_20260113.csv` (556,569 registros)

2. **unmatched_specs_YYYYMMDD.csv**
   - Registros de productos sin coincidencia en categorías
   - Contiene solo columnas del archivo de especificaciones de producto
   - Útil para análisis de discrepancias
   - Ejemplo: `unmatched_specs_20260113.csv` (74 registros)

### Con deduplicación (--deduplicate)

Además de los anteriores:

3. **matched_specs_unique_YYYYMMDD.csv**
   - Registros sin duplicados por columna ID
   - Conserva primera ocurrencia de cada ID
   - Ejemplo: `matched_specs_unique_20260113.csv` (18,488 registros)

## Cómo Funciona

### Fase 1: Carga y Validación
1. Lee archivo de categorías y valida columna SKU
2. Lee archivo de productos y valida columna SKU
3. Normaliza valores SKU (elimina comillas, espacios)

### Fase 2: Mapeo de Categorías
1. Construye diccionario de SKU → datos de categoría
2. Si hay duplicados, la última ocurrencia sobrescribe
3. Registra SKUs únicos encontrados

### Fase 3: Matching de Productos
Para cada producto:
1. Normaliza su SKU
2. Busca en mapeo de categorías
3. Si encuentra coincidencia:
   - Combina datos de categoría + datos de producto
   - Preserva `_ProductId` en salida
4. Si no encuentra coincidencia:
   - Registra en archivo de no encontrados

### Fase 4: Deduplicación (opcional)
1. Lee archivo de coincidencias
2. Itera registros por primera vez vista de ID
3. Descarta duplicados posteriores

## Normalización de SKU

El script maneja múltiples formatos de SKU:

```
"000013"      → 000013  (comillas dobles)
'000013'      → 000013  (comillas simples)
" 000013 "    → 000013  (espacios)
000013        → 000013  (número)
" '000013' "  → 000013  (múltiples formatos)
```

## Argumentos CLI

```
match_specifications.py [-h]
                       [--sku-column NOMBRE]
                       [--deduplicate]
                       [--id-column NOMBRE]
                       categoria_specs
                       product_specs

Posicionales:
  categoria_specs       Archivo CSV con especificaciones de categoría
  product_specs         Archivo CSV con especificaciones de producto

Opcionales:
  -h, --help           Muestra mensaje de ayuda
  --sku-column NOMBRE  Nombre columna SKU (default: "SKU")
  --deduplicate        Genera archivo sin duplicados por ID
  --id-column NOMBRE   Nombre columna ID (default: "ID")
```

## Ejemplo Completo de Ejecución

```bash
# Matching básico
python3 match_specifications.py specs_cat.csv specs_prod.csv

# Salida esperada:
# - matched_specs_20260113.csv
# - unmatched_specs_20260113.csv

# Con deduplicación
python3 match_specifications.py specs_cat.csv specs_prod.csv --deduplicate

# Salida esperada:
# - matched_specs_20260113.csv
# - unmatched_specs_20260113.csv
# - matched_specs_unique_20260113.csv
```

## Estadísticas de Salida

El script imprime un reporte detallado:

```
======================================================================
CSV SPECIFICATION MATCHING RESULTS
======================================================================

File 1 (Category Specifications):
  Total records:                19,051,116
  Unique SKUs:                  19,000

File 2 (Product Specifications):
  Total records:                322,080
  Matched with File 1:          322,006 (99.9%)
  Not found in File 1:          74 (0.1%)

Output Files Generated:
  1. matched_specs_20260113.csv
  2. unmatched_specs_20260113.csv

Deduplication Summary:
  Original matched records:     322,006
  Unique records by 'ID':       18,488
  Duplicates removed:           303,518

======================================================================
```

## Notas y Consideraciones

- **SKUs vacíos**: Se omiten automáticamente con mensaje de estadística
- **Duplicados**: Si hay SKUs duplicados en categorías, última ocurrencia gana
- **Encoding**: Requiere UTF-8 obligatoriamente
- **Preservación de _ProductId**: Este campo se mantiene en todas las salidas
- **Performance**: Manejo eficiente en memoria con diccionarios de búsqueda
- **Reintentos**: Para archivos grandes, puede requerir suficiente memoria RAM

## Troubleshooting

### Error: "column not found"
Verifique que ambos archivos tienen la columna SKU (o especifique con `--sku-column`)

### Error de encoding
Asegúrese que los archivos CSV están guardados con encoding UTF-8

### Sin coincidencias
- Verifique que los valores SKU son compatibles entre archivos
- Revise si hay espacios o caracteres especiales ocultos
- Use el archivo `unmatched_specs_*.csv` para análisis
