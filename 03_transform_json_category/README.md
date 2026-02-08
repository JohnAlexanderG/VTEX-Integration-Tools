# 03_transform_json_category

## Descripción

Script especializado para transformar estructura de categorías desde campos separados a formato jerárquico. Une los campos `CATEGORIA`, `SUBCATEGORIA` y `LINEA` en un campo único con jerarquía clara separada por `>`.

La herramienta detecta automáticamente categorías problemáticas (aquellas que contienen `/` en la subcategoría o línea) y las exporta a archivos JSON y CSV para revisión manual.

## Requisitos Previos

### Dependencias de Python
```bash
pip install
```
(Solo requiere módulos estándar: json, csv, argparse)

### Dependencias del Sistema
- Python 3.6+

## Uso

**Transformación básica:**
```bash
python3 03_transform_json_category/transform_json_category.py entrada.json salida.json
```

**Transformación con indentación personalizada:**
```bash
python3 03_transform_json_category/transform_json_category.py entrada.json salida.json --indent 2
```

**Exportación personalizada de elementos problemáticos a CSV:**
```bash
python3 03_transform_json_category/transform_json_category.py entrada.json salida.json --csv-export categorias_problematicas.csv
```

**Argumentos:**
- `input`: Ruta al archivo JSON de entrada
- `output`: Ruta al archivo JSON de salida
- `-i, --indent`: Número de espacios para indentación (opcional, por defecto: 4)
- `--csv-export`: Ruta al archivo CSV para elementos problemáticos (opcional, genera automáticamente si se omite)

## Formato de Entrada

### Estructura JSON de Entrada
Array de objetos con campos de categoría separados:

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "CATEGORIA": "Cuidado Personal",
        "SUBCATEGORIA": "Cuidado del Pelo",
        "LINEA": "Secadores",
        "precio": "50.00"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "CATEGORIA": "Electrónica",
        "SUBCATEGORIA": "Accesorios/Periféricos",
        "LINEA": "",
        "precio": "30.00"
    }
]
```

## Formato de Salida

### Archivo JSON Principal (salida.json)
Estructura transformada con jerarquía unificada:

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "CATEGORIA": "Cuidado Personal>Cuidado del Pelo>Secadores",
        "precio": "50.00"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "CATEGORIA": "Electrónica>Accesorios/Periféricos",
        "precio": "30.00"
    }
]
```

### Archivo JSON de Problemáticos (salida_problematicos.json)
Contiene registros completos donde SUBCATEGORIA o LINEA contienen `/`:

```json
[
    {
        "id": "002",
        "nombre": "Producto B",
        "CATEGORIA": "Electrónica",
        "SUBCATEGORIA": "Accesorios/Periféricos",
        "LINEA": "",
        "precio": "30.00"
    }
]
```

### Archivo CSV de Problemáticos (salida_problematicos.csv)
Versión deduplicada en CSV de los elementos problemáticos para revisión manual:

```csv
id,nombre,CATEGORIA,SUBCATEGORIA,LINEA,precio
002,Producto B,Electrónica,Accesorios/Periféricos,,30.00
```

## Cómo Funciona

### Transformación por Pasos

1. **Lectura del JSON**: Carga el archivo de entrada (soporta objeto único o array de objetos)

2. **Procesamiento de Cada Registro**:
   - Extrae valores de campos `CATEGORIA`, `SUBCATEGORIA` y `LINEA`
   - Detecta si SUBCATEGORIA o LINEA contienen el carácter `/`
   - Si contienen `/`, marca el registro como problemático

3. **Unificación de Jerarquía**:
   - Une campos no vacíos con separador `>`
   - Ejemplo: `"Cuidado Personal" + "Cuidado del Pelo" + "Secadores"` → `"Cuidado Personal>Cuidado del Pelo>Secadores"`
   - Si un campo está vacío, se omite de la jerarquía

4. **Eliminación de Campos Originales**:
   - Elimina los campos `CATEGORIA`, `SUBCATEGORIA` y `LINEA`
   - Crea nuevo campo `CATEGORIA` con la jerarquía unificada
   - Preserva todos los demás campos del registro original

5. **Exportación de Problemáticos**:
   - Registros con `/` se exportan a JSON con sufijo `_problematicos.json`
   - Se deduplicnan en versión CSV con sufijo `_problematicos.csv`
   - Úsalos para revisión manual antes de procesamiento posterior

### Ejemplos de Transformación

| Entrada | Salida |
|---|---|
| CATEGORIA: "Cuidado Personal", SUBCATEGORIA: "Cuidado del Pelo", LINEA: "Secadores" | "Cuidado Personal>Cuidado del Pelo>Secadores" |
| CATEGORIA: "Electrónica", SUBCATEGORIA: "Accesorios", LINEA: "" | "Electrónica>Accesorios" |
| CATEGORIA: "Hogar", SUBCATEGORIA: "", LINEA: "" | "Hogar" |
| CATEGORIA: "Moda", SUBCATEGORIA: "Ropa/Accesorios", LINEA: "Camisetas" | "Moda>Ropa/Accesorios>Camisetas" (Problemático) |

## Archivos de Ejemplo

**Entrada:**
- `2025.11.21_CATEGORIAS.json` (9.2 MB)

**Salida:**
- `2025.11.21_CATEGORIAS-recategorizacion.json` (8.2 MB) - Datos transformados
- `2025.11.21_CATEGORIAS-recategorizacion_problematicos.json` - Elementos problemáticos (si existen)
- `2025.11.21_CATEGORIAS-recategorizacion_problematicos.csv` - CSV de problemáticos (si existen)

## Notas y Consideraciones

- **Codificación**: Preserva UTF-8 para caracteres especiales españoles
- **Campos Vacíos**: Se omiten automáticamente de la jerarquía, no generan `>>` dobles
- **Detectores de Problemas**: Solo el carácter `/` en SUBCATEGORIA o LINEA marca como problemático
- **Deduplicación CSV**: La exportación CSV elimina duplicados basados en campos problemáticos
- **Archivo de Revisión**: Verifica `_problematicos.csv` antes de usar datos en producción
- **Indentación**: Controla la legibilidad del JSON de salida
- **Preservación**: Todos los campos adicionales del registro original se mantienen intactos
