# 69_vtex_masterdata_search_exporter

## Descripcion

Consulta la API de VTEX Master Data (`dataentities/scroll`) para una entidad dada (ej. `CL` -
clientes) y exporta **todos** los registros a un `.csv`, sin importar cuantos sean. Se usa el
endpoint `/scroll` (en vez de `/search`) porque VTEX limita `/search` a un maximo de 10.000
documentos; para colecciones mas grandes, o para traer la coleccion completa, VTEX exige `/scroll`.
El script implementa autopaginacion por token: en el primer request pide `_size` registros (max.
1000) y recibe un token de continuacion en el header `X-VTEX-MD-TOKEN`; con ese token sigue
pidiendo paginas hasta que la respuesta viene vacia.

**Caso de uso:** exportar el catalogo completo de una entidad de Master Data (clientes, direcciones,
cualquier entidad custom) a CSV para analisis, migracion o carga en otra herramienta, sin tener que
armar manualmente la paginacion contra la API.

## Requisitos

- Python 3.6+
- `requests`, `python-dotenv` (dependencias del venv raiz del proyecto)
- Credenciales VTEX en el `.env` de la raiz del proyecto:
  - `X-VTEX-API-AppKey`
  - `X-VTEX-API-AppToken`
  - `VTEX_ACCOUNT_NAME`
  - `VTEX_ENVIRONMENT` (default: `vtexcommercestable`)

## Uso

```bash
python3 vtex_masterdata_search_exporter.py --data-entity-name <dataEntityName> [opciones]
```

### Argumentos

| Argumento | Tipo | Descripcion |
|-----------|------|-------------|
| `-e`, `--data-entity-name` | Requerido | Nombre de la entidad de Master Data a consultar (ej. `CL`) |
| `-o`, `--output` | Opcional | Archivo CSV de salida (default: `{dataEntityName}_search_{timestamp}.csv`) |
| `-r`, `--report` | Opcional | Archivo de reporte Markdown de salida (default: `{dataEntityName}_search_report_{timestamp}.md`) |
| `--fields` | Opcional | Lista de campos separada por comas para `_fields` (default: set predefinido de campos de cliente, ver abajo) |
| `--page-size` | Opcional | Registros por pagina, `_size` (default: `1000`, el maximo que acepta VTEX) |
| `--schema` | Opcional | Nombre del schema (`_schema`) de la entidad. Algunas cuentas de VTEX lo exigen en `/scroll` al usar `_fields` (ver Notas/Caveats) |
| `--delay` | Opcional | Pausa en segundos entre paginas (default: `0.5`) |
| `--timeout` | Opcional | Timeout por request en segundos (default: `30`) |
| `--retries` | Opcional | Reintentos ante 429, 5xx, timeout o error de red (default: `3`) |

### Ejemplos

```bash
# Basico, con los campos por defecto
python3 vtex_masterdata_search_exporter.py --data-entity-name CL

# Con archivo de salida y tamano de pagina personalizados
python3 vtex_masterdata_search_exporter.py -e CL -o clientes.csv --page-size 1000

# Solo algunos campos
python3 vtex_masterdata_search_exporter.py -e CL --fields id,email,firstName,lastName

# Con mas delay entre paginas (entidades grandes / rate limit ajustado)
python3 vtex_masterdata_search_exporter.py -e CL --delay 1.0 --retries 5

# Si la cuenta exige _schema para usar _fields en /scroll
python3 vtex_masterdata_search_exporter.py -e CL --schema clientes-v2
```

Genera:
- `{dataEntityName}_search_{timestamp}.csv`
- `{dataEntityName}_search_report_{timestamp}.md`

## Campos por defecto (`_fields`)

Si no se pasa `--fields`, se consulta este set (pensado para la entidad de clientes `CL`):

```
id, accountId, accountName, dataEntityId, isCorporate, tradeName, homePhone, phone, email,
userId, firstName, lastName, document, isNewsletterOptIn, localeDefault, birthDate,
businessPhone, corporateDocument, corporateName, documentType, gender, birthDateMonth,
createdBy, createdIn, updatedBy, updatedIn
```

## Formatos de Salida

### {dataEntityName}_search_{timestamp}.csv

Una fila por registro de la entidad, con los campos solicitados como columnas (en el mismo orden
de `--fields`/default). Si un registro no trae un campo, la celda queda vacia.

### {dataEntityName}_search_report_{timestamp}.md

Reporte markdown con:
- Cuenta y ambiente VTEX consultados, fecha de generacion.
- Resumen: metodo de paginacion (`/scroll`), registros exportados, paginas consultadas, tamano de
  pagina (`_size`), duracion total. `/scroll` no expone un total anticipado de registros (a
  diferencia de `/search`); el conteo final solo se conoce al terminar de iterar.
- Configuracion usada (`--page-size`, `--delay`, `--timeout`, `--retries`, `--schema`, campos, ruta
  del CSV).
- Incidencias durante la paginacion, si las hubo (ej. no se recibio el header `X-VTEX-MD-TOKEN` y
  no fue posible continuar).

## Logica de Funcionamiento

1. Cargar credenciales VTEX desde `.env` (mismo patron que `59_vtex_sku_service_exporter`).
2. Pedir la primera pagina: `GET /scroll?_fields=...&_size={page_size}` (+ `_schema` si se paso
   `--schema`). Sin `_token`.
3. Leer el header de respuesta `X-VTEX-MD-TOKEN` y guardarlo como token de continuacion.
4. Acumular los registros de la pagina.
5. Pedir la siguiente pagina solo con `GET /scroll?_token={token}` (ya no hace falta reenviar
   `_fields` ni `_size`), actualizando el token con el que devuelva cada respuesta.
6. Repetir hasta que una pagina venga vacia (fin normal de la coleccion).
7. Reintentar automaticamente ante `429`, `5xx`, timeout o error de red, con backoff exponencial
   (`BACKOFF_FACTOR ** intento`).
8. Exportar todos los registros acumulados a CSV y generar el reporte Markdown con el resumen de
   la ejecucion.

## Notas/Caveats

- Se usa `/scroll` en vez de `/search` porque VTEX responde `HTTP 400` en `/search` a partir del
  registro 10.000 (`"Para consultar acima de dez mil documentos utilize a rota /scroll"`). `/scroll`
  no tiene ese limite.
- `--page-size` (`_size`) maximo permitido por VTEX es 1000.
- El token de `/scroll` expira a los 20 minutos de inactividad; cada request hecho con el token
  reinicia el temporizador. Con el `--delay` por defecto (paginas cada fracción de segundo) no
  deberia expirar salvo reintentos muy prolongados.
- Segun la documentacion de VTEX, `_schema` es requerido en `/scroll` cuando se usa `_fields` o
  `_where`. Muchas cuentas funcionan igual sin especificarlo (usan el schema por defecto); si VTEX
  devuelve error pidiendo el schema, volver a correr con `--schema <nombre>`.
- Si no se recibe el header `X-VTEX-MD-TOKEN` en una respuesta con datos, el script no puede seguir
  paginando: registra la incidencia en el reporte y corta el loop, dejando en el CSV lo acumulado
  hasta ese punto.
- El script usa el dominio de cuenta (`https://{account}.{environment}.com.br`), no el host global
  `api.vtex.com`.
- No requiere `--dry-run`: al ser una consulta de solo lectura (`GET`), correrlo no modifica datos
  en VTEX.
