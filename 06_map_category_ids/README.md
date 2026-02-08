# 06_map_category_ids

## Descripción

Script de integración VTEX que mapea IDs de departamento y categoría desde el catálogo VTEX. Conecta con la API de VTEX, descarga el árbol completo de categorías, normaliza nombres y asigna identificadores apropiados a cada producto.

Este es el tercer paso en el flujo de transformación de datos. Genera reportes detallados JSON, Markdown y CSV de registros que fallaron en el mapeo.

## Requisitos Previos

### Dependencias de Python
```bash
pip install requests python-dotenv
```

### Dependencias del Sistema
- Python 3.6+
- Conexión a internet (para acceder a API VTEX)
- Archivo `.env` en la raíz del proyecto con credenciales

### Archivo .env Requerido
Crear archivo `/proyecto/.env` con las siguientes variables:
```
X-VTEX-API-AppKey=tu_app_key_vtex
X-VTEX-API-AppToken=tu_app_token_vtex
VTEX_ACCOUNT_NAME=nombre_cuenta
VTEX_ENVIRONMENT=vtexcommercestable
```

## Uso

**Mapeo básico (usa variables del .env automáticamente):**
```bash
python3 06_map_category_ids/map_category_ids.py entrada.json salida.json
```

**Mapeo con indentación personalizada:**
```bash
python3 06_map_category_ids/map_category_ids.py entrada.json salida.json --indent 2
```

**Mapeo con endpoint personalizado:**
```bash
python3 06_map_category_ids/map_category_ids.py entrada.json salida.json --endpoint https://custom.vtexcommercestable.com.br/api/catalog_system/pub/category/tree/2/
```

**Ejemplo con archivos reales:**
```bash
python3 06_map_category_ids/map_category_ids.py PRODUCTOS_A_SUBIR_VTEX-final-transformed.json PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada.json
```

**Argumentos:**
- `input_file`: Ruta al archivo JSON de entrada con lista de productos
- `output_file`: Ruta al archivo JSON de salida con IDs agregados
- `--endpoint`: URL del endpoint VTEX (opcional, se construye desde .env)
- `--indent`: Número de espacios para indentación (opcional, por defecto: 4)

## Formato de Entrada

### JSON de Productos (entrada.json)
Array de productos con campo de categoría jerárquica:

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "Categoría": "Cuidado Personal>Cuidado del Pelo>Secadores",
        "precio": "150.00"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "CategoryPath": "Electrónica>Periféricos",
        "precio": "80.00"
    }
]
```

## Formato de Salida

### JSON Principal (salida.json)
Productos con IDs de departamento y categoría agregados:

```json
[
    {
        "id": "001",
        "nombre": "Producto A",
        "CategoryPath": "Cuidado Personal/Cuidado del Pelo/Secadores",
        "DepartmentId": 10,
        "CategoryId": 15,
        "precio": "150.00"
    },
    {
        "id": "002",
        "nombre": "Producto B",
        "CategoryPath": "Electrónica/Periféricos",
        "DepartmentId": 20,
        "CategoryId": 25,
        "precio": "80.00"
    }
]
```

### Archivos de Reporte Automáticos

**1. JSON Detallado de Comparación (salida_comparison_log.json):**
Contiene información exhaustiva del mapeo:
- Árbol completo de categorías VTEX disponibles
- Detalles de parsing de cada ruta de categoría
- Resultados de matching (encontrado/no encontrado)
- Categorías disponibles en VTEX para comparación

**2. Reporte Markdown (salida_category_log.md):**
Resumen legible de la ejecución:
- Estadísticas de éxito/fracaso
- Tasa de éxito en porcentaje
- Errores agrupados por tipo
- Categorías disponibles en VTEX para registros fallidos

**3. CSV de Fallidos (salida_fallidos.csv):**
Registros completos que fallaron en el mapeo, con columna `_error_reason` explicando por qué:
```csv
id,nombre,Categoría,precio,_error_reason
003,Producto C,Categoría Inexistente,90.00,Departamento no existe
```

## Cómo Funciona

### Lógica de Mapeo

**1. Descarga del Árbol de Categorías:**
- Conecta a API VTEX usando credenciales del .env
- Descarga estructura completa: Departamentos > Categorías > Subcategorías

**2. Normalización de Nombres:**
Para coincidencia robusta:
- Elimina acentos (á→a, ñ→n, etc.)
- Convierte a minúsculas
- Elimina espacios extras
- Ejemplo: "Cuidado del Pelo" → "cuidado del pelo"

**3. Parsing de CategoryPath:**
Divide la ruta jerárquica por `>`:
- Primer segmento → Departamento
- Segundo segmento → Categoría
- Tercer segmento → Subcategoría
- Segmentos adicionales → Se ignoran

**4. Búsqueda Jerárquica:**
```
¿Existe Departamento? SÍ → DepartmentId = dept.id
├─ ¿Existe Categoría? SÍ → CategoryId = cat.id
│  └─ ¿Existe Subcategoría? SÍ → CategoryId = sub.id
│  └─ ¿NO? → CategoryId = cat.id
└─ ¿NO? → CategoryId = dept.id
¿NO existe Departamento? → CategoryId = NULL
```

**5. Transformación de CategoryPath:**
- Reemplaza cualquier `/` existente por `-`
- Reemplaza primeros dos `>` por `/`
- Mantiene `>` para separadores adicionales
- Ejemplo: "Dept>Cat>SubCat>Extra" → "Dept/Cat/SubCat>Extra"

**6. Exportación de Reportes:**
- Genera JSON con detalles completos
- Genera Markdown con resumen
- Genera CSV con registros fallidos y motivos

### Pasos de Ejecución

1. Descarga árbol de categorías VTEX
2. Construye mapeo normalizado
3. Lee archivo JSON de entrada
4. Procesa cada producto:
   - Parsea CategoryPath
   - Normaliza nombres
   - Busca coincidencias en VTEX
   - Asigna IDs
   - Registra éxito/fallo
5. Genera reportes JSON, Markdown y CSV
6. Escribe JSON de salida

## Archivos de Ejemplo

**Entrada:**
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed.json` (21 MB)

**Salida:**
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada.json` (23 MB) - Con IDs
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada_comparison_log.json` (25 MB) - Detalles
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada_category_log.md` (9 KB) - Resumen
- `PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada_fallidos.csv` (110 KB) - Errores

## Notas y Consideraciones

- **Credenciales**: Asegura que .env tenga variables correctas o el script fallará
- **Normalización**: La comparación es case-insensitive y sin acentos
- **Rendimiento**: Con millones de registros, puede tardar varios minutos
- **Progreso**: Muestra cada 100 registros procesados
- **Campos Dinámicos**: Soporta tanto `Categoría` como `CategoryPath` como nombre de campo
- **Revisión CSV**: Siempre verifica `_fallidos.csv` para identificar problemas de categorías VTEX
- **Reportes Detallados**: El JSON de comparación incluye árbol completo para debugging
- **Reintentos**: Si hay fallos, verifica que las categorías existan en VTEX y estén bien formateadas
