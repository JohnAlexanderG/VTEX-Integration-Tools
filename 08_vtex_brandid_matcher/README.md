# 08_vtex_brandid_matcher

## Descripción

Herramienta de integración VTEX que mapea identificadores de marca (BrandId) desde la API de VTEX a productos en un archivo JSON. El script busca automaticamente los BrandIds correspondientes a cada marca utilizando normalización de texto robusto que elimina acentos y caracteres especiales para un matching preciso.

Este es el cuarto paso del flujo de transformación de datos, ubicado entre el procesamiento de categorías y departamentos y la clasificación de productos listos para crear en VTEX.

## Funcionalidad

- Conecta con la API de VTEX para obtener el catálogo completo de marcas
- Carga mapeo local SKU → Marca desde archivo `marcas.json`
- Realiza búsqueda de BrandIds mediante normalización de nombres (elimina acentos, ñ→n, minúsculas)
- Soporta campos alternativos "Marca" y "MARCA" en archivo de marcas
- Soporta campos alternativos "RefId" y "SKU" en archivo de productos
- Asigna BrandId correspondiente a cada producto
- Exporta productos sin BrandId encontrado a CSV para revisión manual
- Genera reporte Markdown detallado con estadísticas y análisis de fallos
- Implementa logging detallado en terminal durante el procesamiento

## Requisitos Previos

### Variables de Entorno (.env)

Requiere las siguientes variables en archivo `.env` en la raíz del proyecto:

```
X-VTEX-API-AppKey=<tu_app_key>
X-VTEX-API-AppToken=<tu_app_token>
VTEX_ACCOUNT_NAME=<nombre_cuenta>
VTEX_ENVIRONMENT=vtexcommercestable  # (opcional, por defecto)
```

### Dependencias Python

```
requests
python-dotenv
```

## Uso

### Comando Básico

```bash
python3 vtex_brandid_matcher.py marcas.json data.json
```

### Con Archivos de Salida Personalizados

```bash
python3 vtex_brandid_matcher.py marcas.json data.json \
    --output_json final.json \
    --output_csv faltantes.csv \
    --output_report reporte.md
```

### Con Configuración Personalizada

```bash
python3 vtex_brandid_matcher.py marcas.json data.json \
    --account CUENTA_VTEX \
    --env vtexcommercestable
```

## Argumentos CLI

| Argumento | Descripción | Obligatorio | Valor por Defecto |
|-----------|-------------|-------------|-------------------|
| `marcas_file` | Ruta al archivo JSON con mapeo SKU → Marca | Sí | N/A |
| `data_file` | Ruta al archivo JSON con productos | Sí | N/A |
| `--output_json` | Archivo JSON de salida con BrandIds asignados | No | `data_brandid.json` |
| `--output_csv` | Archivo CSV con productos sin BrandId | No | `no_brandid_found.csv` |
| `--output_report` | Archivo Markdown con reporte detallado | No | `brand_matching_report.md` |
| `--account` | Nombre cuenta VTEX (sobrescribe .env) | No | Desde .env |
| `--env` | Ambiente VTEX (sobrescribe .env) | No | `vtexcommercestable` |

## Formato de Entrada

### marcas.json

Archivo JSON con lista de objetos que mapean SKU a nombre de marca:

```json
[
  {
    "SKU": "SKU001",
    "Marca": "Nike"
  },
  {
    "SKU": "SKU002",
    "MARCA": "Adidas"
  }
]
```

**Campos esperados:**
- `SKU`: Identificador único del producto (obligatorio)
- `Marca` o `MARCA`: Nombre de la marca del producto (obligatorio)

### data.json

Archivo JSON con lista de productos a procesar:

```json
[
  {
    "RefId": "SKU001",
    "Name": "Zapatos Nike",
    "DepartmentId": 1,
    "CategoryId": 10
  },
  {
    "SKU": "SKU002",
    "Name": "Zapatillas Adidas",
    "DepartmentId": 2,
    "CategoryId": 20
  }
]
```

