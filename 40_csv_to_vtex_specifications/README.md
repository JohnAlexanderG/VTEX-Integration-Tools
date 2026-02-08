# Transformador CSV a Especificaciones VTEX

Transforma CSV con datos de productos al formato requerido para importar especificaciones en VTEX.

## Descripción

Este script transforma datos de productos en CSV al formato de especificaciones esperado por VTEX, listos para ser importados o procesados por otros scripts.

**Función:**
- Lee CSV con datos de productos y especificaciones
- Transforma columnas al formato VTEX
- Genera CSV con estructura preparada para VTEX

## Requisitos

- Python 3.6+
- Archivo CSV con datos de productos

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Uso Básico

```bash
python3 csv_to_vtex_specifications.py entrada.csv salida.csv
```

### Con Archivo de Inválidos

```bash
python3 csv_to_vtex_specifications.py entrada.csv salida.csv --invalid invalidos.csv
```

### Ejemplo Completo

```bash
python3 csv_to_vtex_specifications.py matched_data.csv vtex_specs.csv --invalid vtex_specs_invalid.csv
```

### Ver Ayuda

```bash
python3 csv_to_vtex_specifications.py --help
```

## Formato de Entrada

### Archivo CSV de Entrada

Estructura esperada:

```csv
_SkuId,_ProductId,SKU,Categoria,Subcategoria,Linea,Nombre Especificacion,Especificacion,cantidad,COGNOTACIÓN,ID,DepartamentID,categorieID
1001,100,001,Ropa,Camisas,Manga Corta,Color,Rojo,1,cod1,id1,1,10
1002,200,002,Ropa,Pantalones,Jeans,Talla,Talla M,1,cod2,id2,1,20
1003,300,003,Hogar,Muebles,Sillas,Material,Madera,1,cod3,id3,2,30
```

**Columnas requeridas para transformación:**
- `Nombre Especificacion`: Nombre del campo de especificación
- `Especificacion`: Valor de la especificación
- `cantidad`: Valor alternativo si Especificacion == Nombre Especificacion
- `categorieID`: ID de la categoría

**Columnas opcionales:**
- `_SkuId`, `_ProductId`, `SKU`: Se copian a salida
- Cualquier otra columna: se copia a salida

**Lógica de Transformación:**
```python
if Especificacion == Nombre Especificacion:
    valor_final = cantidad  # Usa cantidad como fallback
else:
    valor_final = Especificacion  # Usa valor directo
```

**Ejemplo real:**
- Archivo: `filtered_specs_v2_enriched.csv`
- Registros: 20,209,277 filas

### Mapeo de Columnas

| Entrada | Salida | Descripción |
|---------|--------|-------------|
| `categorieID` | `categoryId` | ID de categoría |
| `Nombre Especificacion` | `specificationName` | Nombre del campo |
| `Especificacion` o `cantidad` | `specificationValue` | Valor del campo |
| `_ProductId` | `productId` | ID del producto |
| (fijo) | `groupName` | Siempre "Especificaciones" |
| (fijo) | `fieldTypeId` | Siempre 5 (Combo) |
| (fijo) | `isFilter` | Siempre "TRUE" |
| (fijo) | `isRequired` | Siempre "FALSE" |
| (fijo) | `isOnProductDetails` | Siempre "TRUE" |

## Formato de Salida

### 1. Archivo CSV Principal (salida.csv)

Formato listo para importación a VTEX.

**Estructura:**
```csv
categoryId,groupName,specificationName,specificationValue,productId,fieldTypeId,isFilter,isRequired,isOnProductDetails
10,Especificaciones,Color,Rojo,100,5,TRUE,FALSE,TRUE
20,Especificaciones,Talla,Talla M,200,5,TRUE,FALSE,TRUE
30,Especificaciones,Material,Madera,300,5,TRUE,FALSE,TRUE
```

