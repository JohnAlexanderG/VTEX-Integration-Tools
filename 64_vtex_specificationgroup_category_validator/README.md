# Validador de CategoryId para Grupos de Especificación

Valida el CSV exitoso generado por `31_vtex_specificationgroup_create` contra
`tree-categories.json` para separar los grupos cuyo `CategoryId` corresponde al
tercer nivel del árbol VTEX.

El archivo correcto conserva exactamente las columnas originales del CSV de
entrada y es el que debe usarse como input del siguiente proceso de carga.

## Inputs esperados

### CSV exitoso del paso 31

El CSV debe incluir una columna `CategoryId`. El formato actual exportado por el
paso 31 contiene:

```csv
Id,GroupId,CategoryId,Name,Position,StatusCode
511,511,1528,Especificaciones (SKU),,200
```

Puedes cambiar el nombre de la columna con `--category-id-column`.

### JSON de categorías del paso 61

El archivo `tree-categories.json` debe ser una lista JSON con nodos VTEX que
incluyan `id`, `name` y `children`. El validador clasifica los IDs como:

- Nivel 1: departamento.
- Nivel 2: categoría hija directa.
- Nivel 3: línea o subcategoría hoja válida para continuar.
- No encontrado: ID que aparece en el CSV pero no existe en el árbol usado.

## Uso

Comando recomendado cuando los insumos están en este directorio:

```bash
python3 64_vtex_specificationgroup_category_validator/validate_specgroup_categories.py 64_vtex_specificationgroup_category_validator/20260601_223044_sku_specificationgroup_creation_successful.csv 64_vtex_specificationgroup_category_validator/tree-categories.json
```

Ejemplo usando los outputs actuales desde la raíz del repositorio:

```bash
python3 64_vtex_specificationgroup_category_validator/validate_specgroup_categories.py 31_vtex_specificationgroup_create/20260601_223044_sku_specificationgroup_creation_successful.csv 61_sku_spec_matcher/tree-categories.json -o resultado_validacion_specgroups
```

Opciones principales:

- `-o, --output-prefix`: prefijo de salida. Default:
  `resultado_YYYYMMDD_HHMMSS`.
- `--category-id-column`: columna con el ID de categoría. Default:
  `CategoryId`.
- `--encoding`: encoding de entrada y salida. Default: `utf-8-sig`.
- `--output-dir`: directorio de salida. Default: directorio del CSV de entrada.

## Salidas

El script genera dos CSV:

1. `<prefix>_categoryid_tercer_nivel_correctos.csv`
   - Contiene solo filas con `CategoryId` de nivel 3.
   - Conserva exactamente los encabezados originales del CSV de entrada.
   - Debe usarse como entrada del siguiente proceso.

2. `<prefix>_categoryid_no_coinciden.csv`
   - Contiene filas con `CategoryId` inválido, no encontrado o de otro nivel.
   - Agrega columnas de auditoría:
     `CategoryLevel`, `CategoryName`, `ParentCategoryId`,
     `ParentCategoryName`, `CategoryPath` y `ValidationReason`.

Los valores de `ValidationReason` incluyen:

- `INVALID_CATEGORY_ID`: el valor está vacío o no es numérico.
- `CATEGORY_ID_LEVEL_1`: el ID corresponde a un departamento.
- `CATEGORY_ID_LEVEL_2`: el ID corresponde a una categoría de segundo nivel.
- `CATEGORY_ID_NOT_IN_TREE`: el ID no existe en el árbol JSON usado.

## Datos locales

Los archivos CSV y JSON de entrada son datos locales de trabajo y no se
versionan. La raíz del repositorio ignora `*.csv`, `*.json` y `*.md` en
`.gitignore`, dejando permitidos solo Markdown/documentación allow-listada.
