# json_to_csv

## Descripción

Convertidor simple de archivos JSON a formato CSV. Extrae todos los campos únicos de un JSON (objeto único o array) y genera un archivo CSV con encabezados ordenados alfabéticamente. Útil para revisar datos procesados en Excel o exportar a otras herramientas.

## Requisitos

- Python 3.6+ (librerías estándar: json, csv, argparse, sys)
- Sin dependencias externas

## Uso

```bash
python3 json_to_csv.py <input.json> <output.csv>
```

### Argumentos

- `input.json` - Archivo JSON de entrada
- `output.csv` - Archivo CSV de salida

### Ejemplos

```bash
python3 json_to_csv.py datos.json datos.csv
python3 json_to_csv.py productos_finales.json revision_manual.csv
```

## Formato de Entrada

Archivo JSON con uno de estos formatos:

### Objeto JSON único
```json
{
  "RefId": "000050",
  "Name": "Producto A",
  "Price": 99.99,
  "Stock": 100
}
```

### Array de objetos JSON
```json
[
  {
    "RefId": "000050",
    "Name": "Producto A",
    "Price": 99.99
  },
  {
    "RefId": "000099",
    "Name": "Producto B",
    "Stock": 50
  }
]
```

## Formato de Salida

Archivo CSV con encabezados ordenados alfabéticamente y valores rellenados con cadenas vacías para campos faltantes.

**output.csv**
```csv
Name,Price,RefId,Stock
Producto A,99.99,000050,
Producto B,,000099,50
```

## Características

- **Campos inconsistentes**: Se incluyen todos los campos únicos encontrados en el JSON
- **Valores faltantes**: Se rellenan con strings vacíos
- **Ordenamiento**: Encabezados ordenados alfabéticamente para consistencia
- **UTF-8**: Mantiene codificación correcta para caracteres especiales
- **Flexibilidad**: Soporta tanto objetos únicos como arrays de objetos

## Lógica de Funcionamiento

1. Lee el archivo JSON de entrada
2. Si es un objeto único, lo convierte a array de un elemento
3. Valida que todos los elementos sean objetos
4. Extrae todos los nombres de campos únicos de todos los objetos
5. Ordena los nombres de campos alfabéticamente
6. Escribe CSV con:
   - Encabezados (campos ordenados)
   - Una fila por objeto JSON
   - Campos faltantes rellenados con cadenas vacías

## Notas/Caveats

- JSON malformado causa error de salida
- Valores que no sean objetos (strings, números, arrays anidados) causan error
- Campos con valores `null` se convierten a strings vacíos en CSV
- Objetos vacíos resultan en filas sin datos (solo encabezados)
- Encodificación UTF-8 se preserva automáticamente
- No maneja valores complejos (objetos/arrays anidados se convierten a string)
- Buen uso para preparar datos para revisión manual en Excel
