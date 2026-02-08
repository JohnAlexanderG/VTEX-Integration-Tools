# 17_upload_sku_images

## Descripción

Sube imágenes de SKUs a la API de catálogo de VTEX mediante peticiones HTTP. Lee un archivo JSON con estructura de imágenes validadas y realiza POST a cada SKU en VTEX, con manejo de reintentos, rate limiting y generación de reportes detallados.

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
python3 upload_sku_images.py <input_json> <output_csv> [report_md]
```

### Comando básico

```bash
python3 upload_sku_images.py merged_sku_images.json failed_uploads.csv upload_report.md
```

### Sin archivo de reporte

```bash
python3 upload_sku_images.py merged_sku_images.json failed_uploads.csv
```

## Argumentos

| Argumento | Tipo | Descripción |
|-----------|------|-------------|
| `input_json` | str | (posicional) Archivo JSON con imágenes de SKUs |
| `output_csv` | str | (posicional) Archivo CSV para exportar fallos |
| `report_md` | str | (posicional, opcional) Archivo markdown con reporte |

## Formato de entrada

### Archivo JSON (merged_sku_images.json)

Estructura: SKU → lista de objetos de imagen

```json
{
    "123456": [
        {
            "Name": "imagen1.jpg",
            "Text": "descripcion-slug",
            "Url": "https://cdn.example.com/imagen1.jpg",
            "Position": 0,
            "IsMain": true,
            "Label": "Main",
            "UrlValid": true,
            "StatusCode": 200
        },
        {
            "Name": "imagen2.jpg",
            "Text": "descripcion-slug",
            "Url": "https://cdn.example.com/imagen2.jpg",
            "Position": 1,
            "UrlValid": true,
            "StatusCode": 200
        }
    ],
    "123457": [
        {
            "Name": "imagen3.jpg",
            "Text": "segunda-imagen",
            "Url": "https://cdn.example.com/imagen3.jpg",
            "Position": 0,
            "IsMain": true,
            "Label": "Main",
            "UrlValid": true,
            "StatusCode": 200
        }
    ]
}
```

**Campos validados:**
- Solo se suben imágenes con `UrlValid=true` AND `StatusCode=200`
- Las demás se registran como fallos
- Campos requeridos en cada imagen: `Name`, `Url`

## Formato de salida

### Archivo CSV de fallos (failed_uploads.csv)

Contiene todas las imágenes que no pudieron procesarse:

```csv
Sku,Name,Text,Url,Position,IsMain,Label,UrlValid,StatusCode
123456,imagen1.jpg,descripcion-slug,https://cdn.example.com/imagen1.jpg,0,True,Main,False,
123457,imagen2.jpg,segunda-imagen,https://cdn.example.com/imagen2.jpg,1,,Main,True,500
```

### Archivo de reporte (upload_report.md)

Documento markdown con estadísticas:

```markdown
# Informe de Subida de Imágenes SKU - VTEX

**Fecha de ejecución:** 2025-02-08 15:30:45

## Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Total SKUs procesados** | 150 |
| **Total imágenes procesadas** | 450 |
| **Subidas exitosas** | 420 |
| **Fallos totales** | 30 |
| **Tasa de éxito** | 93.33% |
...
```

## Cómo funciona

1. **Validación de credenciales**: Carga variables de entorno desde `.env` y valida que todas estén presentes
2. **Carga de datos**: Lee el archivo JSON con estructura de imágenes por SKU
3. **Rate limiting**: Configura límite de 1 request/segundo y procesa en lotes de 25 imágenes
4. **Procesamiento por SKU**:
   - Para cada SKU en el dataset
   - Para cada imagen del SKU
5. **Validación de imágenes**:
   - Solo procesa si `UrlValid=true` AND `StatusCode=200`
   - Salta y registra como fallo en caso contrario
6. **Construcción de payload**:
   - Extrae nombre de archivo de la URL
   - Aplica URL encoding para caracteres especiales
   - Construye JSON con campos: `Name`, `Text`, `Url`, `Position`, `IsMain`, `Label`
7. **Envío a VTEX**:
   - POST a `/api/catalog/pvt/stockkeepingunit/{sku}/file`
   - Respeta rate limiting con delays entre requests
8. **Manejo de errores**:
   - HTTP 429: reintenta con delay de 10 segundos
   - Timeout: reintenta después de 2 segundos
   - Otros errores: registra en CSV de fallos
9. **Pausas entre lotes**: 3 segundos de pausa cada 25 imágenes para no sobrecargar VTEX
10. **Generación de reportes**:
    - CSV con todos los fallos
    - Markdown con estadísticas y análisis de errores

## Notas y caveats

- **Solo sube imágenes válidas**: Imágenes con `UrlValid=false` o `StatusCode≠200` se saltan automáticamente
- **Reintentos automáticos**:
  - Para errores 429 (Too Many Requests): reintenta con 10s de espera
  - Para timeouts: reintenta con 2s de espera
- **Rate limiting conservador**: 1 request/segundo para evitar sobrecarga de VTEX
- **Procesamiento en lotes**: Pausa de 3 segundos cada 25 imágenes
- **URL encoding**: Aplica URL encoding al nombre de archivo para manejar caracteres especiales (puntos, espacios, etc.)
- **Nombres de archivo**: Se extrae automáticamente de la URL (el último componente después del último `/`)
- **Error 404 en URLs**: Si la URL de la imagen devuelve 404, se considera inválida y se salta
- Si el payload está incompleto (falta Name o Url), se registra como fallo
- Los tiempos de respuesta pueden variar; considera aumentar `--sleep` en caso de muchos 429s
