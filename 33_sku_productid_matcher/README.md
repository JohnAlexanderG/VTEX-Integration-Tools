# Coincidencia de SKU con ProductId

Enlaza datos de SKU con IDs de producto usando un archivo de mapeo.

## Descripción

Este script relaciona el campo `SKU` de un archivo de datos con el campo `_SKUReferenceCode` de un archivo de mapeo, enriqueciendo la salida con el `_ProductId` correspondiente.

**Flujo:**
1. Lee archivo de mapeo con `_SKUReferenceCode` → `_ProductId`
2. Lee archivo de datos con columna `SKU`
3. Empareja por SKU y agrega `_ProductId` a cada registro
4. Exporta registros con match y sin match

## Requisitos

- Python 3.6+
- Archivos en formato CSV o JSON

## Instalación

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pip install -r requirements.txt
```

## Uso

### Uso Básico

```bash
python3 sku_productid_matcher.py mapeo.json datos.json salida.csv
```

### Con archivos CSV

```bash
python3 sku_productid_matcher.py skus.csv productos.csv output.csv
```

### Ver Ayuda

```bash
python3 sku_productid_matcher.py --help
```

## Formato de Entrada

### Archivo de Mapeo

Contiene la relación `_SKUReferenceCode` → `_ProductId`.

**Ejemplo (JSON o CSV):**
```json
[
  {
    "_SkuId": "1001",
    "_SKUReferenceCode": "001",
    "_ProductId": "100"
  },
  {
    "_SkuId": "1002",
    "_SKUReferenceCode": "002",
    "_ProductId": "200"
  }
]
```

**Columnas requeridas:**
- `_SKUReferenceCode`: Identificador de SKU a mapear
- `_ProductId`: ID del producto asociado

**Ejemplo real:**
- Archivo: `skus_mapping.csv` o `skus_mapping.json`

### Archivo de Datos

Contiene los registros a enriquecer con `_ProductId`.

**Ejemplo (JSON o CSV):**
```json
[
  {
    "SKU": "001",
    "Nombre": "Producto A",
    "Precio": "100"
  },
  {
    "SKU": "002",
    "Nombre": "Producto B",
    "Precio": "200"
  }
]
```

**Columna requerida:**
- `SKU`: Identificador a emparejar

**Ejemplo real:**
- Archivo: `especificaciones.csv` o `productos.json`

## Formato de Salida

El script genera tres archivos:

### 1. output.csv (Registros con Match)

Contiene todos los registros del archivo de datos que tuvieron coincidencia en el mapeo, enriquecidos con `_ProductId`.

**Estructura:**
```csv
_ProductId,SKU,Nombre,Precio
100,001,Producto A,100
200,002,Producto B,200
```

**Ubicación:** Mismo directorio, mismo nombre + sufijo

**Ejemplo real:**
- `output.csv`: Registros emparejados correctamente

### 2. output_no_match.csv (Registros sin Match)

Contiene registros del archivo de datos que NO tuvieron coincidencia en el mapeo (sin `_ProductId`).

**Estructura:**
```csv
SKU,Nombre,Precio
003,Producto C,300
004,Producto D,400
```

**Ubicación:** Mismo directorio base, con sufijo `_no_match.csv`

**Ejemplo real:**
- `output_no_match.csv`: SKUs que no se encontraron en el mapeo

### 3. output_report.md (Reporte)

Reporte markdown con estadísticas detalladas del proceso.

**Contenido:**
```markdown
# SKU ProductId Matcher - Reporte

**Fecha:** 2026-01-15 18:04:00

## Archivos procesados

- **Archivo de mapeo:** `skus.csv` (1000 registros)
- **Archivo de datos:** `productos.csv` (850 registros)
- **Referencias en mapeo:** 900 referencias unicas

## Resultados

| Metrica | Valor |
|---------|-------|
| Total registros | 850 |
| Con _ProductId | 820 |
| Sin match | 30 |
| Tasa de match | 96.5% |

