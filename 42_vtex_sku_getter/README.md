# 42_vtex_sku_getter

## Descripción

Consulta SKUs individuales en la API privada de VTEX y exporta las respuestas. Lee un CSV generado por `41_generate_sku_range`, consulta cada SKU contra el endpoint de catálogo de VTEX, descarta resultados 404 y exporta los datos restantes en formato JSON.

## Requisitos

- Python 3.7+
- Dependencias: `requests`, `python-dotenv`

Instalar con:
```bash
pip install requests python-dotenv
```

### Variables de Entorno (.env)

Archivo `.env` en la raíz del proyecto con:
```env
X-VTEX-API-AppKey=<your_app_key>
X-VTEX-API-AppToken=<your_app_token>
VTEX_ACCOUNT_NAME=<your_account_name>
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

```bash
python3 vtex_sku_getter.py <input.csv> <output.json> [--delay <segundos>] [--timeout <segundos>]
```

### Argumentos

- `input.csv` - CSV con columna `CODIGO SKU` (típicamente generado por 41_generate_sku_range)
- `output.json` - Archivo JSON de salida con respuestas de la API
- `--delay <segundos>` - Pausa entre requests (default: 1s)
- `--timeout <segundos>` - Timeout por request en segundos (default: 30s)

### Ejemplo

```bash
python3 vtex_sku_getter.py input.csv output.json --delay 1 --timeout 30
```

## Formato de Entrada

### input.csv
Requiere columna: `CODIGO SKU`

**Ejemplo:**
```
CODIGO SKU
000050
000099
000101
```

## Formato de Salida

JSON array con objetos conteniendo:
- `sku_id` - SKU consultado
- `status_code` - Código HTTP de respuesta
- `response` - Body de respuesta (JSON si es parseable, texto si no)
- `timestamp` - Fecha/hora ISO de la consulta

**output.json**
```json
[
  {
    "sku_id": "000050",
    "status_code": 200,
    "response": { "id": 123, "name": "Producto A" },
    "timestamp": "2026-01-30T19:59:00.123456"
  },
  {
    "sku_id": "000099",
    "status_code": 400,
    "response": "Invalid reference ID",
    "timestamp": "2026-01-30T19:59:02.654321"
  }
]
```

*Nota: Los resultados con status_code 404 se descartan completamente*

## Control de Rate Limiting

- **Pausa automática**: 1 segundo entre requests (configurable con `--delay`)
- **Backoff exponencial**: Si se detecta 429 (rate limiting), espera se incrementa exponencialmente
- **Reintentos**: Máximo 3 intentos por SKU con backoff
- **Timeout**: 30 segundos por request (configurable)

## Lógica de Funcionamiento

1. Valida que todas las credenciales VTEX estén configuradas en .env
2. Lee los SKU IDs desde el CSV de entrada
3. Para cada SKU:
   - Aguarda el delay configurado
   - Consulta `GET /api/catalog/pvt/stockkeepingunit?RefId={sku_id}`
   - Si 404 → descarta (no incluye en salida)
   - Si 429 → reintenta con backoff exponencial
   - Si otros status → incluye en salida con la respuesta
4. Exporta array JSON con todas las respuestas (excepto 404s)

## Notas/Caveats

- Requiere credenciales VTEX válidas (AppKey + AppToken)
- 404s se descartan silenciosamente (no aparecen en output.json)
- Rate limiting es común con muchas consultas; ajustar `--delay` si es necesario
- La duración depende del número de SKUs y del delay configurado
- Utiliza sesión HTTP persistente para mejorar rendimiento
- Muestra progreso cada 10 items procesados
