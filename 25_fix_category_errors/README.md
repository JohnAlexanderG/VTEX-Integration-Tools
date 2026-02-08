# 25_fix_category_errors

Corrige errores de categorías en archivos JSON mediante referencia cruzada entre dos fuentes de datos basándose en un reporte de errores en markdown.

## Descripción

Este script lee un reporte markdown generado por otro proceso que lista categorías problemáticas, luego:

1. **Extrae categorías con error** desde el markdown
2. **Busca el SKU asociado** en el archivo JSON principal (input-1)
3. **Obtiene la categoría correcta** consultando ese SKU en el archivo de referencia (input-2)
4. **Reemplaza todas las ocurrencias** del categoría problemático con el correcto
5. **Genera reportes** en JSON y markdown con estadísticas completas

Útil para corregir categorías incorrectas o mal mapeadas en datos de productos VTEX.

## Prerrequisitos

- Python 3.6+
- Archivo markdown con errores de categorías (generado por `06_map_category_ids`)
- Dos archivos JSON con estructura de lista: `input-1.json` e `input-2.json`
- Ambos archivos deben contener campos `SKU` y `Categoría`

## Uso

### Sintaxis básica

```bash
python3 fix_category_errors.py <archivo_markdown> <input_1.json> <input_2.json> <output.json>
```

### Parámetros requeridos

- `archivo_markdown`: Reporte markdown con categorías problemáticos
- `input_1.json`: Archivo JSON principal (contiene categorías y SKU)
- `input_2.json`: Archivo JSON de referencia (contiene SKU y categorías correctas)
- `output.json`: Archivo JSON de salida con categorías corregidas

### Opciones

- `--indent N`: Nivel de indentación JSON (default: 4)

### Ejemplos

```bash
# Uso básico
python3 25_fix_category_errors/fix_category_errors.py \
  error_log.md \
  input1.json \
  input2.json \
  output.json

# Con indentación personalizada
python3 25_fix_category_errors/fix_category_errors.py \
  06_map_category_ids/PRODUCTOS_category_log.md \
  PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada.json \
  reference_products.json \
  PRODUCTOS_A_SUBIR_VTEX-final-transformed-categorizada-FIXED.json \
  --indent 2
```

## Formato de Entrada

### 1. Archivo Markdown con Errores

Formato esperado:
```markdown
- `Aseo>Ambientadores Hogar>Pilas Recargables AA` *(×12)*
- `Camping>Carpas>NO EXISTE LINEA` *(×5)*
```

El script busca categorías entre backticks. La cuenta `*(×N)*` es opcional.

### 2. Archivo input-1.json (Principal)

Array de objetos JSON con campos requeridos:
- `SKU`: Identificador del producto
- `Categoría`: Categoría problemática (valor a reemplazar)

```json
[
  {
    "SKU": "000123",
    "Nombre": "Producto A",
    "Categoría": "Aseo>Ambientadores Hogar>Pilas Recargables AA"
  },
  {
    "SKU": "000124",
    "Nombre": "Producto B",
    "Categoría": "Camping>Carpas>NO EXISTE LINEA"
  }
]
```

### 3. Archivo input-2.json (Referencia)

Array de objetos JSON con campos requeridos:
- `SKU`: Identificador del producto (debe coincidir con input-1)
- `Categoría`: Categoría correcta

```json
[
  {
    "SKU": "000123",
    "Categoría": "Aseo>Ambientadores Hogar>Pilas"
  },
  {
    "SKU": "000124",
    "Categoría": "Camping>Carpas>Tiendas"
  }
]
```

## Archivos de Salida

Todos los archivos se generan en el mismo directorio que el script.

### 1. `output.json`

Versión corregida del archivo input-1.json con categorías reemplazadas:

```json
[
  {
    "SKU": "000123",
    "Nombre": "Producto A",
    "Categoría": "Aseo>Ambientadores Hogar>Pilas"
  }
]
```

### 2. `YYYYMMDD_HHMMSS_category_fix_report.md`

Reporte legible en markdown con:
- Resumen general (totales, tasas de éxito)
- Lista de correcciones exitosas (hasta 50)
- Listado de errores (Categoría no encontrado, SKU no encontrado)
- Archivos procesados y resultados

Ejemplo:
```markdown
# Reporte de Corrección de Categorías VTEX

**Fecha:** 2025-12-04 17:55:00

## 📊 Resumen General

| Métrica | Valor |
|---------|-------|
| **Total Categoría procesados** | 1432 |
| **✅ Correcciones exitosas** | 1410 |
| **❌ Errores (Categoría no encontrado)** | 15 |
| **❌ Errores (SKU no encontrado)** | 7 |
| **📈 Tasa de éxito** | 98.5% |
| **📝 Registros modificados** | 5240 |
```

### 3. `YYYYMMDD_HHMMSS_category_fix_log.json`

Log detallado en JSON con:
- Todas las correcciones exitosas
- Todos los errores con detalles
- Mapping completo de reemplazos
- Timestamps y metadatos

```json
{
  "timestamp": "2025-12-04 17:55:00",
  "successful_fixes": [
    {
      "problematic_path": "Aseo>Ambientadores Hogar>Pilas Recargables AA",
      "sku": "000123",
      "correct_category": "Aseo>Ambientadores Hogar>Pilas"
    }
  ],
  "path_not_found_errors": [...],
  "sku_not_found_errors": [...],
  "replacement_map": {...},
  "total_paths_processed": 1432,
  "total_records_modified": 5240,
  "success_rate": 98.5
}
```

