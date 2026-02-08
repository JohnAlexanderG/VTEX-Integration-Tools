# VTEX Integration Tools

Colección de utilidades de transformación de datos en Python para la integración con la plataforma de comercio electrónico VTEX. El proyecto implementa una arquitectura de flujo de trabajo secuencial numerado para convertir datos CSV de productos al formato listo para VTEX con integración completa de API, validación, creación de catálogo, gestión de precios e inventario, y asignación de especificaciones de producto.

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
4. **Validación, Actualización y Formateo** (09-11, 10.1): Análisis de preparación de productos, actualización de descripciones, formateo VTEX
5. **Creación de Catálogo VTEX** (12-15.2): Creación completa de productos, SKUs y códigos EAN en VTEX
6. **Gestión de Medios y Archivos** (16-18): Manejo de imágenes SKU, subida de archivos, limpieza de contenido
7. **Operaciones Masivas de SKU** (20-21): Actualización de atributos SKU desde CSV, detección de SKUs sin imágenes
8. **Gestión de Precios e Inventario** (22-23, 28-29): Actualización masiva de precios, carga de inventario, filtrado previo
9. **Gestión de Categorías** (24-26): Creación de jerarquía de categorías, corrección de errores, filtrado por marca
10. **Especificaciones de Producto** (30-40): Pipeline completo de creación y asignación de especificaciones VTEX
11. **Consulta y Comparación de SKUs** (41-42): Comparación ERP vs VTEX, consulta de detalles de SKU
12. **Gestión de Inventario Diferencial** (44): Filtrado inteligente de inventario para actualizaciones incrementales
13. **Herramientas de Utilidad** (19, 27, 43 y no numeradas): Filtrado, conversión de formatos, generadores NDJSON, XML

### Patrón de Flujo de Datos Extendido
```
Datos CSV → Conversión JSON → Transformación de Campos → Procesamiento de Categorías →
Unificación de Datos → Mapeo API VTEX → Validación → Creación de Categorías →
Creación de Productos → Creación de SKUs → Asignación de EANs →
Subida de Medios → Actualización de Precios → Carga de Inventario →
Especificaciones de Producto → Verificación Final
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

### 4. Validación, Actualización y Formateo
```bash
# 9. Generar reporte de preparación de productos
python3 09_generate_vtex_report/generate_vtex_report.py final_data.json -o report.md

# 10. [DEPRECATED] Actualización masiva de productos VTEX (desactiva IsActive/IsVisible)
python3 10_deprecated_update_vtex_products/update_vtex_products.py data.json

# 10.1. Actualizar descripciones de productos VTEX desde CSV
python3 10.1_update_product_description/update_product_description.py products.json descriptions.csv

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

# 15.2. Crear códigos EAN para SKUs en VTEX
python3 15.2_vtex_sku_ean_create/vtex_sku_ean_create.py vtex_skus.json
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

### 7. Operaciones Masivas de SKU
```bash
# 20. Actualizar atributos de SKU desde CSV (IsActive, Name, dimensiones, peso)
python3 20_vtex_update_sku_from_csv/vtex_update_sku_from_csv.py input.csv

# 21. Encontrar SKUs sin imágenes asociadas en VTEX
python3 21_vtex_sku_no_image_finder/vtex_sku_no_image_finder.py
```

### 8. Gestión de Precios e Inventario
```bash
# 28. Filtrar lista de precios para incluir solo productos existentes en VTEX
python3 28_filter_price_list/filter_price_list.py price_list.csv vtex_skus.csv

# 22. Actualizar precios en VTEX (soporta costPrice opcional)
python3 22_vtex_price_updater/vtex_price_updater_cost_optional.py prices.json

# 29. Filtrar inventario para incluir solo productos existentes en VTEX
python3 29_filter_inventory/filter_inventory.py inventory.csv vtex_skus.csv

# 23. Cargar inventario en VTEX con rate limiting concurrente
python3 23_vtex_inventory_uploader/vtex_inventory_uploader.py inventory.json
```

### 9. Gestión de Categorías
```bash
# 24. Crear jerarquía completa de categorías en VTEX (3 niveles)
python3 24_vtex_category_creator/vtex_category_creator.py category_data.json --dry-run  # Probar primero
python3 24_vtex_category_creator/vtex_category_creator.py category_data.json             # Crear

# 25. Corregir errores de categoría cruzando datos con reporte de errores
python3 25_fix_category_errors/fix_category_errors.py data1.json data2.json errors.md

# 26. Filtrar productos por BrandId específico
python3 26_filter_brandid/filter_brandid.py data.json
```

