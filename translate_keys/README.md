# translate_keys

## Descripción

Script para traducir claves de JSON del español al inglés. Elimina duplicados manteniendo la versión en inglés cuando existe una clave traducida y su equivalente en español. Ordena alfabéticamente todas las claves en el resultado.

## Requisitos

- Python 3.6+ (librerías estándar: json, argparse, sys)
- Sin dependencias externas

## Uso

```bash
python3 translate_keys.py <input.json> <output.json> [-i <indentacion>]
```

### Argumentos

- `input.json` - Archivo JSON de entrada
- `output.json` - Archivo JSON de salida
- `-i, --indent` - Nivel de indentación en salida (default: 4)

### Ejemplos

```bash
python3 translate_keys.py datos_es.json datos_en.json
python3 translate_keys.py productos.json productos_traducido.json --indent 2
python3 translate_keys.py catalogo_es.json catalogo_en.json -i 4
```

## Formato de Entrada

Archivo JSON con claves en español y/o inglés.

**input.json**
```json
[
  {
    "Nombre": "Producto A",
    "Name": "Product A",
    "Descripción": "Una descripción",
    "Categoría": "Electrónica > Computadoras",
    "Peso": 2.5,
    "Precio_Sugerido": 99.99
  },
  {
    "Nombre": "Producto B",
    "Categoría": "Ropa > Camisetas"
  }
]
```

## Formato de Salida

Archivo JSON con claves traducidas al inglés, ordenadas alfabéticamente, sin duplicados.

**output.json**
```json
[
  {
    "CategoryPath": "Electrónica/Computadoras",
    "Name": "Product A",
    "Price_List_1": 99.99,
    "Weight": 2.5
  },
  {
    "CategoryPath": "Ropa/Camisetas",
    "Name": "Product B"
  }
]
```

## Mapeo de Traducciones

| Español | Inglés | Notas |
|---------|--------|-------|
| Nombre | Name | Se elimina "Nombre" si existe "Name" |
| Descripción | Description | Se elimina si existe versión en inglés |
| Creado | Created | |
| Imágenes | Images | |
| Para_recogida | For_pickup | |
| Categoría | CategoryPath | Cambia separador `>` por `/` |
| Stock | Stock | Ya está en inglés |
| Eliminó | Deleted | |
| Producto_Descontinuado | Discontinued_Product | |
| Vender_usando_ERP | Sell_using_ERP | |
| Vender_en_la_Tienda_Web | Sell_on_Web_Store | |
| Vender_usando_POS | Sell_using_POS | |
| Vender_a_través_de_EDI | Sell_through_EDI | |
| Peso | Weight | |
| Precio_Sugerido | Suggested_Price | |
| Lista_de_Precios_1 | Price_List_1 | |
| Lista_de_Precios_2 | Price_List_2 | |
| Lista_de_Precios_3 | Price_List_3 | |

## Transformaciones Especiales

### Categoría → CategoryPath
El separador `>` se convierte a `/`:
```
Entrada:  "Categoría": "Electrónica > Computadoras > Laptops"
Salida:   "CategoryPath": "Electrónica/Computadoras/Laptops"
```

### Eliminación de Duplicados
Si existe tanto la clave española como la inglesa, se mantiene solo la versión en inglés:
```json
{
  "Nombre": "Producto",     // Se elimina
  "Name": "Product"         // Se mantiene
}
```
Resultado:
```json
{
  "Name": "Product"
}
```

## Lógica de Funcionamiento

1. Lee archivo JSON (objeto único o array de objetos)
2. Para cada objeto:
   - Verifica qué claves en inglés ya existen
   - Para cada clave original:
     - Si es clave que debe eliminarse y existe versión inglesa → omite
     - Si tiene traducción → usa la traducción
     - Si no tiene traducción → mantiene clave original
     - Aplica transformaciones especiales (ej: Categoría → CategoryPath)
   - Ordena alfabéticamente todas las claves resultantes
3. Exporta resultado a JSON con indentación especificada

## Notas/Caveats

- Solo traduce claves del mapeo predefinido
- Claves no mapeadas se mantienen sin cambios
- Duplicados se resuelven manteniendo versión en inglés
- Categoría tiene transformación especial (separador)
- Orden alfabético es determinístico
- JSON malformado causa error
- UTF-8 se preserva en caracteres especiales
- Indentación por defecto es 4 espacios
- Buen uso para normalizar esquemas de datos multiidioma
