# 05_compare_json_to_csv

## Descripción

Script de comparación que identifica registros faltantes entre dos archivos JSON. Compara datos antiguos con datos nuevos buscando diferencias por identificador (SKU en datos antiguos vs RefId en datos nuevos).

La herramienta genera un archivo CSV con todos los registros que existen en los datos antiguos pero no tienen equivalente en los datos nuevos, facilitando la identificación de productos descontinuados o no procesados.

## Requisitos Previos

### Dependencias de Python
```bash
pip install
```
(Solo requiere módulos estándar: json, csv, argparse)

### Dependencias del Sistema
- Python 3.6+

## Uso

**Comparación básica:**
```bash
python3 05_compare_json_to_csv/compare_json_to_csv.py datos_antiguos.json datos_nuevos.json faltantes.csv
```

**Ejemplo con archivos reales:**
```bash
python3 05_compare_json_to_csv/compare_json_to_csv.py data_transform.json data_unificada.json data_no_unificada_faltante.csv
```

**Argumentos posicionales (requeridos):**
- Primer argumento: Ruta al archivo JSON antiguo (con campo SKU)
- Segundo argumento: Ruta al archivo JSON nuevo (con campo RefId)
- Tercer argumento: Ruta al archivo CSV de salida con registros faltantes

## Formato de Entrada

### Archivo JSON Antiguo (datos_antiguos.json)
Array de productos con identificador SKU:

```json
[
    {
        "SKU": "176391",
        "nombre": "Producto A",
        "precio": "100.00",
        "categoria": "Electrónica"
    },
    {
        "SKU": "176392",
        "nombre": "Producto B",
        "precio": "80.00",
        "categoria": "Accesorios"
    },
    {
        "SKU": "176393",
        "nombre": "Producto C",
        "precio": "50.00",
        "categoria": "Periféricos"
    }
]
```

### Archivo JSON Nuevo (datos_nuevos.json)
Array de productos con identificador RefId. Solo contiene algunos de los productos antiguos:

```json
[
    {
        "RefId": "176391",
        "nombre": "Producto A",
        "estado": "activo"
    },
    {
        "RefId": "176392",
        "nombre": "Producto B",
        "estado": "activo"
    }
]
```

## Formato de Salida

### Archivo CSV (faltantes.csv)
Contiene todos los registros del archivo antiguo cuyo SKU no existe en los RefId del archivo nuevo:

```csv
SKU,nombre,precio,categoria
176393,Producto C,50.00,Periféricos
```

En este ejemplo, solo el producto con SKU "176393" aparece en el CSV porque existe en datos antiguos pero no en datos nuevos.

## Cómo Funciona

### Lógica de Comparación

1. **Carga de Archivos**:
   - Lee ambos archivos JSON (deben ser arrays de objetos)
   - Valida que sean listas válidas

2. **Extracción de Identificadores Nuevos**:
   - Crea un conjunto (set) con todos los valores `RefId` del archivo nuevo
   - Esto permite búsquedas muy rápidas O(1)

3. **Filtrado de Registros Faltantes**:
   - Itera sobre todos los registros del archivo antiguo
   - Para cada registro, verifica si su `SKU` existe en el conjunto de `RefId` nuevos
   - Si NO existe, lo incluye en la lista de faltantes

4. **Preservación de Columnas**:
   - Mantiene el orden exacto de columnas del primer registro antiguo
   - Asegura que los encabezados del CSV sean consistentes

5. **Exportación a CSV**:
   - Escribe todos los registros faltantes al archivo CSV
   - Usa codificación UTF-8
   - Crea encabezados basados en los campos del primer registro

### Pasos de Ejecución

```
Datos Antiguos     Datos Nuevos
├─ SKU: 176391     ├─ RefId: 176391 ✓ (existe)
├─ SKU: 176392     ├─ RefId: 176392 ✓ (existe)
├─ SKU: 176393     └─ (no existe)
└─ SKU: 176394     └─ (no existe)

Resultado CSV:
├─ 176393 (faltante)
└─ 176394 (faltante)
```

## Archivos de Ejemplo

**Entrada:**
- `data_transform.json` (64 MB) - Datos antiguos
- `data_unificada.json` (22 MB) - Datos nuevos ya procesados

**Salida:**
- `data_no_unificada_faltante.csv` (24 MB) - Registros no encontrados en datos nuevos

## Notas y Consideraciones

- **Codificación**: Preserva UTF-8 para caracteres especiales españoles
- **Orden de Columnas**: El CSV mantiene el orden exacto del primer registro antiguo
- **Comparación de Strings**: La comparación de SKU vs RefId es exacta, no tolera espacios adicionales
- **Validación**: Si el archivo antiguo está vacío, genera CSV sin datos (solo encabezados)
- **Rendimiento**: Usa sets para búsqueda O(1), eficiente incluso con millones de registros
- **Campos Requeridos**: El archivo antiguo DEBE tener campo `SKU`, el nuevo DEBE tener campo `RefId`
- **Arrays Únicos**: Solo procesa si ambos archivos son arrays JSON válidos
- **Sin Filtros**: Exporta TODOS los campos del registro antiguo, sin filtrado selectivo
