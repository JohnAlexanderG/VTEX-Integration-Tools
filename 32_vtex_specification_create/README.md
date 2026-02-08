# Creador de Especificaciones VTEX

Crea especificaciones dentro de grupos de especificaciones en VTEX mediante API.

## Descripción

Este script lee un archivo JSON con respuestas de creación de grupos de especificaciones (paso 31) y crea especificaciones dentro de esos grupos utilizando el endpoint `/api/catalog/pvt/specification` de la API de Catálogo de VTEX.

## Requisitos Previos

- Python 3.6+
- Credenciales VTEX configuradas en archivo `.env` en raíz del proyecto
- Grupos de especificaciones ya creados (salida del paso 31)
- Definiciones de especificaciones preparadas en formato JSON

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install requests python-dotenv
```

## Configuración de Credenciales

Asegúrese que el archivo `.env` en la raíz contiene:

```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

### Uso Básico

```bash
python3 vtex_specification_create.py grupos.json especificaciones.json
```

### Modo Dry-Run (Prueba sin crear)

```bash
python3 vtex_specification_create.py grupos.json especificaciones.json --dry-run
```

### Con Delay y Timeout Personalizados

```bash
python3 vtex_specification_create.py grupos.json especificaciones.json --delay 2.0 --timeout 60
```

### Ejemplo Completo

```bash
# Primero probar con dry-run
python3 vtex_specification_create.py \
  20260108_023307_specificationgroup_creation_successful.json \
  especificaciones_template.json \
  --dry-run

# Si todo se ve bien, ejecutar de verdad
python3 vtex_specification_create.py \
  20260108_023307_specificationgroup_creation_successful.json \
  especificaciones_template.json
```

### Ver Ayuda Completa

```bash
python3 vtex_specification_create.py --help
```

## Formato de Entrada

### Archivo JSON de Grupos (desde paso 31)

Estructura esperada:

```json
[
  {
    "group_data": {
      "CategoryId": 118,
      "Name": "PUM_CAT",
      "line_number": 2
    },
    "response": {
      "Id": 168,
      "CategoryId": 118,
      "Name": "PUM_CAT",
      "Position": null
    },
    "status_code": 200
  }
]
```

El script extrae:
- `response.Id` → `FieldGroupId` (ID del grupo de especificación)
- `response.CategoryId` → `CategoryId` (ID de categoría)

### Archivo JSON de Especificaciones

Estructura esperada:

```json
[
  {
    "Name": "VALOR UNIDAD DE MEDIDA",
    "FieldTypeId": 4,
    "IsFilter": false,
    "IsRequired": false,
    "IsOnProductDetails": true,
    "IsStockKeepingUnit": true,
    "IsActive": true,
    "IsTopMenuLinkActive": false,
    "IsSideMenuLinkActive": false
  }
]
```

Puede definir múltiples especificaciones en el array, y se crearán para TODOS los grupos.

### Referencia de FieldTypeId en VTEX

Tipos de campo comunes:
- `1`: Texto (corto)
- `2`: Texto (largo/multilínea)
- `4`: Número
- `5`: Combo (dropdown)
- `6`: Botón de radio
- `7`: Checkbox

## Formato de Salida

El script genera varios archivos con timestamp (YYYYMMDD_HHMMSS):

### 1. Especificaciones Creadas Exitosamente

**YYYYMMDD_HHMMSS_specification_creation_successful.json**
- Respuestas API completas para creaciones exitosas
- Incluye todos los campos extraídos y datos completos de respuesta

**YYYYMMDD_HHMMSS_specification_creation_successful.csv**
- Tabla resumen con campos clave:
  - `FieldId`: ID del campo de especificación VTEX
  - `CategoryId`: ID de categoría
  - `FieldGroupId`: ID del grupo de especificación
  - `Name`: Nombre de la especificación
  - `FieldTypeId`: Tipo de campo (1=Texto, 4=Número, 5=Combo, etc.)
  - `Position`: Posición de visualización
  - `IsRequired`: Si el campo es requerido
  - `IsFilter`: Si el campo es filtrable
  - `IsActive`: Si el campo está activo

### 2. Especificaciones que Fallaron

**YYYYMMDD_HHMMSS_specification_creation_failed.json**
- Información detallada de errores para creaciones fallidas

**YYYYMMDD_HHMMSS_specification_creation_failed.csv**
- Resumen de errores para revisión manual

