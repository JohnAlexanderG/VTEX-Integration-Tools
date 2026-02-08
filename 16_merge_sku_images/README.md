# 16_merge_sku_images

## Descripción

Combina un archivo JSON de referencia de SKUs con un archivo CSV de imágenes para construir objetos de imagen compatibles con VTEX. El script normaliza automáticamente los valores de SKU (maneja múltiples formatos), valida URLs de imágenes y genera un archivo JSON listo para la API de VTEX.

## Requisitos

- Python 3.6+
- Dependencias: `requests`, `python-dotenv`
- Instalación: `pip install requests python-dotenv`

## Uso

```bash
python3 merge_sku_images.py --json-input <archivo_json> --csv-input <archivo_csv> --output-json <archivo_salida> --not-found-csv <archivo_no_encontrados>
```

### Comando básico

```bash
python3 merge_sku_images.py --json-input products.json --csv-input fotos-productos-pendientes.csv --output-json output.json --not-found-csv not_found.csv
```

### Con validación de URLs

```bash
python3 merge_sku_images.py --json-input products.json --csv-input fotos-productos-pendientes.csv --output-json output.json --validate-urls --url-timeout 15
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `--json-input` | str | Ruta al archivo JSON con referencia de SKUs | (requerido) |
| `--csv-input` | str | Ruta al archivo CSV con datos de imágenes | (requerido) |
| `--output-json` | str | Ruta de salida para el JSON combinado | `output.json` |
| `--not-found-csv` | str | Ruta para exportar SKUs no encontrados | `not_found.csv` |
| `--json-key` | str | Campo en JSON que contiene el SKU | `RefId` |
| `--csv-sku-column` | str | Nombre de columna CSV con SKU | `SKU` |
| `--csv-product-column` | str | Nombre de columna CSV con nombre del producto | `PRODUCTO` |
| `--csv-url-column` | str | Nombre de columna CSV con URL de imagen | `URL` |
| `--csv-order-column` | str | Columna CSV para ordenar imágenes por SKU | `IMAGEN` |
| `--validate-urls` | flag | Validar cada URL con peticiones HTTP HEAD | (desactivado) |
| `--url-timeout` | int | Timeout en segundos para validación de URLs | `10` |

## Formato de entrada

### Archivo JSON (products.json)

Estructura simple con RefId:
```json
[
    {"RefId": "000013", "ProductName": "Producto A", "...": "..."},
    {"RefId": "000014", "ProductName": "Producto B", "...": "..."}
]
```

O estructura anidada:
```json
[
    {
        "sku_data": {"RefId": "000013"},
        "ref_id": "000013",
        "...": "..."
    }
]
```

### Archivo CSV (fotos-productos-pendientes.csv)

Columnas mínimas requeridas: `SKU`, `PRODUCTO`, `URL`, `IMAGEN`

```csv
SKU,PRODUCTO,URL,IMAGEN
000013,Candado 40ml,"https://cdn.example.com/imagen1.jpg",1
"000013",Candado 40ml,"https://cdn.example.com/imagen2.jpg",2
000014,Barre Puerta,"https://cdn.example.com/imagen3.jpg",1
```

SKUs soportados (normalizados automáticamente):
- Sin formato: `000013`
- Con guiones: `000-013`
- Con comillas dobles: `"000013"`
- Con comillas simples: `'000013'`
- Con espacios: ` 000013 ` o ` '000013' `

## Formato de salida

### Archivo JSON (output.json)

Mapeo de SKU a lista de imágenes:
```json
{
    "000013": [
        {
            "IsMain": true,
            "Label": "Main",
            "Name": "Candado 40ml",
            "Text": "candado-40ml",
            "Url": "https://cdn.example.com/imagen1.jpg",
            "Position": 0,
            "UrlValid": true,
            "StatusCode": 200
        },
        {
            "Name": "Candado 40ml",
            "Text": "candado-40ml",
            "Url": "https://cdn.example.com/imagen2.jpg",
            "Position": 1,
            "UrlValid": true,
            "StatusCode": 200
        }
    ],
    "000014": [
        {
            "IsMain": true,
            "Label": "Main",
            "Name": "Barre Puerta",
            "Text": "barre-puerta",
            "Url": "https://cdn.example.com/imagen3.jpg",
            "Position": 0
        }
    ]
}
```

### Archivo CSV de no encontrados (not_found.csv)

Contiene todas las filas del CSV que no tuvieron coincidencia en el JSON:
```csv
SKU,PRODUCTO,URL,IMAGEN
000999,Producto inexistente,"https://cdn.example.com/imagen.jpg",1
```

## Cómo funciona

1. **Carga del JSON**: Lee el archivo JSON y extrae todos los valores del campo especificado (por defecto `RefId`) para construir un conjunto de SKUs válidos
2. **Normalización de SKUs**: Procesa cada fila del CSV, normalizando el valor del SKU (removiendo comillas, espacios, etc.)
3. **Agrupación**: Agrupa las filas del CSV por SKU normalizado
4. **Construcción de objetos**: Para cada SKU agrupado, construye objetos de imagen VTEX con:
   - Primera imagen: incluye `IsMain=true` y `Label="Main"`
   - Imágenes posteriores: omiten estos campos
   - Slug: convierte el nombre del producto a formato URL (minúsculas, sin acentos, guiones)
5. **Validación de URLs** (opcional): Si se activa `--validate-urls`, realiza peticiones HTTP HEAD para cada URL y agrega campos `UrlValid`, `StatusCode` y `ValidationError`
6. **Exportación**: Genera el JSON final y un CSV con los SKUs que no coincidieron

## Notas y caveats

- La validación de URLs se realiza **solo para imágenes que aparecen en el archivo final** de salida
- Si no se encuentra un SKU del CSV en el JSON, se registra en `not_found.csv` para revisión manual
- El campo `Text` (slug) se genera automáticamente a partir del campo `Name` del CSV
- La normalización de SKUs es automática y soporta múltiples formatos para máxima compatibilidad
- Las peticiones de validación de URL usan método HEAD para minimizar transferencia de datos
- Timeout por defecto es 10 segundos; puede ajustarse con `--url-timeout`
