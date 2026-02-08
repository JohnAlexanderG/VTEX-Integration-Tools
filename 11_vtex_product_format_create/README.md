# 11_vtex_product_format_create

## Descripción

Herramienta de formateo final de productos VTEX para creación de catálogo. Transforma datos procesados del pipeline completo a formato optimizado requerido por VTEX API. Valida campos críticos, genera LinkIds SEO-friendly, y filtra productos listos para creación, exportando separadamente aquellos que requieren revisión manual.

## Funcionalidad

- Toma datos procesados del pipeline completo
- Incluye solo campos esenciales requeridos para creación exitosa
- Genera LinkIds SEO-friendly automáticamente si no están presentes
- Valida longitud del campo Title (máximo 150 caracteres para SEO)
- Filtra productos listos vs no listos para creación
- Exporta productos no creables a archivo separado para revisión manual
- Soporta tanto productos individuales como arrays
- Implementa validación robusta de campos requeridos

## Requisitos Previos

No requiere variables de entorno ni credenciales VTEX.

### Dependencias Python

```
(dependencias estándar de Python)
```

## Uso

### Comando Básico

```bash
python3 vtex_product_formatter.py productos.json vtex_ready.json
```

### Con Indentación Personalizada

```bash
python3 vtex_product_formatter.py productos.json vtex_ready.json --indent 4
```

### Con Productos No Listos Incluidos

```bash
python3 vtex_product_formatter.py final_data.json formatted.json --include-not-ready
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input_file` | Archivo JSON de entrada con productos procesados | Sí | N/A |
| `output_file` | Archivo JSON de salida formateado para VTEX | Sí | N/A |
| `--indent` | Espacios de indentación JSON | No | 2 |
| `--include-not-ready` | Incluir productos no listos en archivo separado | No | False |

## Formato de Entrada

### productos.json

Archivo JSON con datos procesados del pipeline:

```json
[
  {
    "Name": "Zapatos Nike Azules",
    "RefId": "SKU001",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "Description": "Zapatos deportivos de alta calidad",
    "DescriptionShort": "Zapatos Nike",
    "KeyWords": "nike, zapatos, azules",
    "Title": "Zapatos Nike Azules Deportivos Originales",
    "MetaTagDescription": "Compra Zapatos Nike Azules",
    "IsVisible": true,
    "IsActive": true,
    "ShowWithoutStock": true
  },
  {
    "Name": "Pantalón Adidas",
    "RefId": "SKU002",
    "CategoryId": 20,
    "BrandId": 2000002,
    "Description": "Pantalón deportivo gris"
  }
]
```

**Campos reconocidos:**
- `Name`: Nombre del producto (obligatorio)
- `RefId`: ID de referencia (obligatorio)
- `DepartmentId`: ID de departamento (opcional)
- `CategoryId`: ID de categoría (opcional)
- `BrandId`: ID de marca (obligatorio para creación)
- `CategoryPath`: Path de categoría si no hay IDs (opcional)
- `Description`: Descripción larga (opcional)
- `DescriptionShort`: Descripción corta (opcional)
- `KeyWords`: Palabras clave SEO (opcional)
- `Title`: Título SEO (opcional, se valida longitud)
- `MetaTagDescription`: Meta descripción (opcional)
- `IsVisible`: Visibilidad (default: true)
- `IsActive`: Estado activo (default: true)
- `ShowWithoutStock`: Mostrar sin stock (default: true)
- `LinkId`: URL SEO (generado automáticamente si falta)

## Formato de Salida

### vtex_ready.json

Archivo JSON formateado para envío a API VTEX:

```json
[
  {
    "Name": "Zapatos Nike Azules",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "RefId": "SKU001",
    "IsVisible": true,
    "Description": "Zapatos deportivos de alta calidad",
    "IsActive": true,
    "LinkId": "zapatos-nike-azules-sku001",
    "DescriptionShort": "Zapatos Nike",
    "KeyWords": "nike, zapatos, azules",
    "Title": "Zapatos Nike Azules Deportivos Originales",
    "MetaTagDescription": "Compra Zapatos Nike Azules",
    "ShowWithoutStock": true
  }
]
```

### vtex_ready_cannot_create.json

Archivo JSON con productos que NO pueden crearse (campos faltantes):

```json
[
  {
    "Name": "Pantalón Adidas",
    "RefId": "SKU002",
    "CategoryId": 20,
    "BrandId": 2000002,
    "Description": "Pantalón deportivo gris",
    "DepartmentId": null
  }
]
```

**Razones comunes para no poder crear:**
- Falta BrandId (crítico)
- Falta DepartmentId y CategoryId
- Falta Name o RefId
- Falta CategoryPath (si no hay IDs)

## Generación de LinkId

El script genera automáticamente LinkIds SEO-friendly:

### Proceso

1. Normaliza el nombre: Elimina acentos, caracteres especiales
2. Convierte a minúsculas
3. Reemplaza espacios y caracteres especiales con guiones
4. Agrega RefId al final para unicidad
5. Limpia guiones duplicados

### Ejemplos

```
"Zapatos Nike Azules" + "SKU001"
→ "zapatos-nike-azules-sku001"

"Café Del Campo" + "SKU002"
→ "cafe-del-campo-sku002"

"Niños - Camisetas" + "SKU003"
→ "ninos-camisetas-sku003"
```

## Validación del Campo Title

El campo Title se valida automáticamente:

### Regla de Longitud

- Máximo: 150 caracteres (límite VTEX para SEO)
- Si excede: Se trunca en palabra completa si es posible
- Ejemplo: "Zapatos Nike Azules Deportivos Originales Color Azul Talla 42 Modelo 2025" → "Zapatos Nike Azules Deportivos Originales Color Azul Talla 42"

