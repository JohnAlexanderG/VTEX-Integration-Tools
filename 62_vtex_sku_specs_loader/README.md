# 62 - VTEX SKU Specs Loader

Este directorio contiene el insumo `resultado_encontrados.csv`, generado para cargar
especificaciones de SKU en VTEX. El loader se va a reconstruir desde cero; este
documento deja registrado el analisis del CSV antes de implementar la carga.

## Archivo Analizado

- Archivo: `resultado_encontrados.csv`
- Tamano aproximado: 20 MB
- Filas totales con encabezado: 114.631
- Filas de datos: 114.630
- Codificacion recomendada de lectura: `utf-8-sig`
- Separador: coma

Columnas detectadas:

```text
SKU,Categoria,Subcategoria,Linea,Nombre,Descripcion,Nombre Especificacion,Especificacion,cantidad,Category ID
```

## Resumen General

| Metrica | Valor |
| --- | ---: |
| Filas de datos | 114.630 |
| Columnas por fila | 10 |
| Filas con estructura invalida | 0 |
| SKUs unicos | 19.278 |
| Category IDs unicos | 1.221 |
| Nombres de especificacion unicos | 26 |
| Duplicados exactos | 0 |
| Duplicados logicos | 0 |

Duplicado logico evaluado con:

```text
SKU + Category ID + Nombre Especificacion + Especificacion + cantidad
```

## Valores Faltantes

| Columna | Filas vacias |
| --- | ---: |
| SKU | 0 |
| Categoria | 0 |
| Subcategoria | 0 |
| Linea | 0 |
| Nombre | 0 |
| Descripcion | 2 |
| Nombre Especificacion | 28 |
| Especificacion | 28 |
| cantidad | 28.860 |
| Category ID | 0 |

Hay 28 filas sin `Nombre Especificacion`, sin `Especificacion` y sin `cantidad`.
Estas filas no son cargables como especificaciones de SKU y deben omitirse o
reportarse en el preflight.

## Especificaciones Mas Frecuentes

| Nombre Especificacion | Filas |
| --- | ---: |
| Medida Empaque Frente | 16.945 |
| Medida Empaque Alto | 16.945 |
| Medida Empaque Fondo | 16.945 |
| Materiales 1 | 11.009 |
| Color | 10.905 |
| Medida Producto Uso Alto | 8.256 |
| Medida Producto Uso Frente | 7.772 |
| Peso | 3.812 |
| Medida Producto Uso Fondo | 3.731 |
| Unidades x Paquete | 2.046 |
| Capacidad | 2.031 |
| Dias recibo antes vencimiento | 1.766 |
| Dias retiro antes vencimiento | 1.765 |
| Dias entrega antes vencimiento | 1.765 |
| Porcentaje Composicion | 1.641 |
| Tamano | 1.407 |
| Potencia | 1.083 |
| Diametro Producto | 976 |
| Longitud 2 | 860 |
| Liquidos | 841 |

## Perfil De Especificaciones

| Spec | Filas | Valores unicos | Con cantidad | Sin cantidad | Categorias |
| --- | ---: | ---: | ---: | ---: | ---: |
| Aroma | 286 | 65 | 0 | 286 | 39 |
| Capacidad | 2.031 | 18 | 2.031 | 0 | 200 |
| Color | 10.905 | 101 | 0 | 10.905 | 842 |
| Diametro Producto | 976 | 1 | 976 | 0 | 100 |
| Dias entrega antes vencimiento | 1.765 | 1 | 1.765 | 0 | 142 |
| Dias recibo antes vencimiento | 1.766 | 1 | 1.766 | 0 | 143 |
| Dias retiro antes vencimiento | 1.765 | 1 | 1.765 | 0 | 142 |
| Edad | 630 | 8 | 0 | 630 | 30 |
| Genero | 14 | 3 | 0 | 14 | 7 |
| Hilos | 64 | 2 | 0 | 64 | 12 |
| Liquidos | 841 | 4 | 841 | 0 | 95 |
| Longitud 2 | 860 | 4 | 0 | 860 | 83 |
| Materiales 1 | 11.009 | 89 | 540 | 10.469 | 829 |
| Materiales 2 | 549 | 44 | 518 | 31 | 84 |
| Medida Empaque Alto | 16.945 | 1 | 16.944 | 1 | 1.184 |
| Medida Empaque Fondo | 16.945 | 1 | 16.945 | 0 | 1.184 |
| Medida Empaque Frente | 16.945 | 1 | 16.945 | 0 | 1.184 |
| Medida Producto Uso Alto | 8.256 | 1 | 8.256 | 0 | 692 |
| Medida Producto Uso Fondo | 3.731 | 1 | 3.731 | 0 | 400 |
| Medida Producto Uso Frente | 7.772 | 1 | 7.772 | 0 | 674 |
| Peso | 3.812 | 3 | 3.812 | 0 | 598 |
| Porcentaje Composicion | 1.641 | 1 | 80 | 1.561 | 212 |
| Potencia | 1.083 | 4 | 1.083 | 0 | 136 |
| Sabor | 558 | 72 | 0 | 558 | 68 |
| Tamano | 1.407 | 26 | 0 | 1.407 | 183 |
| Unidades x Paquete | 2.046 | 57 | 0 | 2.046 | 339 |

