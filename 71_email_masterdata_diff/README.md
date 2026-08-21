# 71_email_masterdata_diff

## Descripción

Compara dos CSV por correo electrónico, de forma **case-insensitive**, para detectar qué registros del segundo archivo (datos nuevos a evaluar) ya existen en el primero (estado actual de Master Data). Pensado como paso previo a una carga masiva: en vez de intentar crear en VTEX Master Data registros que ya existen, separa los correos que ya coinciden de los que realmente faltan por crear. Para las coincidencias, además arma el payload de actualización parcial (PATCH) que completaría los campos vacíos en Master Data con el dato de archivo2, **sin sobreescribir nada que ya exista** — y separa las que sí necesitan ese PATCH de las que ya están completas y no requieren ninguna acción.

- `archivo1` = export actual de Master Data (ej. salida de `69_vtex_masterdata_search_exporter`), con el correo en la columna `email` (configurable) y el `id` del documento en la columna `id`.
- `archivo2` = datos nuevos candidatos a cargar (ej. salida de `70_csv_datos_personales_co`), con el correo en la columna `Correo` (configurable).
- La comparación normaliza ambos correos con `strip().lower()` antes de comparar, así que `Juan@Mail.com` y `juan@mail.com ` se consideran el mismo correo.
- **Este script no llama a la API de VTEX.** Solo prepara los datos; `patch_payload` y `create_payload` quedan listos para un futuro paso que ejecute `PATCH`/`POST` contra `/api/dataentities/{dataEntityName}/documents(/{id})`.

## Requisitos

- Python 3.6+ (solo librería estándar: csv, json, argparse, sys, datetime)
- Sin dependencias externas

## Uso

```bash
python3 email_masterdata_diff.py <archivo1.csv> <archivo2.csv> <output_prefix> [opciones]
```

### Argumentos

- `archivo1.csv` - CSV con el estado actual de Master Data (debe incluir columna `id`)
- `archivo2.csv` - CSV con los datos nuevos a evaluar
- `output_prefix` - Prefijo para los 5 archivos de salida generados
- `--email-col1 <nombre>` - Columna de correo en archivo1 (default: `email`)
- `--email-col2 <nombre>` - Columna de correo en archivo2 (default: `Correo`)
- `--encoding <encoding>` - Encoding de los CSV de entrada/salida (default: `utf-8`)

### Ejemplos

```bash
# Con los nombres de columna por defecto (email / Correo)
python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida

# Con nombres de columna personalizados
python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida --email-col1 email --email-col2 Correo

# Caso de uso real del repo (masterdata actual vs datos personales formateados)
python3 71_email_masterdata_diff/email_masterdata_diff.py \
    69_vtex_masterdata_search_exporter/CL_search_20260818_165833.csv \
    70_csv_datos_personales_co/output_formateado.csv \
    resultado
```

## Formato de Entrada

No exige un esquema de columnas fijo: solo requiere que exista la columna indicada en `--email-col1` (en archivo1) y `--email-col2` (en archivo2). El resto de columnas de archivo2 se preservan tal cual en la salida.

**Ejemplo archivo1 (masterdata):**
```csv
id,email,firstName,lastName
1,juan@mail.com,Juan,Perez
```

**Ejemplo archivo2 (datos a evaluar):**
```csv
Nombres,Apellidos,Correo
JUAN,PEREZ,Juan@Mail.com
```

## Formato de Salida

Genera 5 archivos a partir de `output_prefix`:

- **`{prefix}_coincidencias_actualizar.csv`** - Filas de archivo2 cuyo correo ya existe en archivo1 **y** tienen al menos un campo vacío que se puede completar. Columnas: las originales de archivo2 + `id` (del documento en archivo1, para la futura URL del PATCH) + `patch_payload` (JSON con los campos VTEX a completar; nunca vacío en este archivo).
- **`{prefix}_coincidencias_sin_cambios.csv`** - Filas de archivo2 cuyo correo ya existe en archivo1 y **no** requieren ningún cambio (archivo1 ya tenía todos los campos completos). Columnas: las originales de archivo2 + `id` (de referencia; sin `patch_payload`, no aplica). No hace falta ninguna acción sobre estas.
- **`{prefix}_crear.csv`** - Filas de archivo2 cuyo correo NO existe en archivo1. Son las que hay que dar de alta. Columnas: las originales de archivo2 + `create_payload` (JSON con el objeto completo listo para un futuro POST de creación; a diferencia de `patch_payload`, siempre incluye todas las claves).
- **`{prefix}_duplicados.csv`** - Todas las filas de archivo2 cuyo correo aparece 2 o más veces dentro de archivo2 (cada fila se conserva en su archivo normal además de aparecer aquí). Columnas: las originales de archivo2 + `categoria` (`coincidencia_actualizar`, `coincidencia_sin_cambios` o `a_crear`, según a cuál de los otros archivos fue esa fila), para revisión manual.
- **`{prefix}_REPORT.md`** - Correos únicos cargados de archivo1, total de archivo2, cantidad de coincidencias (desglosadas en con-payload/sin-cambios), cantidad a crear, filas sin correo, correos duplicados dentro de archivo2 y cuántas filas están involucradas, y desglose de cuántas veces se completó cada campo.

