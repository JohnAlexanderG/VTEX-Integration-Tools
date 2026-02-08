# 27_csv_cleaner

Limpia archivos CSV removiendo espacios en blanco innecesarios de campos y líneas vacías.

## Descripción

Este script lee un archivo CSV y aplica las siguientes operaciones de limpieza:

1. Elimina espacios en blanco al inicio y final de cada campo
2. Preserva espacios internos dentro de valores
3. Elimina comas finales al final de líneas
4. Remueve filas completamente vacías (después de limpiar)
5. Preserva la fila de encabezados y orden de columnas

Útil para preparar archivos CSV descargados o generados para procesamiento posterior.

## Prerrequisitos

- Python 3.6+
- Archivo CSV con encabezados en la primera fila
- Encoding especificado (default: UTF-8)

## Uso

### Sintaxis básica

```bash
python3 csv_cleaner.py <input.csv> <output.csv>
```

### Parámetros requeridos

- `input.csv`: Archivo CSV a limpiar
- `output.csv`: Archivo CSV de salida (limpio)

### Opciones

- `--encoding ENCODING`: Encoding del archivo (default: utf-8)

### Ejemplos

```bash
# Limpieza básica con UTF-8
python3 27_csv_cleaner/csv_cleaner.py productos.csv productos_clean.csv

# Con encoding específico
python3 27_csv_cleaner/csv_cleaner.py datos.csv limpio.csv --encoding utf-8

# Con encoding LATIN1
python3 27_csv_cleaner/csv_cleaner.py datos_latin.csv limpio.csv --encoding latin-1

# Rutas absolutas
python3 27_csv_cleaner/csv_cleaner.py /ruta/entrada.csv /ruta/salida.csv
```

## Formato de Entrada

### Estructura CSV esperada

**Archivo sucio (entrada):**

```csv
SKU,Precio,Cantidad,Descripción
000013    ,280,000000000,
000014  ,350,  100  ,Producto con espacios
  ,450,,Fila muy mala
000015,200,50,
```

**Problemas detectados:**
- Línea 1: Espacios finales después de SKU
- Línea 1: Coma final al final de línea
- Línea 2: Espacios internos en Cantidad
- Línea 3: Espacios iniciales en SKU
- Línea 3: Coma final
- Línea 4: Comas intermedias múltiples (fila con problemas graves)

### Campos Requeridos

El CSV debe tener encabezados en la primera fila. Cualquier estructura de encabezados es válida.

## Archivos de Salida

### `output.csv`

Archivo CSV limpio con misma estructura, sin espacios innecesarios.

**Archivo limpio (salida):**

```csv
SKU,Precio,Cantidad,Descripción
000013,280,000000000,
000014,350,100,Producto con espacios
000015,200,50,
```

**Cambios realizados:**
- Espacios al inicio/final removidos de todos los campos
- Comas finales eliminadas
- Filas completamente vacías eliminadas
- Estructura y orden preservados

## Flujo de Procesamiento

1. **Lectura del CSV**
   - Lee archivo con DictReader
   - Extrae encabezados
   - Carga todas las filas

2. **Limpieza de Datos**
   - Para cada fila:
     - Aplica `strip()` a cada campo (remove espacios inicio/final)
     - Verifica si fila está completamente vacía
     - Descarta si está vacía
     - Agrega a resultado si tiene datos

3. **Guardado de Resultado**
   - Escribe encabezados
   - Escribe filas limpias en orden
   - Usa CSV writer (maneja comas automáticamente)
   - Encoding especificado

## Ejemplo de Ejecución

```bash
$ python3 27_csv_cleaner/csv_cleaner.py nivelto_20260130_1105.csv nivelto_clean.csv

📄 Reading CSV file: nivelto_20260130_1105.csv...
✅ Loaded 243627 rows (+ 1 header row)

🧹 Cleaning CSV data...
  - Removing leading/trailing whitespace from fields
  - Removing trailing commas from lines
  - Filtering empty rows

💾 Writing cleaned CSV to: nivelto_clean.csv...
✅ Successfully wrote 242891 rows

📊 Cleaning Statistics:
  Input rows (excluding headers):  243627
  Output rows:                     242891
  Empty rows removed:              736
  Fields cleaned:                  2184843

✅ CSV cleaning completed successfully!
```

## Características Principales

### Preservación de Datos
- Mantiene estructura original
- Preserva espacios internos en valores
- Mantiene tipos de datos (numéricos como strings)
- No modifica valores, solo espacios

