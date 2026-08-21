# 72_vtex_masterdata_patch_updater

## Descripción

Ejecuta el `PATCH` real contra la API de VTEX Master Data v2 para actualizar parcialmente documentos existentes, a partir de un CSV con columnas `id` y `patch_payload` (JSON string por fila) — el formato exacto que genera [`71_email_masterdata_diff/email_masterdata_diff.py`](../71_email_masterdata_diff/README.md) en `_coincidencias_actualizar.csv`.

```
PATCH https://{accountName}.{environment}.com.br/api/dataentities/{dataEntityName}/documents/{id}
```

Documentación oficial: [Master Data API v2 - PATCH](https://developers.vtex.com/docs/api-reference/master-data-api-v2#patch-/api/dataentities/-dataEntityName-/documents/-id-)

- `dataEntityName` es configurable vía `--data-entity-name`/`-e`, default `CL`.
- El `id` de cada fila se usa como identificador del documento en la URL; el contenido de `patch_payload` (parseado como JSON) se envía tal cual como body del request.
- Soporta `--dry-run` para simular el proceso completo sin hacer ningún `PATCH` real.
- Reintenta automáticamente con backoff exponencial ante HTTP 429, 5xx, timeout o error de red.
- Filas con `id` vacío o `patch_payload` inválido (no es JSON válido) se registran como error de validación y **no** llaman a la API; el resto de filas se sigue procesando normalmente.

## Requisitos

- Python 3.6+
- Dependencias externas: `requests`, `python-dotenv`
- Archivo `.env` en la raíz del proyecto con las credenciales VTEX (ver más abajo)

## Uso

```bash
python3 vtex_masterdata_patch_updater.py <input.csv> [opciones]
```

### Argumentos

- `input.csv` - CSV con columnas `id` y `patch_payload` (ej. salida de `71_email_masterdata_diff`)
- `-e, --data-entity-name <nombre>` - Entidad de Master Data a actualizar (default: `CL`)
- `--id-col <nombre>` - Columna con el id del documento (default: `id`)
- `--payload-col <nombre>` - Columna con el JSON del patch (default: `patch_payload`)
- `-o, --output <archivo>` - CSV de errores (default: `{data_entity_name}_patch_errors_{timestamp}.csv`)
- `-r, --report <archivo>` - Reporte Markdown (default: `{data_entity_name}_patch_report_{timestamp}.md`)
- `--log <archivo>` - Log incremental CSV, una fila por documento procesado (default: `{data_entity_name}_patch_log_{timestamp}.csv`)
- `--delay <segundos>` - Pausa entre requests (default: `0.5`)
- `--timeout <segundos>` - Timeout por request (default: `30`)
- `--retries <n>` - Reintentos para 429/5xx/timeout/error de red (default: `3`)
- `--encoding <encoding>` - Encoding del CSV de entrada (default: `utf-8`)
- `--dry-run` - Simula el proceso sin hacer ningún `PATCH` real

### Ejemplos

```bash
# Ejecución real
python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv

# Simular antes de ejecutar en real (recomendado)
python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv --dry-run

# Entidad y delay personalizados
python3 vtex_masterdata_patch_updater.py resultado_coincidencias_actualizar.csv -e CL --delay 1.0

# Caso de uso real del repo (encadenado con 71_email_masterdata_diff)
python3 72_vtex_masterdata_patch_updater/vtex_masterdata_patch_updater.py \
    resultado_coincidencias_actualizar.csv --dry-run
```

## Formato de Entrada

Requiere que el CSV tenga al menos las columnas indicadas en `--id-col` (default `id`) y `--payload-col` (default `patch_payload`), donde `patch_payload` es un JSON string válido con los campos a actualizar.

**Ejemplo:**
```csv
Nombres,...,Correo,id,patch_payload
VIVIAN,...,vivigrewe@gmail.com,d4cd7902-99bd-483e-997d-d68a4bc9c4db,"{""firstName"": ""VIVIAN"", ""homePhone"": ""3102106732""}"
```

## Formato de Salida

- **CSV de errores** (`{data_entity_name}_patch_errors_{timestamp}.csv`, solo si hubo errores) - Columnas `id`, `patch_payload`, `motivo`. Incluye tanto errores de validación (id vacío, JSON inválido) como errores de la API tras agotar reintentos.
- **Reporte Markdown** (`{data_entity_name}_patch_report_{timestamp}.md`) - Cuenta total de filas, actualizadas/simuladas/con error, configuración usada y tabla de errores (máx. 50 filas mostradas, resto resumido).
- **Log incremental** (`{data_entity_name}_patch_log_{timestamp}.csv`) - Columnas `fila`, `id`, `estado` (`actualizado`/`simulado`/`error`/`id_vacio`/`payload_invalido`), `motivo`. Se escribe **una fila apenas se resuelve cada documento** (con `flush()` + `os.fsync()` inmediatos), a diferencia del CSV de errores y el reporte, que solo se generan al terminar todo el proceso. Ver "Notas/Caveats" para por qué esto importa ante una interrupción abrupta.

## Variables de Entorno

Requeridas en `.env` de la raíz del proyecto:

- `X-VTEX-API-AppKey`
- `X-VTEX-API-AppToken`
- `VTEX_ACCOUNT_NAME`
- `VTEX_ENVIRONMENT` (default: `vtexcommercestable`)

## Lógica de Funcionamiento

1. Carga credenciales VTEX desde `.env` (falla con mensaje claro si falta alguna).
2. Lee el CSV de entrada completo con `csv.DictReader`, valida que existan las columnas `--id-col` y `--payload-col`.
3. Para cada fila:
   - Si `id` está vacío, se registra como error de validación (`"id vacío"`) y se pasa a la siguiente fila sin llamar a la API.
   - Si `patch_payload` no es JSON válido, se registra como error de validación (`"patch_payload inválido: ..."`) y se pasa a la siguiente fila sin llamar a la API.
   - Si `--dry-run`: no se hace ningún request; se imprime `🔍 dry-run` y se cuenta como simulada.
   - Si no: se ejecuta `PATCH {base_url}/api/dataentities/{dataEntityName}/documents/{id}` con el payload parseado como body. Reintenta con backoff exponencial (`2^intento` segundos) en HTTP 429, 5xx, timeout o error de red; éxito (2xx) se cuenta como actualizada, error tras agotar reintentos se registra con el código/motivo.
   - Se respeta `--delay` segundos entre requests reales (no aplica en dry-run ni entre filas con error de validación).
4. Al terminar, genera el CSV de errores (si hay) y el reporte Markdown con las estadísticas finales.

## Notas/Caveats

- **Este script sí ejecuta llamadas HTTP reales** (a diferencia de `71_email_masterdata_diff`, que solo prepara los datos). Usar `--dry-run` primero para validar el CSV antes de una corrida real.
- **Si el proceso se detiene abruptamente (Ctrl+C, `kill`, cierre de terminal), los `PATCH` ya confirmados por VTEX quedan aplicados** — no hay rollback. El CSV de errores y el reporte Markdown solo se escriben al terminar todo el proceso, así que si se interrumpe a mitad de camino **no se generan**; el único rastro persistente es el log incremental (`--log`), que se actualiza fila por fila en tiempo real. No hay modo resume: si vuelves a correr el script con el mismo CSV, reprocesa todas las filas desde el principio. Para el PATCH esto es seguro (es idempotente: reenviar los mismos valores no causa duplicados ni efectos secundarios).
- No hace ningún `GET` previo para verificar el estado actual del documento; confía en que `patch_payload` ya fue armado correctamente (ej. por `71_email_masterdata_diff`) siguiendo la regla de "solo completar campos vacíos, nunca sobreescribir".
- No deduplica ni valida filas repetidas por `id`; si el CSV de entrada tiene el mismo `id` más de una vez, se ejecuta un `PATCH` por cada fila.
- El dominio usado es `https://{accountName}.{environment}.com.br` (Master Data / Catalog API), **no** `api.vtex.com` (ese dominio es específico de la Pricing API usada en `29_vtex_price_fetcher`).
- Solo dependencias externas: `requests`, `python-dotenv` (mismas que el resto de scripts que llaman a la API de VTEX en este repo).
- Pensado para encadenarse después de `71_email_masterdata_diff/email_masterdata_diff.py`, usando su archivo `_coincidencias_actualizar.csv` como input directo.