## Interpretacion De Campos

El CSV mezcla especificaciones enumeradas y especificaciones numericas:

- Specs con `cantidad`: `Peso`, `Capacidad`, `Potencia`, medidas, dias,
  `Liquidos`, entre otras. En estos casos `cantidad` parece ser el valor real y
  `Especificacion` suele representar la unidad o el nombre tecnico del campo.
- Specs sin `cantidad`: `Color`, `Aroma`, `Edad`, `Sabor`, `Tamano`,
  `Unidades x Paquete`, entre otras. En estos casos `Especificacion` es el valor
  cargable.
- Specs mixtas: `Materiales 1`, `Materiales 2`, `Porcentaje Composicion`. Estas
  requieren validacion adicional porque algunas filas tienen cantidad y otras no.

## Hallazgos De Calidad De Datos

### Filas No Cargables

Se detectaron 28 filas sin nombre ni valor de especificacion. Ejemplos:

| SKU | Categoria | Subcategoria | Linea | Category ID |
| --- | --- | --- | --- | ---: |
| 177280 | Mesa | Jarras | Jarras Vidrio | 731 |
| 190798 | Complementos Hogar | Soportes De Television | Soportes De Television 50 Pulgadas O Ma | 1511 |
| 209328-2 | Decoracion | Decoracion Jardin | Portamateras | 338 |
| 225033 | Organizacion | Closet | Gancho Infantil | 765 |
| 225034 | Organizacion | Closet | Gancho Infantil | 765 |

### SKUs Con Mas De Un Category ID

Se detectaron 9 SKUs asociados a mas de un `Category ID`:

| SKU | Category IDs |
| --- | --- |
| 11511 | 859, 891 |
| 11522 | 859, 879 |
| 12986 | 1112, 42 |
| 14704 | 285, 375 |
| 14705 | 1117, 285 |
| 15012 | 1056, 1421 |
| 16112 | 1614, 849 |
| 168594 | 224, 400 |
| 175564 | 1449, 224 |

Esto debe bloquearse o reportarse antes de escribir en VTEX, porque la categoria
define donde se crean o reutilizan las especificaciones.

### Category IDs Con Multiples Rutas

Se detectaron 62 `Category ID` relacionados con mas de una ruta
`Categoria/Subcategoria/Linea`. Casos con mas filas:

| Category ID | Total filas | Rutas principales |
| ---: | ---: | --- |
| 755 | 1.964 | Canastas Organizadoras; Organizador Multiusos |
| 540 | 520 | Botellas; Despensa Vidrio; Termos Metalicos; Sarten Otros Materiales |
| 346 | 362 | Cuadro Abstracto Hasta 1 Mt; Cuadro Figura Humana Hasta 1 Mt |
| 1034 | 313 | Dispensador De Jabon Liquido; Porta Esponja |
| 1027 | 305 | Toallas 500 Gramos Cuerpo; Toallas Playeras |
| 338 | 264 | Portamateras; Bases Materas |
| 1278 | 249 | Galletas Dulces Saludables; Dulces Duro |
| 640 | 242 | Porta Comida; Recipientes Vidrio |
| 347 | 237 | Cuadro Abstracto Mas De 1 Mt; Cuadro Figura Humana Hasta 1 Mt |
| 1377 | 212 | Adornos Ceramica Y Poliresina Navidad; Adornos Metal Madera Navidad |

Este hallazgo puede ser normal si el matcher trae rutas historicas o aliases,
pero el loader debe auditarlo antes de operar por categoria.

## Recomendaciones Para El Nuevo Loader

Antes de ejecutar escrituras contra VTEX, implementar un preflight que:

1. Lea el CSV con `encoding='utf-8-sig'`.
2. Valide que existan las 10 columnas esperadas.
3. Reporte filas sin `Nombre Especificacion` o sin valor cargable.
4. Reporte SKUs asociados a multiples `Category ID`.
5. Reporte `Category ID` asociados a multiples rutas.
6. Separe specs numericas, enumeradas y mixtas.
7. Genere un resumen Markdown y CSV antes de cualquier mutacion.
8. Mantenga modo `--dry-run` para cualquier operacion contra VTEX.

Reglas iniciales sugeridas:

- Para filas con `cantidad`, usar `cantidad` como valor principal y
  `Especificacion` como unidad o metadata del campo.
- Para filas sin `cantidad`, usar `Especificacion` como valor principal.
- Omitir filas completamente vacias de especificacion y registrarlas como
  `skipped`.
- No crear ni asociar specs para SKUs con categoria ambigua hasta resolver el
  conflicto.
- No ejecutar escrituras contra VTEX sin confirmacion explicita.
