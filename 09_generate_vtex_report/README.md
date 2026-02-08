# 09_generate_vtex_report

## Descripción

Herramienta de análisis que evalúa la preparación de productos para creación en VTEX. Clasifica productos en tres categorías basadas en campos requeridos y genera múltiples archivos JSON para diferentes flujos de trabajo. Este paso produce reportes de estadísticas y archivos separados para productos listos, con categoría a crear, o no creables.

## Funcionalidad

- Analiza productos procesados para determinar su preparación para VTEX
- Clasifica productos en 3 categorías basadas en disponibilidad de campos críticos
- Valida presencia de DepartmentId, CategoryId, BrandId y campo de categoría
- Genera múltiples archivos JSON para cada categoría de producto
- Exporta productos no creables a JSON y CSV para revisión manual
- Crea reporte Markdown con resumen estadístico y análisis
- Muestra progreso en tiempo real durante el procesamiento

## Requisitos Previos

No requiere variables de entorno ni credenciales VTEX. Solo necesita:

### Dependencias Python

```
(dependencias estándar de Python)
```

## Uso

### Comando Básico

```bash
python3 generate_vtex_report.py input.json -o reporte.md
```

### Con Archivo de Entrada Personalizado

```bash
python3 generate_vtex_report.py productos_final.json -o analisis_productos.md
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input` | Ruta al archivo JSON de entrada | Sí | N/A |
| `-o`, `--output` | Ruta al archivo Markdown de salida | No | `report.md` |

## Formato de Entrada

### input.json

Archivo JSON con lista de productos procesados:

```json
[
  {
    "Name": "Zapatos Nike Azules",
    "RefId": "SKU001",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "Description": "Zapatos deportivos"
  },
  {
    "Name": "Pantalón Adidas",
    "RefId": "SKU002",
    "DepartmentId": 2,
    "CategoryId": null,
    "BrandId": 2000002,
    "Categoría": "Ropa Deportiva"
  },
  {
    "Name": "Producto Sin Marca",
    "RefId": "SKU003",
    "DepartmentId": 3,
    "CategoryId": 30,
    "BrandId": null
  }
]
```

**Campos analizados:**
- `DepartmentId`: ID del departamento (puede ser null)
- `CategoryId`: ID de la categoría (puede ser null)
- `BrandId`: ID de la marca (crítico, no puede ser null)
- `Categoría` o `Categoria`: Nombre de categoría (opcional)
- Otros campos se preservan en salida

## Formato de Salida

### report.md

Reporte Markdown principal con estadísticas:

```markdown
# Reporte de Creación de Productos VTEX

- **Total de productos procesados:** 1000
- **Productos listos para crear:** 800
- **Productos que requieren crear categoría:** 150
- **Productos que no se pueden crear:** 50

## Archivos Generados

- **Productos listos para crear:** `report_listos_para_crear.json` (800 productos)
- **Productos con categoría a crear:** `report_categoria_a_crear.json` (150 productos)
- **Productos que no se pueden crear (JSON):** `report_no_se_pueden_crear.json` (50 productos)
- **Productos que no se pueden crear (CSV):** `report_no_se_pueden_crear.csv` (50 productos)
```

### report_listos_para_crear.json

Archivo JSON con productos completamente preparados para creación en VTEX:

```json
[
  {
    "Name": "Zapatos Nike Azules",
    "RefId": "SKU001",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "Description": "Zapatos deportivos"
  }
]
```

**Condición:** Tienen DepartmentId, CategoryId y BrandId (todos no-null)

### report_categoria_a_crear.json

Archivo JSON con productos que requieren creación de nueva categoría:

```json
[
  {
    "Name": "Pantalón Adidas",
    "RefId": "SKU002",
    "DepartmentId": 2,
    "CategoryId": null,
    "BrandId": 2000002,
    "Categoría": "Ropa Deportiva"
  }
]
```

**Condición:** Falta CategoryId pero tienen nombre de categoría en campo "Categoría"

### report_no_se_pueden_crear.json

Archivo JSON con productos que no pueden crearse (sin BrandId):

```json
[
  {
    "Name": "Producto Sin Marca",
    "RefId": "SKU003",
    "DepartmentId": 3,
    "CategoryId": 30,
    "BrandId": null
  }
]
```

