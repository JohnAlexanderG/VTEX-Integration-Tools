# 63. VTEX Product Specification Delete

Elimina especificaciones de producto en VTEX a partir de:

1. Un CSV de productos permitidos.
2. Un CSV de especificaciones de producto exportado desde VTEX.

El modo por defecto es seguro y selectivo: borra solo los pares `Product ID` + `Specification IDs` listados en el CSV de especificaciones.

## Distinción importante

Este script elimina asignaciones/valores de especificaciones en productos usando endpoints de producto. No elimina la definición del field de especificación a nivel categoría.

Por eso, un borrado exitoso para un producto específico no prueba que el nombre del field esté libre para crear una SKU spec con el mismo nombre. Antes de usar `62_vtex_sku_specs_loader/vtex_sku_specs_loader.py` con el mismo nombre, refresque el export de product specs o confirme por API que la categoría ya no reporta ese field como product spec.

## Requisitos

El script lee credenciales VTEX desde `.env` en la raiz del repositorio:

```bash
X-VTEX-API-AppKey=...
X-VTEX-API-AppToken=...
VTEX_ACCOUNT_NAME=...
VTEX_ENVIRONMENT=vtexcommercestable
```

En `--dry-run` no se ejecutan requests HTTP. Si no hay `.env`, el dry-run igual genera salidas con el endpoint plantilla para revision.

## CSV de productos

Columnas requeridas:

- `Product ID`
- `SKU reference code`

Ejemplo:

```csv
Product ID,SKU reference code
123,ABC-001
456,ABC-002
```

El CSV funciona como lista permitida. Una especificacion cuyo producto no este aqui se omite y queda registrada en los reportes.

## CSV de especificaciones

Columnas requeridas para construir tareas:

- `Product ID`
- `Product reference code`
- `Specification IDs`

Columnas esperadas si el archivo viene del export administrativo VTEX:

- `Field ID`
- `Field name`

`Field ID` y `Field name` se preservan en los reportes si existen. Si `Product ID` viene vacio, el script intenta resolverlo con `Product reference code` contra la columna `SKU reference code` del CSV de productos.

`Specification IDs` puede contener multiples valores separados por saltos de linea, `;` o `|`. No se separa por coma.

## Modos

### `--mode listed` (default)

Usa:

```text
DELETE /api/catalog/pvt/product/{productId}/specification/{specificationId}
```

Crea una tarea unica por cada par `(Product ID, Specification ID)` permitido.

### `--mode all`

Usa:

```text
DELETE /api/catalog/pvt/product/{productId}/specification
```

Este endpoint elimina todas las especificaciones del producto. Por seguridad requiere `--confirm-delete-all`. En este modo `Specification IDs` se ignora y se crea una sola tarea por `Product ID` unico permitido.

## Ejemplos

Revisar primero sin ejecutar DELETE:

```bash
python3 vtex_product_specification_delete.py productos.csv product-specs.csv --dry-run
```

Ejecutar borrado selectivo:

```bash
python3 vtex_product_specification_delete.py productos.csv product-specs.csv --workers 5 --rps 10
```

Revisar borrado total de especificaciones por producto:

```bash
python3 vtex_product_specification_delete.py productos.csv product-specs.csv --mode all --confirm-delete-all --dry-run
```

Ejecutar borrado total solo despues de revisar el dry-run:

```bash
python3 vtex_product_specification_delete.py productos.csv product-specs.csv --mode all --confirm-delete-all
```

## Salidas

El script genera archivos timestamped en `--output-dir`:

- `*_successful.json`
- `*_failed.json`
- `*_failed.csv`
- `*_skipped.json`
- `*_skipped.csv`
- `*_deletion_report.md`

Los JSON se escriben en UTF-8 con `ensure_ascii=False` e indentacion de 4 espacios.

## Seguridad operativa

- Ejecutar siempre un `--dry-run` antes de operar contra VTEX.
- Revisar `*_successful.json` del dry-run para confirmar endpoints y conteos.
- Mantener `--mode listed` salvo que se quiera borrar todas las especificaciones de cada producto.
- No ejecutar contra una cuenta real sin confirmar que el `.env` apunta al ambiente correcto.
