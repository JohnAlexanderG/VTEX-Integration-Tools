#!/usr/bin/env python3
"""
csv_datos_personales_co.py

Limpia, valida y formatea un CSV de datos personales de clientes colombianos.

Funcionalidad:
- Lee un CSV con columnas: Nombres, Apellidos, Cedula, Celular, Fecha Nacimiento,
  Correo, Genero, Ciudad, Tipo Documento, Sucursal
- Limpia y valida Cedula según Tipo Documento:
    * CC (Cédula de Ciudadanía): solo dígitos, 4 a 10 caracteres (^\\d{4,10}$)
    * CE (Cédula de Extranjería): letras y/o números, 3 a 10 caracteres
      (^[A-Za-z0-9]{3,10}$), quitando ceros a la izquierda
    * Cualquier otro Tipo Documento se considera no soportado
- Valida Celular contra el formato de celular colombiano, aceptando prefijo
  opcional +57/57 (^(?:\\+?57)?3\\d{9}$), y lo normaliza a 10 dígitos sin prefijo
- Convierte Fecha Nacimiento de YYYYMMDD a ISO 8601 (YYYY-MM-DDT00:00:00Z)
- Filas con Cedula, Celular o Fecha Nacimiento inválidos se exportan completas
  (columnas originales + Motivo) a un archivo de revisión separado
- Genera un reporte Markdown con estadísticas del procesamiento

Dependencias:
- Solo librería estándar: csv, re, argparse, sys, datetime

Ejecución:
    python3 csv_datos_personales_co.py clientes.csv salida

    # Con encoding personalizado
    python3 csv_datos_personales_co.py clientes.csv salida --encoding latin-1

Ejemplo:
    python3 70_csv_datos_personales_co/csv_datos_personales_co.py clientes.csv resultado
    # Genera: resultado_formateado.csv, resultado_revision.csv, resultado_REPORT.md
"""
import argparse
import csv
import re
import sys
from datetime import datetime

FIELDNAMES = [
    "Nombres", "Apellidos", "Cedula", "Celular", "Fecha Nacimiento",
    "Correo", "Genero", "Ciudad", "Tipo Documento", "Sucursal",
]

CEDULA_CC_RE = re.compile(r"^\d{4,10}$")
CEDULA_CE_RE = re.compile(r"^[A-Za-z0-9]{3,10}$")
CELULAR_RE = re.compile(r"^(?:\+?57)?3\d{9}$")


def clean_cedula(raw):
    """Deja solo caracteres alfanuméricos y quita ceros a la izquierda."""
    only_alnum = re.sub(r"[^A-Za-z0-9]", "", raw or "")
    stripped = only_alnum.lstrip("0")
    return stripped or only_alnum


def validate_cedula(cedula, tipo_documento):
    """True si cedula (ya limpia) cumple el formato oficial para su Tipo Documento."""
    if tipo_documento == "CC":
        return bool(CEDULA_CC_RE.match(cedula))
    if tipo_documento == "CE":
        return bool(CEDULA_CE_RE.match(cedula))
    return False


def normalize_celular(raw):
    """Retorna el celular normalizado a 10 dígitos (sin prefijo) o None si es inválido."""
    digits_plus = re.sub(r"[^\d+]", "", raw or "")
    if not CELULAR_RE.match(digits_plus):
        return None
    return re.sub(r"\D", "", digits_plus)[-10:]


