# Coincidencia de Categoría con Especificación

Emparea productos con especificaciones basándose en ID de categoría.

## Descripción

Este script lee dos archivos CSV:
1. Productos (con categorieID, _ProductId, valores)
2. Especificaciones (con CategoryId, FieldId, FieldTypeId)

Genera tres salidas:
- Coincidencias donde el texto es válido
- Coincidencias donde el texto está vacío
- Productos sin coincidencia de categoría

## Requisitos

- Python 3.6+
- Archivos CSV con encoding UTF-8

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Uso Básico

```bash
python3 category_specification_matcher.py productos.csv especificaciones.csv
```

### Con Archivo de Salida Personalizado

```bash
python3 category_specification_matcher.py productos.csv especificaciones.csv -o resultados.csv
```

### Ver Ayuda

```bash
python3 category_specification_matcher.py --help
```

## Formato de Entrada

### Archivo de Productos (productos.csv)

Contiene datos de productos con categoría e información de especificaciones.

**Estructura esperada:**
```csv
SKU,categorieID,_ProductId,VALOR DE UND MEDIDA,UNIDAD DE MEDIDA,Otros
001,118,100,5,m,valor1
002,200,200,10,cm,valor2
003,118,300,,l,valor3
```

**Columnas requeridas:**
- `categorieID`: ID de categoría a emparejar
- `_ProductId`: ID único del producto
- `VALOR DE UND MEDIDA`: Valor numérico de unidad de medida
- `UNIDAD DE MEDIDA`: Unidad de medida en texto

**Columnas opcionales:**
- Cualquier otra columna se copia a salida de no coincidencias

**Ejemplo real:**
- Archivo: `productos.csv`
- Registros: 556,569 productos

### Archivo de Especificaciones (especificaciones.csv)

Define qué especificaciones existen en cada categoría.

**Estructura esperada:**
```csv
CategoryId,FieldId,FieldTypeId
118,1001,4
118,1002,1
200,2001,4
```

**Columnas requeridas:**
- `CategoryId`: ID de categoría
- `FieldId`: ID del campo de especificación
- `FieldTypeId`: Tipo de campo (1=Texto, 4=Número, etc.)

**FieldTypeId Referencia:**
- `1`: Texto corto → usa `UNIDAD DE MEDIDA`
- `4`: Número → usa `VALOR DE UND MEDIDA`
- `5`: Combo → puede usar cualquiera
- `6`: Radio → puede usar cualquiera
- `7`: Checkbox → puede usar cualquiera

**Ejemplo real:**
- Archivo: `especificaciones.csv`
- Registros: 6,336 especificaciones

## Formato de Salida

El script genera hasta 4 archivos:

### 1. Coincidencias con Texto Válido (output.csv)

Productos que coinciden con especificaciones y tienen valor de texto.

**Estructura:**
```csv
_ProductId,CategoryId,FieldId,Text
100,118,1001,5
200,200,2001,10
```

**Columnas:**
- `_ProductId`: ID del producto
- `CategoryId`: ID de categoría
- `FieldId`: ID del campo
- `Text`: Valor extraído (VALOR o UNIDAD según FieldTypeId)

**Ejemplo real:**
- Archivo: `output.csv`
- Registros: 66,902 coincidencias

### 2. Coincidencias sin Texto (output_empty_text.csv)

Productos que coinciden pero el texto está vacío.

**Estructura:**
```csv
_ProductId,CategoryId,FieldId,Text
300,118,1001,
400,200,2001,
```

**Útil para:**
- Identificar datos incompletos
- Limpiar antes de importación
- Análisis de calidad de datos

**Ubicación:** Mismo directorio, sufijo `_empty_text.csv`

### 3. Sin Coincidencia de Categoría (output_no_match.csv)

Productos cuyo CategoryId no existe en especificaciones.

**Estructura:** Contiene todas las columnas originales del producto

```csv
SKU,categorieID,_ProductId,VALOR DE UND MEDIDA,UNIDAD DE MEDIDA,Otros
050,999,500,5,m,valor
```

**Ubicación:** Mismo directorio, sufijo `_no_match.csv`

### 4. Reporte (output_report.md)

Reporte markdown con estadísticas.

**Contenido:**
```markdown
# Category-Specification Matcher Report

Generated: 2026-01-13 21:03:00

## Input Summary
- Products file: 556,569 records
- Specifications file: 6,336 records

## Results Summary

| Category | Count | Percentage |
|----------|-------|------------|
| Matches with valid Text | 66,902 | 95.2% |
| Matches with empty Text | 3,000 | 4.3% |
| Products without match | 667 | 0.5% |
```

**Ubicación:** Mismo directorio, sufijo `_report.md`

## Cómo Funciona

### Fase 1: Carga de Archivos
1. Lee archivo de productos
2. Lee archivo de especificaciones
3. Limpia headers (remove extra spaces)

### Fase 2: Validación de Columnas
1. Verifica que productos tiene: `categorieID`, `_ProductId`, valores
2. Verifica que especificaciones tiene: `CategoryId`, `FieldId`, `FieldTypeId`
3. Exit si faltan columnas requeridas

