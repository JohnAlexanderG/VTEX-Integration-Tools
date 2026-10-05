# 76 - VTEX Price SKU ID → Reference Code

Convierte la exportación de precios de VTEX (indexada por **SKU ID**) al CSV de precios en **formato ERP** (indexado por **código de referencia**), cruzando con el export `products-and-skus` de VTEX.

## Uso

```bash
python3 76_vtex_price_skuid_to_refcode/price_skuid_to_refcode.py <precios_vtex.xlsx> <products_and_skus.xlsx> <output_prefix> [--dry-run]
```

Ejemplo:

```bash
python3 76_vtex_price_skuid_to_refcode/price_skuid_to_refcode.py \
    "681f3d3a-...xlsx" 2026-10-05T15_20_48Z_products-and-skus_didopet.xlsx didopet_precios
```

## Entradas

| Archivo | Columnas requeridas |
|---|---|
| Precios VTEX (xlsx) | `SKU ID`, `Cost Price`, `Base Price`, `List Price` (opcionales: `Error Code`, `Error Message`) |
| Products and SKUs (xlsx) | `SKU ID`, `SKU reference code` (opcionales: `Product ID`, `SKU name`) |

> El export `products-and-skus` debe incluir la columna **SKU reference code**.

> Acepta los xlsx tal como los descarga VTEX: la fila "Learn how to fill out this spreadsheet here" se omite automáticamente (los encabezados se detectan en las primeras 10 filas).

## Salidas

| Archivo | Contenido |
|---|---|
| `{prefix}_erp_precios.csv` | `codigo producto,Costo,Precio Venta,% IVA,Precio Lista o Precio Promocion` (`% IVA` vacío) |
| `{prefix}_sin_refcode.csv` | Precios cuyo SKU ID no tiene código de referencia |
| `{prefix}_skus_sin_precio.csv` | SKUs del catálogo sin precio |
| `{prefix}_errores.csv` | Filas con `Error Code`/`Error Message` (solo si existen) |
| `{prefix}_REPORT.md` | Estadísticas y códigos de referencia compartidos por varios SKU ID |

Mapeo: `Cost Price → Costo`, `Base Price → Precio Venta`, `List Price → Precio Lista o Precio Promocion`.

Dependencias: `openpyxl`.

También disponible en la webapp como **"Precios SKU ID → RefCode"** (`tool_price_skuid_to_refcode`).