## Archivos generados

- `output.csv` - Resultados completos
- `output_no_match.csv` - Registros sin match
- `output_report.md` - Este reporte

## SKUs sin match

| # | SKU |
|---|-----|
| 1 | 003 |
| 2 | 004 |
```

**Ubicación:** Mismo directorio base, con sufijo `_report.md`

## Cómo Funciona

### Fase 1: Carga de Archivos
1. Detecta formato (JSON o CSV) por extensión
2. Lee archivo de mapeo
3. Lee archivo de datos
4. Valida que existan campos requeridos

### Fase 2: Construcción de Mapeo
1. Crea diccionario: `_SKUReferenceCode` → `{_SkuId, _ProductId}`
2. Registra referencias únicas
3. Ignora referencias vacías

### Fase 3: Procesamiento de Datos
Para cada registro:
1. Extrae valor `SKU`
2. Limpia (strip de espacios)
3. Busca en mapeo
4. Si encuentra: copia registro y agrega `_ProductId`
5. Si no encuentra: registra en lista de no encontrados

### Fase 4: Exportación
1. Exporta registros con match a CSV
2. Exporta registros sin match a CSV separado
3. Genera reporte markdown con estadísticas

## Limpieza de Datos

El script aplica `clean_value()` a todos los valores:
- Convierte a string
- Remueve espacios al inicio/final (strip)
- Maneja valores None

## Argumentos CLI

```
sku_productid_matcher.py [-h] mapping_file data_file output_file

Posicionales:
  mapping_file    Archivo con _SkuId, _SKUReferenceCode, _ProductId
  data_file       Archivo con campo SKU a enriquecer
  output_file     Archivo CSV de salida

Opcionales:
  -h, --help      Muestra mensaje de ayuda
```

## Ejemplo Completo

```bash
# Preparar datos de ejemplo
python3 sku_productid_matcher.py vtex_skus.csv filtered_specs.csv output.csv

# Archivos generados:
# - output.csv (registros con match)
# - output_no_match.csv (registros sin match)
# - output_report.md (reporte)
```

## Estadísticas de Ejemplo

```
============================================================
🔧 SKU ProductId Matcher
============================================================

📋 Configuración:
   Archivo de mapeo: vtex_skus.csv
   Archivo de datos: filtered_specs.csv
   Archivo de salida: output.csv

📂 Cargando archivos...
   ✓ Archivo de mapeo: 354,348 registros
   ✓ Archivo de datos: 1,469,553 registros

🔗 Construyendo mapeo _SKUReferenceCode -> _ProductId...
   ✓ 350,000 referencias únicas en mapeo

🔍 Procesando datos...

💾 Exportando resultados...
✅ Archivo exportado: output.csv

============================================================
📊 Resumen
============================================================
   Total registros: 1,469,553
   ✅ Con _ProductId: 1,450,000
   ⚠️ Sin match: 19,553
   📈 Tasa de match: 98.7%

✓ Proceso completado exitosamente
```

## Notas

- **Preservación de datos**: Todos los campos originales se copian a salida
- **Posicionamiento de _ProductId**: Aparece como primera columna en CSV de salida
- **Casos especiales**: Valores "None" se tratan como vacíos
- **Performance**: Usa diccionarios para búsqueda O(1)
- **Memoria**: Carga completa de archivos en memoria

## Troubleshooting

### Error: "Campo '_SKUReferenceCode' no encontrado"
Verifique que el archivo de mapeo tiene esta columna exacta

### Error: "Campo 'SKU' no encontrado"
Verifique que el archivo de datos tiene columna `SKU`

### Tasa de match baja
- Revise si los SKUs están en diferentes formatos (espacios, mayúsculas)
- Use `output_no_match.csv` para analizar las discrepancias
- Verifique que el mapeo contiene todos los SKUs esperados

### Archivo muy lento
- Para archivos >1M registros, considere dividir en lotes
- Verifique RAM disponible del sistema