**Condición:** Falta BrandId (campo crítico requerido por VTEX)

### report_no_se_pueden_crear.csv

Archivo CSV equivalente con productos no creables (una fila por producto):

| Name | RefId | DepartmentId | CategoryId | BrandId |
|------|-------|--------------|------------|---------|
| Producto Sin Marca | SKU003 | 3 | 30 | (vacío) |

## Clasificación de Productos

El script clasifica productos en 3 categorías:

### ✅ Listos para Crear

**Condición:** Tienen DepartmentId, CategoryId y BrandId

Estos productos pueden crearse directamente en VTEX sin pasos adicionales.

**Archivo:** `report_listos_para_crear.json`

### 🔧 Requieren Crear Categoría

**Condición:** Falta CategoryId pero tienen campo "Categoría" y tienen BrandId

Estos productos requieren crear la categoría primero, pero el nombre está disponible.

**Archivo:** `report_categoria_a_crear.json`

### ❌ No Se Pueden Crear

**Condición:** Falta BrandId (o falta DepartmentId/CategoryId sin categoría disponible)

Estos productos requieren revisión manual antes de poder crearse.

**Archivos:** `report_no_se_pueden_crear.json` y `.csv`

## Cómo Funciona

### Proceso de Clasificación

1. **Lee archivo JSON de entrada**
2. **Para cada producto:**
   - Verifica si tiene DepartmentId, CategoryId, BrandId
   - Verifica si tiene campo de categoría disponible
   - Clasifica en una de las 3 categorías
3. **Genera archivos JSON separados** para cada categoría
4. **Crea archivo CSV** para productos no creables
5. **Genera reporte Markdown** con resumen y lista de archivos

### Validación de Campos

- **BrandId:** Campo crítico - Si falta, producto no puede crearse
- **DepartmentId:** Requerido junto a CategoryId
- **CategoryId:** Puede omitirse si hay nombre de categoría disponible
- **Categoría/Categoria:** Nombre para crear nueva categoría (soporta ambas variantes)

## Ejemplos de Ejecución

```bash
# Análisis básico
python3 09_generate_vtex_report/generate_vtex_report.py productos_final.json

# Con archivo Markdown personalizado
python3 09_generate_vtex_report/generate_vtex_report.py \
    productos.json \
    -o analisis_detallado.md

# Visualizar estructura del JSON antes
python3 -m json.tool productos.json | head -50
```

## Archivos Generados

El script genera hasta 5 archivos (además del Markdown principal):

1. **report_listos_para_crear.json** - Productos listos para creación
2. **report_categoria_a_crear.json** - Productos con categoría a crear
3. **report_no_se_pueden_crear.json** - Productos no creables (JSON)
4. **report_no_se_pueden_crear.csv** - Productos no creables (CSV)
5. **report.md** - Reporte Markdown principal

## Casos de Uso

### Caso 1: Todos los productos listos

```
Total procesados: 1000
Listos para crear: 1000
Requieren crear categoría: 0
No se pueden crear: 0
```

**Acción:** Proceder al paso 12 para creación de productos

### Caso 2: Algunos requieren crear categoría

```
Total procesados: 1000
Listos para crear: 800
Requieren crear categoría: 150
No se pueden crear: 50
```

**Acción:**
1. Crear categorías del archivo `categoria_a_crear.json`
2. Actualizar CategoryIds manualmente
3. Revisar 50 productos en `no_se_pueden_crear.csv`

### Caso 3: Muchos productos no creables

```
Total procesados: 1000
Listos para crear: 500
Requieren crear categoría: 100
No se pueden crear: 400
```

**Acción:** Revisar y corregir datos de entrada antes de proceder

## Troubleshooting

### Archivo JSON inválido

```bash
python3 -m json.tool input.json  # Valida JSON
```

### Demasiados productos no creables

Verifica que tengan BrandId asignado:
```bash
# Buscar productos sin BrandId
grep -c '"BrandId": null' input.json
```

### Campos alternativos no reconocidos

El script soporta variantes:
- `Categoría` o `Categoria` para nombre de categoría
- Ambas variantes se reconocen automáticamente

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** Productos del paso 08 (con BrandId asignado)
- **Salida:** Archivos preparados para pasos 11 (formateo) y 12 (creación)
