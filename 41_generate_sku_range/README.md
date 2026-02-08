# 41_generate_sku_range

## Descripción

Herramienta para comparar SKUs del ERP vs SKUs de VTEX. Identifica códigos de SKU del ERP que no existen en VTEX mediante comparación exacta de strings, preservando ceros a la izquierda.

## Requisitos

- Python 3.7+
- Dependencias: `pandas`, `xlrd`

Instalar con:
```bash
pip install pandas xlrd
```

## Uso

```bash
python3 generate_sku_range.py <vtex_file.xls> <erp_file.csv> <output.csv>
```

### Ejemplo

```bash
python3 generate_sku_range.py vtex_export.xls erp_inventory.csv output.csv
```

## Formato de Entrada

### Archivo VTEX (.xls)
- Requiere columna: `_SKUReferenceCode`
- Contendrá los códigos SKU existentes en VTEX
- Soporta múltiples hojas

**Ejemplo:**
```
_SKUReferenceCode | Other_Column
000050           | Data1
000051           | Data2
```

### Archivo ERP (.csv)
- Requiere columna: `CODIGO SKU`
- Contiene todos los códigos SKU del inventario ERP

**Ejemplo:**
```
CODIGO SKU,Nombre,Cantidad
000050,Producto A,100
000099,Producto B,50
```

## Formato de Salida

Genera un archivo CSV con una única columna `CODIGO SKU` conteniendo los SKUs del ERP que NO se encuentran en VTEX.

**output.csv**
```
CODIGO SKU
000099
000100
000101
```

## Lógica de Funcionamiento

1. Carga todos los SKUs de VTEX desde la columna `_SKUReferenceCode`
2. Carga todos los SKUs únicos del ERP desde la columna `CODIGO SKU`
3. Compara strings exactos (sin conversión de tipos)
4. Genera lista de SKUs del ERP no encontrados en VTEX
5. Exporta resultado ordenado alfabéticamente

## Notas/Caveats

- La comparación es sensible a espacios en blanco (automáticamente eliminados)
- Se preservan los ceros a la izquierda (ej: "000050" ≠ "50")
- Los valores vacíos/NULL se omiten en ambos archivos
- Archivos .xls pueden estar limitados a 65,536 filas; si alcanza este límite, considere usar .xlsx o dividir el export
- Entrada es case-sensitive para la comparación
