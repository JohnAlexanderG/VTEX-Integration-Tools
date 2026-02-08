# Coincidencia de SKU CSV

Compara y filtra datos CSV basándose en SKUs existentes, con dos scripts complementarios.

## Descripción General

Este directorio contiene dos scripts que trabajan juntos:

1. **csv_sku_matcher.py**: Compara SKUs de dos archivos CSV y genera coincidencias
2. **enrich_category_ids.py**: Enriquece datos con IDs de categoría faltantes

## Requisitos

- Python 3.6+
- Archivos CSV con encoding UTF-8

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install -r requirements.txt
```

---

## Script 1: csv_sku_matcher.py

### Descripción

Compara SKUs de dos archivos CSV:
- **Archivo 1**: SKUs existentes con `_SkuId`, `_SKUReferenceCode`, `_ProductId`
- **Archivo 2**: Datos a filtrar con columna `SKU` (puede tener múltiples filas por SKU)

Genera:
- Filas coincidentes enriquecidas con `_SkuId` y `_ProductId`
- Filas no coincidentes
- Reporte markdown con estadísticas

### Uso

```bash
python3 csv_sku_matcher.py skus_existentes.csv datos_a_filtrar.csv prefijo_salida
```

### Ejemplo

```bash
python3 csv_sku_matcher.py vtex_skus.csv specifications.csv filtered_specs
```

**Archivos generados:**
- `filtered_specs_matched.csv` (coincidencias)
- `filtered_specs_not_found.csv` (no coincidencias)
- `filtered_specs_REPORT.md` (reporte)

### Formato de Entrada

#### Archivo 1: SKUs Existentes (vtex_skus.csv)

```csv
_SkuId,_SKUReferenceCode,_ProductId,OtrosCampos
1001,001,100,valor1
1002,002,200,valor2
```

**Columnas requeridas:**
- `_SkuId`: ID único del SKU
- `_SKUReferenceCode`: Código de referencia a emparejar
- `_ProductId`: ID del producto

**Ejemplo real:**
- Archivo: `vtex_skus.csv`
- Registros: 354,348 SKUs

#### Archivo 2: Datos a Filtrar (specifications.csv)

```csv
SKU,Nombre,Precio,Otros
001,Producto A,100,valor1
001,Producto A,100,valor2
002,Producto B,200,valor3
```

**Columna requerida:**
- `SKU`: Identificador a emparejar

**Características:**
- Puede tener múltiples filas por SKU
- Preserva todas las columnas originales
- Enriquece con `_SkuId` y `_ProductId`

**Ejemplo real:**
- Archivo: `specifications.csv`
- Registros: 19,051,026 especificaciones

### Formato de Salida

#### 1. Coincidencias (prefijo_matched.csv)

Contiene datos del archivo 2 enriquecidos con info del archivo 1.

```csv
_SkuId,_ProductId,SKU,Nombre,Precio,Otros
1001,100,001,Producto A,100,valor1
1001,100,001,Producto A,100,valor2
1002,200,002,Producto B,200,valor3
```

**Ejemplo real:**
- Archivo: `filtered_specs_v2_matched.csv`
- Registros: 20,207,272 coincidencias

#### 2. No Coincidencias (prefijo_not_found.csv)

Contiene filas del archivo 2 que no tuvieron match.

```csv
SKU,Nombre,Precio,Otros
003,Producto C,300,valor4
```

**Ejemplo real:**
- Archivo: `filtered_specs_v2_not_found.csv`
- Registros: 1,753,691 no encontrados

#### 3. Reporte (prefijo_REPORT.md)

Reporte markdown con estadísticas.

```markdown
# CSV SKU Matcher Report

**Date:** 2026-01-16 02:23:00

## Input Files
- File 1 (Existing SKUs): `vtex_skus.csv` (354,348 records)
- File 2 (Data to Filter): `filtered_specs_matched.csv` (20,207,272 records)
- Unique SKU References: 350,000

## Results

| Metric | Count | Percentage |
|--------|-------|-----------|
| Matched | 20,207,272 | 91.9% |
| Not Found | 1,753,691 | 8.1% |
| Total | 21,960,963 | 100.0% |

