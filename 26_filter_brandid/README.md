# 26_filter_brandid

Filtra datos de productos en JSON para incluir solamente registros con un BrandId específico (2000000).

## Descripción

Este script lee un archivo JSON con datos de productos y selecciona únicamente aquellos registros que tienen `BrandId = 2000000`. Útil para:

- Filtrar productos por marca específica
- Extraer un subconjunto de un catálogo grande
- Preparar datos para un proceso específico que requiere una marca

## Prerrequisitos

- Python 3.6+
- Archivo JSON con estructura de lista o diccionario
- Campo `BrandId` presente en los registros (debe ser numérico)

## Uso

### Sintaxis básica

```bash
python3 filter_brandid.py <input.json> <output.json>
```

### Parámetros requeridos

- `input.json`: Archivo JSON con datos de productos
- `output.json`: Archivo JSON de salida (filtrado)

### Opciones

- `--indent N`: Nivel de indentación JSON (default: 4)

### Ejemplos

```bash
# Filtrado básico
python3 26_filter_brandid/filter_brandid.py productos.json filtered.json

# Con indentación personalizada
python3 26_filter_brandid/filter_brandid.py datos.json resultado.json --indent 2

# Con rutas absolutas
python3 26_filter_brandid/filter_brandid.py /ruta/productos.json /ruta/resultado.json
```

## Formato de Entrada

### Estructura JSON esperada

**Opción 1: Lista de registros**

```json
[
  {
    "RefId": "SKU001",
    "BrandId": 2000000,
    "ProductName": "Producto A",
    "Price": 99.99
  },
  {
    "RefId": "SKU002",
    "BrandId": 1500000,
    "ProductName": "Producto B",
    "Price": 149.99
  },
  {
    "RefId": "SKU003",
    "BrandId": 2000000,
    "ProductName": "Producto C",
    "Price": 79.99
  }
]
```

**Opción 2: Diccionario con claves RefId**

```json
{
  "SKU001": {
    "BrandId": 2000000,
    "ProductName": "Producto A",
    "Price": 99.99
  },
  "SKU002": {
    "BrandId": 1500000,
    "ProductName": "Producto B",
    "Price": 149.99
  },
  "SKU003": {
    "BrandId": 2000000,
    "ProductName": "Producto C",
    "Price": 79.99
  }
}
```

### Campos Requeridos

- `BrandId`: Campo numérico que contiene el ID de la marca

### Campos Opcionales

Cualquier otro campo se preserva en la salida si el registro cumple el filtro.

## Archivos de Salida

### `output.json`

Archivo JSON con la misma estructura que input, pero solo con registros donde `BrandId = 2000000`.

**Ejemplo (desde lista):**

```json
[
  {
    "RefId": "SKU001",
    "BrandId": 2000000,
    "ProductName": "Producto A",
    "Price": 99.99
  },
  {
    "RefId": "SKU003",
    "BrandId": 2000000,
    "ProductName": "Producto C",
    "Price": 79.99
  }
]
```

**Ejemplo (desde diccionario):**

```json
{
  "SKU001": {
    "BrandId": 2000000,
    "ProductName": "Producto A",
    "Price": 99.99
  },
  "SKU003": {
    "BrandId": 2000000,
    "ProductName": "Producto C",
    "Price": 79.99
  }
}
```

## Flujo de Procesamiento

1. **Carga del archivo JSON**
   - Lee archivo input
   - Detecta si es lista o diccionario
   - Valida estructura

2. **Filtrado por BrandId**
   - Itera todos los registros
   - Compara `BrandId` con valor 2000000
   - Preserva estructura (lista o diccionario)

3. **Cálculo de estadísticas**
   - Cuenta registros totales
   - Cuenta registros que pasan filtro
   - Calcula porcentajes

4. **Guardado del resultado**
   - Escribe archivo JSON de salida
   - Usa indentación especificada
   - Encoding UTF-8

## Ejemplo de Ejecución