**Campos esperados:**
- `RefId` o `SKU`: Identificador del producto (obligatorio para matching)
- Otros campos opcionales se preservan en salida

## Formato de Salida

### data_brandid.json

Archivo JSON con todos los productos, incluyendo campo `BrandId` asignado:

```json
[
  {
    "RefId": "SKU001",
    "Name": "Zapatos Nike",
    "DepartmentId": 1,
    "CategoryId": 10,
    "BrandId": 2000001
  }
]
```

### no_brandid_found.csv

Archivo CSV con productos donde NO se encontró BrandId en VTEX:

| RefId | Name | BrandId | Marca |
|-------|------|---------|-------|
| SKU001 | Zapatos Nike | null | Nike |
| SKU999 | Producto Desconocido | null | NO_ENCONTRADA |

### brand_matching_report.md

Reporte Markdown con:
- Resumen ejecutivo con estadísticas
- Tabla de configuración utilizada
- Ejemplos de matches exitosos
- Análisis de marcas no encontradas en VTEX
- Recomendaciones para resolver problemas

## Cómo Funciona

### Proceso de Mapeo

1. **Obtiene catálogo VTEX**: Conecta a API y obtiene todas las marcas registradas
2. **Normaliza marcas VTEX**: Crea diccionario `nombre_normalizado → BrandId`
3. **Carga archivos locales**: Lee `marcas.json` y `data.json`
4. **Busca SKU en marcas.json**: Para cada producto, busca su RefId/SKU
5. **Normaliza nombre de marca**: Elimina acentos, ñ→n, minúsculas
6. **Busca en catálogo VTEX**: Busca BrandId con nombre normalizado
7. **Asigna BrandId**: Agrega campo `BrandId` a cada producto
8. **Genera reportes**: Crea archivos CSV y Markdown de análisis

### Normalización de Texto

La normalización se aplica a nombres de marcas para matching robusto:

```
"Café Del Campo" → "cafe del campo"
"Niños" → "ninos"
"ILUMAX" → "ilumax"
```

## Notas Importantes

- **Acentos**: Se eliminan automáticamente para búsqueda robusta
- **Campos alternativos**: Soporta tanto "Marca" como "MARCA", y "RefId" como "SKU"
- **BrandId null**: Si no se encuentra marca en VTEX, el campo `BrandId` se asigna como `null`
- **CSV de faltantes**: Contiene todos los productos sin BrandId para revisión manual
- **Rate limiting**: La API VTEX puede tener límites; el script maneja pausas automáticas
- **Marcas similares**: En caso de no encontrar match, el reporte sugiere marcas VTEX similares

## Ejemplos de Ejecución

```bash
# Ejecución básica
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json data.json

# Con archivos personalizados
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py \
    productos_marcas.json \
    productos_catalogo.json \
    --output_json productos_con_brandid.json \
    --output_csv productos_sin_marca.csv

# Con cuenta específica
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py \
    marcas.json data.json \
    --account mitienda
```

## Archivos Generados

El script genera tres archivos:

1. **data_brandid.json** - Todos los productos con BrandId asignado
2. **no_brandid_found.csv** - Productos sin BrandId (requieren revisión)
3. **brand_matching_report.md** - Reporte detallado con estadísticas

## Troubleshooting

### Credenciales faltantes

Si obtiene error sobre credenciales faltantes:
```
Asegurate de que .env contiene: X-VTEX-API-AppKey, X-VTEX-API-AppToken, VTEX_ACCOUNT_NAME
```

### Marcas no encontradas

Si muchas marcas no se encuentran en VTEX:
1. Verifica que los nombres en `marcas.json` coincidan con VTEX
2. Revisa el reporte para ver "Marcas VTEX similares" sugeridas
3. Crea las marcas faltantes en VTEX antes de proceder
4. Re-ejecuta el script

### Archivo JSON inválido

Asegurate que los archivos JSON sean válidos:
```bash
python3 -m json.tool marcas.json  # Valida JSON
```