def convert_fecha_nacimiento(raw):
    """Convierte YYYYMMDD a ISO 8601 (YYYY-MM-DDT00:00:00Z) o None si es inválida."""
    try:
        dt = datetime.strptime((raw or "").strip(), "%Y%m%d")
    except ValueError:
        return None
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def process_row(row):
    """
    Procesa una fila del CSV de entrada.

    Retorna una tupla (es_valida, fila_resultado, motivos):
    - Si es válida: fila_resultado trae Cedula/Celular/Fecha Nacimiento transformados.
    - Si no: fila_resultado es la fila original sin modificar, motivos lista los problemas.
    """
    reasons = []
    tipo_documento = (row.get("Tipo Documento") or "").strip().upper()

    cedula_limpia = clean_cedula(row.get("Cedula"))
    if tipo_documento not in ("CC", "CE"):
        reasons.append("Tipo Documento no soportado")
    elif not validate_cedula(cedula_limpia, tipo_documento):
        reasons.append("Cédula inválida")

    celular_normalizado = normalize_celular(row.get("Celular"))
    if celular_normalizado is None:
        reasons.append("Celular inválido")

    fecha_iso = convert_fecha_nacimiento(row.get("Fecha Nacimiento"))
    if fecha_iso is None:
        reasons.append("Fecha Nacimiento inválida")

    if reasons:
        return False, dict(row), reasons

    result = dict(row)
    result["Cedula"] = cedula_limpia
    result["Celular"] = celular_normalizado
    result["Fecha Nacimiento"] = fecha_iso
    return True, result, []


def write_csv(path, rows, fieldnames, encoding):
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path, stats):
    lines = [
        "# Reporte de formateo de datos personales",
        "",
        f"**Fecha de ejecución:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- Total de filas procesadas: {stats['total']}",
        f"- Filas formateadas correctamente: {stats['validas']}",
        f"- Filas enviadas a revisión: {stats['invalidas']}",
        "",
        "## Motivos de revisión",
        "",
    ]
    if stats["motivos"]:
        for motivo, count in sorted(stats["motivos"].items(), key=lambda x: -x[1]):
            lines.append(f"- {motivo}: {count}")
    else:
        lines.append("- (ninguno)")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Limpia, valida y formatea un CSV de datos personales de clientes colombianos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python3 csv_datos_personales_co.py clientes.csv salida
  python3 csv_datos_personales_co.py clientes.csv salida --encoding latin-1
""",
    )
    parser.add_argument("input_csv", help="Ruta del CSV de entrada")
    parser.add_argument(
        "output_prefix",
        help="Prefijo para los archivos de salida (genera _formateado.csv, _revision.csv, _REPORT.md)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding del CSV de entrada/salida (default: utf-8)",
    )
    args = parser.parse_args()

    try:
        with open(args.input_csv, "r", newline="", encoding=args.encoding) as f:
            reader = csv.DictReader(f)
            missing = [c for c in FIELDNAMES if c not in (reader.fieldnames or [])]
            if missing:
                print(f"✗ El CSV de entrada no tiene las columnas requeridas: {missing}", file=sys.stderr)
                sys.exit(1)
            rows = list(reader)
    except FileNotFoundError:
        print(f"✗ Archivo no encontrado: {args.input_csv}", file=sys.stderr)
        sys.exit(1)

    validas = []
    invalidas = []
    motivos_count = {}

    for row in rows:
        is_valid, result_row, reasons = process_row(row)
        if is_valid:
            validas.append(result_row)
        else:
            result_row["Motivo"] = "; ".join(reasons)
            invalidas.append(result_row)
            for motivo in reasons:
                motivos_count[motivo] = motivos_count.get(motivo, 0) + 1

    formateado_path = f"{args.output_prefix}_formateado.csv"
    revision_path = f"{args.output_prefix}_revision.csv"
    report_path = f"{args.output_prefix}_REPORT.md"

    write_csv(formateado_path, validas, FIELDNAMES, args.encoding)
    write_csv(revision_path, invalidas, FIELDNAMES + ["Motivo"], args.encoding)
    write_report(report_path, {
        "total": len(rows),
        "validas": len(validas),
        "invalidas": len(invalidas),
        "motivos": motivos_count,
    })

    print(f"✓ Filas procesadas: {len(rows)}")
    print(f"✓ Formateadas correctamente: {len(validas)} -> {formateado_path}")
    print(f"⚠ Enviadas a revisión: {len(invalidas)} -> {revision_path}")
    print(f"✓ Reporte: {report_path}")


if __name__ == "__main__":
    main()
