# 01_csv_to_json

## Descripción

Suite de herramientas para convertir archivos de datos en diferentes formatos (CSV, XLS, XLSX, XLSB) a formato JSON. Constituye el primer paso del flujo de transformación de datos para integración con la plataforma e-commerce VTEX.

El directorio contiene tres scripts especializados:
- **csv_to_json.py**: Convierte CSV y archivos Excel en JSON
- **xlsx_to_csv.py**: Convierte archivos XLSX/XLS a CSV
- **xlsb_to_csv.py**: Convierte archivos XLSB (Excel Binary Workbook) a CSV

## Requisitos Previos

### Dependencias de Python
```bash
pip install pandas openpyxl xlrd pyxlsb
```

### Dependencias del Sistema
- Python 3.6+
- Soporte de codificación UTF-8

## Uso

### csv_to_json.py - Convertir CSV/Excel a JSON

**Conversión básica desde CSV:**
```bash
python3 01_csv_to_json/csv_to_json.py entrada.csv salida.json
```

**Conversión con indentación personalizada:**
```bash
python3 01_csv_to_json/csv_to_json.py entrada.csv salida.json --indent 4
```

**Conversión de archivos Excel (.xlsx, .xls, .xlsb):**
```bash
python3 01_csv_to_json/csv_to_json.py productos.xlsx productos.json --indent 4
python3 01_csv_to_json/csv_to_json.py productos.xls productos.json --indent 4
python3 01_csv_to_json/csv_to_json.py productos.xlsb productos.json --indent 4
```

**Usando pipelines (solo CSV desde stdin/stdout):**
```bash
cat entrada.csv | python3 01_csv_to_json/csv_to_json.py - > salida.json
```

**Argumentos:**
- `input_file`: Archivo de entrada (CSV, XLS, XLSX o XLSB). Usar `-` para stdin
- `json_output`: Archivo JSON de salida. Usar `-` para stdout (opcional, por defecto stdout)
- `-i, --indent`: Número de espacios para indentación (opcional, por defecto: formato compacto)

### xlsx_to_csv.py - Convertir XLSX/XLS a CSV

**Conversión básica:**
```bash
python3 01_csv_to_json/xlsx_to_csv.py entrada.xlsx salida.csv
```

**Conversión con encabezados en fila específica:**
```bash
python3 01_csv_to_json/xlsx_to_csv.py entrada.xlsx salida.csv --header-row 1
```

**Argumentos:**
- `input_file`: Archivo XLSX o XLS de entrada
- `output_file`: Archivo CSV de salida
- `--header-row`: Número de fila (indexado desde 0) donde están los encabezados (opcional, por defecto: 0)

### xlsb_to_csv.py - Convertir XLSB a CSV

**Conversión básica:**
```bash
python3 01_csv_to_json/xlsb_to_csv.py entrada.xlsb salida.csv
```

**Conversión con encabezados en fila específica:**
```bash
python3 01_csv_to_json/xlsb_to_csv.py entrada.xlsb salida.csv --header-row 1
```

**Argumentos:**
- `input_file`: Archivo XLSB de entrada
- `output_file`: Archivo CSV de salida
- `--header-row`: Número de fila (indexado desde 0) donde están los encabezados (opcional, por defecto: 0)

## Formatos de Entrada

### CSV
Formato tabular estándar con encabezados en la primera fila:
```csv
SKU,MARCA,DESCRIPCION
176391,ILUMAX,Producto 1
176392,SAMSUNG,Producto 2
```

### Excel (.xlsx, .xls, .xlsb)
Archivos de hoja de cálculo Excel estándar. El script lee automáticamente:
- La primera hoja del archivo
- Los encabezados de la primera fila (o fila especificada con `--header-row`)
- Convierte valores vacíos (NaN) a strings vacíos

## Formatos de Salida

### JSON (csv_to_json.py)
Array de objetos JSON con los encabezados como claves:
```json
[
    {
        "SKU": "176391",
        "MARCA": "ILUMAX",
        "DESCRIPCION": "Producto 1"
    },
    {
        "SKU": "176392",
        "MARCA": "SAMSUNG",
        "DESCRIPCION": "Producto 2"
    }
]
```

### CSV (xlsx_to_csv.py, xlsb_to_csv.py)
Formato CSV estándar UTF-8 con encabezados en primera fila:
```csv
SKU,MARCA,DESCRIPCION
176391,ILUMAX,Producto 1
176392,SAMSUNG,Producto 2
```

## Cómo Funciona

### csv_to_json.py
1. **Detección de formato**: Identifica automáticamente el tipo de archivo por extensión
2. **Lectura**:
   - CSV: Lee mediante `csv.DictReader` línea por línea
   - Excel: Usa pandas con engine automático (openpyxl para XLSX, xlrd para XLS, pyxlsb para XLSB)
3. **Normalización**: Convierte valores NaN a strings vacíos
4. **Conversión**: Transforma cada fila en un objeto JSON
5. **Escritura**: Genera JSON con opción de indentación personalizada

### xlsx_to_csv.py y xlsb_to_csv.py
1. **Lectura**: Carga el archivo Excel con pandas especificando fila de encabezados
2. **Normalización**: Convierte NaN a strings vacíos
3. **Conversión**: Transforma a lista de diccionarios
4. **Escritura**: Exporta a CSV con codificación UTF-8

## Archivos de Ejemplo

**Entrada (CSV):**
- `brands.csv` (391 KB)
- `2025.11.21_CATEGORIAS.csv` (3.2 MB)
- `20260130-reset.csv` (27 KB)

**Salida (JSON):**
- `brands.json` (1.5 MB)
- `2025.11.21_CATEGORIAS.json` (10 MB)
- `20260130-reset.json` (166 KB)

## Notas y Consideraciones

- **Codificación**: Todos los scripts preservan UTF-8 para caracteres especiales españoles
- **Pipelines**: Solo `csv_to_json.py` soporta stdin/stdout (no para archivos Excel)
- **Formato Compacto**: Por defecto, JSON se genera sin indentación para reducir tamaño de archivo
- **Encabezados**: Es obligatorio que los archivos CSV/Excel tengan encabezados en la fila especificada
- **Primer Registro**: Para Excel, el script siempre procesa la primera hoja del libro
- **Valores Vacíos**: Los valores NaN en Excel se convierten a strings vacíos (`""`) para compatibilidad