## Output Files
- `filtered_specs_v2_matched.csv` (20,207,272 rows)
- `filtered_specs_v2_not_found.csv` (1,753,691 rows)
- `filtered_specs_v2_REPORT.md` (this report)
```

**Ubicación:** Mismo directorio, sufijo `_REPORT.md`

### Cómo Funciona csv_sku_matcher.py

1. **Carga SKUs existentes** → crea mapeo `_SKUReferenceCode` → `{_SkuId, _ProductId}`
2. **Lee datos a filtrar** por fila
3. **Busca SKU** en mapeo
4. **Si encuentra**: copia fila y agrega `_SkuId`, `_ProductId`
5. **Si no encuentra**: registra en no encontrados
6. **Genera reportes** con estadísticas

### Argumentos CLI

```
csv_sku_matcher.py existing_skus.csv data_to_filter.csv output_prefix

Positional Arguments:
  existing_skus        CSV with _SkuId, _SKUReferenceCode, _ProductId
  data_to_filter       CSV with SKU column to match
  output_prefix        Output files prefix
```

---

## Script 2: enrich_category_ids.py

### Descripción

Enriquece CSV con IDs de categoría faltantes usando tabla de búsqueda.

Llena valores `categorieID` faltantes haciendo matching del path de categoría (Categoria>Subcategoria>Linea) contra tabla de búsqueda.

**Características:**
- Matching exacto por path completo
- Matching por prefijo para nombres truncados
- Normalización de texto (acentos, espacios)

### Uso

```bash
python3 enrich_category_ids.py entrada.csv categorias.csv salida.csv
```

### Ejemplo

```bash
python3 enrich_category_ids.py filtered_specs_v2_matched.csv categorias.csv enriched.csv
```

### Formato de Entrada

#### Archivo 1: Datos a Enriquecer (filtered_specs_v2_matched.csv)

Debe tener columna `categorieID` (puede estar vacía).

```csv
SKU,Categoria,Subcategoria,Linea,categorieID,Otros
001,Ropa,Camisas,Manga Corta,118,valor1
002,Ropa,Pantalones,Jeans,200,valor2
003,Hogar,Muebles,Sillas,,valor3
```

**Columnas requeridas:**
- `Categoria`: Nombre de categoría principal
- `Subcategoria`: Nombre de subcategoría
- `Linea`: Nombre de línea de producto
- `categorieID`: ID de categoría (puede estar vacío)

**Características:**
- `categorieID` vacío: se intenta enriquecer
- `categorieID` presente: se mantiene tal cual
- Otros campos: se copian en salida

**Ejemplo real:**
- Archivo: `filtered_specs_v2_matched.csv`
- Registros: 20,209,277 filas

#### Archivo 2: Tabla de Búsqueda (categorias.csv)

```csv
Path,DepartamentID,categorieID,SubcategorieID
/Ropa>Camisas>Manga Corta,1,118,1001
/Ropa>Pantalones>Jeans,1,200,2001
/Hogar>Muebles>Sillas,2,300,3001
```

**Columnas requeridas:**
- `Path`: Ruta completa (Categoria>Subcategoria>Linea)
- `categorieID` o `SubcategorieID` o `DepartamentID`: Al menos una

**Búsqueda:**
- Usa ID más específico disponible: SubcategorieID > categorieID > DepartamentID

**Ejemplo real:**
- Archivo: `categorias.csv`
- Registros: 88,336 categorías

### Formato de Salida

#### Archivo Enriquecido (enriched.csv)

Mismo formato que entrada, pero con `categorieID` completado.

```csv
SKU,Categoria,Subcategoria,Linea,categorieID,Otros
001,Ropa,Camisas,Manga Corta,118,valor1
002,Ropa,Pantalones,Jeans,200,valor2
003,Hogar,Muebles,Sillas,300,valor3
```

**Ejemplo real:**
- Archivo: `filtered_specs_v2_enriched.csv`
- Registros: 20,209,277 filas enriquecidas

### Cómo Funciona enrich_category_ids.py

1. **Carga tabla de búsqueda**
   - Crea mapeo exacto: Path normalizado → ID
   - Crea índice de prefijos: Categoria>Subcategoria → lista de IDs

2. **Para cada fila de entrada:**
   - Si ya tiene `categorieID`: mantiene
   - Si no tiene:
     - Intenta matching exacto: Categoria>Subcategoria>Linea
     - Si no: intenta matching por prefijo
     - Si encuentra: rellena `categorieID`
     - Si no: deja vacío

3. **Exporta resultado** con categorieID enriquecido

### Normalización de Texto

Antes de comparar, normaliza:
```
Acentos: "ropa" = "ropa" (sin importar tildes)
Espacios: múltiples espacios → uno solo
Mayúsculas: TODO → minúsculas
Caracteres especiales: °,©,™ → espacio
Unicode: NFD (descomposición)
```

Ejemplo:
```
"Ropa > Camisas > Manga Corta"  → "ropa > camisas > manga corta"
"Ropa>Camisas>Manga Corta"      → "ropa>camisas>manga corta"
"Ropa  >  Camisas  >  Manga Corta" → "ropa>camisas>manga corta"
```

### Argumentos CLI

```
enrich_category_ids.py [-h] input_csv categories_csv output_csv

