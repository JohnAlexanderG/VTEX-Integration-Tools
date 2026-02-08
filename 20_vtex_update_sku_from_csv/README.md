# 20_vtex_update_sku_from_csv

## Descripción

Actualiza propiedades de SKUs en VTEX a partir de datos en un archivo CSV. Lee un CSV con información de SKU (usando `RefId` para localizar), y realiza PUT requests a la API de VTEX para actualizar propiedades como estado de activación, nombre y dimensiones de empaque.

## Requisitos

- Python 3.6+
- Dependencias: `requests`, `python-dotenv`
- Instalación: `pip install requests python-dotenv`
- Archivo `.env` en el directorio padre (../.env) con credenciales VTEX

### Variables de entorno (.env)

```
VTEX_ACCOUNT_NAME=tu_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
```

## Uso

```bash
python3 vtex_update_sku_from_csv.py <input_csv> [opciones]
```

### Comando básico

```bash
python3 vtex_update_sku_from_csv.py input.csv
```

### Con opciones de rate limiting y reintentos

```bash
python3 vtex_update_sku_from_csv.py input.csv --sleep 0.6 --retries 3 --dry-run
```

## Argumentos

| Argumento | Tipo | Descripción | Valor por defecto |
|-----------|------|-------------|-------------------|
| `input.csv` | str | (posicional) Archivo CSV con datos de SKU | (requerido) |
| `--sleep` | float | Segundos de espera entre requests | `1.0` |
| `--retries` | int | Número de reintentos para errores | `3` |
| `--dry-run` | flag | Simula la ejecución sin realizar cambios | (desactivado) |
| `--case-insensitive` | flag | Búsqueda de columnas sin importar mayúsculas | (desactivado) |

## Formato de entrada

### Archivo CSV (input.csv)

Columnas requeridas (exactas, case-sensitive por defecto):
```
ProductId, IsActive, ActivateIfPossible, Name, RefId,
PackagedHeight, PackagedLength, PackagedWidth, PackagedWeightKg
```

**Ejemplo de datos:**
```csv
ProductId,IsActive,ActivateIfPossible,Name,RefId,PackagedHeight,PackagedLength,PackagedWidth,PackagedWeightKg
12345,true,true,Candado 40ml,210794,5.0,3.0,2.0,0.1
12346,false,true,Barre Puerta,210795,10.5,8.0,5.5,0.25
12347,true,false,Producto Test,210796,#N/A,8.0,5.5,
12348,1,1,Otro Producto,210797,,,
```

**Notas sobre formato:**
- Valores booleanos aceptados: `true`, `1`, `yes`, `y` (case-insensitive)
- Valores vacíos o `#N/A` se convierten a `0` para campos numéricos
- Comas pueden usarse como separador decimal: `5,5` → `5.5`

## Formato de salida

### Archivo de resultados (input_results.csv)

Reporte detallado de cada fila procesada:

```csv
RowIndex,ProductId,RefId,Status,HttpCode,Response,Details
1,12345,210794,SUCCESS,200,OK,SKU actualizado correctamente
2,12346,210795,FAILED,404,Not Found,RefId no encontrado
3,12347,210796,SUCCESS,200,OK,SKU actualizado - propiedades numéricas ajustadas
```

### Archivo de fallos (input_failed.csv)

Solo las filas que fallaron (si existen):

```csv
ProductId,IsActive,ActivateIfPossible,Name,RefId,PackagedHeight,PackagedLength,PackagedWidth,PackagedWeightKg
12346,false,true,Barre Puerta,210795,10.5,8.0,5.5,0.25
```

### Archivo de resumen (input_summary.md)

Reporte markdown con estadísticas:

```markdown
# Resumen de Actualización de SKUs - VTEX

**Fecha:** 2025-02-08 15:30:45

## Estadísticas Generales

- **Total filas procesadas:** 4
- **Exitosas:** 3
- **Fallos:** 1
- **Tasa de éxito:** 75%

## Errores por tipo

- 404 Not Found: 1

...
```

## Cómo funciona

1. **Carga de credenciales**: Lee `.env` desde el directorio padre o actual
2. **Validación de columnas**: Verifica que el CSV tenga todas las columnas requeridas
3. **Lectura del CSV**: Itera sobre cada fila del archivo
4. **Para cada fila**:
   - Extrae el `RefId`
   - Busca el SKU correspondiente en VTEX mediante GET `/api/catalog/pvt/stockkeepingunit?refId={refId}`
   - Si encuentra el SKU, obtiene su `Id` (SkuId)
   - Construye el payload con los campos a actualizar:
     - `IsActive` (booleano)
     - `ActivateIfPossible` (booleano)
     - `Name` (string)
     - Dimensiones: `PackagedHeight`, `PackagedLength`, `PackagedWidth`, `PackagedWeightKg` (números)
5. **Envío a VTEX**: PUT a `/api/catalog/pvt/stockkeepingunit/{skuId}`
6. **Manejo de reintentos**: Si falla, reintenta según `--retries`
7. **Rate limiting**: Espera `--sleep` segundos entre requests
8. **Generación de reportes**:
   - CSV con resultados de cada fila
   - CSV con solo las filas fallidas
   - Markdown con estadísticas

## Notas y caveats

- **RefId como identificador**: El script usa `RefId` del CSV para localizar el SKU en VTEX (no usa `ProductId`)
- **Normalización numérica**: Valores `#N/A`, vacíos, o no-numéricos se convierten a `0`
- **Comma decimal support**: Soporta tanto `.` como `,` como separador decimal (ej: `5,5` = 5.5)
- **Booleanos**: Aceptados `true`, `1`, `yes`, `y` (case-insensitive)
- **Modo dry-run**: Útil para testing sin afectar datos reales
- **Rate limiting**: Por defecto 1 segundo entre requests; ajustable con `--sleep`
- **Reintentos**: Por defecto 3 intentos para errores transitorios
- **Case-insensitive**: Usar `--case-insensitive` si las columnas tienen mayúsculas distintas
- **Errores 404**: Indican que el RefId no existe en VTEX
- **Salida de archivos**: Se generan archivos con prefijo del nombre del CSV (ej: `input_results.csv`, `input_failed.csv`, `input_summary.md`)
