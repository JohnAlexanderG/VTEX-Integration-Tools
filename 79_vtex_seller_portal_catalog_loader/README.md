# 79 — Carga masiva de productos Seller Portal

Crea productos propios con sus SKUs, imágenes, precio y stock en una cuenta **VTEX Seller Portal**
a partir de un Excel o CSV. Usa la [Catalog API - Seller Portal](https://developers.vtex.com/docs/api-reference/catalog-api-seller-portal),
que está en **beta**.

## Por qué existe

El Seller Portal **no tiene importación por hoja de cálculo**. La planilla de *Catálogo > Importación
y exportación* es del Admin clásico. Un seller solo puede crear productos propios uno por uno desde la
interfaz o por API. Este script hace esa carga por API desde una planilla.

> Para productos que el marketplace ya comparte con el seller no hace falta esta herramienta.
> Se importan desde *Productos compartidos > Disponibles > Importar seleccionados*.

## Requisitos de la cuenta seller

1. **Credenciales de la cuenta del seller**, no del marketplace. Se crean en Seller Portal >
   avatar > *Configuración de la cuenta > Claves de aplicación*.
2. La API key debe tener un **rol personalizado**; ningún rol predefinido aplica. Sin el recurso
   correspondiente, la API responde 403. El rol necesita:
   - **CatalogV2 > Management**: Product Read, Product Write, Brand Read, Brand Write, Category Read
   - **Pricing**: lectura y escritura de precios
   - **Logistics**: inventario y lectura de warehouses
3. **Categorías**: las define el marketplace. La ruta de cada producto debe existir en el árbol de
   la cuenta seller.
4. Límite de 100 mil productos por cuenta.

En WebOps, el seller es un **tenant de tipo Seller Portal**. Un admin carga estas credenciales en
*Configuración*.

## Archivo de entrada

Una fila por SKU. Las filas con el mismo `product_external_id` son SKUs del mismo producto.
La plantilla está en `webapp/backend/templates/step_79_input_file.xlsx`, con una hoja de instrucciones.

| Columna | Obligatoria | Descripción |
|---|---|---|
| `product_external_id` | Sí | Código único del producto. Sirve para no duplicar al re-ejecutar |
| `product_name` | Sí | Máximo 150 caracteres |
| `product_description` | No | |
| `brand` | Sí | Nombre de la marca (sin distinguir acentos ni mayúsculas) |
| `category_path` | Sí* | Ej. `Hogar/Cocina/Ollas` (también acepta `>`). *O `category_id` |
| `product_status` | No | `active` (default) o `inactive` |
| `slug` | No | Ej. `/olla-presion-6l`. Si se omite, se genera desde el nombre |
| `sku_external_id` | Sí | Código único del SKU |
| `sku_name` | Sí | Máximo 150 caracteres |
| `ean`, `manufacturer_code` | No | |
| `sku_active` | No | `true` (default) / `false` |
| `weight` | Sí | Gramos (entero) |
| `width`, `height`, `length` | Sí | cm |
| `spec:<Nombre>` | Si hay variaciones | Una columna por variación (`spec:Color`, `spec:Talla`). Obligatoria si el producto tiene más de un SKU; la combinación no se puede repetir |
| `attr:<Nombre>` | No | Atributos del producto para filtros (`attr:Material`) |
| `image_urls` | Sí | URLs **https** públicas separadas por `\|`. Al menos una por producto |
| `price`, `list_price`, `cost_price` | No | Vacío = no se toca el precio |
| `stock` | No | Entero ≥ 0. Vacío = no se toca el stock |

## Flujo

1. **Validación local.** Revisa obligatorios, números, longitudes, URLs https, SKUs duplicados y
   consistencia de specs. Si un producto tiene un error, no se envía ninguno de sus SKUs.
2. **Referencias.** Lee `GET /category-tree` y `GET /brands` y resuelve los nombres sin acentos.
   Una categoría inexistente marca la fila como error. Una marca inexistente también, salvo que se
   use `--create-missing-brands`.
3. **Imágenes.** Descarga cada URL (máximo 10 MB, jpg/png/webp/gif) y la sube a
   `vtex.catalog-images`, porque la API solo acepta imágenes de `{cuenta}.vtexassets.com`.
   - El nombre del archivo es `sha1(url)`, así que al re-ejecutar la API responde 409 y se
     reutiliza la imagen.
   - El token local se obtiene con `apptoken/login`.
   - El producto lleva `images` como objetos `{id, url, alt}`; cada SKU las referencia por **URL
     completa** de vtexassets (si la fila no trae imágenes propias, hereda todas las del producto).
4. **Producto.** `GET /products/external-id={id}`:
   - Si no existe → `POST /products` (producto y todos sus SKUs en una sola llamada).
   - Si existe → se omite, o se hace `PUT /products/{id}` con `--update-existing`. El PUT conserva
     los SKU ids, el `origin`, el slug actual y los SKUs que no vienen en el archivo.
5. **Precio y stock.** Con los SKU ids creados:
   - `PUT api.vtex.com/{cuenta}/pricing/prices/{skuId}`
   - `PUT /api/logistics/pvt/inventory/skus/{skuId}/warehouses/{wh}`. El warehouse sale de
     `--warehouse-id` o es el primero activo de la cuenta.

## Uso

```bash
# 1. Verificar credenciales y permisos de lectura de cada API
python3 79_vtex_seller_portal_catalog_loader/seller_portal_catalog_loader.py productos.xlsx --check

# 2. Simular: valida, resuelve categorías/marcas, consulta existentes y genera los payloads (sin escribir)
python3 79_vtex_seller_portal_catalog_loader/seller_portal_catalog_loader.py productos.xlsx --dry-run

# 3. Carga real
python3 79_vtex_seller_portal_catalog_loader/seller_portal_catalog_loader.py productos.xlsx

# Actualizar existentes y crear marcas faltantes
python3 79_vtex_seller_portal_catalog_loader/seller_portal_catalog_loader.py productos.xlsx --update-existing --create-missing-brands

# Con credenciales de otra cuenta y sin tocar stock
python3 79_vtex_seller_portal_catalog_loader/seller_portal_catalog_loader.py productos.csv --env-file .env.glam --skip-stock
```

| Flag | Descripción |
|---|---|
| `--check` | Solo prueba credenciales y permisos de lectura (catálogo, pricing, logistics, token de imágenes) |
| `--dry-run` | Solo lecturas; genera `seller_portal_payloads_*.json` |
| `--update-existing` | PUT de productos que ya existen |
| `--create-missing-brands` | Crea las marcas que falten |
| `--skip-price` / `--skip-stock` | No aplica precio / stock |
| `--warehouse-id` | Warehouse para el stock |
| `--sheet` | Hoja del Excel (default: la primera) |
| `--delay` / `--timeout` | Segundos entre escrituras (default 1.0) / timeout por request |
| `--output-dir` | Directorio de salida (default `seller_portal_output`) |
| `--env-file` | `.env` alternativo |

Reintenta con backoff exponencial ante HTTP 429, 5xx o errores de red.

## Salidas (`--output-dir`)

- `seller_portal_results_{ts}.csv`: una fila por SKU con `product_id`, `sku_id` y el estado de cada
  etapa (`product_status`: created / updated / skipped_exists / dry_run_* / failed / invalid).
- `seller_portal_errors_{ts}.csv`: filas originales con el motivo, listas para corregir y re-ejecutar.
- `seller_portal_image_map_{ts}.csv`: URL de origen → URL en vtexassets.
- `seller_portal_payloads_{ts}.json`: solo en dry-run.
- `seller_portal_report_{ts}.md`: resumen.

El proceso termina con exit 1 solo si hubo errores y ningún producto se procesó bien.

## Pendiente de validar con una cuenta real

La documentación de VTEX no cubre estos puntos. Hay que confirmarlos con una corrida de 1 producto
en estado `inactive`:

- El nombre del campo multipart en `catalog-images/save` (el script usa `file`).
- Que las APIs de Pricing y Logistics respondan en cuentas Seller Portal con la misma API key.
- Si `categoryIds` debe llevar solo la hoja (el script envía solo la hoja) o toda la ruta.