**Columnas:**
- `categoryId`: ID de la categoría (desde `categorieID`)
- `groupName`: Nombre del grupo (siempre "Especificaciones")
- `specificationName`: Nombre de la especificación (desde `Nombre Especificacion`)
- `specificationValue`: Valor de la especificación (desde `Especificacion` o `cantidad`)
- `productId`: ID del producto (desde `_ProductId`)
- `fieldTypeId`: Tipo de campo (siempre 5 para Combo)
- `isFilter`: Es filtrable (siempre TRUE)
- `isRequired`: Es requerido (siempre FALSE)
- `isOnProductDetails`: Muestra en detalles del producto (siempre TRUE)

**Ejemplo real:**
- Archivo: `vtex_specifications.csv`
- Registros: 7,792,591 especificaciones transformadas

### 2. Archivo CSV de Inválidos (opcional)

Se genera si `--invalid` está especificado y hay registros sin especificación.

**Estructura:** Todas las columnas del archivo original

```csv
_SkuId,_ProductId,SKU,Categoria,Subcategoria,Linea,Nombre Especificacion,Especificacion,cantidad,...
```

**Ubicación:** Directorio especificado en `--invalid`

## Cómo Funciona

### Fase 1: Carga del CSV
1. Lee archivo de entrada
2. Valida formato CSV
3. Carga todas las filas en memoria

### Fase 2: Transformación por Fila
Para cada fila:
1. Extrae `Nombre Especificacion` y `Especificacion`
2. Aplica lógica:
   - Si son iguales: usa `cantidad` como valor
   - Si diferentes: usa `Especificacion` como valor
3. Crea diccionario con campos mapeados
4. Agrega valores fijos (groupName, fieldTypeId, etc.)

### Fase 3: Exportación
1. Escribe CSV de salida con headers de VTEX
2. Si hay inválidos y `--invalid` especificado:
   - Escribe archivo separado con registros problemáticos
3. Imprime estadísticas

## Lógica de Especificación

**Ejemplo 1: Valores diferentes**
```
Nombre Especificacion = "Color"
Especificacion = "Rojo"
cantidad = "1"

→ specificationValue = "Rojo"  (usa Especificacion)
```

**Ejemplo 2: Valores iguales**
```
Nombre Especificacion = "Talla"
Especificacion = "Talla"
cantidad = "M"

→ specificationValue = "M"  (usa cantidad como fallback)
```

**Ejemplo 3: Especificacion vacía**
```
Nombre Especificacion = "Material"
Especificacion = ""
cantidad = "Madera"

→ specificationValue = "Madera"  (usa cantidad)
```

## Argumentos CLI

```
csv_to_vtex_specifications.py [-h] [-i INVALID_CSV]
                              input_csv
                              output_csv

Positional Arguments:
  input_csv           CSV de entrada con datos de productos
  output_csv          CSV de salida con formato VTEX

Optional Arguments:
  -h, --help          Muestra mensaje de ayuda
  -i, --invalid INVALID_CSV  CSV de salida para filas inválidas
```

## Ejemplos

### Ejemplo 1: Transformación Básica

```bash
python3 csv_to_vtex_specifications.py datos.csv especificaciones.csv

# Genera:
# - especificaciones.csv (todos los registros transformados)
```

### Ejemplo 2: Con Validación de Inválidos

```bash
python3 csv_to_vtex_specifications.py datos.csv especificaciones.csv \
    --invalid especificaciones_invalid.csv

# Genera:
# - especificaciones.csv (solo registros válidos)
# - especificaciones_invalid.csv (registros sin especificación)
```

### Ejemplo 3: Subdirectorio de Salida

```bash
python3 csv_to_vtex_specifications.py datos.csv output/especificaciones.csv \
    --invalid output/especificaciones_invalid.csv

# Crea directorio 'output' si no existe
# Genera archivos en 'output/'
```

## Estadísticas Típicas

Para 20M registros de entrada:

