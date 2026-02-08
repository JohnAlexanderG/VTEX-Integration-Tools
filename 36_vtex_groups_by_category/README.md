# Grupos de Especificaciones por Categoría

Consulta grupos de especificaciones en VTEX agrupados por categoría.

## Descripción

Este script lee un CSV con IDs de categoría y consulta la API de VTEX para obtener todos los grupos de especificaciones definidos en cada categoría, generando archivos consolidados con los resultados.

## Requisitos

- Python 3.6+
- Credenciales VTEX en `.env`
- Archivo CSV con IDs de categoría

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install requests python-dotenv
```

## Configuración

Archivo `.env` en raíz:

```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

### Uso Básico

```bash
python3 vtex_groups_by_category.py categorias.csv
```

### Dry-Run (sin consultas reales)

```bash
python3 vtex_groups_by_category.py categorias.csv --dry-run
```

### Con Delay Personalizado

```bash
python3 vtex_groups_by_category.py categorias.csv --delay 0.5
```

### Con Timeout Personalizado

```bash
python3 vtex_groups_by_category.py categorias.csv --timeout 60
```

### Combinado

```bash
python3 vtex_groups_by_category.py categorias.csv --delay 1.0 --timeout 60 --dry-run
```

### Ver Ayuda

```bash
python3 vtex_groups_by_category.py --help
```

## Formato de Entrada

### Archivo CSV

Debe contener IDs de categoría a consultar.

**Estructura esperada:**
```csv
categoryId
118
200
300
```

**Alternativas soportadas:**
- Con header "categoryId" (case-insensitive)
- Sin header: usa primera columna

**Ejemplos de entrada:**
```csv
ID
1
2
3
```

O sin header:
```
118
200
300
```

**Ejemplo real:**
- Archivo: `categories.csv`
- Registros: 8,582 categorías

## Formato de Salida

El script genera archivos con timestamp (YYYYMMDD_HHMMSS):

### 1. Respuestas Completas JSON

**YYYYMMDD_HHMMSS_groups_by_category_results.json**

Estructura:
```json
{
  "categories": {
    "118": {
      "categoryId": 118,
      "groups": [
        {
          "id": 168,
          "name": "PUM_CAT",
          "position": 1
        },
        {
          "id": 169,
          "name": "Especificaciones",
          "position": 2
        }
      ]
    },
    "200": {
      "categoryId": 200,
      "groups": [
        {
          "id": 200,
          "name": "Tamaño",
          "position": 1
        }
      ]
    }
  }
}
```

### 2. CSV Consolidado

**YYYYMMDD_HHMMSS_groups_by_category_results.csv**

Una fila por grupo encontrado:
```csv
categoryId,groupId,groupName,groupPosition
118,168,PUM_CAT,1
118,169,Especificaciones,2
200,200,Tamaño,1
300,,,(sin grupos)
```

**Columnas:**
- `categoryId`: ID de la categoría
- `groupId`: ID del grupo de especificación
- `groupName`: Nombre del grupo
- `groupPosition`: Posición del grupo

**Ejemplo real:**
- Archivo: `20260113_154526_groups_by_category_results.csv`
- Registros: 340,816 filas (múltiples grupos por categoría)

### 3. Errores (si los hay)

**YYYYMMDD_HHMMSS_groups_by_category_errors.json**
- Detalles de errores API para categorías fallidas

**YYYYMMDD_HHMMSS_groups_by_category_errors.csv**
- Resumen de errores para revisión manual

### 4. Reporte

**YYYYMMDD_HHMMSS_groups_by_category_REPORT.md**

Ejemplo:
```markdown
# VTEX Groups by Category Report

**Timestamp:** 2026-01-13 15:45:26

## Summary
- Total Categories: 8,582
- Successful: 8,500
- Failed: 82
- Success Rate: 99.0%

## Groups Statistics
- Total Groups Found: 340,816
- Avg Groups per Category: 40.0
- Categories with Groups: 8,500
- Categories without Groups: 82

## Errors
- 404 Not Found: 50
- 403 Forbidden: 20
- 429 Rate Limit: 12
```

## Cómo Funciona

### Fase 1: Carga de Entrada
1. Lee archivo CSV
2. Detecta delimitador automáticamente (`,` `;` `\t` `|`)
3. Identifica columna con IDs
4. Carga IDs de categoría preservando orden

### Fase 2: Configuración API
1. Valida credenciales VTEX
2. Construye headers de autenticación
3. Construye URL base de API

### Fase 3: Consultas Concurrentes
Para cada CategoryId:
1. Construye URL: `/api/catalog/pvt/categoryTree/{categoryId}`
2. Realiza GET con headers de autenticación
3. Maneja rate limiting con delay configurable
4. Reintenta con exponential backoff si falla

