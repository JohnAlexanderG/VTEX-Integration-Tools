# 77 — Filtrar precios por listado de SKUs (CSV → XLSX)

Exporta a `.xlsx` solo los precios de los SKUs listados en un CSV (p. ej. `_skus_sin_precio.csv` de la herramienta 76), tomándolos de un xlsx de precios en formato VTEX.

## Uso

```bash
python3 77_price_filter_by_sku_list/filter_prices_by_sku.py <skus.csv> <precios.xlsx> <output_prefix> [--column "SKU ID"]
```

## Entradas

- `skus.csv`: CSV con columna `SKU ID` (configurable con `--column`).
- `precios.xlsx`: columnas `SKU ID, Cost Price, Base Price, List Price, Error Code, Error Message`. Se usa la primera hoja que tenga las columnas requeridas.

## Salidas

- `{prefix}_precios.xlsx`: precios de los SKUs del CSV, mismas 6 columnas, en el orden del CSV.
- `{prefix}_no_encontrados.csv`: SKUs del CSV sin precio en el xlsx (solo si hay).
- `{prefix}_REPORT.md`: estadísticas.