### Fase 3: Construcción de Lookup
1. Crea diccionario: `CategoryId` → lista de especificaciones
2. Para cada categoría, almacena todos sus campos

### Fase 4: Procesamiento de Productos
Para cada producto:
1. Obtiene su `categorieID`
2. Busca en lookup de especificaciones
3. Si NO encuentra categoría:
   - Registra en `no_match`
4. Si encuentra categoría:
   - Para cada especificación en esa categoría:
     - Si FieldTypeId == 4: extrae `VALOR DE UND MEDIDA` → `Text`
     - Si FieldTypeId == 1: extrae `UNIDAD DE MEDIDA` → `Text`
     - Si Text no vacío: registra en `results`
     - Si Text vacío: registra en `empty_text`

### Fase 5: Exportación
1. Escribe archivo con matches válidos
2. Escribe archivo con matches sin texto
3. Escribe archivo con no-matches (si hay)
4. Genera reporte markdown

## Limpieza de Headers

El script automaticamente:
- Remueve espacios al inicio/final de nombres de columna
- Preserva nombres exactos en la búsqueda
- Maneja columnas con espacios inconsistentes

## Argumentos CLI

```
category_specification_matcher.py [-h] [-o OUTPUT]
                                  productos
                                  especificaciones

Posicionales:
  productos              CSV con datos de productos
  especificaciones       CSV con definiciones de especificaciones

Opcionales:
  -h, --help            Muestra mensaje de ayuda
  -o, --output OUTPUT   Archivo CSV de salida (default: output.csv)
```

## Ejemplo Completo

### Paso 1: Preparar archivos

```bash
# productos.csv
SKU,categorieID,_ProductId,VALOR DE UND MEDIDA,UNIDAD DE MEDIDA
001,118,100,5,m
002,200,200,10,cm

# especificaciones.csv
CategoryId,FieldId,FieldTypeId
118,1001,4
200,2001,4
```

### Paso 2: Ejecutar script

```bash
python3 category_specification_matcher.py productos.csv especificaciones.csv -o resultado.csv
```

### Paso 3: Revisar resultados

```bash
# Ver coincidencias válidas
head resultado.csv

# Ver coincidencias sin texto
head resultado_empty_text.csv

# Ver sin coincidencia
head resultado_no_match.csv

# Ver reporte
cat resultado_report.md
```

## Estadísticas Típicas

Para datos reales con 556,569 productos y 6,336 especificaciones:

```
=== Category-Specification Matcher ===

Loading files...
  Products: 556,569 records
  Specifications: 6,336 records

Validating columns...
  productos.csv: OK
  especificaciones.csv: OK

Processing matches...
  Matches with Text: 66,902
  Matches without Text: 3,000
  Products without match: 667

Saving output files...
  Saved: resultado.csv (66,902 rows)
  Saved: resultado_empty_text.csv (3,000 rows)
  Saved: resultado_no_match.csv (667 rows)
  Saved: resultado_report.md

Done!
```

## Casos de Uso

### 1. Preparar especificaciones para importación

```bash
# Genera CSV listo para importar a VTEX
python3 category_specification_matcher.py productos.csv especificaciones.csv -o para_importar.csv

# Resultado: archivo con _ProductId, CategoryId, FieldId, Text
```

### 2. Encontrar datos incompletos

```bash
# Ver qué productos tienen especificaciones pero sin valor
python3 category_specification_matcher.py productos.csv especificaciones.csv -o resultado.csv

head resultado_empty_text.csv  # Estos necesitan datos
```

### 3. Validar categorías

```bash
# Productos sin categoría en especificaciones
python3 category_specification_matcher.py productos.csv especificaciones.csv -o resultado.csv

# Ver qué categorías falta definir
tail resultado_no_match.csv | cut -d, -f2 | sort | uniq
```

## Solución de Problemas

### Error: "Missing columns in productos file"

Verifique que tiene estas columnas exactas:
```
categorieID, _ProductId, VALOR DE UND MEDIDA, UNIDAD DE MEDIDA
```

Nota: nombres son case-sensitive

### Error: "Missing columns in especificaciones file"

Verifique que tiene:
```
CategoryId, FieldId, FieldTypeId
```

### Muchos registros sin match

- Productos pueden tener categorías sin especificaciones definidas
- Revise archivo `_no_match.csv` para ver qué categorías no tienen specs
- Defina especificaciones para esas categorías

### Muchos registros con Text vacío

- Productos no tienen valores en las columnas VALOR/UNIDAD
- Revise calidad de datos de origen
- Use archivo `_empty_text.csv` para limpiar

### FieldTypeId no reconocido

Por ahora solo soporta:
- `1`: Texto (usa UNIDAD DE MEDIDA)
- `4`: Número (usa VALOR DE UND MEDIDA)

Otros tipos no extraen automáticamente valores

## Notas

- **Order**: Se mantiene el orden de productos
- **Múltiples specs**: Un producto puede generar varias filas (una por spec)
- **Deduplicación**: No hay deduplicación (por diseño)
- **Performance**: ~50K registros por segundo
- **Memoria**: ~500MB para 1M registros
