# VTEX SKU Service Exporter

Exporta servicios SKU consultando directamente el endpoint privado de Catalog API:

```bash
GET https://{accountName}.{environment}.com.br/api/catalog/pvt/skuservice/{skuServiceId}
```

El script recorre un rango de `skuServiceId` y genera un archivo JSON con metadatos, resumen de conteos, respuestas encontradas y errores. Por defecto consulta los IDs `1` a `50` inclusive.

## Dependencias

Desde la raiz del repositorio:

```bash
pip install requests python-dotenv
```

## Credenciales

Configura las credenciales en el archivo `.env` de la raiz del proyecto o como variables de entorno:

```bash
X-VTEX-API-AppKey=tu_app_key_aqui
X-VTEX-API-AppToken=tu_app_token_aqui
VTEX_ACCOUNT_NAME=nombre_cuenta_vtex
VTEX_ENVIRONMENT=vtexcommercestable
```

`VTEX_ENVIRONMENT` es opcional y usa `vtexcommercestable` por defecto.

El archivo JSON de salida no incluye app keys, tokens ni valores de credenciales.

## Uso

Consultar IDs `1` a `50` y escribir solo servicios encontrados o fallos relevantes:

```bash
python3 59_vtex_sku_service_exporter/vtex_sku_service_exporter.py sku_services.json
```

Consultar un rango ampliado e incluir tambien los `404` en `results`:

```bash
python3 59_vtex_sku_service_exporter/vtex_sku_service_exporter.py output/sku_services_1_100.json --start-id 1 --end-id 100 --include-not-found
```

Opciones disponibles:

```bash
python3 59_vtex_sku_service_exporter/vtex_sku_service_exporter.py --help
```

Argumentos principales:

- `output_json`: ruta del JSON de salida.
- `--start-id`: primer ID a consultar. Default: `1`.
- `--end-id`: ultimo ID a consultar, inclusive. Default: `50`.
- `--delay`: pausa entre requests. Default: `0.6` segundos.
- `--timeout`: timeout por request. Default: `30` segundos.
- `--retries`: reintentos para `429`, `5xx`, timeout o error de red. Default: `3`.
- `--include-not-found`: incluye respuestas `404` dentro de `results`. Sin esta opcion, los `404` solo quedan contados en `summary.notFound`.

## Formato de salida

Ejemplo abreviado:

```json
{
  "metadata": {
    "generatedAt": "2026-05-06T12:00:00+00:00",
    "accountName": "mi-cuenta",
    "environment": "vtexcommercestable",
    "endpointTemplate": "/api/catalog/pvt/skuservice/{skuServiceId}",
    "startId": 1,
    "endId": 50
  },
  "summary": {
    "totalRequested": 50,
    "found": 1,
    "notFound": 49,
    "failed": 0
  },
  "results": [
    {
      "skuServiceId": 1,
      "statusCode": 200,
      "found": true,
      "response": {
        "Id": 1,
        "Name": "Servicio de ejemplo"
      },
      "error": ""
    }
  ]
}
```

## Comportamiento ante errores

- `200`: parsea la respuesta JSON y la agrega a `results` con `found: true`.
- `404`: no aborta la ejecucion; incrementa `summary.notFound` y continua.
- `429` y `5xx`: reintenta con backoff exponencial hasta agotar `--retries`.
- Timeouts, errores de red o respuestas no JSON: se registran como fallo con `found: false`, `response: null` y un mensaje en `error`.

Si falta `VTEX_ACCOUNT_NAME`, `X-VTEX-API-AppKey` o `X-VTEX-API-AppToken`, el script termina con codigo `1` antes de hacer requests.
