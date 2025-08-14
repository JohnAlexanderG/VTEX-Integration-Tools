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
El proyecto implementa una arquitectura estilo microservicios con directorios numerados que representan un pipeline completo de creación de catálogo e-commerce:

1. **Importación y Transformación de Datos** (01-03): Ingesta CSV, normalización de campos, procesamiento de categorías
2. **Unificación y Validación de Datos** (04-05): Fusión de conjuntos de datos, detección de registros faltantes
3. **Integración con API VTEX** (06-08): Mapeo de categorías, resolución de IDs de marca usando APIs VTEX
4. **Validación y Operaciones** (09-11): Análisis de preparación de productos, actualizaciones masivas, formateo VTEX
5. **Creación de Catálogo VTEX** (12-15): Creación completa de productos y SKUs en VTEX
6. **Gestión de Medios y Archivos** (16-18): Manejo de imágenes SKU, subida de archivos, limpieza de contenido
7. **Operaciones de Utilidad** (19+): Filtrado de datos, conversión de formatos, transformaciones especializadas

### Patrón de Flujo de Datos Extendido
```
Datos CSV → Conversión JSON → Transformación de Campos → Procesamiento de Categorías → 
Unificación de Datos → Mapeo API VTEX → Validación → Creación de Productos →
Creación de SKUs → Subida de Medios → Gestión de Archivos → Verificación Final
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

### 4. Validación y Formateo
```bash
# 9. Generar reporte de preparación de productos
python3 09_generate_vtex_report/generate_vtex_report.py final_data.json -o report.md

# 10. Actualización masiva de productos VTEX
python3 10._update_vtex_products/update_vtex_products.py data.json

# 11. Formatear productos para creación VTEX
python3 11_vtex_product_format_create/vtex_product_formatter.py data.json
```

### 5. Creación de Catálogo VTEX
```bash
# 12. Crear productos en VTEX vía API
python3 12_vtex_product_create/vtex_product_create.py formatted_products.json

# 13. Extraer respuestas exitosas de creación
python3 13_extract_json_response/extract_response.py successful_products.json

# 14. Transformar datos de productos a formato SKU
python3 14_to_vtex_skus/to_vtex_skus.py response_data.json sku_data.json

# 15. Crear SKUs en VTEX vía API
python3 15_vtex_sku_create/vtex_sku_create.py vtex_skus.json
```

### 6. Gestión de Medios y Archivos
```bash
# 16. Fusionar datos de productos con imágenes
python3 16_merge_sku_images/merge_sku_images.py products.json images.csv

# 16.2. Mapear RefId a SkuId para asociaciones precisas
python3 16.2_refid_to_skuid/refid_to_skuid_mapper.py data.json mapping.json

# 17. Subir imágenes a SKUs VTEX
python3 17_upload_sku_images/upload_sku_images.py sku_images.json

# 18. Eliminar archivos SKU obsoletos
python3 18_delete_sku_files/delete_sku_files.py sku_list.json
```

### 7. Comandos de Utilidades
```bash
# Filtrar datos por estado o condiciones
python3 19_csv_json_status_filter/csv_json_status_filter.py input.csv output.json

# Extraer mapeos RefId y EAN
python3 extract_refid_ean/extract_refid_ean.py data.json sku_ean.json

# Conversión de fuentes TTF a WOFF2
python3 tranform_font-ttf-woff/ttf2woff2_converter.py fonts/ woff2-fonts/

# Traducir claves en español a inglés
python3 translate_keys/translate_keys.py input.json translated.json --indent 4

# Convertir JSON de vuelta a CSV
python3 json_to_csv/json_to_csv.py input.json output.csv

# Filtrar datos comparando archivos JSON por _SKUReferenceCode
python3 filtrar_sku/filtrar_sku.py archivo1.json archivo2.json
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

### Pipeline de Validación y Formateo (09-11)
- **`09_generate_vtex_report/`**: Genera reportes sobre la preparación de productos para la creación del catálogo VTEX
- **`10._update_vtex_products/`**: Actualiza productos VTEX en lote (establece IsActive/IsVisible en False)
- **`11_vtex_product_format_create/`**: Formatea productos clasificados al formato requerido por la API de creación VTEX

### Pipeline de Creación de Catálogo VTEX (12-15)
- **`12_vtex_product_create/`**: Crea productos en VTEX vía API con manejo de rate limiting y retry
- **`13_extract_json_response/`**: Extrae respuestas exitosas de creación de productos para obtener Product IDs
- **`14_to_vtex_skus/`**: Transforma datos de respuesta de productos al formato SKU con dimensiones y EAN
- **`15_vtex_sku_create/`**: Crea SKUs en VTEX vía API con manejo comprehensivo de errores

