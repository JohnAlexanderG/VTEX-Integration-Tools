# 13_extract_json_response

## Descripción

Herramienta utilidad que extrae valores 'response' de un archivo JSON que contiene resultados de creación de productos VTEX. Transforma archivos de salida complejos del paso 12 en archivos JSON simples con solo los objetos de respuesta de VTEX, facilitando el procesamiento posterior en pasos subsecuentes como creación de SKUs.

## Funcionalidad

- Lee archivo JSON con respuestas de creación VTEX (paso 12)
- Extrae solo los valores del campo 'response' de cada objeto
- Maneja tanto objetos individuales como arrays de objetos
- Exporta respuestas extraídas a nuevo archivo JSON
- Soporta formateo JSON personalizable (indentación)
- Validación robusta de entrada

## Requisitos Previos

No requiere variables de entorno ni credenciales VTEX.

### Dependencias Python

```
(dependencias estándar de Python)
```

## Uso

### Comando Básico

```bash
python3 extract_response.py input.json output.json
```

### Con Indentación Personalizada

```bash
python3 extract_response.py input.json output.json --indent 4
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `input_file` | Ruta al archivo JSON con respuestas VTEX | Sí | N/A |
| `output_file` | Ruta al archivo JSON de salida | Sí | N/A |
| `--indent` | Espacios de indentación JSON | No | 4 |

## Formato de Entrada

### input.json (Salida del Paso 12)

Archivo JSON con estructura compleja de creación de productos:

```json
[
  {
    "product_data": {
      "Name": "Zapatos Nike Azules",
      "DepartmentId": 1,
      "CategoryId": 10,
      "BrandId": 2000001,
      "RefId": "SKU001",
      ...
    },
    "response": {
      "Id": 1000001,
      "Name": "Zapatos Nike Azules",
      "DepartmentId": 1,
      "CategoryId": 10,
      "BrandId": 2000001,
      "RefId": "SKU001",
      "LinkId": "zapatos-nike-azules-sku001",
      "Description": "Zapatos deportivos",
      "DescriptionShort": "Zapatos Nike",
      "Ean": [],
      "IsActive": true,
      "IsVisible": true,
      "Score": 0,
      "KeyWords": "nike zapatos",
      "MetaTagDescription": "Zapatos Nike",
      "ShowWithoutStock": true
    },
    "status_code": 200,
    "ref_id": "SKU001",
    "name": "Zapatos Nike Azules",
    "timestamp": "2025-01-14T19:21:31.123456"
  },
  {
    "product_data": { ... },
    "response": {
      "Id": 1000002,
      ...
    },
    ...
  }
]
```

**Estructura esperada:**
- Array de objetos OR objeto individual
- Cada objeto debe contener campo 'response'
- Se extraen SOLO los valores de 'response'

### Objeto Individual (Alternativa)

```json
{
  "product_data": { ... },
  "response": {
    "Id": 1000001,
    ...
  },
  ...
}
```

## Formato de Salida

### output.json

Archivo JSON simplificado con solo las respuestas de VTEX:

```json
[
  {
    "Id": 1000001,
    "Name": "Zapatos Nike Azules",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001,
    "RefId": "SKU001",
    "LinkId": "zapatos-nike-azules-sku001",
    "Description": "Zapatos deportivos",
    "DescriptionShort": "Zapatos Nike",
    "Ean": [],
    "IsActive": true,
    "IsVisible": true,
    "Score": 0,
    "KeyWords": "nike zapatos",
    "MetaTagDescription": "Zapatos Nike",
    "ShowWithoutStock": true
  },
  {
    "Id": 1000002,
    "Name": "Pantalón Adidas",
    ...
  }
]
```

**Contenido:**
- Array de objetos de respuesta de VTEX
- Solo campos que VTEX devolvió
- Siempre es un array (incluso si entrada es objeto individual)
- Indentación limpia (por defecto 4 espacios)

## Cómo Funciona

### Proceso de Extracción

1. **Lee archivo JSON de entrada**
2. **Valida estructura:**
   - Si es array: Itera cada elemento
   - Si es objeto: Trata como único elemento
3. **Para cada elemento:**
   - Verifica si tiene campo 'response'
   - Extrae valor de 'response'
   - Agrega a lista de salida
4. **Exporta array resultante** a JSON

### Lógica de Extracción

```python
responses = []

if isinstance(data, list):
    for item in data:
        if 'response' in item:
            responses.append(item['response'])
elif isinstance(data, dict):
    if 'response' in data:
        responses.append(data['response'])
```

## Ejemplos de Ejecución

### Ejemplo 1: Extracción Básica

```bash
python3 13_extract_json_response/extract_response.py \
    20250114_142531_vtex_creation_successful.json \
    respuestas_extraidas.json
```

**Entrada:** 100 objetos complejos con campo 'response'
**Salida:** Array de 100 respuestas de VTEX

### Ejemplo 2: Con Indentación Personalizada

```bash
python3 13_extract_json_response/extract_response.py \
    respuestas.json \
    salida.json \
    --indent 2
```

**Genera:** JSON con indentación de 2 espacios

### Ejemplo 3: Desde Directorio Diferente

```bash
python3 13_extract_json_response/extract_response.py \
    ../12_vtex_product_create/20250114_142531_vtex_creation_successful.json \
    productos_para_skus.json