### 10. Especificaciones de Producto
Pipeline completo para crear y asignar especificaciones de producto en VTEX:

```
39: csv_sku_matcher (filtrar por SKUs existentes)
  ↓
39: enrich_category_ids (enriquecer con IDs de categoría)
  ↓
40: csv_to_vtex_specifications (transformar a formato VTEX)
  ↓
35: unify_category_ids (extraer lista única de categorías)
  ↓
36: vtex_groups_by_category (consultar grupos existentes)
  ↓
31: vtex_specificationgroup_create (crear grupos faltantes)
  ↓
32: vtex_specification_create (crear campos de especificación)
  ↓
37: category_specification_matcher (emparejar productos con campos)
  ↓
33: sku_productid_matcher (obtener ProductIds)
  ↓
38: add_product_specifications (asignar valores a productos)

Para limpiar especificaciones existentes:
34: delete_product_specifications
```

```bash
# 39. Filtrar CSV de especificaciones por SKUs existentes en VTEX
python3 39_csv_sku_matcher/csv_sku_matcher.py existing_skus.csv data.csv output_prefix

# 39. Enriquecer datos con IDs de categoría faltantes
python3 39_csv_sku_matcher/enrich_category_ids.py input.csv categories.csv output.csv

# 40. Transformar CSV de producto a formato de especificación VTEX
python3 40_csv_to_vtex_specifications/csv_to_vtex_specifications.py input.csv output.csv

# 30. Comparar y fusionar especificaciones de categoría y producto por SKU
python3 30_match_specifications/match_specifications.py categorias.csv productos.csv --deduplicate

# 35. Extraer lista única de IDs de categoría de CSV
python3 35_unify_category_ids/unify_category_ids.py input.csv output.csv

# 36. Consultar grupos de especificación por categoría vía API VTEX
python3 36_vtex_groups_by_category/vtex_groups_by_category.py categories.csv --dry-run

# 31. Crear grupos de especificación en VTEX desde CSV
python3 31_vtex_specificationgroup_create/vtex_specificationgroup_create.py input.csv --dry-run

# 32. Crear campos de especificación dentro de grupos VTEX
python3 32_vtex_specification_create/vtex_specification_create.py groups.json specs.json --dry-run

# 37. Emparejar productos con especificaciones por CategoryId
python3 37_category_specification_matcher/category_specification_matcher.py products.csv specs.csv -o output.csv

# 33. Emparejar SKU con ProductId para asignación de especificaciones
python3 33_sku_productid_matcher/sku_productid_matcher.py mapping.json data.json output.csv

# 38. Asignar valores de especificación a productos VTEX vía API
python3 38_add_product_specifications/add_product_specifications.py input.csv --workers 8 --rps 15

# 34. Eliminar todas las especificaciones de productos (limpieza)
python3 34_delete_product_specifications/delete_product_specifications.py products.csv --dry-run
```

### 11. Consulta y Comparación de SKUs
```bash
# 41. Comparar SKUs de ERP vs VTEX e identificar faltantes
python3 41_generate_sku_range/generate_sku_range.py vtex_export.xls erp_inventory.csv missing_skus.csv

# 42. Consultar detalles de SKU en VTEX por RefId con retry y backoff
python3 42_vtex_sku_getter/vtex_sku_getter.py input.csv output.json --delay 2 --timeout 45
```

### 12. Gestión de Inventario Diferencial
```bash
# 44. Filtrar inventario completo para identificar registros que requieren actualización en VTEX
python3 44_stock_diff_filter/stock_diff_filter.py vtex_skus.xls uploaded.csv full_inventory.csv vtex_inventory.xls output_prefix
```

