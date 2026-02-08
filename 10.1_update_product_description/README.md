# 10.1_update_product_description

## Descripción

Herramienta para actualizar descripciones de productos existentes en VTEX. Realiza matching entre datos CSV (con columna SKU) y JSON (con datos de productos creados) para actualizar el campo Description mediante la API privada de VTEX. Utilizado para enriquecer descripciones de productos ya creados en el catálogo.

## Funcionalidad

- Realiza matching entre CSV y JSON usando SKU/RefId como clave
- Lee descripciones desde archivo CSV
- Obtiene ProductIds desde archivo JSON (respuestas de creación VTEX)
- Realiza PUT requests a la API VTEX para actualizar descripciones
- Soporta campos alternativos en CSV para SKU y Descripción
- Implementa rate limiting y reintentos automáticos con backoff exponencial
- Modo dry-run para previsualizar cambios sin ejecutar
- Manejo robusto de errores con logging detallado
- Soporta timeout configurable y delimitador de CSV automático

## Requisitos Previos

### Variables de Entorno (.env)

Requiere las siguientes variables en archivo `.env` en la raíz del proyecto:

```
X-VTEX-API-AppKey=<tu_app_key>
X-VTEX-API-AppToken=<tu_app_token>
VTEX_ACCOUNT_NAME=<nombre_cuenta>
VTEX_ENVIRONMENT=vtexcommercestable  # (opcional, por defecto)
```

### Dependencias Python

```
requests
python-dotenv
```

## Uso

### Comando Básico

```bash
python3 update_product_description.py --json productos.json --csv productos.csv
```

### Modo Dry-Run (Previsualizar sin cambios)

```bash
python3 update_product_description.py --json productos.json --csv productos.csv --dry-run
```

### Con Configuración Personalizada de Columnas

```bash
python3 update_product_description.py \
    --json productos.json \
    --csv productos.csv \
    --sku-col "SKU" \
    --desc-col "Descripción"
```

### Con Límite de Productos

```bash
python3 update_product_description.py \
    --json productos.json \
    --csv productos.csv \
    --limit 100
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `--json` | Ruta al archivo JSON con datos de productos | Sí | N/A |
| `--csv` | Ruta al archivo CSV con descripciones | Sí | N/A |
| `--sku-col` | Nombre exacto de columna SKU en CSV | No | `SKU` |
| `--desc-col` | Nombre exacto de columna Descripción en CSV | No | `Descripción` |
| `--dry-run` | Simula actualizaciones sin ejecutar PUTs | No | False |
| `--limit` | Procesa solo N productos (0 = sin límite) | No | 0 |

## Formato de Entrada

### productos.json

Archivo JSON con respuestas de creación de productos VTEX:

```json
[
  {
    "response": {
      "Id": 1000001,
      "Name": "Zapatos Nike Azules",
      "RefId": "SKU001",
      "CategoryId": 10,
      "BrandId": 2000001,
      "LinkId": "zapatos-nike-azules-sku001"
    },
    "ref_id": "SKU001"
  },
  {
    "response": {
      "Id": 1000002,
      "Name": "Pantalón Adidas",
      "RefId": "SKU002",
      "CategoryId": 20,
      "BrandId": 2000002
    },
    "ref_id": "SKU002"
  }
]
```

**Estructura esperada:**
- Cada elemento debe tener `response` con el objeto del producto (contiene `Id` = productId)
- Debe incluir `RefId` (desde `response.RefId` o campo `ref_id`)
- Campos analizados: `Name`, `CategoryId`, `BrandId`, `LinkId`

### productos.csv

Archivo CSV con SKU y descripciones:

```csv
SKU,Nombre,Descripción,Cantidad
SKU001,Zapatos Nike,Zapatos deportivos azules de alta calidad,50
SKU002,Pantalón Adidas,Pantalón deportivo gris talla M y L,30
SKU003,Camiseta Puma,Camiseta de algodón 100%,100
```

**Campos esperados:**
- Columna SKU: Identificador del producto (por defecto: "SKU")
- Columna Descripción: Texto para actualizar (por defecto: "Descripción")
- Solo se procesan filas con SKU y Descripción no vacíos
- Soporta delimitadores automáticos: coma, punto y coma, tabulación, tubería

## Formato de Salida

El script no genera archivos de salida, solo:
- Logs en consola con resultado de cada actualización
- Resumen final con estadísticas

### Ejemplo de Salida en Consola

```
[INFO] Cuenta: mitienda / Env: vtexcommercestable
[INFO] CSV: 3 SKUs con descripción no vacía.
[INFO] JSON: 2 productos en la lista.

[OK] productId=1000001 ref_id=SKU001 status=200
[DRY-RUN] productId=1000002 ref_id=SKU002 -> Description = 'Pantalón deportivo...'
[WARN] Item #3 sin ref_id/response.RefId, se omite. productId=1000003
[WARN] productId=1000002 ref_id=SKU002 faltan campos ['CategoryId'] en response, se omite.