```

## Casos de Uso

### Caso 1: Preparar para Creación de SKUs

```
Paso 12: vtex_product_create.py
    ↓ (genera {timestamp}_vtex_creation_successful.json)
Paso 13: extract_json_response.py
    ↓ (extrae respuestas)
Paso 14: to_vtex_skus.py
    ↓ (transforma a SKUs)
Paso 15: vtex_sku_create.py
    ↓ (crea SKUs en VTEX)
```

### Caso 2: Investigar Productos Creados

Extrae solo las respuestas VTEX para análisis:

```bash
python3 extract_response.py \
    respuestas_complejas.json \
    respuestas_limpias.json

# Luego analizar
cat respuestas_limpias.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total productos: {len(data)}')
print(f'Primero: {data[0][\"Id\"]} - {data[0][\"Name\"]}')"
```

### Caso 3: Filtrar Productos Creados

Extrae y luego filtra por criterio:

```bash
python3 extract_response.py entrada.json salida_temp.json

# Filtrar activos
python3 -c "
import json
data = json.load(open('salida_temp.json'))
activos = [p for p in data if p.get('IsActive')]
json.dump(activos, open('salida_filtrada.json', 'w'), indent=2)"
```

## Archivos Generados

El script genera 1 archivo:

1. **output.json** - Respuestas extraídas de VTEX

## Ejemplos Completos

### Entrada Compleja

```json
[
  {
    "product_data": {
      "Name": "Zapatos Nike",
      "BrandId": 2000001
    },
    "response": {
      "Id": 1000001,
      "Name": "Zapatos Nike",
      "BrandId": 2000001
    },
    "status_code": 200,
    "timestamp": "2025-01-14T19:21:31"
  },
  {
    "product_data": {
      "Name": "Pantalón Adidas",
      "BrandId": 2000002
    },
    "response": {
      "Id": 1000002,
      "Name": "Pantalón Adidas",
      "BrandId": 2000002
    },
    "status_code": 200,
    "timestamp": "2025-01-14T19:21:32"
  }
]
```

### Salida Extraída

```json
[
  {
    "Id": 1000001,
    "Name": "Zapatos Nike",
    "BrandId": 2000001
  },
  {
    "Id": 1000002,
    "Name": "Pantalón Adidas",
    "BrandId": 2000002
  }
]
```

## Notas Importantes

- **Siempre devuelve array:** Incluso si entrada es objeto individual
- **Solo extrae 'response':** Descarta producto_data y metadatos
- **Valida entrada:** Si no hay campo 'response', se omite ese elemento
- **Indentación:** Por defecto 4 espacios, personalizable
- **Mantiene orden:** Preserva orden de elementos de entrada
- **Sin duplicados:** Extrae cada response una sola vez

## Troubleshooting

### Error: "File not found"

```bash
ls -la entrada.json  # Verifica existencia
```

### Error: "Invalid JSON"

```bash
python3 -m json.tool entrada.json  # Valida JSON
```

### Archivo de salida vacío

Posibles causas:
1. Archivo entrada no tiene campo 'response'
2. Entrada es array pero está vacío
3. Todos los elementos tienen 'response' pero vacío

Verifica estructura:

```bash
python3 -c "
import json
data = json.load(open('entrada.json'))
print(type(data))
if isinstance(data, list):
    print(f'Elementos: {len(data)}')
    if data:
        print(f'Tiene response: {\"response\" in data[0]}')"
```

### Error de indentación

Si especificas indentación inválida:

```bash
# Válido
python3 extract_response.py entrada.json salida.json --indent 2

# Inválido
python3 extract_response.py entrada.json salida.json --indent abc
```

## Integración en Pipeline

Este paso es utilidad entre:
- **Entrada:** Salida del paso 12 (`*_successful.json`)
- **Salida:** Respuestas limpias
- **Seguimiento:** Paso 14 o paso 15 (pasos que necesitan objeto de respuesta)

### Ubicación en Flujo

```
Paso 12: vtex_product_create.py
    ↓
Paso 13: extract_json_response.py (AQUÍ - extrae respuestas)
    ↓
Paso 14: to_vtex_skus.py (transforma a SKUs)
    ↓
Paso 15: vtex_sku_create.py (crea SKUs)
```

## Mejores Prácticas

1. **Nombres descriptivos:** Usa nombres que indiquen el contenido
   ```bash
   # Bien
   python3 extract_response.py productos_creados.json respuestas_para_skus.json

   # Menos claro
   python3 extract_response.py datos.json salida.json
   ```

2. **Valida entrada:** Verifica que tenga campo 'response'
   ```bash
   head entrada.json | grep -c response
   ```

3. **Mantén archivo original:** No sobrescribas el original
   ```bash
   # Bien
   python3 extract_response.py entrada.json salida_extraida.json

   # Riesgoso
   python3 extract_response.py entrada.json entrada.json
   ```

4. **Documenta intención:** Usa prefijos en nombres
   ```bash
   # Claro
   respuestas_para_skus.json    # Para paso 14
   respuestas_respaldo.json     # Backup
   respuestas_filtradas.json    # Versión procesada
   ```