```
======================================================================
CSV to VTEX Specifications Transformer
======================================================================

📁 Archivo de entrada:   filtered_specs_v2_enriched.csv
📁 Archivo de salida:    vtex_specifications.csv
📁 Archivo inválidos:    vtex_specifications_invalid.csv

======================================================================
📋 Resumen
======================================================================
   Filas leídas:      20,209,277
   Filas exportadas:  20,207,000
   Filas inválidas:   2,277
======================================================================
✓ Archivo generado: vtex_specifications.csv
✓ Inválidos exportados: vtex_specifications_invalid.csv
```

## Casos de Uso

### 1. Preparar para Importación a VTEX

```bash
# Transformar y guardar con validación
python3 csv_to_vtex_specifications.py datos_limpios.csv para_vtex.csv --invalid fallos.csv

# Revisar fallos antes de importar
head fallos.csv
```

### 2. Procesar por Lotes

```bash
# Lote 1
python3 csv_to_vtex_specifications.py lote1.csv lote1_vtex.csv

# Lote 2
python3 csv_to_vtex_specifications.py lote2.csv lote2_vtex.csv

# Combinar resultados
cat lote1_vtex.csv lote2_vtex.csv > todo_vtex.csv
```

### 3. Validación de Calidad

```bash
# Transformar con separación de inválidos
python3 csv_to_vtex_specifications.py entrada.csv salida.csv --invalid recheck.csv

# Revisar qué registros fallan
wc -l recheck.csv  # ¿Cuántos?

# Revisar columna especificación
cut -d, -f8 recheck.csv | sort | uniq -c
```

## Performance

- **Velocidad**: ~100K registros/segundo
- **Memoria**: ~1GB para 20M registros
- **Duración**: 20M registros: ~3 minutos

**Ejemplo:**
```bash
time python3 csv_to_vtex_specifications.py datos.csv salida.csv
# real    3m15s
# user    2m50s
# sys     0m25s
```

## Troubleshooting

### Error: "Archivo 'entrada.csv' no encontrado"
Verifique que el archivo existe y la ruta es correcta

### Pocas filas en salida
- Revise archivo de inválidos con `--invalid`
- Muchos registros pueden no tener especificaciones

### Columnas faltantes en entrada
- Verifique que tiene: `Nombre Especificacion`, `Especificacion`, `cantidad`, `categorieID`
- Use `head entrada.csv` para ver estructura

### Valores incorrectos en salida
- Revise lógica: si Especificacion == Nombre Especificacion, usa cantidad
- Verifique datos de origen

### Archivo muy grande tarda
- Python puede procesar 20M+ registros
- Considere dividir si excede memoria disponible

## Notas

- **fieldTypeId fijo:** Siempre se establece en 5 (Combo)
- **groupName fijo:** Siempre "Especificaciones"
- **Flags fijos:** isFilter=TRUE, isRequired=FALSE, isOnProductDetails=TRUE
- **Orden preservado:** Se mantiene el orden de entrada
- **Encoding:** UTF-8 tanto entrada como salida
- **Directorios:** Se crean automáticamente si no existen

## Valores Predefinidos

El script siempre genera:

```
groupName = "Especificaciones"
fieldTypeId = 5 (Combo)
isFilter = "TRUE"
isRequired = "FALSE"
isOnProductDetails = "TRUE"
```

Si necesita valores diferentes, edite líneas 49-52 en el script.

## Paso Siguiente

Después de generar `vtex_specifications.csv`, típicamente:

1. **Importar a VTEX** mediante API o admin
2. **Asignar a productos** con script `38_add_product_specifications`
3. **Validar en VTEX** que aparecen en productos

## Scripts Relacionados

- **37_category_specification_matcher**: Prepara datos para este script
- **38_add_product_specifications**: Asigna especificaciones a productos en VTEX
- **39_csv_sku_matcher**: Enriquece datos antes de transformación
