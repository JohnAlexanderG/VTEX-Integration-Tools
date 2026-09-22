# VTEX Product & SKU Deleter

## Descripción

Elimina masivamente SKUs y Productos completos en VTEX, en dos fases estrictas y en el orden que exige la propia API de VTEX:

1. **Fase 1**: `DELETE /api/catalog/pvt/stockkeepingunit/{skuId}` para todos los SKUs del CSV de entrada.
2. **Fase 2**: `DELETE /api/catalog/pvt/product/{productId}` **solo** para los productos cuyos SKUs (todos los listados en el CSV para ese `ProductId`) terminaron en éxito o ya no existían (HTTP 404) en la Fase 1.

Si algún SKU de un producto no se pudo eliminar, ese producto se **omite** en la Fase 2 (no se llama a la API) y queda registrado para revisión manual — evita quemar rate limit disparando un error ya esperado por VTEX ("el producto todavía tiene SKUs").

> **Nota sobre estos endpoints**: no aparecen en la referencia pública de la Catalog API (`https://developers.vtex.com/docs/api-reference/catalog-api`), que solo documenta DELETE para especificaciones, archivos/imágenes, EANs, servicios, kits y colecciones. Son endpoints de la API privada/legacy de catálogo (prefijo `/pvt/`), funcionales con las credenciales correctas, y son los que VTEX Soporte recomienda para este tipo de limpieza masiva por lotes.

## Features

- Ejecución concurrente con rate limiting adaptativo (token bucket + backoff en HTTP 429), igual motor que `63_vtex_product_specification_delete`.
- Gate estricto de dos fases: un producto nunca se intenta borrar si todavía tiene un SKU pendiente.
- HTTP 404 se trata como "ya no existe" (éxito idempotente), no como fallo — así una segunda corrida sobre el mismo archivo no bloquea productos ya limpiados en una corrida anterior.
- `--dry-run` obligatorio de facto: sin él y sin `--confirm-delete`, el script se niega a ejecutar.
- Reportes separados por fase (JSON + CSV) y un reporte Markdown consolidado con el mensaje de error exacto de cada fallo.

## Requisitos

Variables de entorno en `.env` en la raíz del proyecto (no se requieren con `--dry-run`):

| Variable | Descripción |
|----------|-------------|
| `X-VTEX-API-AppKey` | AppKey con permisos de Catálogo |
| `X-VTEX-API-AppToken` | AppToken con permisos de Catálogo |
| `VTEX_ACCOUNT_NAME` | Nombre de la cuenta VTEX |
| `VTEX_ENVIRONMENT` | Entorno VTEX (default: `vtexcommercestable`) |

## Uso

```bash
# 1. Siempre simular primero
python3 vtex_product_sku_deleter.py ids.csv --dry-run

# 2. Ejecución real (requiere --confirm-delete explícito)
python3 vtex_product_sku_deleter.py ids.csv --confirm-delete

# 3. Con workers/rps personalizados (lotes grandes)
python3 vtex_product_sku_deleter.py ids.csv --confirm-delete --workers 8 --rps 8

# 4. Probar solo un subconjunto antes del lote completo
python3 vtex_product_sku_deleter.py ids.csv --confirm-delete --limit 2
```

## Formato de Entrada

CSV con una fila por SKU. Varios SKUs pueden compartir el mismo `ProductId`:

```csv
SkuId,ProductId
123456,987
123457,987
123458,988
```

Los encabezados se detectan sin distinguir espacios/mayúsculas (`SkuId`, `SKU ID`, `Sku Id` son equivalentes; igual para `ProductId`).

## Formato de Salida

Todos los archivos se escriben en `--output-dir` (default: directorio actual) con el prefijo `--output-prefix` (default: timestamp):

- `{prefix}_skus_successful.json` / `{prefix}_skus_failed.json` / `.csv`
- `{prefix}_products_successful.json` / `{prefix}_products_failed.json` / `.csv`
- `{prefix}_rows_skipped.json` / `.csv` — filas del CSV con `SkuId`/`ProductId` vacío o duplicado
- `{prefix}_products_skipped.json` / `.csv` — productos omitidos en Fase 2 por tener un SKU sin eliminar
- `{prefix}_deletion_report.md` — reporte consolidado con ambas fases

