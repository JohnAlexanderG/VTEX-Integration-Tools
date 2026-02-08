# 10_deprecated_update_vtex_products

## Descripción

Script obsoleto para actualizar masivamente el estado de productos en VTEX. **NO SE RECOMIENDA USAR EN OPERACIONES DE PRODUCCIÓN.** Este script solo debe utilizarse en cargas iniciales o durante mantenimiento específico de catálogo.

La funcionalidad permite obtener todos los IDs de productos del catálogo VTEX, descargar su información completa, modificar campos IsActive e IsVisible, y actualizar cada producto en la API VTEX.

## Advertencia

```
⚠️ SCRIPT OBSOLETO - NO UTILIZAR EN PRODUCCIÓN
Este script modifica TODOS los productos del catálogo VTEX.
Solo úsalo si:
1. Es para carga inicial
2. Necesitas desactivar masivamente productos
3. Entiendes las implicaciones
```

## Funcionalidad

- Obtiene todos los IDs de productos del catálogo VTEX usando paginación
- Descarga información completa de cada producto via API GET
- Modifica campos `IsActive` e `IsVisible` a `False` (desactiva productos)
- Actualiza cada producto individualmente via API PUT
- Exporta lista completa de productos actualizados a JSON
- Implementa rate limiting para evitar saturar la API VTEX

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

### Ejecución Básica (sin parámetros)

```bash
python3 update_vtex_products.py
```

**Nota:** No acepta argumentos CLI. Desactiva todos los productos del catálogo.

## Proceso de Ejecución

### Paso 1: Obtener IDs de Productos

```
Obteniendo IDs de productos...
```

El script llama al endpoint de paginación para obtener todos los `productId`:

```
GET /api/catalog_system/pvt/products/GetProductAndSkuIds?_from=0&_to=249
GET /api/catalog_system/pvt/products/GetProductAndSkuIds?_from=250&_to=499
... (paginación hasta obtener todos)
```

**Rate limiting:** 200ms entre requests de paginación

### Paso 2: Actualizar Productos

```
Actualizando productos...
```

Para cada `productId`:

```
GET /api/catalog/pvt/product/{productId}
    ↓
Modifica: IsActive = False, IsVisible = False
    ↓
PUT /api/catalog/pvt/product/{productId}
```

**Rate limiting:** 100ms entre requests individuales

### Paso 3: Exportar Resultados

```
Se actualizaron N productos. Output en: updated_products.json
```

## Formato de Salida

### updated_products.json

Archivo JSON con lista de todos los productos actualizados:

```json
[
  {
    "Id": 1000001,
    "Name": "Zapatos Nike",
    "IsActive": false,
    "IsVisible": false,
    "Ean": ["123456789"],
    "RefId": "SKU001",
    "CategoryId": 10,
    "BrandId": 2000001,
    "LinkId": "zapatos-nike",
    "Description": "Zapatos deportivos",
    "DescriptionShort": "Zapatos",
    "ReleaseDate": "2025-08-01T00:00:00",
    "ShowWithoutStock": true,
    "IsVisible": false,
    "Score": 0,
    "KeyWords": "nike zapatos",
    "SupplierCode": "",
    "MetaTagDescription": "Zapatos Nike",
    "Title": "Zapatos Nike"
  }
]
```

## Cómo Funciona

### Obtención de IDs (GetProductAndSkuIds)

```
Paginación en bloques de 250 productos:
- _from=0, _to=249 (primeros 250)
- _from=250, _to=499 (siguientes 250)
- ... hasta obtener todos
```

La API devuelve:
```json
{
  "data": [
    { "productId": 1000001, "skuId": 2000001 },
    { "productId": 1000002, "skuId": 2000002 }
  ],
  "range": {
    "total": 5000
  }
}
```

### Actualización de Cada Producto

```
Para cada productId:
1. GET /api/catalog/pvt/product/{productId}
   → Obtiene objeto completo del producto

2. Modifica el objeto:
   - IsActive = False
   - IsVisible = False

3. PUT /api/catalog/pvt/product/{productId}
   → Envía objeto modificado
```

## Ejemplos de Ejecución

### Desactivar Todos los Productos

```bash
python3 10_deprecated_update_vtex_products/update_vtex_products.py
```

**Resultado:**
```
Obteniendo IDs de productos...
Total de productos encontrados: 1250
Actualizando productos...
Se actualizaron 1250 productos. Output en: updated_products.json
```

## Archivos Generados

1. **updated_products.json** - Todos los productos con IsActive=False e IsVisible=False

## Notas Importantes

- **Desactivación permanente:** Los productos se marcan como inactivos e invisibles
- **Sin reversión:** Debes activar manualmente en VTEX si cometiste error
- **Rate limiting:** El script pausa automáticamente para no sobrecargar la API
  - 200ms entre paginaciones
  - 100ms entre actualizaciones individuales
- **Paginación automática:** Maneja automáticamente todos los productos
- **Tiempo de ejecución:** Varía según cantidad (típicamente 1-2 minutos por 100 productos)

## Casos de Uso (Deprecados)

Aunque está deprecado, podría usarse para:

1. **Carga inicial:** Desactivar productos previos antes de cargar nuevos
2. **Limpieza de catálogo:** Desactivar todos para empezar de cero
3. **Mantenimiento:** Desactivar productos mientras se corrigen datos

## Troubleshooting

### Credenciales faltantes

```
EnvironmentError: Faltan variables de entorno.
Asegúrate de definir VTEX_ACCOUNT_NAME, VTEX_ENVIRONMENT,
X-VTEX-API-AppKey y X-VTEX-API-AppToken en tu .env
```

Solución: Completa todas las variables en `.env`

### Error "401 Unauthorized"

Las credenciales en `.env` son incorrectas o han expirado.

Verifica en VTEX Admin:
- Las AppKey y AppToken son válidas
- Las credenciales tienen permisos para catálogo

### El script se detiene a mitad

Posible error de red o timeout. El script detiene al primer error.

El archivo `updated_products.json` contendrá solo los productos procesados hasta ese punto.

## Alternativa Recomendada

Para actualizar productos, usa en su lugar:

- **Paso 11:** `11_vtex_product_format_create` - Formatea productos
- **Paso 12:** `12_vtex_product_create` - Crea nuevos productos
- **Paso 10.1:** `10.1_update_product_description` - Actualiza descripciones

## Integración en Pipeline

Este paso está **deprecado** y no se recomienda su uso en flujos de trabajo estándar.

**Nota de historial:**
- Usado en: Cargas iniciales de catálogo
- Reemplazado por: Pasos 11 y 12 (crear productos nuevos)
- Aplicación actual: Solo mantenimiento manual

## Código Referencia

El script ejecuta aproximadamente:

```python
# 1. Obtener todos los IDs
product_ids = get_all_product_ids(chunk_size=250)

# 2. Para cada ID:
#   - GET el producto
#   - Modifica IsActive = False, IsVisible = False
#   - PUT de vuelta

# 3. Exporta lista a JSON
```

Con pausas de 200ms y 100ms entre requests para rate limiting.
