# 70_csv_datos_personales_co

## Descripción

Limpia, valida y formatea un CSV de datos personales de clientes colombianos. Limpia y valida el campo `Cedula` según `Tipo Documento` (CC/CE), valida y normaliza el campo `Celular` al formato de celular colombiano, y convierte `Fecha Nacimiento` de `YYYYMMDD` a ISO 8601. Las filas que no cumplen alguna de estas validaciones se separan en un archivo de revisión aparte con el motivo, en vez de detener el procesamiento.

## Requisitos

- Python 3.6+ (solo librería estándar: csv, re, argparse, sys, datetime)
- Sin dependencias externas

## Uso

```bash
python3 csv_datos_personales_co.py <input.csv> <output_prefix> [--encoding <encoding>]
```

### Argumentos

- `input.csv` - CSV de entrada con las columnas requeridas (ver Formato de Entrada)
- `output_prefix` - Prefijo para los 3 archivos de salida generados
- `--encoding <encoding>` - Encoding del CSV de entrada/salida (default: `utf-8`)

### Ejemplos

```bash
# Conversión básica
python3 csv_datos_personales_co.py clientes.csv salida

# Con encoding personalizado
python3 csv_datos_personales_co.py clientes.csv salida --encoding latin-1
```

## Formato de Entrada

### input.csv

Requiere exactamente estas columnas:

```
Nombres,Apellidos,Cedula,Celular,Fecha Nacimiento,Correo,Genero,Ciudad,Tipo Documento,Sucursal
```

**Ejemplo:**
```csv
Nombres,Apellidos,Cedula,Celular,Fecha Nacimiento,Correo,Genero,Ciudad,Tipo Documento,Sucursal
EDUARDO,CABASCANGO,000000000101952,3103417578,19470130,WECA75@HOTMAIL.COM,M,11001,CE,001
```

## Formato de Salida

Genera 3 archivos a partir de `output_prefix`:

- **`{prefix}_formateado.csv`** - Filas válidas, mismas columnas del input, con `Cedula`, `Celular` y `Fecha Nacimiento` ya transformados.
- **`{prefix}_revision.csv`** - Filas inválidas, columnas originales sin modificar + columna `Motivo` (razones separadas por `; `).
- **`{prefix}_REPORT.md`** - Reporte con total de filas procesadas, válidas, en revisión y desglose por motivo.

**Ejemplo de fila formateada** (a partir del ejemplo de entrada anterior):
```csv
Nombres,Apellidos,Cedula,Celular,Fecha Nacimiento,Correo,Genero,Ciudad,Tipo Documento,Sucursal
EDUARDO,CABASCANGO,101952,3103417578,1947-01-30T00:00:00Z,WECA75@HOTMAIL.COM,M,11001,CE,001
```

**Ejemplo de fila en revisión:**
```csv
Nombres,Apellidos,Cedula,Celular,Fecha Nacimiento,Correo,Genero,Ciudad,Tipo Documento,Sucursal,Motivo
JOSE,CASTILLO,000000000102958,3112155511,19731031,JOSEEM17@HOTMAIL.COM,M,11001,CC,068,Cédula inválida
```

## Reglas de Validación

| Campo | Tipo Documento | Regex | Descripción |
|-------|-----------------|-------|-------------|
| Cedula | CC (Cédula de Ciudadanía) | `^\d{4,10}$` | Solo dígitos, 4 a 10 caracteres |
| Cedula | CE (Cédula de Extranjería) | `^[A-Za-z0-9]{3,10}$` | Letras y/o números, 3 a 10 caracteres |
| Cedula | Otro | — | No soportado, la fila va a revisión |
| Celular | — | `^(?:\+?57)?3\d{9}$` | Celular colombiano, acepta prefijo opcional `+57`/`57` |

Antes de validar, `Cedula` se limpia quitando todo carácter no alfanumérico y luego se le quitan los ceros a la izquierda. `Celular` válido se normaliza a 10 dígitos sin prefijo de país. `Fecha Nacimiento` se interpreta como `YYYYMMDD` y se convierte a `YYYY-MM-DDT00:00:00Z`.

## Lógica de Funcionamiento

1. Lee el CSV usando `csv.DictReader`, valida que existan las columnas requeridas
2. Para cada fila:
   - Limpia `Cedula` y la valida contra la regex de su `Tipo Documento` (CC/CE)
   - Normaliza `Celular` y valida el formato colombiano
   - Convierte `Fecha Nacimiento` de `YYYYMMDD` a ISO 8601
   - Si todos los campos son válidos, la fila transformada va a `_formateado.csv`
   - Si algún campo falla, la fila original (sin modificar) + `Motivo` va a `_revision.csv`
3. Genera `_REPORT.md` con estadísticas del procesamiento (total, válidas, en revisión, desglose por motivo)

## Notas/Caveats

- El mínimo de 4 dígitos para CC es más permisivo que el estándar oficial (NUIP moderno: 10 dígitos; formato antiguo: 7-8 dígitos). Se usa este mínimo para no descartar cédulas históricas de números bajos, asignadas de forma secuencial desde el inicio del sistema y aún válidas para personas de edad avanzada.
- Un `Tipo Documento` distinto de `CC`/`CE` siempre envía la fila a revisión (no hay regla de validación para otros tipos como TI, NIT, PA, RC)
- `Celular` acepta el prefijo `+57`/`57` en la entrada, pero siempre se normaliza a 10 dígitos sin prefijo en la salida
- Una fila puede acumular varios motivos de revisión simultáneamente (ej. `Cédula inválida; Celular inválido`)
- Solo librería estándar, sin dependencias externas
- Verificado contra el fixture real `27_csv_cleaner/clientes-sentry.csv` (407,335 filas): 404,296 formateadas correctamente, 3,039 enviadas a revisión