Las filas de archivo2 con correo vacío no se pueden verificar contra archivo1: se excluyen de todos los archivos de salida y se cuentan aparte (`sin correo`) en el reporte, para revisión manual.

**Ejemplo de fila en `_coincidencias_actualizar.csv`:**
```csv
Nombres,...,Correo,id,patch_payload
VIVIAN,...,vivigrewe@gmail.com,d4cd7902-99bd-483e-997d-d68a4bc9c4db,"{""firstName"": ""VIVIAN"", ""homePhone"": ""3102106732""}"
```

**Ejemplo de fila en `_crear.csv`:**
```csv
Nombres,...,Correo,create_payload
EDUARDO,...,weca75@hotmail.com,"{""email"": ""weca75@hotmail.com"", ""firstName"": ""EDUARDO"", ""lastName"": ""CABASCANGO"", ""document"": ""101952"", ""homePhone"": ""3103417578"", ""birthDate"": ""1947-01-30T00:00:00Z"", ""gender"": ""M"", ""documentType"": ""CE"", ""phone"": """", ""isCorporate"": false, ""isNewsletterOptIn"": true, ""localeDefault"": ""es-CO""}"
```

## Mapeo de Campos

### Para `patch_payload` (coincidencias)

| Columna archivo2   | Campo VTEX (archivo1) |
|---------------------|------------------------|
| Nombres              | firstName              |
| Apellidos            | lastName                |
| Cedula                | document                |
| Celular                | homePhone               |
| Fecha Nacimiento    | birthDate                |
| Genero                 | gender                    |
| Tipo Documento      | documentType            |

`Correo`/`email` no se incluye en el payload porque es la clave de match (ya coincide). `Ciudad` y `Sucursal` se omiten porque no tienen un campo equivalente conocido en la entidad `CL` de Master Data.

### Para `create_payload` (a crear)

| Columna archivo2      | Clave del payload |
|-------------------------|---------------------|
| Correo (normalizado)   | email                |
| Nombres                  | firstName            |
| Apellidos                | lastName              |
| Cedula                    | document              |
| Celular                    | homePhone             |
| Fecha Nacimiento        | birthDate              |
| Genero                     | gender                  |
| Tipo Documento          | documentType          |
| *(fijo)*                  | `phone`: `""`         |
| *(fijo)*                  | `isCorporate`: `false` |
| *(fijo)*                  | `isNewsletterOptIn`: `true` |
| *(fijo)*                  | `localeDefault`: `"es-CO"` |

A diferencia de `patch_payload`, `create_payload` **siempre incluye todas las claves** (no hay archivo1 con qué comparar); si una celda de archivo2 está vacía, la clave queda con `""`. `phone` siempre queda vacío — solo se usa `homePhone` porque archivo2 solo trae un número de celular. `Ciudad` y `Sucursal` se siguen omitiendo.

## Lógica de Funcionamiento

1. Lee archivo1 completo con `csv.DictReader` y arma un diccionario `correo_normalizado -> fila completa` (valida que existan las columnas `id` y `--email-col1`).
2. Lee archivo2 con `csv.DictReader` y valida que exista la columna `--email-col2`.
3. Para cada fila de archivo2:
   - Si el correo está vacío, se cuenta como "sin correo" y se excluye de todos los archivos de salida.
   - Si el correo normalizado NO está en archivo1, se arma `create_payload` (siempre con todas las claves) y la fila (+ `create_payload`) va a `_crear.csv`.
   - Si el correo normalizado SÍ está en archivo1: recorre el mapeo de campos — si el campo VTEX en archivo1 está vacío/ausente y archivo2 trae un valor no vacío, lo agrega al payload.
     - Si el payload quedó con al menos un campo, la fila (+ `id` + `patch_payload`) va a `_coincidencias_actualizar.csv`.
     - Si el payload quedó vacío (archivo1 ya tenía todo), la fila (+ `id`) va a `_coincidencias_sin_cambios.csv`.
   - Los correos repetidos dentro de archivo2 no se deduplican: cada fila se conserva en su archivo normal, y además se registra junto con las demás filas que comparten su correo.
4. Al terminar, junta todas las filas cuyo correo aparece 2+ veces en archivo2 y las escribe en `_duplicados.csv` (con la columna `categoria` indicando a cuál archivo fue cada una).
5. Genera `_REPORT.md` con las estadísticas del procesamiento y el desglose de campos completados.

## Notas/Caveats

- **No ejecuta ninguna llamada HTTP.** Es solo un paso de preparación de datos; el PATCH/POST real contra `/api/dataentities/{dataEntityName}/documents(/{id})` es un paso futuro separado.
- La comparación de correos es case-insensitive y también ignora espacios al inicio/fin (`strip().lower()`); no normaliza acentos ni variantes tipográficas del correo.
- La regla de armado del payload es por **existencia**, no por diferencia: si archivo1 ya tiene un valor (aunque sea distinto al de archivo2), ese campo no se toca. Nunca sobreescribe datos existentes.
- Si archivo1 tiene correos duplicados, gana la última fila leída para ese correo (se sobreescribe en el diccionario de carga).
- Solo librería estándar, sin dependencias externas.
- Pensado para encadenarse después de `69_vtex_masterdata_search_exporter` (genera archivo1) y `70_csv_datos_personales_co` (genera archivo2 vía `_formateado.csv`).