### 13. Comandos de Utilidades
```bash
# Filtrar datos por estado o condiciones
python3 19_csv_json_status_filter/csv_json_status_filter.py input.csv output.json

# Limpiar CSV (eliminar espacios y comas finales)
python3 27_csv_cleaner/csv_cleaner.py input.csv output.csv

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

# Convertir JSON array a NDJSON con filtrado de campos
python3 json_to_ndjson/json_to_ndjson.py -i input.json -o output.ndjson --keep field1,field2

# Generar registros de inventario NDJSON desde datos de SKU
python3 ndjson_inventory_generator/ndjson_inventory_generator.py input.ndjson output.ndjson --mode inventory

# Generar registros de precios NDJSON desde datos de SKU
python3 ndjson_price_generator/ndjson_price_generator.py input.ndjson output.ndjson --cost-price 9000000

# Generar XML de venta desde orden VTEX
python3 generate_sale_xml/generate_sale_xml.py -i response-order.json -o venta.xml

# Convertir tabular (CSV/XLSX) a DynamoDB JSON
python3 to_dynamojson/dynamojson_from_tabular.py input.xlsx -o output.json --table-name MyTable

# Dividir batch DynamoDB en lotes de 25 items
python3 to_dynamojson/split_dynamo_batch.py batch.json --batch-size 25

# Convertir CSV con columna DynamoDB a JSON plano
python3 43_dynamodb_to_json/dynamodb_to_json.py input.csv output.json --indent 4
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

### Pipeline de Validación y Formateo (09-11, 10.1)
- **`09_generate_vtex_report/`**: Genera reportes sobre la preparación de productos para la creación del catálogo VTEX
- **`10_deprecated_update_vtex_products/`**: ~~Actualiza productos VTEX en lote~~ **[DEPRECATED]** — Desactiva IsActive/IsVisible, solo usar durante carga inicial
- **`10.1_update_product_description/`**: Actualiza descripciones de productos en VTEX cruzando JSON de productos con CSV de descripciones por SKU/RefId
- **`11_vtex_product_format_create/`**: Formatea productos clasificados al formato requerido por la API de creación VTEX

### Pipeline de Creación de Catálogo VTEX (12-15.2)
- **`12_vtex_product_create/`**: Crea productos en VTEX vía API con manejo de rate limiting y retry
- **`13_extract_json_response/`**: Extrae respuestas exitosas de creación de productos para obtener Product IDs
- **`14_to_vtex_skus/`**: Transforma datos de respuesta de productos al formato SKU con dimensiones y EAN
- **`15_vtex_sku_create/`**: Crea SKUs en VTEX vía API con manejo comprehensivo de errores
- **`15.2_vtex_sku_ean_create/`**: Crea códigos EAN para SKUs en VTEX vía API de catálogo con rate limiting

### Pipeline de Gestión de Medios (16-18)
- **`16_merge_sku_images/`**: Combina datos de productos con URLs de imágenes de fuentes externas
- **`16.2_refid_to_skuid/`**: Mapea valores RefId a SkuId VTEX para asociaciones precisas de imágenes
- **`17_upload_sku_images/`**: Sube imágenes en lote a SKUs VTEX con validación de URL y formato
- **`18_delete_sku_files/`**: Elimina archivos SKU obsoletos y gestiona activos de catálogo

### Pipeline de Operaciones Masivas de SKU (20-21)
- **`20_vtex_update_sku_from_csv/`**: Actualiza atributos de SKU (IsActive, Name, dimensiones, peso) desde CSV con búsqueda por RefId
- **`21_vtex_sku_no_image_finder/`**: Encuentra SKUs en VTEX sin imágenes asociadas y exporta resultados a CSV con capacidad de reanudación

### Pipeline de Precios e Inventario (22-23, 28-29)
- **`22_vtex_price_updater/`**: Actualización masiva de precios VTEX con soporte de costPrice opcional y requests concurrentes
- **`23_vtex_inventory_uploader/`**: Cargador concurrente de inventario VTEX con rate limiting token bucket y backoff adaptativo
- **`28_filter_price_list/`**: Filtra lista de precios CSV para incluir solo productos existentes en VTEX con estadísticas
- **`29_filter_inventory/`**: Filtra inventario CSV para incluir solo productos en VTEX preservando todos los registros por almacén

### Pipeline de Gestión de Categorías (24-26)
- **`24_vtex_category_creator/`**: Crea jerarquía completa de 3 niveles (Departamentos → Categorías → Subcategorías) en VTEX con re-ejecución idempotente
- **`25_fix_category_errors/`**: Corrige errores de categoría en datos de productos cruzando archivos JSON con reporte de errores markdown
- **`26_filter_brandid/`**: Filtra datos JSON de productos para incluir solo registros con un BrandId específico

### Pipeline de Especificaciones de Producto (30-40)
- **`30_match_specifications/`**: Compara y fusiona especificaciones de categoría y producto por SKU con deduplicación opcional
- **`31_vtex_specificationgroup_create/`**: Crea grupos de especificación en VTEX vía API desde CSV con modo dry-run
- **`32_vtex_specification_create/`**: Crea campos de especificación dentro de grupos usando respuestas de creación de grupos y plantillas JSON
- **`33_sku_productid_matcher/`**: Empareja SKU con _SKUReferenceCode para enriquecer datos con _ProductId
- **`34_delete_product_specifications/`**: Elimina especificaciones de productos con workers concurrentes y rate limiting token bucket
- **`35_unify_category_ids/`**: Extrae IDs únicos de categoría de columnas categorieID y SubcategorieID, deduplicados y ordenados
- **`36_vtex_groups_by_category/`**: Consulta API VTEX para obtener grupos de especificación por ID de categoría con rate limiting
- **`37_category_specification_matcher/`**: Empareja productos con especificaciones por CategoryId separando resultados en coincidencias y no coincidencias
- **`38_add_product_specifications/`**: Asigna valores de especificación a productos VTEX vía API concurrente con backoff adaptativo para 429
- **`39_csv_sku_matcher/`**: Filtra CSV por SKUs existentes y enriquece con IDs de categoría faltantes (dos scripts: `csv_sku_matcher.py` y `enrich_category_ids.py`)
- **`40_csv_to_vtex_specifications/`**: Transforma CSV de producto a formato de especificación VTEX mapeando columnas de entrada a estructura requerida

### Pipeline de Consulta de SKUs (41-42)
- **`41_generate_sku_range/`**: Compara SKUs de ERP vs VTEX e identifica códigos SKU faltantes en VTEX
- **`42_vtex_sku_getter/`**: Consulta API VTEX para detalles de SKU por RefId con retry exponencial y filtrado de 404

### Gestión de Inventario Diferencial (44)
- **`44_stock_diff_filter/`**: Filtra inventario completo para identificar registros que requieren actualización en VTEX comparando SKUs válidos, excluyendo duplicados procesados y contrastando con inventario actual

### Herramientas de Utilidad
- **`19_csv_json_status_filter/`**: Filtra datasets basado en condiciones de estado y criterios
- **`27_csv_cleaner/`**: Limpia archivos CSV eliminando espacios en blanco y comas finales
- **`43_dynamodb_to_json/`**: Convierte CSV con columna DynamoDB AttributeValue JSON a JSON plano deserializando tipos recursivamente
- **`extract_refid_ean/`**: Extrae mapeos de SKU y códigos EAN de datasets unificados
- **`tranform_font-ttf-woff/`**: Convierte fuentes TTF a formato WOFF2 para optimización web
- **`filtrar_sku/`**: Compara dos archivos JSON por _SKUReferenceCode, exporta coincidencias como JSON con _SkuId y no coincidencias como CSV
- **`translate_keys/`**: Traduce claves JSON del español al inglés con lógica de deduplicación
- **`json_to_csv/`**: Convertidor simple de JSON a CSV
- **`json_to_ndjson/`**: Convertidor streaming de JSON array a NDJSON con filtrado de campos y auto-detección de formato
- **`ndjson_inventory_generator/`**: Genera registros de inventario VTEX desde datos NDJSON de SKU (modos inventario y reset para 18 almacenes)
- **`ndjson_price_generator/`**: Genera registros de precios VTEX (costPrice y basePrice) desde datos NDJSON de referencia SKU
- **`generate_sale_xml/`**: Convierte JSON de orden VTEX a formato XML de venta para integración ERP
- **`to_dynamojson/`**: Convierte archivos tabulares (CSV/XLSX/XLS) a formato DynamoDB JSON con inferencia de tipos, incluye utilidad de división en lotes de 25 items

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

### Creación de Jerarquía de Categorías (24)
- **Estructura automatizada de 3 niveles**: Crea Departamentos → Categorías → Subcategorías desde JSON plano
- **Diseño idempotente**: Re-ejecuciones omiten categorías existentes sin errores
- **Pre-verificación**: Consulta árbol de categorías VTEX existente antes de crear
- **Procesamiento secuencial**: Crea nivel 1 primero, luego nivel 2, luego nivel 3 para asegurar que las categorías padre existan
- **Normalización Unicode**: Coincidencia robusta removiendo acentos
- **Modo dry-run**: Simula operaciones sin hacer llamadas API reales

### Pipeline de Especificaciones
Flujo completo para asignar especificaciones de producto en VTEX:
1. **Filtrado de SKUs** (39): Filtra datos de especificaciones por SKUs que existen en VTEX
2. **Enriquecimiento** (39): Completa IDs de categoría faltantes usando tabla de búsqueda
3. **Transformación** (40): Convierte datos a formato de especificación VTEX
4. **Extracción de categorías** (35): Obtiene lista única de IDs de categoría
5. **Consulta de grupos** (36): Verifica grupos de especificación existentes por categoría
6. **Creación de grupos** (31): Crea grupos de especificación faltantes
7. **Creación de campos** (32): Crea campos de especificación dentro de grupos
8. **Emparejamiento** (37): Vincula productos con campos de especificación por categoría
9. **Resolución de IDs** (33): Obtiene ProductIds para asignación
10. **Asignación** (38): Asigna valores de especificación a productos vía API

### Actualización de Precios e Inventario
- **Precios**: Endpoint `/api/pricing/prices/{skuId}` con soporte de costPrice y basePrice
- **Inventario**: Endpoint de warehouse con carga concurrente y token bucket rate limiting
- **Filtrado previo recomendado**: Usar herramientas 28 (precios) y 29 (inventario) para filtrar solo productos existentes en VTEX antes de actualizar

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
12. **Códigos EAN asignados**: EANs creados para SKUs vía API de catálogo
13. **Precios actualizados**: costPrice y basePrice establecidos para cada SKU
14. **Inventario cargado**: Cantidades de stock asignadas por almacén para cada SKU
15. **Especificaciones asignadas**: Valores de especificación vinculados a productos por categoría

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
- **Procesamiento concurrente**: ThreadPoolExecutor para operaciones masivas (precios, inventario, especificaciones)
- **Rate limiting con token bucket**: Control de velocidad adaptativo para respetar límites de API
- **Backoff exponencial adaptativo**: Reintentos inteligentes con retroceso ante errores 429
- **Resistencia a errores**: Reportes de error integrales con logs markdown y exportaciones CSV
- **Coincidencia de texto Unicode**: Eliminación de acentos y normalización de mayúsculas para búsquedas API
- **Soporte NDJSON streaming**: Procesamiento de archivos grandes sin cargar todo en memoria

### Manejo de Errores y Validación
- **Exportaciones multi-formato**: Casos fallidos exportados a formatos JSON y CSV
- **Registro detallado**: Reportes markdown con indicadores emoji y análisis de errores agrupados
- **Reconciliación de datos**: Comparación SKU vs RefId con resolución de conflictos
- **Clasificación de productos**: Análisis de preparación de tres niveles para creación de catálogo VTEX
- **Análisis bidireccional**: Comparación ERP → VTEX y VTEX → inventario actual para actualizaciones diferenciales

## Organización de Archivos

### Convenciones de Entrada/Salida
- **Archivos de entrada**: `input.csv`, `data.csv`, `marcas.csv`, `images.csv`
- **Archivos intermedios**: `data.json`, `transformed.json`, `categorized.json`, `sku_images.json`
- **Archivos de salida**: `final_data.json`, `report.md`, logs basados en timestamp de creación
- **Exportaciones de error**: `_problematicos.json/csv`, `_no_unificados.csv`, `no_brandid_found.csv`
- **Salidas de creación**: `{timestamp}_vtex_creation_successful.json`, `{timestamp}_vtex_creation_failed.json`
- **Respuestas API**: archivos `responses.json` organizados por carpetas de fecha
- **Salidas de precios**: `price-update-success-{timestamp}.json`, `price-update-failed-{timestamp}.json`
- **Salidas de inventario**: `failures_{timestamp}.csv`, `summary_{timestamp}.md`
- **Salidas de especificaciones**: `{timestamp}_specificationgroup_creation_successful.json`, `{timestamp}_specificationgroup_creation_failed.json`
- **Archivos NDJSON**: `*.ndjson` para procesamiento streaming de datos masivos
- **Exportaciones XML**: `venta_{order_number}.xml` para integración ERP

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
- Incluir rate limiting para operaciones API VTEX (1 segundo mínimo entre requests)
- Proveer salidas con timestamp para seguimiento de operaciones en lote

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
- Operaciones masivas concurrentes (22-23, 34, 38): `concurrent.futures` (librería estándar)
- Comparación de SKUs y inventario diferencial (41, 44): `pandas`, `xlrd`
- Conversión DynamoDB desde Excel (to_dynamojson): `pandas`, `openpyxl` (opcional, solo para .xlsx/.xls)
- Utilidades sin dependencias externas: `json_to_ndjson`, `ndjson_inventory_generator`, `ndjson_price_generator`, `generate_sale_xml`, `43_dynamodb_to_json`, `27_csv_cleaner`

Las dependencias se importan directamente en los scripts - no hay gestión centralizada de requisitos.

## Desactivar el Entorno Virtual

```bash
deactivate
```
