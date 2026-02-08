# 21_vtex_sku_no_image_finder

## Descripción

Descubre y exporta todos los SKUs de una cuenta VTEX que no tienen imágenes asociadas. Recorre la API de VTEX, detecta SKUs sin imágenes, obtiene sus datos (RefId, ProductId, Name) y exporta la lista a un archivo CSV con opción de resume mediante checkpoint.

## Requisitos

- Python 3.8+
- Dependencias: `requests`, `python-dotenv`
- Instalación: `pip install requests python-dotenv`
- Archivo `.env` en la raíz del proyecto con credenciales VTEX

### Variables de entorno (.env)

```
VTEX_ACCOUNT_NAME=tu_cuenta
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

```bash
python3 vtex_sku_no_image_finder.py [opciones]
```

### Comando básico

```bash
python3 vtex_sku_no_image_finder.py --output sin_imagenes.csv --delay 0.2
```

### Con checkpoint y logging

```bash
python3 vtex_sku_no_image_finder.py \
    --page-size 1000 \
    --output skus_sin_imagenes.csv \
    --log-file ejecucion.log \
    --checkpoint progreso.json \
    --delay 0.2
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `--page-size` | int | Tamaño de página para paginación VTEX | `1000` |
| `--output` | str | Archivo CSV de salida | `skus_without_images.csv` |
| `--log-file` | str | Archivo de log (opcional) | (sin archivo) |
| `--checkpoint` | str | Archivo de checkpoint para resume | (sin checkpoint) |
| `--delay` | float | Segundos entre requests | `0.2` |

## Formato de entrada

**No hay entrada de archivo.** El script obtiene datos directamente de la API de VTEX usando las credenciales del `.env`.

### APIs utilizadas

1. **Listar SKU IDs**: `GET /api/catalog_system/pvt/sku/stockkeepingunitids?page={page}&pagesize={pagesize}`
2. **Obtener detalles de SKU**: `GET /api/catalog/pvt/stockkeepingunit/{skuId}`

## Formato de salida

### Archivo CSV (skus_without_images.csv)

Contiene lista de todos los SKUs sin imágenes:

```csv
SkuId,RefId,ProductId,Name,ImageCount
5380,210794,12345,Candado 40ml,0
5381,210795,12346,Barre Puerta,0
5382,210796,12347,Producto Test,0
5383,210797,12348,Otro Producto,0
```

**Campos:**
- `SkuId`: ID único del SKU en VTEX
- `RefId`: ID de referencia interno
- `ProductId`: ID del producto padre
- `Name`: Nombre del producto
- `ImageCount`: Número de imágenes (siempre 0 en este export)

### Archivo de Checkpoint (progreso.json)

Almacena el progreso para poder reanudar la ejecución:

```json
{
    "last_sku_id": 5382,
    "last_page": 5,
    "total_processed": 5382,
    "skus_without_images": 127
}
```

### Archivo de Log (ejecucion.log)

Registro detallado de la ejecución:

```
2025-02-08 15:30:45 | INFO | Starting SKU scan...
2025-02-08 15:30:46 | INFO | Fetching page 1 (SKUs 1-1000)...
2025-02-08 15:30:48 | INFO | SKU 5380: RefId=210794 - No images (ImageCount=0)
2025-02-08 15:30:49 | DEBUG | SKU 5381: RefId=210795 - Has 3 images
...
2025-02-08 15:45:12 | INFO | Scan completed: 5382 total SKUs, 127 without images
```

## Cómo funciona

1. **Inicialización**:
   - Carga credenciales desde `.env`
   - Configura logging en consola y archivo (si especificado)
   - Carga checkpoint anterior si existe

2. **Escaneo de SKUs**:
   - Itera sobre páginas de SKU IDs usando paginación
   - Tamaño de página configurable (por defecto 1000)
   - Reintenta automáticamente si encuentra errores 429/5xx

3. **Para cada SKU**:
   - Obtiene detalles usando GET `/api/catalog/pvt/stockkeepingunit/{skuId}`
   - Cuenta las imágenes en el campo `Images` (array)
   - Si `ImageCount == 0`, agrega a la lista de SKUs sin imágenes
   - Extrae datos: `Id`, `RefId`, `ProductId`, `Name`, `Images.length`

4. **Reintentos y rate limiting**:
   - Reintenta con backoff exponencial ante errores 429/5xx
   - Respeta cabecera `X-RateLimit-Reset` de VTEX
   - Aplica delay configurable entre requests (`--delay`)
   - Máximo 6 intentos por request con backoff

5. **Checkpoint**:
   - Guarda el último SKU procesado y página actual
   - Permite reanudar sin perder progreso si se interrumpe la ejecución
   - Se actualiza cada página completada

6. **Exportación**:
   - Escribe CSV idempotente (mantiene encabezado)
   - Modo append si el archivo ya existe
   - Exporta solo SKUs sin imágenes

## Notas y caveats

- **Progreso pausable**: Con `--checkpoint`, puedes interrumpir y reanudar sin perder progreso
- **Logging dual**: Salida en consola + archivo opcional
- **Rate limiting automático**: Respeta límites de VTEX con backoff adaptativo
- **Reintentos robustos**: Máximo 6 intentos con delay creciente
- **Procesamiento por páginas**: Ideal para cuentas con muchos SKUs (> 100k)
- **Delay configurable**: Por defecto 0.2s; aumentar si recibe muchos 429s
- **ImageCount = 0**: Solo exporta SKUs que literalmente no tienen imágenes
- **RefId obligatorio**: Si un SKU no tiene RefId, se salta con warning
- **Append mode**: Si el CSV ya existe, agrega nuevos registros sin duplicar encabezados
- **Timeout automático**: 30 segundos por request; reintenta si expira