## Cómo Funciona

1. Se lee el CSV y se construye: la lista de SKUs (deduplicada), y un mapa `ProductId → [SkuId, ...]`.
2. **Fase 1**: se ejecuta `DELETE /api/catalog/pvt/stockkeepingunit/{skuId}` para cada SKU único, con concurrencia y rate limiting.
3. Se calcula qué productos son elegibles: solo aquellos donde **todos** sus SKUs terminaron en éxito o 404 en la Fase 1. Los demás se marcan `skipped`.
4. **Fase 2**: se ejecuta `DELETE /api/catalog/pvt/product/{productId}` únicamente para los productos elegibles.
5. Se exportan los resultados de ambas fases y se genera el reporte Markdown.

## Parámetros de Configuración

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--workers` | 5 | Workers concurrentes por fase |
| `--rps` | 5.0 | Límite de requests por segundo (compartido entre workers) |
| `--timeout` | 30 | Timeout por request (segundos) |
| `--limit` | Sin límite | Procesa solo las primeras N filas del CSV |
| `--confirm-delete` | — | Obligatorio para ejecutar el borrado real |
| `--dry-run` | — | Simula sin ejecutar ningún DELETE |

Valores conservadores por defecto porque los lotes típicos son pequeños (decenas de IDs). Para lotes más grandes, subir `--workers`/`--rps` gradualmente y observar el reporte de rate limiting en consola.

## Rate Limiting

Igual mecanismo que `63_vtex_product_specification_delete`: un `TokenBucket` compartido entre workers limita el RPS objetivo; ante HTTP 429 se reduce el RPS a la mitad y se restaura gradualmente tras 60s sin nuevos 429. Los códigos `408/409/425/429/500/502/503/504` se reintentan con backoff exponencial (hasta 5 intentos); `404` se trata como éxito idempotente; cualquier otro código se registra como fallo definitivo con el cuerpo de la respuesta.

## Ejemplo Completo

```bash
# Dry-run con reporte en carpeta dedicada
python3 vtex_product_sku_deleter.py homesentry_ids.csv --dry-run \
    --output-dir reportes/2026-09-22 --output-prefix homesentry

# Revisar reportes/2026-09-22/homesentry_deletion_report.md, confirmar que
# los productos/SKUs a borrar son los esperados, y luego:
python3 vtex_product_sku_deleter.py homesentry_ids.csv --confirm-delete \
    --output-dir reportes/2026-09-22 --output-prefix homesentry_real
```

## Códigos de Respuesta Esperados

| Código | Significado |
|--------|-------------|
| 200/202/204 | Eliminado correctamente |
| 404 | Ya no existe (tratado como éxito idempotente) |
| 409 | Conflicto — normalmente hay dependencias vigentes (SKU con pedidos/inventario, o producto que aún tiene SKUs no incluidos en el CSV) |
| 429 | Rate limit — se reintenta automáticamente con backoff |
| 500/502/503/504 | Error transitorio del servidor — se reintenta automáticamente |

## Seguridad

- **Siempre corra `--dry-run` primero** y revise el reporte antes de la ejecución real.
- `--confirm-delete` es obligatorio para cualquier corrida real — el script se niega a ejecutar sin él.
- **Esta operación es irreversible.** VTEX no ofrece una forma de recuperar un SKU o Producto eliminado por esta vía.
- Antes de borrar, exporte/respalde los datos del producto (`GET /api/catalog/pvt/product/{productId}` y sus SKUs) si existe alguna duda.
- Como alternativa reversible mientras se confirma el borrado definitivo, puede desactivar los SKUs de inmediato (`IsActive=false`) con `20_vtex_update_sku_from_csv/vtex_update_sku_from_csv.py`, sin perder los datos.
- Pruebe primero contra uno o dos IDs de bajo riesgo (o un ambiente sandbox) antes de correr el lote completo.

## Notas Importantes

- La eliminación dispara reindexación automática en VTEX; puede tardar algunos minutos en reflejarse en el storefront y en la búsqueda.
- Un error persistente al borrar un producto normalmente indica que aún existen dependencias — comparta el mensaje de error exacto (incluido en el reporte y en el CSV de fallos) con VTEX Soporte si necesita ayuda.
