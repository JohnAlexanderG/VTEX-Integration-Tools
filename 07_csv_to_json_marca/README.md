# 07_csv_to_json_marca

## Descripción

Script especializado para extraer información de marcas desde archivos CSV de opciones de productos. Procesa archivos de configuración donde las marcas se identifican por un tipo específico, extrae el mapeo SKU→Marca y genera un archivo JSON estructurado.

La herramienta es el primer paso para preparar datos de marcas que serán utilizados posteriormente por el script `08_vtex_brandid_matcher` para asignar IDs de marca de VTEX.

## Requisitos Previos

### Dependencias de Python
```bash
pip install
```
(Solo requiere módulos estándar: csv, json, argparse)

### Dependencias del Sistema
- Python 3.6+

## Uso

**Extracción básica de marcas:**
```bash
python3 07_csv_to_json_marca/csv_to_json_marca.py entrada.csv marcas.json
```

**Ejemplo con archivo real:**
```bash
python3 07_csv_to_json_marca/csv_to_json_marca.py opciones_productos.csv marcas.json
```

**Argumentos posicionales (requeridos):**
- Primer argumento: Ruta al archivo CSV de entrada
- Segundo argumento: Ruta al archivo JSON de salida

## Formato de Entrada

### CSV de Opciones (entrada.csv)
Archivo con estructura de opciones de productos donde las marcas se identifican por TIPO='MARCA':

```csv
SKU,TIPO,OPCIONES
176391,MARCA,ILUMAX
176391,COLOR,Blanco
176391,TAMAÑO,Grande
176392,MARCA,SAMSUNG
176392,COLOR,Negro
176392,TAMAÑO,Mediano
176393,MARCA,LG
176393,VOLTAJE,110V
```

**Campos requeridos:**
- `SKU`: Identificador único del producto
- `TIPO`: Tipo de opción (debe contener "MARCA" para registros a extraer)
- `OPCIONES`: Valor de la opción (contiene el nombre de la marca para TIPO='MARCA')

## Formato de Salida

### JSON de Marcas (marcas.json)
Array de objetos con mapeo SKU→Marca:

```json
[
    {
        "SKU": "176391",
        "Marca": "ILUMAX"
    },
    {
        "SKU": "176392",
        "Marca": "SAMSUNG"
    },
    {
        "SKU": "176393",
        "Marca": "LG"
    }
]
```

**Estructura:**
- Array de objetos JSON
- Cada objeto tiene exactamente dos campos:
  - `SKU`: Identificador del producto (string)
  - `Marca`: Nombre de la marca (string)
- Indentación de 4 espacios para legibilidad
- Codificación UTF-8

## Cómo Funciona

### Lógica de Extracción

1. **Lectura del CSV**:
   - Abre archivo con codificación UTF-8
   - Usa `csv.DictReader` para leer con encabezados
   - Itera línea por línea

2. **Filtrado de Marcas**:
   - Para cada fila, extrae el campo `TIPO`
   - Convierte a minúsculas para comparación case-insensitive
   - Verifica si el tipo es exactamente `"marca"`
   - Si coincide, procesa el registro

3. **Extracción de Datos**:
   - Para filas con TIPO='MARCA':
     - Extrae `SKU` (identificador único)
     - Extrae `OPCIONES` (nombre de la marca)
     - Aplica `.strip()` para eliminar espacios

4. **Construcción de Objetos**:
   - Crea diccionario con:
     - Clave `SKU`: valor del campo SKU
     - Clave `Marca`: valor del campo OPCIONES
   - Agrega a lista de resultados

5. **Escritura a JSON**:
   - Crea archivo JSON con codificación UTF-8
   - Usa `json.dump()` con `ensure_ascii=False` para preservar caracteres especiales
   - Aplica indentación de 4 espacios

### Ejemplo Paso a Paso

```
CSV de entrada:
┌─────────┬──────┬──────────┐
│ SKU     │ TIPO │ OPCIONES │
├─────────┼──────┼──────────┤
│ 176391  │ MARCA│ ILUMAX   │ ← Se incluye
│ 176391  │ COLOR│ Blanco   │ ← Se ignora (TIPO ≠ MARCA)
│ 176392  │ MARCA│ SAMSUNG  │ ← Se incluye
└─────────┴──────┴──────────┘

JSON de salida:
[
    {
        "SKU": "176391",
        "Marca": "ILUMAX"
    },
    {
        "SKU": "176392",
        "Marca": "SAMSUNG"
    }
]
```

## Archivos de Ejemplo

**Entrada:**
- `marcas.csv` (5.5 MB) - Archivo de opciones con marcas

**Salida:**
- `marcas.json` (1.8 MB) - Mapeo SKU→Marca extraído

## Notas y Consideraciones

- **Codificación**: Preserva UTF-8 para caracteres especiales españoles
- **Case-Insensitive**: La comparación de TIPO es case-insensitive (`"marca"`, `"MARCA"`, `"Marca"` son equivalentes)
- **Espacios**: Se eliminan espacios al inicio y final (`.strip()`)
- **Filtrado Selectivo**: Solo extrae registros con TIPO='MARCA', ignora otros tipos (COLOR, TAMAÑO, etc.)
- **Duplicados**: No elimina duplicados SKU; si existen múltiples TIPO='MARCA' para el mismo SKU, ambos se incluyen
- **Campos Requeridos**: Si faltan campos SKU, TIPO u OPCIONES, el script puede fallar
- **Orden**: El orden en JSON mantiene el orden del CSV de origen
- **Sin Validación**: No valida que SKU sean únicos ni que marcas sean válidas
- **Próximo Paso**: La salida se usa típicamente con `08_vtex_brandid_matcher` para obtener IDs de marca VTEX

## Casos de Uso

1. **Mapeo de Marcas**: Crear correspondencia entre productos y sus marcas
2. **Unificación**: Combinar con otros datos de productos para enriquecimiento
3. **Validación**: Identificar productos sin marca asignada
4. **Integración VTEX**: Preparar datos para asignación de BrandId en VTEX
