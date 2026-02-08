# 02_data-transform

## Descripción

Script de transformación JSON que procesa y normaliza estructuras de datos complejas. Divide claves compuestas (con formato "Campo1, Campo2, Campo3") en campos individuales y normalizados. Este es el segundo paso en el flujo de transformación de datos VTEX.

La herramienta es particularmente útil para procesar datos de productos que tienen múltiples valores en un solo campo separados por comas.

## Requisitos Previos

### Dependencias de Python
```bash
pip install
```
(Solo requiere módulos estándar: json, argparse, re)

### Dependencias del Sistema
- Python 3.6+

## Uso

**Transformación básica:**
```bash
python3 02_data-transform/transform_json_script.py entrada.json salida.json
```

**Transformación con indentación personalizada:**
```bash
python3 02_data-transform/transform_json_script.py entrada.json salida.json --indent 2
```

**Argumentos:**
- `input`: Ruta al archivo JSON de entrada
- `output`: Ruta al archivo JSON de salida
- `-i, --indent`: Número de espacios para indentación (opcional, por defecto: 4)

## Formato de Entrada

### Estructura JSON de Entrada
Array de objetos JSON donde algunos campos tienen claves compuestas (separadas por comas):

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "Lista de Precios 1, Lista de Precios 2": "100.00, 120.00",
        "stock": "50"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "Categoría Principal, Categoría Secundaria": "Electrónica, Accesorios",
        "stock": "30"
    }
]
```

## Formato de Salida

### Estructura JSON de Salida
Objetos transformados con claves normalizadas y valores separados:

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "Lista_de_Precios_1": "100.00",
        "Lista_de_Precios_2": "120.00",
        "stock": "50"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "Categora_Principal": "Electrónica",
        "Categora_Secundaria": "Accesorios",
        "stock": "30"
    }
]
```

## Cómo Funciona

### Transformación por Pasos

1. **Lectura del JSON**: Carga el archivo de entrada (soporta objeto único o array de objetos)

2. **Normalización de Claves Compuestas**:
   - Detecta claves que contienen comas (`,`)
   - Separa cada clave en sus componentes individuales
   - Normaliza cada componente:
     - Elimina espacios al inicio y final
     - Reemplaza espacios y guiones por guiones bajos (`_`)
     - Elimina caracteres especiales (no alfanuméricos ni guiones bajos)

3. **Asignación de Valores**:
   - Separa los valores de la clave compuesta por comas
   - Empareja cada clave normalizada con su valor correspondiente por posición
   - Preserva whitespace en los valores

4. **Preservación de Claves Simples**:
   - Las claves sin comas se mantienen sin cambios
   - Solo se transforman claves que contengan separadores de coma

### Ejemplos de Normalización

| Campo Original | Campo Transformado | Ejemplo de Valor |
|---|---|---|
| `Lista de Precios 1, Lista de Precios 2` | `Lista_de_Precios_1`, `Lista_de_Precios_2` | "100.00" → "100.00", "120.00" → "120.00" |
| `Categoría Principal, Categoría Secundaria` | `Categora_Principal`, `Categora_Secundaria` | "Electrónica, Accesorios" → "Electrónica", "Accesorios" |
| `Detalles (1), Detalles (2)` | `Detalles_1`, `Detalles_2` | "Detalle 1, Detalle 2" → "Detalle 1", "Detalle 2" |
| `campo_simple` | `campo_simple` | Sin cambios | Sin cambios |

## Archivos de Ejemplo

**Entrada:**
- `data.json` (64 MB) - Datos sin transformar con claves compuestas
- `productos-pendientes.json` (35 KB) - Productos pendientes de procesamiento

**Salida:**
- `data_transform.json` (65 MB) - Datos transformados con claves normalizadas
- `productos-pendientes-output.json` (35 KB) - Productos pendientes procesados

## Notas y Consideraciones

- **Codificación**: Preserva UTF-8 para caracteres especiales españoles
- **Acentos Eliminados**: La normalización elimina acentos y caracteres especiales de los nombres de campo
- **Coincidencia de Valores**: La cantidad de valores debe coincidir con la cantidad de claves en la clave compuesta
- **Campos Vacíos**: Si un valor está vacío, se omite durante la separación
- **Indentación**: El parámetro `--indent` controla la legibilidad del JSON de salida
- **Tipos de Datos**: El script trata todos los valores como strings; no realiza conversión de tipos
- **Objetos Anidados**: Solo procesa el primer nivel de claves; no transforma objetos anidados