[SUMMARY]
  Actualizados: 1
  Sin match SKU==RefId: 1
  Match pero descripción vacía: 0
  Errores: 1
```

## Cómo Funciona

### Proceso de Actualización

1. **Valida credenciales** VTEX desde .env
2. **Carga archivo JSON** y extrae productos con sus IDs
3. **Carga archivo CSV** y crea mapa SKU → Descripción
4. **Para cada producto:**
   - Extrae productId desde `response.Id`
   - Extrae RefId desde `response.RefId` o `ref_id`
   - Busca RefId en mapa CSV
   - Valida campos requeridos (Name, CategoryId, BrandId)
   - Construye payload PUT mínimo
   - Ejecuta PUT request o simula (dry-run)
5. **Maneja errores:**
   - Rate limiting (429): reintenta con backoff exponencial
   - Timeout: registra y continúa
   - Otros errores: registra y continúa
6. **Imprime resumen** con estadísticas

### Formato del Payload PUT

El script envía un payload mínimo requerido:

```json
{
  "Name": "Zapatos Nike Azules",
  "CategoryId": 10,
  "BrandId": 2000001,
  "LinkId": "zapatos-nike-azules-sku001",
  "Description": "Zapatos deportivos azules de alta calidad"
}
```

Campos incluidos:
- `Name`: Nombre del producto (desde respuesta)
- `CategoryId`: Categoría (desde respuesta)
- `BrandId`: Marca (desde respuesta)
- `LinkId`: URL SEO (desde respuesta, si existe)
- `Description`: Descripción (desde CSV)

## Control de Rate Limiting

- **Delay entre requests:** 0.05 segundos (50ms)
- **Timeout por request:** 60 segundos
- **Reintentos automáticos:** En caso de status 429 o 5xx
- **Backoff exponencial:** Aumenta espera entre reintentos

## Ejemplos de Ejecución

### Ejemplo 1: Actualización Simple

```bash
python3 10.1_update_product_description/update_product_description.py \
    --json 20260114_142531_vtex_creation_successful.json \
    --csv productos.csv
```

### Ejemplo 2: Previsualizar Cambios

```bash
python3 10.1_update_product_description/update_product_description.py \
    --json respuesta.json \
    --csv descripciones.csv \
    --dry-run
```

### Ejemplo 3: Con Columnas Personalizadas

```bash
python3 10.1_update_product_description/update_product_description.py \
    --json productos.json \
    --csv datos.csv \
    --sku-col "CodigoProducto" \
    --desc-col "TextoDescriptivo"
```

### Ejemplo 4: Procesar Solo Primeros 50

```bash
python3 10.1_update_product_description/update_product_description.py \
    --json productos.json \
    --csv descripciones.csv \
    --limit 50
```

## Archivos Requeridos

1. **productos.json** - Salida de creación de productos (paso 12)
   - Ejemplo: `20260114_142531_vtex_creation_successful.json`

2. **productos.csv** - Archivo con descripciones a actualizar
   - Ejemplo: `productos.csv`

3. **.env** - Credenciales VTEX (en raíz del proyecto)

## Notas Importantes

- **Dry-run recomendado:** Ejecuta primero con `--dry-run` para verificar
- **Matching por SKU:** Solo actualiza productos que coincidan en SKU/RefId
- **Campos críticos:** Se valida presencia de Name, CategoryId, BrandId antes de actualizar
- **Descripción vacía:** Se omiten filas con descripción vacía
- **Delimitador automático:** El script detecta automáticamente el delimitador CSV
- **Espacios en nombre columna:** Se normalizan automáticamente para búsqueda

## Troubleshooting

### Error: "No encontré la columna SKU"

Verifica el nombre exacto de la columna en el CSV:

```bash
head -1 productos.csv  # Muestra encabezado
```

Luego usa `--sku-col` con el nombre exacto.

### Error: "Credenciales VTEX faltantes"

Asegurate que `.env` tiene todas las variables:

```
X-VTEX-API-AppKey=...
X-VTEX-API-AppToken=...
VTEX_ACCOUNT_NAME=...
```

### Error: "CSV no tiene encabezados"

El archivo CSV debe tener una fila de encabezados. Ejemplo:

```csv
SKU,Descripción
SKU001,Descripción del producto 1
```

### No se actualizaron productos (sin match)

Verifica que los SKUs en CSV coincidan exactamente con los RefIds en JSON:

```bash
# Ver primeros SKUs del CSV
head productos.csv

# Ver primeros RefIds del JSON
python3 -c "import json; data=json.load(open('productos.json'));
print([p.get('ref_id', p.get('response', {}).get('RefId')) for p in data[:5]])"
```

## Integración en Pipeline

Este paso se ubica entre:
- **Entrada:** Productos creados en paso 12 (JSON + CSV de descripciones)
- **Salida:** Productos con descripciones actualizadas en VTEX
- **Seguimiento:** Paso 14 (extracción de respuestas) o paso 15 (creación SKUs)
