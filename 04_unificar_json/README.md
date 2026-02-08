# 04_unificar_json

## Descripción

Script de unificación que combina dos archivos JSON de diferentes fuentes, resolviendo conflictos y sincronizando datos. Realiza un merge inteligente basado en claves de identificación diferentes (SKU en datos antiguos, MECA en datos nuevos).

El resultado es un único dataset unificado que preserva información antigua, la actualiza con datos nuevos, y genera un reporte de registros que no pudieron unificarse para revisión manual.

## Requisitos Previos

### Dependencias de Python
```bash
pip install
```
(Solo requiere módulos estándar: json, sys, csv, pathlib)

### Dependencias del Sistema
- Python 3.6+

## Uso

**Unificación de dos archivos JSON:**
```bash
python3 04_unificar_json/unificar_json.py datos_antiguos.json datos_nuevos.json salida_unificada.json
```

**Ejemplo con nombres reales:**
```bash
python3 04_unificar_json/unificar_json.py PRODUCTOS_A_SUBIR_VTEX-final-transformed.json 2025.11.21_CATEGORIAS-recategorizacion.json PRODUCTOS_A_SUBIR_VTEX-final-transformed-join-with-recategorizacion.json
```

**Argumentos posicionales (requeridos):**
- Primer argumento: Ruta al archivo JSON antiguo (con campo SKU)
- Segundo argumento: Ruta al archivo JSON nuevo (con campo MECA)
- Tercer argumento: Ruta al archivo JSON de salida unificado

## Formato de Entrada

### Archivo JSON Antiguo (datos_antiguos.json)
Array de productos con identificador SKU:

```json
[
    {
        "SKU": "176391",
        "Descripción": "Descripción antigua del producto",
        "Precio": "100.00",
        "Categoría": "cuidado personal>cuidado del pelo",
        "Stock": "50"
    },
    {
        "SKU": "176392",
        "Descripción": "Otro producto antiguo",
        "Precio": "80.00",
        "Categoría": "electrónica>accesorios",
        "Stock": "30"
    }
]
```

### Archivo JSON Nuevo (datos_nuevos.json)
Array de productos con identificador MECA y información actualizada:

```json
[
    {
        "MECA": "176391",
        "DESCRIPCION": "DESCRIPCION NUEVA DEL PRODUCTO",
        "CATEGORIA": "cuidado personal>cuidado del pelo>secadores",
        "OTROS_DATOS": "valor"
    },
    {
        "MECA": "176393",
        "DESCRIPCION": "NUEVO PRODUCTO",
        "CATEGORIA": "electrónica>periféricos",
        "OTROS_DATOS": "otro valor"
    }
]
```

## Formato de Salida

### Archivo JSON Principal (salida_unificada.json)
Registros unificados con información sincronizada:

```json
[
    {
        "RefId": "176391",
        "Descripción": "Descripción antigua del producto",
        "Precio": "100.00",
        "Categoría": "Cuidado Personal>Cuidado Del Pelo",
        "Stock": "50",
        "Description": "Descripción Antigua Del Producto",
        "Name": "Descripcion Nueva Del Producto"
    },
    {
        "RefId": "176392",
        "Descripción": "Otro producto antiguo",
        "Precio": "80.00",
        "Categoría": "Electrónica>Accesorios",
        "Stock": "30",
        "Description": "Otro Producto Antiguo"
    },
    {
        "RefId": "176393",
        "Categoría": "Electrónica>Periféricos",
        "Name": "Nuevo Producto",
        "Description": ""
    }
]
```

### Archivo CSV de No Unificados (salida_unificada_no_unificados.csv)
Registros del archivo antiguo que no tienen equivalente en el nuevo:

```csv
SKU,Descripción,Precio,Categoría,Stock
176392,Otro producto antiguo,80.00,electrónica>accesorios,30
```

## Cómo Funciona

### Lógica de Unificación

**1. Registros Comunes (SKU existe en ambos archivos):**
- Renombra `SKU` → `RefId`
- Actualiza `Categoría` con formato Title Case desde `CATEGORIA` nuevo
  - "cuidado personal>cuidado del pelo" → "Cuidado Personal>Cuidado Del Pelo"
- Agrega campo `Name` desde `DESCRIPCION` del archivo nuevo (convertido de UPPERCASE a Title Case)
- Renombra `Descripción` → `Description` preservando valor antiguo
- Mantiene todos los demás campos del registro antiguo

**2. Registros Solo en Archivo Nuevo (MECA sin equivalente en SKU):**
- Crea registro mínimo con campos:
  - `RefId`: Valor de MECA
  - `Categoría`: Formateado a Title Case desde `CATEGORIA` nuevo
  - `Name`: Formateado desde `DESCRIPCION` nuevo
  - `Description`: Campo vacío

**3. Registros Solo en Archivo Antiguo (SKU sin equivalente en MECA):**
- Se exportan a CSV `*_no_unificados.csv` para revisión manual
- Incluye todos los campos originales del registro antiguo

### Transformaciones Aplicadas

| Campo | Transformación | Ejemplo |
|---|---|---|
| SKU | Renombramiento a RefId | "176391" → "176391" |
| CATEGORIA | Title Case y normalización | "cuidado personal>cuidado del pelo" → "Cuidado Personal>Cuidado Del Pelo" |
| DESCRIPCION | Conversión de UPPERCASE a Title Case | "NUEVO PRODUCTO" → "Nuevo Producto" |
| Descripción | Renombramiento a Description | "Descripción anterior" → "Description: Descripción Anterior" |

### Pasos de Ejecución

1. **Carga**: Lee ambos archivos JSON
2. **Mapeo**: Crea diccionarios para búsquedas rápidas por SKU y MECA
3. **Procesamiento Común**: Itera sobre registros antiguos, actualiza con información nueva
4. **Procesamiento Nuevos**: Agrega registros nuevos sin equivalente antiguo
5. **Exportación No Unificados**: Guarda registros no emparejados en CSV
6. **Escritura**: Genera JSON de salida con indentación de 4 espacios

## Archivos de Ejemplo

**Entrada:**
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed.json` (21 MB) - Datos antiguos
- `2025.11.21_CATEGORIAS-recategorizacion.json` (8.2 MB) - Datos nuevos

**Salida:**
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-join-with-recategorizacion.json` (23 MB) - Unificados
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-join-with-recategorizacion_no_unificados.csv` (1.2 KB) - No unificados

## Notas y Consideraciones

- **Codificación**: Preserva UTF-8 para caracteres especiales españoles
- **Title Case**: Aplica capitalización de primera letra a cada palabra
- **Campos Renombrados**: `SKU` → `RefId`, `Descripción` → `Description`, `CATEGORIA` → `Categoría`
- **Indentación Fija**: Siempre genera JSON con indentación de 4 espacios
- **Revisión Manual**: Verifica siempre el archivo `_no_unificados.csv` para resolver referencias faltantes
- **Orden de Procesamiento**: Primero procesa comunes, luego nuevos, esto afecta el orden final
- **Claves Sensibles**: Distingue entre mayúsculas/minúsculas (SKU ≠ sku)
- **Merge Preservador**: Mantiene todos los campos del archivo antiguo excepto los renombrados
