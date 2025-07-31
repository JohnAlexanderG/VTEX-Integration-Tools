# VTEX Integration Tools

Colección de utilidades de transformación de datos en Python para la integración con la plataforma de comercio electrónico VTEX. El proyecto implementa una arquitectura de flujo de trabajo secuencial numerado para convertir datos CSV de productos al formato listo para VTEX con integración completa de API y validación.

## Configuración del Entorno

### Requisitos Previos
- Python 3.x instalado
- Acceso a las credenciales de la API de VTEX

### Configuración del Entorno Virtual

1. **Crear el entorno virtual**:
```bash
python3 -m venv venv
```

2. **Activar el entorno virtual**:
```bash
# En macOS/Linux
source venv/bin/activate

# En Windows
venv\Scripts\activate
```

3. **Instalar dependencias**:
```bash
pip install requests python-dotenv
```

4. **Configurar variables de entorno**:
Crear archivo `.env` en la raíz del proyecto:
```
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Arquitectura del Proyecto

### Diseño de Flujo de Trabajo Secuencial
El proyecto implementa una arquitectura estilo microservicios con directorios numerados que representan un pipeline claro de procesamiento de datos:

1. **Importación y Transformación de Datos** (01-03): Ingesta CSV, normalización de campos, procesamiento de categorías
2. **Unificación y Validación de Datos** (04-05): Fusión de conjuntos de datos, detección de registros faltantes
3. **Integración con API VTEX** (06-08): Mapeo de categorías, resolución de IDs de marca usando APIs VTEX
4. **Validación y Operaciones** (09-10): Análisis de preparación de productos, actualizaciones masivas

### Patrón de Flujo de Datos Principal
```
Datos CSV → Conversión JSON → Transformación de Campos → Procesamiento de Categorías → 
Unificación de Datos → Mapeo API VTEX → Validación → Salida Final
```

## Flujo de Trabajo Completo

### 1. Conversión y Transformación de Datos
```bash
# 1. Conversión CSV a JSON
python3 01_csv_to_json/csv_to_json.py input.csv data.json --indent 4

# 2. División de claves compuestas y normalización de campos
python3 02_data-transform/transform_json_script.py data.json transformed.json --indent 4

# 3. Procesamiento de categorías y detección de entradas problemáticas
python3 03_transform_json_category/transform_json_category.py transformed.json categorized.json
```

### 2. Unificación y Comparación de Datos
```bash
# 4. Unificar conjuntos de datos (datos antiguos + nuevos)
python3 04_unificar_json/unificar_json.py old_data.json new_data.json unified.json

# 5. Comparar conjuntos de datos para registros faltantes
python3 05_compare_json_to_csv/compare_json_to_csv.py old_data.json new_data.json missing.csv
```

### 3. Integración con VTEX API
```bash
# 6. Mapear IDs de categoría VTEX (usa credenciales .env automáticamente)
python3 06_map_category_ids/map_category_ids.py unified.json categorized.json

# 7. Extraer mapeos de marca de CSV especializado
python3 07_csv_to_json_marca/csv_to_json_marca.py marcas.csv marcas.json

# 8. Coincidir IDs de marca VTEX (usa credenciales .env automáticamente)
python3 08_vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json categorized.json
```

### 4. Validación y Operaciones Finales
```bash
# 9. Generar reporte de preparación de productos
python3 09_generate_vtex_report/generate_vtex_report.py final_data.json -o report.md

# 10. Actualización masiva de productos VTEX
python3 10._update_vtex_products/update_vtex_products.py data.json
```

### Comandos de Utilidades
```bash
# Traducir claves en español a inglés
python3 translate_keys/translate_keys.py input.json translated.json --indent 4