## Clasificación de Productos

El script clasifica productos en DOS categorías:

### ✅ Listos para Crear (VTEX Ready)

**Escenario 1:** Categoría existente

Requiere:
- Name (obligatorio)
- RefId (obligatorio)
- BrandId (obligatorio)
- DepartmentId + CategoryId (ambos obligatorios)

**Escenario 2:** Nueva categoría

Requiere:
- Name (obligatorio)
- RefId (obligatorio)
- BrandId (obligatorio)
- CategoryPath (obligatorio, cuando no hay DepartmentId/CategoryId)

**Archivo:** `vtex_ready.json`

### ❌ No Listos para Crear

Productos que faltan campos requeridos y no pueden procesarse.

**Causas comunes:**
- Falta BrandId (crítico)
- Falta DepartmentId/CategoryId Y CategoryPath
- Falta Name o RefId

**Archivo:** `vtex_ready_cannot_create.json`

## Cómo Funciona

### Proceso de Formateo

1. **Lee archivo JSON de entrada**
2. **Para cada producto:**
   - Extrae campos requeridos (Name, RefId, BrandId, etc.)
   - Genera LinkId si no existe
   - Valida Title (máx 150 caracteres)
   - Incluye solo campos reconocidos por VTEX
   - Aplica valores por defecto (IsActive=true, ShowWithoutStock=true)
3. **Filtra productos:**
   - Listos: Tienen todos los campos críticos
   - No listos: Faltan campos y se exportan separados
4. **Genera archivos JSON:**
   - `vtex_ready.json`: Productos listos
   - `vtex_ready_cannot_create.json`: Productos no listos

### Validación de Campos

```python
# Campos críticos para Escenario 1
- Name ✓
- RefId ✓
- DepartmentId ✓
- CategoryId ✓
- BrandId ✓

# Campos críticos para Escenario 2
- Name ✓
- RefId ✓
- BrandId ✓
- CategoryPath ✓
```

## Ejemplos de Ejecución

### Ejemplo 1: Formateo Básico

```bash
python3 11_vtex_product_format_create/vtex_product_formatter.py \
    productos_finales.json \
    vtex_ready.json
```

### Ejemplo 2: Con Indentación de 4 Espacios

```bash
python3 11_vtex_product_format_create/vtex_product_formatter.py \
    datos.json \
    salida.json \
    --indent 4
```

### Ejemplo 3: Revisar Productos No Listos

```bash
python3 11_vtex_product_format_create/vtex_product_formatter.py \
    datos.json \
    formatted.json

# Luego examinar
cat formatted_cannot_create.json | python3 -m json.tool | head -50
```

## Archivos Generados

El script genera 2 archivos:

1. **vtex_ready.json** - Productos listos para creación en VTEX
2. **vtex_ready_cannot_create.json** - Productos que requieren revisión

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** Productos clasificados del paso 09 (con reportes)
- **Salida:** Productos formateados listos para paso 12 (creación)

### Flujo Recomendado

```
Paso 09: generate_vtex_report.py
    ↓ (productos listos para crear)
Paso 11: vtex_product_formatter.py
    ↓ (productos VTEX ready)
Paso 12: vtex_product_create.py
    ↓ (crea productos en VTEX)
```

## Notas Importantes

- **Campos opcionales:** Se incluyen todos los campos opcionales si están presentes
- **Valores por defecto:** IsActive=true, IsVisible=true, ShowWithoutStock=true
- **LinkId generado:** Si no existe, se crea automáticamente a partir del nombre y RefId
- **Normalización de texto:** Se eliminan acentos al generar LinkId
- **Title validado:** Se trunca a 150 caracteres máximo
- **CategoryPath:** Campo especial para crear nuevas categorías (Escenario 2)

## Troubleshooting

### Error: Archivo JSON inválido

```bash
python3 -m json.tool productos.json  # Valida JSON
```

### Muchos productos no listos

Verifica que tengan BrandId:

```bash
# Buscar productos sin BrandId
python3 -c "import json
data = json.load(open('productos.json'))
sin_brand = [p for p in data if not p.get('BrandId')]
print(f'Sin BrandId: {len(sin_brand)}')"
```

### Title demasiado largo

El script trunca automáticamente al límite VTEX (150 caracteres).

Para previsualizar:

```bash
python3 -c "import json
data = json.load(open('vtex_ready.json'))
for p in data[:5]:
    title = p.get('Title', '')
    print(f'{p[\"RefId\"]}: {len(title)} chars - {title[:80]}...')"
```

### LinkId generados no son válidos

El script normaliza automáticamente eliminando:
- Acentos (á → a)
- Caracteres especiales (→ guion)
- Guiones duplicados

Si necesitas LinkIds personalizados, agregarlos al archivo de entrada.

## Ejemplos de Entrada/Salida

### Entrada Simple

```json
{
  "Name": "Producto Test",
  "RefId": "TEST001",
  "BrandId": 2000001,
  "DepartmentId": 1,
  "CategoryId": 10
}
```

### Salida Formateada

```json
{
  "Name": "Producto Test",
  "DepartmentId": 1,
  "CategoryId": 10,
  "BrandId": 2000001,
  "RefId": "TEST001",
  "IsVisible": true,
  "Description": "",
  "IsActive": true,
  "LinkId": "producto-test-test001",
  "DescriptionShort": "",
  "KeyWords": "",
  "Title": "Producto Test",
  "MetaTagDescription": "",
  "ShowWithoutStock": true
}
```