```bash
$ python3 26_filter_brandid/filter_brandid.py data.json result.json

📄 Reading input file: data.json...
✅ Successfully loaded 23507407 records

🔍 Filtering records with BrandId = 2000000...
✅ Found 2330188 matching records (9.9% of total)

💾 Saving filtered data to result.json...
✅ Successfully saved 2330188 records

📊 Filtering Statistics:
  Input records:    23507407
  Output records:   2330188 (9.9%)
  Filtered out:     21177219 (90.1%)

✅ Filtering completed successfully!
```

## Características Principales

### Flexibilidad de Formato
- Soporta lista JSON o diccionario
- Preserva estructura original en salida
- Mantiene todos los campos de cada registro

### Manejo Robusto de Errores
- Validación de archivo JSON
- Validación de estructura (lista o diccionario)
- Mensajes de error descriptivos

### Estadísticas Claras
- Muestra conteo de entrada/salida
- Calcula porcentajes de filtrado
- Resumen en consola

## Casos de Uso

### Escenario 1: Extracción de una Marca Específica
```bash
# Extraer todos los productos de la marca 2000000 de catálogo general
python3 26_filter_brandid/filter_brandid.py \
  productos_completo.json \
  productos_marca_2000000.json
```

### Escenario 2: Procesamiento Filtrado
```bash
# Preparar datos para proceso específico
python3 26_filter_brandid/filter_brandid.py \
  data.json \
  filtered.json \
  --indent 2
```

### Escenario 3: Validación y Limpieza
```bash
# Verificar cuántos productos pertenecen a marca 2000000
python3 26_filter_brandid/filter_brandid.py \
  all_products.json \
  brand_2000000_only.json
# Revisar resultado en consola para estadísticas
```

## Troubleshooting

### Error: "JSON must be a list or dict"
- Verificar que el archivo JSON es válido
- La raíz del JSON debe ser un array `[]` o un objeto `{}`
- No se soportan JSON primitivos (números, strings solos)

### Error: "File not found"
- Verificar ruta del archivo input
- Usar rutas absolutas o relativas correctas
- Verificar permisos de lectura

### Error: "Error parsing JSON file"
- Validar JSON con: `python3 -m json.tool archivo.json`
- Verificar que el archivo está en UTF-8
- Buscar caracteres inválidos o mal formados

### 0% de registros con BrandId = 2000000
- Verificar que existe el campo `BrandId` en los datos
- Revisar el nombre exacto del campo (case-sensitive)
- Comprobar que algún registro tiene `BrandId = 2000000`
- Usar `python3 -m json.tool` para inspeccionar estructura

### Archivo de salida muy pequeño o vacío
- Verificar valor exacto de `BrandId` en datos
- Comprobar si todos los registros tienen este campo
- Revisar si el filtro es correcto (BrandId = 2000000)

## Notas Técnicas

- **Encoding**: UTF-8 obligatorio
- **Performance**: O(n) - iteración simple sobre todos los registros
- **Memory**: Carga archivo completo en memoria
- **BrandId**: Comparación exacta como número (no string)
- **Estructura**: Preserva formato original (lista o diccionario)
- **Indentación**: Default 4 espacios, personalizable

## Integración con Workflow VTEX

Este script puede usarse en varios puntos:

1. **Después de importación**: Filtrar marca específica de import
2. **Preparación de datos**: Extraer subset para procesamiento
3. **Auditoría**: Verificar distribución de productos por marca

## Ver Ayuda

```bash
python3 26_filter_brandid/filter_brandid.py --help
```

## Archivos de Datos Reales en Este Directorio

```
data.json          - Archivo JSON de entrada con múltiples marcas
result.json        - Archivo JSON filtrado (generado)
filter_brandid.py  - Script principal
README.md          - Este archivo
```

## Ejemplos de Datos Reales

El directorio contiene `data.json` con 23.5 millones de registros de productos. Después de ejecutar el filtro se genera `result.json` con 2.33 millones de registros que pertenecen a `BrandId = 2000000`.

**Tiempo de ejecución esperado**: 10-20 segundos para 23+ millones de registros