### Fase 4: Procesamiento de Respuestas
1. Extrae grupos de cada respuesta
2. Consolida en estructura JSON
3. Genera una fila CSV por grupo
4. Registra errores

### Fase 5: Exportación
1. Escribe JSON con todas las respuestas
2. Escribe CSV consolidado
3. Escribe JSON de errores (si hay)
4. Genera reporte markdown

## Detección de Delimitador

El script detecta automáticamente:

```csv
- Coma (,): valor,valor,valor
- Punto y coma (;): valor;valor;valor
- Tabulación (\t): valor	valor	valor
- Tubería (|): valor|valor|valor
```

## Rate Limiting

- **Default delay:** 0.1 segundos entre requests
- **Exponential backoff:** Para errores 429
- **Compartido:** Mismo delay para todas las categorías

**Configuración:**
```bash
--delay 0.1   # 10 requests/segundo (default)
--delay 0.5   # 2 requests/segundo
--delay 1.0   # 1 request/segundo
```

## Endpoint API

```
GET https://{accountName}.{environment}.com.br/api/catalog/pvt/categoryTree/{categoryId}
```

**Respuesta esperada:**
```json
[
  {
    "id": 168,
    "name": "PUM_CAT",
    "position": 1,
    "children": []
  },
  {
    "id": 169,
    "name": "Especificaciones",
    "position": 2,
    "children": []
  }
]
```

## Argumentos CLI

```
vtex_groups_by_category.py [-h] [--dry-run] [--delay DELAY] [--timeout TIMEOUT]
                           input_csv

Posicionales:
  input_csv       CSV con categoryId a consultar

Opcionales:
  -h, --help      Muestra mensaje de ayuda
  --dry-run       Simula sin hacer consultas API reales
  --delay DELAY   Delay entre requests en segundos (default: 0.1)
  --timeout TIMEOUT  Timeout per request en segundos (default: 30)
```

## Ejemplo Completo

```bash
# Paso 1: Probar con dry-run
python3 vtex_groups_by_category.py categorias.csv --dry-run

# Paso 2: Ejecutar consultas reales
python3 vtex_groups_by_category.py categorias.csv --delay 0.2

# Archivos generados:
# - 20260113_154526_groups_by_category_results.json
# - 20260113_154526_groups_by_category_results.csv
# - 20260113_154526_groups_by_category_REPORT.md
```

## Estadísticas Típicas

```
============================================================
Grupos de Especificaciones por Categoría
============================================================

✅ Credenciales VTEX configuradas para cuenta: micuenta
🔧 Base URL: https://micuenta.vtexcommercestable.com.br
⏱️  Delay: 0.1s between requests
🕐 Timeout: 30s per request

Cargando categoryIds...
Loaded: 8,582 unique categories

Procesando...
[████████████████████░░░░░░░░░░░░░░░] 60%
Processed: 5,149 | Successful: 5,100 | Failed: 49

Exportando resultados...
✓ JSON: 20260113_154526_groups_by_category_results.json
✓ CSV: 20260113_154526_groups_by_category_results.csv
✓ Report: 20260113_154526_groups_by_category_REPORT.md

============================================================
```

## Performance

- **Velocidad:** ~10-40 requests/segundo (depende delay)
- **Duración:** 8,582 categorías @ 10 req/s = ~15 minutos

**Optimization:**
```bash
# Para ir más rápido (pero cuidado con rate limits):
python3 vtex_groups_by_category.py categorias.csv --delay 0.05

# Para ir más lento (más estable):
python3 vtex_groups_by_category.py categorias.csv --delay 0.5
```

## Solución de Problemas

### Error: "Missing VTEX credentials"
Verifique `.env` contiene todas las variables requeridas

### Muchos 404 errors
- IDs de categoría pueden no existir
- Categorías pueden estar desactivadas
- Revise archivo de errores para IDs problemáticos

### Rate limit (429 errors)
- Aumentar delay: `--delay 0.5`
- El script automáticamente reintenta

### Timeout errors
- Aumentar timeout: `--timeout 60`
- VTEX puede estar lento

### Pocas categorías con grupos
- Muchas categorías pueden no tener grupos asignados
- Es normal en algunos catálogos
- Revise CSV de resultados

## Notas

- **Preserve order**: El orden de input se mantiene en outputs
- **Empty groups**: Categorías sin grupos también se reportan en CSV
- **Unique IDs**: Se deduplicarán categorías duplicadas en entrada
- **No groups**: Si una categoría no tiene grupos, aparecerá con ID/Name vacío en CSV