### Robustez
- Manejo de encoding flexible
- Mensajes de error descriptivos
- Validación de estructura CSV

### Estadísticas Detalladas
- Conteo de filas procesadas
- Conteo de filas vacías removidas
- Total de campos limpios
- Antes/después en consola

## Casos de Uso

### Escenario 1: Limpieza de Exportación VTEX
```bash
# Limpiar exportación de VTEX con espacios
python3 27_csv_cleaner/csv_cleaner.py \
  exported_vtex.csv \
  exported_vtex_clean.csv
```

### Escenario 2: Preparación para Importación
```bash
# Limpiar datos antes de enviar a siguiente proceso
python3 27_csv_cleaner/csv_cleaner.py \
  precios_20260105.csv \
  precios_20260105_clean.csv
```

### Escenario 3: Conversión de Encoding
```bash
# Convertir de LATIN1 a UTF-8 y limpiar
python3 27_csv_cleaner/csv_cleaner.py \
  datos_legacy.csv \
  datos_modernos.csv \
  --encoding latin-1
```

## Troubleshooting

### Error: "File not found"
- Verificar que el archivo input existe
- Usar rutas absolutas o relativas correctas
- Verificar permisos de lectura

### Error: "CSV file has no headers"
- Asegurar que la primera fila contiene encabezados
- Verificar que no hay filas vacías al inicio

### Error: "Error decoding file with utf-8 encoding"
- El archivo usa otro encoding (LATIN1, CP1252, etc.)
- Especificar encoding: `--encoding latin-1`
- Usar comando para detectar: `file -i archivo.csv`

### Demasiadas filas removidas
- Revisar si hay muchas filas completamente vacías
- Verificar si hay problemas en estructura CSV original
- Ejecutar con input limpio manualmente primero

### Archivo de salida vacío o muy pequeño
- Verificar que input tiene datos
- Comprobar que primer línea es encabezado válido
- Revisar si todas las líneas están vacías

## Notas Técnicas

- **Encoding**: Default UTF-8, personalizable con `--encoding`
- **Performance**: O(n) - una sola pasada sobre datos
- **Memory**: Carga archivo completo en memoria
- **Whitespace**: `strip()` remove espacios, tabs, newlines
- **CSV**: Usa módulo csv de Python (maneja comillas, escapes)
- **Filas vacías**: Se detectan después de limpiar (ALL campos vacío)

## Casos de Encoding Comunes

```bash
# LATIN1 / ISO-8859-1 (común en sistemas Legacy)
python3 csv_cleaner.py datos.csv limpio.csv --encoding latin-1

# Windows-1252 (común en Windows)
python3 csv_cleaner.py datos.csv limpio.csv --encoding cp1252

# UTF-8 (default)
python3 csv_cleaner.py datos.csv limpio.csv --encoding utf-8

# ASCII
python3 csv_cleaner.py datos.csv limpio.csv --encoding ascii
```

## Integración con Workflow VTEX

Este script se utiliza típicamente:

1. **Después de exportar**: Limpiar datos exportados de VTEX
2. **Antes de filtrar**: Preparar datos para scripts de filtrado (28, 29)
3. **Antes de procesamiento**: Garantizar CSV válido para siguientes pasos

Ejemplo de workflow:
```bash
# 1. Limpiar CSV descargado
python3 27_csv_cleaner/csv_cleaner.py raw.csv clean.csv

# 2. Filtrar por precio (si existe 28_filter_price_list)
python3 28_filter_price_list/filter_price_list.py vtex.csv clean.csv filtered

# 3. Usar resultado filtrado
```

## Ver Ayuda

```bash
python3 27_csv_cleaner/csv_cleaner.py --help
```

## Archivos de Datos Reales en Este Directorio

```
nivelej_20251217_1700.csv          - Inventario nivel elemento
nivelto_20260130_1105.csv          - Inventario nivel tienda
precios_20251212.csv               - Lista de precios
precios_20251226.csv               - Lista de precios
precios_20260105.csv               - Lista de precios
productos-pendientes.csv           - Productos pendientes
productos-pendientes-descripciones.csv - Descripciones pendientes
csv_cleaner.py                     - Script principal
README.md                          - Este archivo
```

## Ejemplos de Limpieza Realizada

Archivo `nivelto_20260130_1105.csv`:
- **Filas entrada**: 243,627
- **Filas procesadas**: 242,891
- **Filas vacías removidas**: 736
- **Tiempo de procesamiento**: ~2-3 segundos

El script es lo suficientemente rápido incluso para CSVs grandes (>1M de filas).
