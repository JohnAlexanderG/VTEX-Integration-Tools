# 78_vtex_masterdata_document_deleter

## Descripción

Ejecuta `DELETE` real contra la API de VTEX Master Data para eliminar documentos, a partir de un CSV con columna `id` — el formato que genera [`69_vtex_masterdata_search_exporter`](../69_vtex_masterdata_search_exporter/README.md).

```
DELETE https://{accountName}.{environment}.com.br/api/dataentities/{dataEntityName}/documents/{id}
```

Documentación oficial: [Master Data API v2 - DELETE](https://developers.vtex.com/docs/api-reference/master-data-api-v2#delete-/api/dataentities/-dataEntityName-/documents/-id-)

> ⚠️ **La eliminación es IRREVERSIBLE.** Exporta siempre la entidad completa (`--fields _all`) antes de borrar; ese CSV es tu único respaldo.

## ¿En qué cuenta se borra?

El script borra en la cuenta indicada por `VTEX_ACCOUNT_NAME`, y lo imprime al inicio junto con el origen de las credenciales:

| Dónde se ejecuta | Credenciales que usa |
|---|---|
| **WebOps** | Las del **tenant del usuario logueado** (Configuración). El `.env` del servidor no se usa para la cuenta. |
| CLI con `--env-file` | Las del archivo indicado. |
| CLI sin `--env-file` | Las del `.env` de la raíz del proyecto. |

Protecciones:
- `--data-entity-name` es obligatorio (sin default).
- En modo real exige `--confirm-account` igual a la cuenta destino.
- En la WebOps, el modo real solo lo pueden ejecutar **administradores del tenant o superadmin**, el backend valida el nombre de la cuenta antes de crear el job y la UI pide confirmación en un modal.

## Flujo recomendado

1. **Exportar** (respaldo): herramienta "Exportar Master Data" (69) con campos `_all`; descarga el CSV.
2. **Simular**: esta herramienta con `--dry-run` sobre ese CSV; revisa el conteo de ids únicos.
3. **Borrar**: sin `--dry-run` y con `--confirm-account <cuenta>`.

Re-ejecutar es seguro: los documentos que ya no existen (HTTP 404) se cuentan como "no existían".

## Uso (CLI)

```bash
python3 vtex_masterdata_document_deleter.py <input.csv> -e <ENTIDAD> [opciones]
```

### Argumentos

- `input.csv` - CSV con columna `id` (ej. salida de 69)
- `-e, --data-entity-name <sigla>` - Entidad de Master Data (**obligatorio**)
- `--id-col <nombre>` - Columna con el id (default: `id`)
- `--confirm-account <cuenta>` - Obligatorio en modo real; debe coincidir con `VTEX_ACCOUNT_NAME`
- `--env-file <archivo>` - `.env` alternativo con credenciales (solo CLI)
- `-o, --output` / `-r, --report` / `--log` - CSV de errores, reporte Markdown y log incremental
- `--delay <seg>` (default `0.2`), `--timeout <seg>` (default `30`), `--retries <n>` (default `3`)
- `--encoding <enc>` - Encoding del CSV (default `utf-8`)
- `--dry-run` - Simula sin hacer ningún `DELETE`

### Ejemplos

```bash
# Respaldo + simulación + borrado real en otra cuenta
python3 69_vtex_masterdata_search_exporter/vtex_masterdata_search_exporter.py -e CL --fields _all --env-file .env.otra -o respaldo_CL.csv
python3 78_vtex_masterdata_document_deleter/vtex_masterdata_document_deleter.py respaldo_CL.csv -e CL --env-file .env.otra --dry-run
python3 78_vtex_masterdata_document_deleter/vtex_masterdata_document_deleter.py respaldo_CL.csv -e CL --env-file .env.otra --confirm-account otra
```

## Salidas

- `{entidad}_delete_log_{timestamp}.csv` - una fila por id (`simulado`, `eliminado`, `no_existe`, `error`), escrita a disco en cada paso
- `{entidad}_delete_errors_{timestamp}.csv` - solo si hubo errores
- `{entidad}_delete_report_{timestamp}.md` - resumen y configuración

Código de salida `1` si hubo errores o si falta la confirmación de cuenta.
