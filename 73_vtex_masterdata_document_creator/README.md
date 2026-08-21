# 73_vtex_masterdata_document_creator

## Descripción

Ejecuta el `POST` real contra la API de VTEX Master Data v2 para crear documentos nuevos, a partir de un CSV con la columna `create_payload` (JSON string por fila) — el formato exacto que genera [`71_email_masterdata_diff/email_masterdata_diff.py`](../71_email_masterdata_diff/README.md) en `_crear.csv`.

```
POST https://{accountName}.{environment}.com.br/api/dataentities/{dataEntityName}/documents
```

Documentación oficial: [Master Data API v2 - POST](https://developers.vtex.com/docs/api-reference/master-data-api-v2#post-/api/dataentities/-dataEntityName-/documents)

Es el equivalente en creación de [`72_vtex_masterdata_patch_updater`](../72_vtex_masterdata_patch_updater/README.md) (que ejecuta `PATCH` sobre documentos existentes). A diferencia de ese script, este **no** recibe ni usa una columna `id` — VTEX genera el `id` al crear el documento.

- `dataEntityName` es configurable vía `--data-entity-name`/`-e`, default `CL`.
- El contenido de `create_payload` (parseado como JSON) se envía tal cual como body del `POST`.
- Soporta `--dry-run` para simular el proceso completo sin hacer ningún `POST` real.
- Reintenta automáticamente con backoff exponencial ante HTTP 429, 5xx, timeout o error de red.
- Filas con `create_payload` vacío o inválido (no es JSON válido) se registran como error de validación y **no** llaman a la API; el resto de filas se sigue procesando normalmente.
- No valida duplicados contra Master Data ni hace ningún `GET` previo — esa verificación ya la hace `71_email_masterdata_diff` al construir `_crear.csv` (solo incluye ahí los correos que no existían en el export de Master Data).

## Requisitos

- Python 3.6+
- Dependencias externas: `requests`, `python-dotenv`
- Archivo `.env` en la raíz del proyecto con las credenciales VTEX (ver más abajo)

## Uso

```bash
python3 vtex_masterdata_document_creator.py <input.csv> [opciones]
```

### Argumentos

- `input.csv` - CSV con columna `create_payload` (ej. salida de `71_email_masterdata_diff`)
- `-e, --data-entity-name <nombre>` - Entidad de Master Data donde crear documentos (default: `CL`)
- `--payload-col <nombre>` - Columna con el JSON del documento a crear (default: `create_payload`)
- `-o, --output <archivo>` - CSV de errores (default: `{data_entity_name}_create_errors_{timestamp}.csv`)
- `-r, --report <archivo>` - Reporte Markdown (default: `{data_entity_name}_create_report_{timestamp}.md`)
- `--log <archivo>` - Log incremental CSV, una fila por documento procesado (default: `{data_entity_name}_create_log_{timestamp}.csv`)
- `--delay <segundos>` - Pausa entre requests (default: `0.5`)
- `--timeout <segundos>` - Timeout por request (default: `30`)
- `--retries <n>` - Reintentos para 429/5xx/timeout/error de red (default: `3`)
- `--encoding <encoding>` - Encoding del CSV de entrada (default: `utf-8`)
- `--dry-run` - Simula el proceso sin hacer ningún `POST` real

### Ejemplos

```bash
# Ejecución real
python3 vtex_masterdata_document_creator.py resultado_crear.csv

# Simular antes de ejecutar en real (recomendado)
python3 vtex_masterdata_document_creator.py resultado_crear.csv --dry-run

# Entidad y delay personalizados
python3 vtex_masterdata_document_creator.py resultado_crear.csv -e CL --delay 1.0

# Caso de uso real del repo (encadenado con 71_email_masterdata_diff)
python3 73_vtex_masterdata_document_creator/vtex_masterdata_document_creator.py \
    resultado_crear.csv --dry-run
```

## Formato de Entrada

Requiere que el CSV tenga al menos la columna indicada en `--payload-col` (default `create_payload`), donde el valor es un JSON string válido con el documento completo a crear.

**Ejemplo:**
```csv
Nombres,...,Correo,create_payload
EDUARDO,...,weca75@hotmail.com,"{""email"": ""weca75@hotmail.com"", ""firstName"": ""EDUARDO"", ""lastName"": ""CABASCANGO"", ""document"": ""101952"", ""homePhone"": ""3103417578"", ""birthDate"": ""1947-01-30T00:00:00Z"", ""gender"": ""M"", ""documentType"": ""CE"", ""phone"": """", ""isCorporate"": false, ""isNewsletterOptIn"": true, ""localeDefault"": ""es-CO""}"
```

## Formato de Salida

- **CSV de errores** (`{data_entity_name}_create_errors_{timestamp}.csv`, solo si hubo errores) - Columnas `referencia`, `create_payload`, `motivo`. `referencia` es el `email` del payload si estaba presente, o `fila {n}` si no. Incluye tanto errores de validación (payload vacío, JSON inválido) como errores de la API tras agotar reintentos.
- **Reporte Markdown** (`{data_entity_name}_create_report_{timestamp}.md`) - Cuenta total de filas, creadas/simuladas/con error, configuración usada y tabla de errores (máx. 50 filas mostradas, resto resumido).
- **Log incremental** (`{data_entity_name}_create_log_{timestamp}.csv`) - Columnas `fila`, `referencia`, `estado` (`creado`/`simulado`/`error`/`payload_vacio`/`payload_invalido`), `motivo` (trae el `Id` creado, si VTEX lo devuelve, cuando `estado` es `creado`). Se escribe **una fila apenas se resuelve cada documento** (con `flush()` + `os.fsync()` inmediatos), a diferencia del CSV de errores y el reporte, que solo se generan al terminar todo el proceso. Ver "Notas/Caveats" para por qué esto importa ante una interrupción abrupta.

## Variables de Entorno

Requeridas en `.env` de la raíz del proyecto:

- `X-VTEX-API-AppKey`
- `X-VTEX-API-AppToken`
- `VTEX_ACCOUNT_NAME`
- `VTEX_ENVIRONMENT` (default: `vtexcommercestable`)

## Lógica de Funcionamiento

1. Carga credenciales VTEX desde `.env` (falla con mensaje claro si falta alguna).
2. Lee el CSV de entrada completo con `csv.DictReader`, valida que exista la columna `--payload-col`.
3. Para cada fila:
   - Si `create_payload` está vacío, se registra como error de validación (`"create_payload vacío"`) y se pasa a la siguiente fila sin llamar a la API.
   - Si `create_payload` no es JSON válido, se registra como error de validación (`"create_payload inválido: ..."`) y se pasa a la siguiente fila sin llamar a la API.
   - Si `--dry-run`: no se hace ningún request; se imprime `🔍 dry-run` y se cuenta como simulada.
   - Si no: se ejecuta `POST {base_url}/api/dataentities/{dataEntityName}/documents` con el payload parseado como body. Reintenta con backoff exponencial (`2^intento` segundos) en HTTP 429, 5xx, timeout o error de red; éxito (2xx) se cuenta como creada (se loguea el `Id`/`DocumentId` de la respuesta si el body lo trae), error tras agotar reintentos se registra con el código/motivo.
   - Se respeta `--delay` segundos entre requests reales (no aplica en dry-run ni entre filas con error de validación).
4. Al terminar, genera el CSV de errores (si hay) y el reporte Markdown con las estadísticas finales.

## Notas/Caveats

- **Este script sí ejecuta llamadas HTTP reales** (a diferencia de `71_email_masterdata_diff`, que solo prepara los datos). Usar `--dry-run` primero para validar el CSV antes de una corrida real.
- **Si el proceso se detiene abruptamente (Ctrl+C, `kill`, cierre de terminal), los documentos ya creados por VTEX quedan creados** — no hay rollback. El CSV de errores y el reporte Markdown solo se escriben al terminar todo el proceso, así que si se interrumpe a mitad de camino **no se generan**; el único rastro persistente es el log incremental (`--log`), que se actualiza fila por fila en tiempo real y sirve para saber qué filas (por `referencia`/email) ya se crearon exitosamente antes del corte.
- **A diferencia de `72_vtex_masterdata_patch_updater`, NO es seguro simplemente re-correr el mismo CSV tras una interrupción**: este script no verifica si el documento ya existe antes de crear, así que reprocesar filas que ya se habían creado exitosamente genera **documentos duplicados**. Antes de reintentar, usa el log incremental (o vuelve a exportar Master Data con `69_vtex_masterdata_search_exporter` y re-corre `71_email_masterdata_diff`) para filtrar del CSV de entrada las filas cuya `referencia` ya quedó en `estado=creado`.
- No hace ningún `GET` previo ni verifica duplicados contra Master Data; confía en que `_crear.csv` ya fue filtrado correctamente por `71_email_masterdata_diff` (solo contiene correos que no existían en el export de Master Data usado para la comparación).
- La documentación pública de VTEX no especifica el formato exacto de la respuesta del `POST` (si trae `Id`/`DocumentId`); el script es tolerante a esto — si la respuesta es JSON y trae alguno de esos campos lo muestra en consola, si no solo reporta éxito/fracaso por código HTTP.
- El dominio usado es `https://{accountName}.{environment}.com.br` (Master Data / Catalog API), **no** `api.vtex.com` (ese dominio es específico de la Pricing API usada en `29_vtex_price_fetcher`).
- Solo dependencias externas: `requests`, `python-dotenv` (mismas que el resto de scripts que llaman a la API de VTEX en este repo).
- Pensado para encadenarse después de `71_email_masterdata_diff/email_masterdata_diff.py`, usando su archivo `_crear.csv` como input directo.