# Convertir JSON de vuelta a CSV
python3 json_to_csv/json_to_csv.py input.json output.csv
```

## Descripción de Componentes

### Pipeline de Transformación de Datos (01-03)
- **`01_csv_to_json/`**: Convertidor principal de CSV a JSON con interfaz CLI
- **`02_data-transform/`**: Transformador JSON-a-JSON que divide claves compuestas y normaliza campos
- **`03_transform_json_category/`**: Procesamiento de categorías y detección de entradas problemáticas

### Pipeline de Unificación y Validación (04-05)
- **`04_unificar_json/`**: Fusiona múltiples archivos JSON con reconciliación de datos
- **`05_compare_json_to_csv/`**: Compara datos JSON y CSV para encontrar registros faltantes (comparación SKU vs RefId)

### Pipeline de Integración VTEX (06-08)
- **`06_map_category_ids/`**: Mapea categorías de productos a IDs de departamento y categoría de VTEX usando la API
- **`07_csv_to_json_marca/`**: Extrae información de SKU y marca de CSV donde TIPO == 'MARCA'
- **`08_vtex_brandid_matcher/`**: Coincide marcas de productos con IDs de marca de VTEX

### Pipeline de Validación y Operaciones (09-10)
- **`09_generate_vtex_report/`**: Genera reportes sobre la preparación de productos para la creación del catálogo VTEX
- **`10_update_vtex_products/`**: Actualiza productos VTEX en lote (establece IsActive/IsVisible en False)

### Herramientas de Utilidad
- **`translate_keys/`**: Traduce claves JSON del español al inglés con lógica de deduplicación
- **`json_to_csv/`**: Convertidor simple de JSON a CSV

## Lógica de Integración VTEX

### Proceso de Mapeo de Categorías
- **Formato de entrada**: `"Departamento>Categoría>Subcategoría"`
- **Normalización Unicode**: Para coincidencia con catálogo VTEX
- **Prioridad de asignación de ID**: ID Subcategoría > ID Categoría > ID Departamento
- **Formato de salida**: `"Departamento/Categoría/Subcategoría"` con "/" existente → "|"

### Proceso de Coincidencia de Marcas
1. `RefId` → buscar SKU en marcas.json
2. SKU → extraer nombre de marca
3. Nombre de marca → coincidir con catálogo de marcas VTEX (sin distinción de mayúsculas, normalizado)
4. Marca VTEX → asignar BrandId o null si no se encuentra

### Clasificación de Preparación de Productos
- **Listos para crear**: Tienen DepartmentId, CategoryId y BrandId (todos no nulos)
- **Requieren creación de categoría**: Falta CategoryId pero tienen nombre de categoría
- **No se pueden crear**: Falta BrandId (requisito crítico de VTEX)

### Evolución de la Estructura de Datos
1. **CSV sin procesar**: Nombres de campos en español, valores compuestos, jerarquías de categorías
2. **JSON normalizado**: Campos en inglés, valores divididos, datos limpios
3. **JSON categorizado**: CategoryPath agregado con separadores "/", entradas problemáticas marcadas
4. **JSON unificado**: Conjuntos de datos antiguos/nuevos fusionados, resolución de duplicados
5. **JSON listo para VTEX**: DepartmentId, CategoryId, BrandId mapeados desde APIs VTEX
6. **Clasificación final**: Productos categorizados como listos/requieren-creación/no-se-pueden-crear

### Mapeos de Campos Clave
- `SKU` → `RefId` (identificador de producto VTEX)
- `Categoría` → `CategoryPath` (ruta jerárquica con separadores "/")
- `Descripción` → `Description` + `Name` (formateado de MAYÚSCULAS a Formato de Título)
- Jerarquía de categoría → `DepartmentId` + `CategoryId` (vía API VTEX)
- Nombre de marca → `BrandId` (vía API VTEX)

## Patrones Arquitectónicos Clave

### Patrones de Transformación de Datos
- **División de claves compuestas**: `"Campo1, Campo2": "Valor1, Valor2"` → campos normalizados separados
- **Normalización Unicode**: Elimina acentos usando unicodedata para coincidencia precisa
- **Normalización de nombres de campos**: Español → Inglés con camelCase y patrones regex
- **Transformación de rutas de categoría**: `"Categoría>Subcategoría"` → `"Categoría/Subcategoría"` para formato VTEX

### Arquitectura de Integración API
- **Credenciales centralizadas**: Todas las herramientas de API VTEX leen del `.env` raíz automáticamente
- **Construcción de endpoints**: URLs dinámicas usando nombre de cuenta y variables de entorno
- **Resistencia a errores**: Reportes de error integrales con logs markdown y exportaciones CSV
- **Coincidencia de texto Unicode**: Eliminación de acentos y normalización de mayúsculas para búsquedas API

### Manejo de Errores y Validación
- **Exportaciones multi-formato**: Casos fallidos exportados a formatos JSON y CSV
- **Registro detallado**: Reportes markdown con indicadores emoji y análisis de errores agrupados
- **Reconciliación de datos**: Comparación SKU vs RefId con resolución de conflictos
- **Clasificación de productos**: Análisis de preparación de tres niveles para creación de catálogo VTEX

## Organización de Archivos

### Convenciones de Entrada/Salida
- **Archivos de entrada**: `input.csv`, `data.csv`, `marcas.csv`
- **Archivos intermedios**: `data.json`, `transformed.json`, `categorized.json`
- **Archivos de salida**: `final_data.json`, `report.md`, logs basados en timestamp
- **Exportaciones de error**: `_problematicos.json/csv`, `_no_unificados.csv`, `no_brandid_found.csv`

### Reportes Generados
- **Logs markdown**: Indicadores emoji, errores agrupados, estadísticas de éxito
- **Exportaciones CSV**: Todos los casos fallidos con datos originales para revisión manual
- **Exportaciones JSON**: Datos estructurados para procesamiento programático

## Desarrollo y Extensión

### Patrones de Desarrollo
- **Diseño CLI-First**: Todas las herramientas esperan invocación basada en argparse con `--help`
- **Formato JSON consistente**: Estándar de indentación de 4 espacios en todo el proyecto
- **Codificación UTF-8**: Crítico para manejo de caracteres en español
- **Configuración por entorno**: Credenciales y configuración VTEX desde `.env` raíz

### Guías de Extensión
- Agregar nuevos directorios numerados para extensiones de flujo de trabajo
- Seguir patrón de docstring con ejemplos de uso en encabezados de módulo
- Implementar manejo integral de errores con exportaciones CSV/JSON
- Generar tanto salidas de datos como reportes legibles por humanos
- Usar normalización Unicode para cualquier operación de coincidencia de texto

### Patrones Comunes de Depuración
- Verificar archivo `.env` para credenciales VTEX
- Validar normalización Unicode para problemas de coincidencia de texto
- Revisar logs markdown generados para fallas de mapeo API
- Examinar exportaciones CSV para datos problemáticos que requieren revisión manual
- Validar consistencia de indentación y codificación JSON

## Dependencias

**Librerías Principales**:
- `json`, `csv`, `argparse`, `sys` (librería estándar)
- `requests` (llamadas API VTEX)
- `python-dotenv` (gestión de entorno)
- `unicodedata` (normalización de texto)

Las dependencias se importan directamente en los scripts - no hay gestión centralizada de requisitos.

## Desactivar el Entorno Virtual

```bash
deactivate
```