### 3. Reporte

**YYYYMMDD_HHMMSS_specification_creation_REPORT.md**
- Reporte markdown comprehensivo con estadísticas y recomendaciones
- Tabla mejorada mostrando todas las propiedades clave de especificación

## Características

- **Rate Limiting**: Delay configurable entre requests (default: 1s)
- **Exponential Backoff**: Reintentos automáticos con delays crecientes para errores 429
- **Modo Dry-Run**: Prueba el proceso sin hacer llamadas reales a la API
- **Manejo de Errores**: Seguimiento comprehensivo de errores con exportaciones detalladas
- **Progreso en Tiempo Real**: Actualizaciones cada 10 grupos procesados
- **Procesamiento por Lotes**: Crea especificaciones para todos grupos × definiciones

## Endpoint API

```
POST https://{accountName}.{environment}.com.br/api/catalog/pvt/specification
```

### Body de Solicitud

```json
{
  "FieldTypeId": 4,
  "CategoryId": 118,
  "FieldGroupId": 168,
  "Name": "VALOR UNIDAD DE MEDIDA",
  "IsFilter": false,
  "IsRequired": false,
  "IsOnProductDetails": true,
  "IsStockKeepingUnit": true,
  "IsActive": true,
  "IsTopMenuLinkActive": false,
  "IsSideMenuLinkActive": false
}
```

## Flujos de Trabajo Comunes

### Crear Una Especificación para Todos los Grupos

1. Prepare su especificación en `especificaciones_template.json`
2. Ejecute dry-run: `python3 vtex_specification_create.py grupos.json especificaciones_template.json --dry-run`
3. Revise la salida
4. Ejecute de verdad: `python3 vtex_specification_create.py grupos.json especificaciones_template.json`

### Crear Múltiples Especificaciones para Todos los Grupos

1. Edite `especificaciones_template.json` para incluir múltiples especificaciones:

```json
[
  {
    "Name": "VALOR UNIDAD DE MEDIDA",
    "FieldTypeId": 4,
    ...
  },
  {
    "Name": "COLOR",
    "FieldTypeId": 1,
    ...
  },
  {
    "Name": "MATERIAL",
    "FieldTypeId": 5,
    ...
  }
]
```

2. Ejecute el script - creará las 3 especificaciones para cada grupo

## Argumentos CLI

```
vtex_specification_create.py [-h] [--dry-run] [--delay DELAY] [--timeout TIMEOUT]
                             grupos_json
                             especificaciones_json

Posicionales:
  grupos_json              JSON con grupos creados (paso 31)
  especificaciones_json    JSON con definiciones de especificaciones

Opcionales:
  -h, --help              Muestra mensaje de ayuda
  --dry-run               Simula sin hacer llamadas API reales
  --delay DELAY           Delay entre requests en segundos (default: 1.0)
  --timeout TIMEOUT       Timeout de request en segundos (default: 30)
```

## Solución de Problemas

### "Missing VTEX credentials in .env"
- Asegúrese que el archivo `.env` en raíz contiene:
  - `X-VTEX-API-AppKey`
  - `X-VTEX-API-AppToken`
  - `VTEX_ACCOUNT_NAME`

### "Rate limit exceeded"
- Aumente delay: `--delay 2.0`
- El script automáticamente reintenta con exponential backoff

### "CategoryId or FieldGroupId not found"
- Verifique estructura del archivo JSON de grupos
- Asegúrese que los grupos fueron creados exitosamente en paso 31

### Algunas especificaciones fallan
- Revise el CSV de fallos para patrones de error
- Verifique que CategoryId y FieldGroupId existan en VTEX
- Revise mensajes de error en reporte markdown

## Performance

- **Tiempo de procesamiento**: ~1 segundo por especificación (con delay default)
- **Ejemplo**: 58 grupos × 1 especificación = ~58 segundos
- **Ejemplo**: 58 grupos × 5 especificaciones = ~290 segundos (~5 minutos)

## Códigos de Salida

- `0`: Todas las especificaciones se crearon exitosamente
- `1`: Algunas especificaciones fallaron (revise exportaciones)

## Scripts Relacionados

- **Paso 31**: `31_vtex_specificationgroup_create` - Crea grupos de especificaciones
- **Siguiente**: Crear valores de especificación para campos combo/radio/checkbox