## Flujo de Procesamiento

1. **Parseo de Markdown**
   - Lee archivo markdown
   - Extrae categorías únicos entre backticks
   - Ignora cuentas `*(×N)*` opcional

2. **Carga de Datos**
   - Carga input-1.json (datos principales)
   - Carga input-2.json (datos de referencia)
   - Construye índice SKU para búsquedas rápidas O(1)

3. **Procesamiento de Correcciones**
   - Para cada categoría problemático:
     - Busca en input-1 para obtener SKU
     - Busca SKU en input-2 para obtener categoría correcta
     - Construye mapping de reemplazos

4. **Aplicación de Reemplazos**
   - Itera input-1 una sola vez
   - Reemplaza valores según mapping
   - Preserva estructura JSON original

5. **Generación de Reportes**
   - Guarda output.json con datos corregidos
   - Genera reporte markdown con estadísticas
   - Genera log JSON detallado

## Ejemplo de Ejecución

```bash
$ python3 25_fix_category_errors/fix_category_errors.py \
    error_log.md \
    input1.json \
    input2.json \
    output.json

🚀 Iniciando corrección de categorías...

🔍 Parseando archivo markdown: error_log.md
   Encontrados: 1432 Categoría únicos problemáticos

📖 Cargando input1.json...
   Registros cargados: 5240

📖 Cargando input2.json...
   Registros cargados: 4500
🔨 Construyendo índice SKU...
   SKUs únicos indexados: 4500

🔍 Procesando 1432 Categoría problemáticos...
   ✅ Aseo>Ambientadores Hogar>Pilas Recargables AA → Aseo>Ambientadores Hogar>Pilas
   ... (más correcciones)

🔄 Aplicando 1410 reemplazos...
   Registros modificados: 5240

💾 Guardando archivo de salida: output.json
   ✅ Archivo guardado exitosamente

📊 Generando reportes...
📄 Reporte markdown generado: 20251204_125548_category_fix_report.md
📄 Log JSON generado: 20251204_125548_category_fix_log.json

================================================================================
🎉 PROCESO COMPLETADO
================================================================================
📊 Total procesado: 1432 Categoría
✅ Exitosos: 1410 (98.5%)
❌ Errores (Categoría no encontrado): 15
❌ Errores (SKU no encontrado): 7
📝 Registros modificados: 5240
================================================================================
```

## Características Principales

### Procesamiento Robusto
- Manejo gracioso de errores sin detener ejecución
- Registro detallado de todos los errores
- Validación de estructura JSON

### Estadísticas Completas
- Tasa de éxito de correcciones
- Conteo de registros modificados
- Análisis de errores con categorización

### Flexibilidad
- Indentación JSON personalizable
- Soporta archivos JSON grandes
- Preserva estructura original

## Casos de Uso

### Escenario 1: Corrección de Mapping de Categorías
```bash
# Después de map_category_ids identificó errores
python3 25_fix_category_errors/fix_category_errors.py \
  06_map_category_ids/error_report.md \
  productos_antes.json \
  productos_referencia.json \
  productos_despues.json
```

### Escenario 2: Unificación de Datos
```bash
# Unificar categorías entre dos fuentes de datos
python3 25_fix_category_errors/fix_category_errors.py \
  discrepancias.md \
  datos_principales.json \
  datos_secundarios.json \
  datos_unificados.json
```

## Troubleshooting

### Error: "Archivo markdown no encontrado"
- Verificar que la ruta del markdown es correcta
- Asegurar que el archivo existe y tiene permisos de lectura

### Error: "JSON inválido"
- Validar JSON con: `python3 -m json.tool archivo.json`
- Verificar encoding UTF-8

### Error: "Categoría no encontrado en input-1.json"
- Verificar que los categorías en markdown coinciden exactamente con input-1
- Revisar si hay espacios adicionales o caracteres especiales

### Error: "SKU no encontrado en input-2.json"
- Verificar que los SKU en input-1 existen en input-2
- Comparar formato de SKU entre archivos

### Muchos registros sin cambios
- Revisar si los categorías problemáticos están en input-1
- Verificar si el mapping SKU->Categoría es correcto en input-2

## Notas Técnicas

- **Encoding**: UTF-8 obligatorio para todos los archivos
- **Performance**: O(n) para procesamiento (una pasada sobre datos)
- **Memory**: Carga archivos completos en memoria
- **JSON**: Preserva estructura original, modifica solo campo "Categoría"

## Integración con Workflow VTEX

Este script se usa típicamente después de:
- **06_map_category_ids**: Genera el reporte de errores

Y antes de:
- **11_vtex_product_format_create**: Crea formatos de productos con categorías correctas

## Ver Ayuda

```bash
python3 25_fix_category_errors/fix_category_errors.py --help
```

## Archivos de Datos Reales en Este Directorio

```
error_log.md                    - Reporte de errores ejemplo
input1.json                     - JSON principal ejemplo
input2.json                     - JSON de referencia ejemplo
output.json                     - JSON corregido (generado)
output_*_category_fix_report.md - Reporte markdown (generado)
output_*_category_fix_log.json  - Log detallado (generado)
```