### Pipeline de Gestión de Medios (16-18)
- **`16_merge_sku_images/`**: Combina datos de productos con URLs de imágenes de fuentes externas
- **`16.2_refid_to_skuid/`**: Mapea valores RefId a SkuId VTEX para asociaciones precisas de imágenes
- **`17_upload_sku_images/`**: Sube imágenes en lote a SKUs VTEX con validación de URL y formato
- **`18_delete_sku_files/`**: Elimina archivos SKU obsoletos y gestiona activos de catálogo

### Operaciones de Utilidad Extendidas (19+)
- **`19_csv_json_status_filter/`**: Filtra datasets basado en condiciones de estado y criterios
- **`extract_refid_ean/`**: Extrae mapeos de SKU y códigos EAN de datasets unificados
- **`tranform_font-ttf-woff/`**: Convierte fuentes TTF a formato WOFF2 para optimización web
- **`filtrar_sku/`**: Compara dos archivos JSON por _SKUReferenceCode, exporta coincidencias como JSON con _SkuId y no coincidencias como CSV

### Herramientas de Utilidad Base
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
6. **Reporte de clasificación**: Productos categorizados como listos/requieren-creación/no-se-pueden-crear
7. **Formato de producto VTEX**: Formateado para endpoint de creación de productos API VTEX
8. **Productos creados**: Respuestas API VTEX con asignaciones de ProductId
9. **Generación de SKU**: Respuestas de productos transformadas a formato de creación SKU
10. **SKUs creados**: Respuestas de creación SKU VTEX con asignaciones de SkuId
11. **Integración de medios**: Imágenes SKU fusionadas y subidas al catálogo VTEX

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
- **Archivos de entrada**: `input.csv`, `data.csv`, `marcas.csv`, `images.csv`
- **Archivos intermedios**: `data.json`, `transformed.json`, `categorized.json`, `sku_images.json`
- **Archivos de salida**: `final_data.json`, `report.md`, logs basados en timestamp de creación
- **Exportaciones de error**: `_problematicos.json/csv`, `_no_unificados.csv`, `no_brandid_found.csv`
- **Salidas de creación**: `{timestamp}_vtex_creation_successful.json`, `{timestamp}_vtex_creation_failed.json`
- **Respuestas API**: archivos `responses.json` organizados por carpetas de fecha

### Reportes Generados
- **Reportes de creación**: Reportes markdown con timestamp con estadísticas de lote y análisis de errores
- **Reportes de subida**: Logs de subida de medios con tasas de éxito y detalles de fallas
- **Logs de respuesta API**: Logging comprehensivo de interacciones API VTEX
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
- **Problemas de entorno**: Verificar archivo `.env` para credenciales VTEX y nombres de variables correctos
- **Coincidencia de texto**: Validar normalización Unicode para problemas de coincidencia de texto
- **Fallas API**: Revisar logs markdown generados para fallas de mapeo y creación API
- **Problemas de datos**: Examinar exportaciones CSV para datos problemáticos que requieren revisión manual
- **Problemas de formato**: Validar consistencia de indentación y codificación JSON (UTF-8, indent 4)
- **Rate limiting**: Monitorear límites API y ajustar delays si es necesario
- **Operaciones en lote**: Verificar carpetas timestamp para resultados de operación en lote organizados
- **Archivos no encontrados**: Asegurar que archivos de entrada existen y rutas son correctas
- **Errores de permisos**: Verificar activación de venv e instalación de paquetes en entorno correcto

## Dependencias

**Librerías Principales**:
- `json`, `csv`, `argparse`, `sys` (librería estándar)
- `requests` (llamadas API VTEX)
- `python-dotenv` (gestión de entorno)
- `unicodedata` (normalización de texto)
- `fonttools`, `brotli` (conversión de fuentes, componentes específicos)

**Dependencias por Componente**:
- Componentes principales (01-15): `requests`, `python-dotenv`
- Gestión de medios (16-18): puede requerir entornos virtuales separados
- Conversión de fuentes (tranform_font-ttf-woff): `fonttools`, `brotli`

Las dependencias se importan directamente en los scripts - no hay gestión centralizada de requisitos.

## Desactivar el Entorno Virtual

```bash
deactivate
```