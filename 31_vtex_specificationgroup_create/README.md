# VTEX Specification Group Creator

Crea grupos de especificaciones en VTEX de forma masiva a partir de un archivo CSV.

## Requisitos

### Archivo CSV
El archivo CSV debe tener las siguientes columnas:
- `CategoryId`: ID numérico de la categoría en VTEX
- `Name`: Nombre del grupo de especificaciones

Ejemplo:
```csv
CategoryId,Name
1309,PUM
1310,Medidas
1311,Características Técnicas
```

### Credenciales VTEX
Asegúrate de que el archivo `.env` en la raíz del proyecto contenga:
```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

### Modo de prueba (Dry-run)
Valida el CSV sin crear grupos:
```bash
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py example_groups.csv --dry-run
```

### Creación real
Crea los grupos de especificaciones:
```bash
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py example_groups.csv
```

### Opciones adicionales
```bash
# Con delay personalizado (2 segundos entre requests)
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py groups.csv --delay 2.0

# Con timeout personalizado
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py groups.csv --timeout 60

# Ver ayuda
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py --help
```

## Archivos de Salida

El script genera automáticamente:

1. **YYYYMMDD_HHMMSS_specificationgroup_creation_successful.json**
   - Grupos creados exitosamente con respuestas completas de la API

2. **YYYYMMDD_HHMMSS_specificationgroup_creation_successful.csv**
   - CSV con GroupId, CategoryId, Name y Position (útil para crear especificaciones)

3. **YYYYMMDD_HHMMSS_specificationgroup_creation_failed.json**
   - Grupos que fallaron con detalles del error

4. **YYYYMMDD_HHMMSS_specificationgroup_creation_failed.csv**
   - CSV con errores para revisión manual

5. **YYYYMMDD_HHMMSS_specificationgroup_creation_REPORT.md**
   - Reporte completo con estadísticas y recomendaciones

### Respuesta de la API

Cuando se crea un grupo exitosamente, la API retorna:
```json
{
  "Id": 10,
  "CategoryId": 1,
  "Name": "Sizes",
  "Position": 3
}
```

El `Id` retornado es el **GroupId** que necesitarás para crear especificaciones dentro de este grupo.

## Características

- ✅ **Rate Limiting**: 1 segundo de delay entre requests (configurable)
- ✅ **Retry Logic**: Hasta 3 reintentos con exponential backoff para errores 429
- ✅ **Dry-run Mode**: Prueba sin crear grupos reales
- ✅ **Progress Tracking**: Estadísticas cada 10 items procesados
- ✅ **Validación**: Verifica formato de CSV y credenciales VTEX
- ✅ **Reportes Detallados**: JSON, CSV y Markdown
- ✅ **Manejo de Errores**: Timeout, rate limit, y errores de red

## Notas

- El script valida que `CategoryId` sea un número entero
- Se omiten líneas con CategoryId inválido o Name vacío
- Los errores se reportan pero el script continúa procesando
- Usa Ctrl+C para interrumpir el proceso de forma segura
