# 18_delete_sku_files

## Descripción

Elimina todos los archivos/imágenes asociados a SKUs en VTEX mediante peticiones DELETE. Lee un archivo JSON con lista de SKU IDs y realiza DELETE a cada uno, con soporte para reintentos, rate limiting y generación de reportes.

## Requisitos

- Python 3.6+
- Dependencias: `requests`, `python-dotenv`
- Instalación: `pip install requests python-dotenv`
- Archivo `.env` en el directorio raíz (nivel anterior) con credenciales VTEX

### Variables de entorno (.env)

```
VTEX_ACCOUNT_NAME=tu_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
```

## Uso

```bash
python3 delete_sku_files.py <input_json> <output_csv> [report_md] [opciones]
```

### Comando básico

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md
```

### Con límite de SKUs

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv deletion_report.md --limit 599
```

### Solo con archivos requeridos

```bash
python3 delete_sku_files.py sku_list.json failed_deletions.csv
```

## Argumentos

| Argumento | Tipo | Descripción |
|-----------|------|-------------|
| `input_json` | str | (posicional) Archivo JSON con lista de SKU IDs |
| `output_csv` | str | (posicional) Archivo CSV para exportar fallos |
| `report_md` | str | (posicional, opcional) Archivo markdown con reporte |
| `--limit` | int | (opcional) Máximo número de SKUs a procesar |

## Formato de entrada

### Archivo JSON (sku_list.json)

**Formato 1: Lista de strings**
```json
[
    "123456",
    "123457",
    "123458",
    "123459"
]
```

**Formato 2: Lista de números**
```json
[
    123456,
    123457,
    123458
]
```

**Formato 3: Diccionario con SKU IDs como claves**
```json
{
    "123456": {},
    "123457": {},
    "123458": {},
    "123459": {}
}
```

## Formato de salida

### Archivo CSV de fallos (failed_deletions.csv)

Contiene todos los SKUs donde la eliminación falló:

```csv
SkuId,StatusCode,ErrorMessage,Timestamp
123456,500,Internal Server Error,2025-02-08 15:30:45
123457,401,Unauthorized,2025-02-08 15:31:12
123460,404,SKU not found,2025-02-08 15:32:05
```

### Archivo de reporte (deletion_report.md)

Documento markdown con estadísticas y análisis de errores:

```markdown
# Informe de Eliminación de Archivos SKU - VTEX

**Fecha de ejecución:** 2025-02-08 15:30:45

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total SKUs procesados** | 600 |
| **Eliminaciones exitosas** | 585 |
| **Fallos totales** | 15 |
| **Tasa de éxito** | 97.50% |

## Análisis de Errores

| Código de Estado | Cantidad |
|------------------|----------|
| **500** | 8 |
| **404** | 5 |
| **401** | 2 |
...
```

## Cómo funciona

1. **Validación de credenciales**: Carga variables de entorno desde `.env`
2. **Carga de datos**: Lee el archivo JSON y detecta automáticamente el formato:
   - Lista de strings/números
   - Diccionario con SKU IDs como claves
3. **Aplicación de límite**: Si se especifica `--limit`, procesa solo los primeros N SKUs
4. **Rate limiting**: Configura límite de 2 requests/segundo para DELETE operations
5. **Procesamiento por lotes**:
   - Procesa en lotes de 20 SKUs
   - Pausa de 3 segundos entre lotes
6. **Eliminación de archivos**:
   - DELETE a `/api/catalog/pvt/stockkeepingunit/{skuId}/file`
   - Elimina TODOS los archivos/imágenes asociados al SKU
7. **Manejo de errores**:
   - Registra errores HTTP con código de estado
   - Reintenta en caso de timeouts
8. **Reportes**:
   - CSV con SKUs donde la eliminación falló
   - Markdown con estadísticas y análisis de errores

## Notas y caveats

- **Operación irreversible**: Este script elimina permanentemente archivos/imágenes de SKUs en VTEX
- **Rate limiting más agresivo**: 2 requests/segundo (vs 1 en upload) porque DELETE es menos pesado
- **Procesamiento en lotes**: Pausa de 3 segundos cada 20 SKUs para respetar límites de VTEX
- **Conversión a strings**: Todos los SKU IDs se convierten a strings internamente
- **Límite temporal**: El parámetro `--limit` es útil para testing o procesamiento gradual (ej: `--limit 599` para evitar límites diarios)
- **Sin reintentos automáticos**: A diferencia del upload, las eliminaciones fallan inmediatamente sin reintentos
- **Fallos registrados**: Solo los SKUs que fallaron se escriben en el CSV
- **Formato de diccionario**: Si el JSON es un diccionario, se usan los keys como SKU IDs (útiles para datos complejos)