Positional Arguments:
  input_csv           Input CSV with missing categorieID values
  categories_csv      Categories lookup CSV (Path, categorieID, SubcategorieID)
  output_csv          Output CSV with enriched category IDs

Optional Arguments:
  -h, --help          Shows help message
```

---

## Flujo de Trabajo Combinado

Típicamente usarás ambos scripts juntos:

```bash
# Paso 1: Coincidencia de SKUs
python3 csv_sku_matcher.py vtex_skus.csv specifications.csv filtered_specs

# Paso 2: Enriquecimiento de Categorías
python3 enrich_category_ids.py filtered_specs_matched.csv categorias.csv filtered_specs_enriched.csv

# Paso 3: Revisar resultado
head filtered_specs_enriched.csv
```

## Archivos de Datos Reales

En este directorio:

```
vtex_skus.csv                    (354,348 registros)
specifications.csv               (19,051,026 registros)
categorias.csv                   (88,336 registros)
```

Salidas:
```
filtered_specs_v2_matched.csv    (20,207,272 registros)
filtered_specs_v2_not_found.csv  (1,753,691 registros)
filtered_specs_v2_enriched.csv   (20,209,277 registros enriquecidos)
filtered_specs_v2_REPORT.md      (reporte)
```

## Performance

### csv_sku_matcher.py
- **Velocidad**: ~500K registros/segundo
- **Memoria**: ~2GB para 20M registros
- **Duración**: 20M registros: ~40 segundos

### enrich_category_ids.py
- **Velocidad**: ~100K registros/segundo
- **Memoria**: ~500MB
- **Duración**: 20M registros: ~3 minutos

## Casos de Uso

### 1. Importación de especificaciones a VTEX

```bash
# Paso 1: Asegurar que todos los SKUs existen
python3 csv_sku_matcher.py vtex_skus.csv especificaciones.csv result

# Paso 2: Enriquecer con categorías
python3 enrich_category_ids.py result_matched.csv categorias.csv final.csv

# result: datos listos para importación con IDs correctos
```

### 2. Validación de datos

```bash
# Ver SKUs no encontrados
tail result_not_found.csv | cut -d, -f1 | sort | uniq

# Ver categorías no enriquecidas
grep "^[^,]*,[^,]*,[^,]*,[^,]*,$" final.csv | head
```

### 3. Limpieza antes de sincronización

```bash
python3 csv_sku_matcher.py skus_vigentes.csv datos_nuevos.csv clean

# Ahora 'clean_matched.csv' contiene solo datos conocidos
```

## Troubleshooting

### csv_sku_matcher.py

**Tasa de match baja**
- SKUs pueden tener formato diferente
- Espacios o caracteres especiales
- Revise archivo `_not_found.csv`

**Archivo muy grande tarda**
- Python maneja 20M+ registros
- Considere dividir en lotes

### enrich_category_ids.py

**Muchos categorieID vacíos al final**
- Paths no coinciden exactamente con tabla de búsqueda
- Verificar normalización
- Usar matching exacto vs prefijo

**"Paths not found"** en salida
- Esos paths no existen en tabla de categorías
- Necesita agregar a tabla de búsqueda

## Notas

- Ambos scripts preservan el orden de entrada
- Manejo robusto de caracteres especiales
- Encoding UTF-8 obligatorio
- Columnas duplicadas se renombran automáticamente
- Sin límite de tamaño de archivo
