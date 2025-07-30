# CSV to JSON - VTEX Integration Tools

Colección de utilidades de transformación de datos en Python para la integración con la plataforma de comercio electrónico VTEX. El proyecto se enfoca en convertir datos CSV a JSON y procesar información de productos para la gestión del catálogo VTEX.

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

## Flujo de Trabajo Principal

### 1. Conversión y Transformación de Datos
```bash
# Convertir CSV a JSON
python3 01_csv_to_json/csv_to_json.py input.csv data.json --indent 4

# Transformar JSON con claves compuestas
python3 02_data-transform/transform_json_script.py data.json transformed.json --indent 4
```

### 2. Integración con VTEX API
```bash
# Mapear IDs de categoría
python3 map_category_ids/map_category_ids.py transformed.json categorized.json --endpoint vtexcommercestable

# Coincidir IDs de marca
python3 vtex_brandid_matcher/vtex_brandid_matcher.py marcas.json categorized.json --account NOMBRE_CUENTA
```

### 3. Validación y Reportes
```bash
# Generar reporte de preparación para VTEX
python3 generate_vtex_report/generate_vtex_report.py final_data.json -o report.md
```

## Descripción de Scripts

### Componentes Principales del Flujo de Trabajo

- **`01_csv_to_json/csv_to_json.py`**: Convertidor principal de CSV a JSON con interfaz CLI
- **`02_data-transform/transform_json_script.py`**: Transformador JSON-a-JSON que divide claves compuestas (ej. "Campo1, Campo2" se convierte en campos separados)

### Herramientas de Integración VTEX

- **`map_category_ids/`**: Mapea categorías de productos a IDs de departamento y categoría de VTEX usando la API de VTEX
- **`vtex_brandid_matcher/`**: Coincide marcas de productos con IDs de marca de VTEX
- **`generate_vtex_report/`**: Genera reportes sobre la preparación de productos para la creación del catálogo VTEX
- **`10._update_vtex_products/`**: Actualiza productos VTEX en lote (establece IsActive/IsVisible en False)

### Convertidores Especializados

- **`csv_to_json_marca/`**: Extrae información de SKU y marca de CSV donde TIPO == 'MARCA'
- **`transform_json_category/`**: Transformaciones JSON específicas de categoría
- **`compare_json_to_csv/`**: Compara datos JSON y CSV para encontrar registros faltantes (comparación SKU vs RefId)
- **`unificar_json/`**: Fusiona múltiples archivos JSON con reconciliación de datos
- **`translate_keys/`**: Traduce claves JSON del español al inglés con lógica de deduplicación
- **`json_to_csv/`**: Convertidor simple de JSON a CSV

## Lógica de Integración VTEX

### Clasificación de Productos
Los productos se clasifican según su preparación para VTEX:
- **Listos para crear**: Tienen DepartmentId, CategoryId y BrandId
- **Requieren creación de categoría**: Falta CategoryId pero tienen nombre de categoría
- **No se pueden crear**: Falta BrandId (requisito crítico)

### Patrones de Procesamiento de Datos
- **División de claves compuestas**: Transforma "Lista de Precios 1, Lista de Precios 2" en campos normalizados separados
- **Normalización de claves**: Convierte nombres de campos usando patrones regex y formato camelCase
- **Formato de categorías**: Estandariza jerarquías de categorías con formato de título apropiado
- **Reconciliación de datos**: Fusiona conjuntos de datos antiguos y nuevos basándose en lógica de coincidencia SKU/RefId

## Manejo de Errores

- Reportes de error integrales con trazas de pila detalladas
- Normalización Unicode para comparación de texto (acentos removidos)
- Registro detallado de fallas de mapeo de categoría con reportes markdown
- Exportación CSV para elementos que no pudieron ser procesados
- Lógica de limitación de velocidad y reintento para llamadas a la API de VTEX

## Desactivar el Entorno Virtual

```bash
deactivate
```