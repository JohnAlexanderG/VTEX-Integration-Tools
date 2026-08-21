#!/usr/bin/env python3
"""
email_masterdata_diff.py

Compara dos CSV por correo electronico (case-insensitive) para detectar que
registros del segundo archivo ya existen en el primero, y arma el payload de
actualizacion parcial (PATCH) para completar los campos vacios de los que ya
existen.

Funcionalidad:
- archivo1 representa el estado ACTUAL de Master Data (ej. export de
  69_vtex_masterdata_search_exporter), con el correo en la columna --email-col1
  (default: "email") y el `id` del documento en la columna "id".
- archivo2 representa datos NUEVOS candidatos a cargar (ej. salida de
  70_csv_datos_personales_co), con el correo en la columna --email-col2
  (default: "Correo").
- Normaliza ambos correos con strip().lower() antes de comparar, para que la
  coincidencia sea insensible a mayusculas/minusculas y espacios.
- Cada fila de archivo2 se clasifica en:
    * Coincidencia con cambios: el correo ya existe en archivo1 y hay al
      menos un campo vacio que se puede completar con archivo2. Se agregan
      las columnas `id` (del documento en archivo1) y `patch_payload` (JSON
      con los campos VTEX a completar) a la fila de salida.
    * Coincidencia sin cambios: el correo ya existe en archivo1 pero este ya
      tenia todos los campos completos -> no hay nada que actualizar. Va a
      un archivo separado (sin `patch_payload`, no aplica).
    * A crear: el correo no existe en archivo1 -> falta darlo de alta en
      Master Data (no aplica PATCH, no tiene `id` todavia). Se agrega la
      columna `create_payload` (JSON) con el objeto completo listo para un
      futuro POST de creacion.
  Las filas con correo vacio en archivo2 no se pueden verificar; se excluyen
  de ambos archivos de salida y se cuentan aparte en el reporte.
- Los duplicados internos de archivo2 (mismo correo repetido varias veces) no
  se deduplican; cada fila se conserva en su archivo de salida normal y,
  ademas, TODAS las filas que comparten un correo duplicado se exportan
  aparte a `_duplicados.csv` (con una columna `categoria` indicando a cual
  de los otros archivos fue cada fila), para revision manual.
- Mapeo de campos usado para `patch_payload` (archivo2 -> campo VTEX):
    Nombres          -> firstName
    Apellidos        -> lastName
    Cedula           -> document
    Celular          -> homePhone
    Fecha Nacimiento -> birthDate
    Genero           -> gender
    Tipo Documento   -> documentType
  Regla: si el campo YA tiene valor en archivo1, NO se incluye en el payload
  (no se sobreescribe); si esta vacio/ausente en archivo1 y archivo2 trae un
  valor, SI se incluye con el valor de archivo2. Correo/email no se incluye
  (es la clave de match). Ciudad y Sucursal se omiten (sin campo equivalente
  conocido en archivo1).
- Mapeo de campos usado para `create_payload` (registros "a crear", sin
  archivo1 con que comparar, asi que SIEMPRE incluye todas las claves):
    Correo           -> email
    Nombres          -> firstName
    Apellidos        -> lastName
    Cedula           -> document
    Celular          -> homePhone
    Fecha Nacimiento -> birthDate
    Genero           -> gender
    Tipo Documento   -> documentType
    (fijo)           -> phone: ""
    (fijo)           -> isCorporate: false
    (fijo)           -> isNewsletterOptIn: true
    (fijo)           -> localeDefault: "es-CO"
  `phone` siempre queda vacio (solo se usa `homePhone`). Ciudad y Sucursal
  se omiten, igual que en `patch_payload`.
- Este script SOLO prepara los datos: no realiza ninguna llamada HTTP a la
  API de VTEX. `patch_payload` y `create_payload` quedan listos para un
  futuro paso que ejecute PATCH/POST contra
  /api/dataentities/{dataEntityName}/documents(/{id}).

Dependencias:
- Solo libreria estandar: csv, json, argparse, sys, datetime

Ejecucion:
    python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida

    # Con nombres de columna de correo personalizados
    python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida \\
        --email-col1 email --email-col2 Correo

Ejemplo:
    python3 71_email_masterdata_diff/email_masterdata_diff.py \\
        69_vtex_masterdata_search_exporter/CL_search_20260818_165833.csv \\
        70_csv_datos_personales_co/output_formateado.csv \\
        resultado
    # Genera: resultado_coincidencias_actualizar.csv (con patch_payload),
    #         resultado_coincidencias_sin_cambios.csv, resultado_crear.csv (con create_payload),
    #         resultado_duplicados.csv, resultado_REPORT.md
"""
import argparse
import csv
import json
import sys
from datetime import datetime

ID_COLUMN = "id"

# archivo2 (columna) -> campo VTEX en archivo1
FIELD_MAP = {
    "Nombres": "firstName",
    "Apellidos": "lastName",
    "Cedula": "document",
    "Celular": "homePhone",
    "Fecha Nacimiento": "birthDate",
    "Genero": "gender",
    "Tipo Documento": "documentType",
}

# Valores fijos incluidos en create_payload para todos los registros "a crear"
CREATE_PAYLOAD_DEFAULTS = {
    "phone": "",
    "isCorporate": False,
    "isNewsletterOptIn": True,
    "localeDefault": "es-CO",
}


def normalize_email(raw):
    """Normaliza un correo para comparacion case-insensitive."""
    return (raw or "").strip().lower()


def load_masterdata_rows(path, email_col, encoding):
    """Lee archivo1 y retorna dict correo_normalizado -> fila completa."""
    rows_by_email = {}
    try:
        with open(path, "r", newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            missing = [c for c in (email_col, ID_COLUMN) if c not in fieldnames]
            if missing:
                print(
                    f"✗ archivo1 no tiene las columnas requeridas {missing}. "
                    f"Columnas disponibles: {fieldnames}",
                    file=sys.stderr,
                )
                sys.exit(1)
            for row in reader:
                normalized = normalize_email(row.get(email_col))
                if normalized:
                    rows_by_email[normalized] = row
    except FileNotFoundError:
        print(f"✗ Archivo no encontrado: {path}", file=sys.stderr)
        sys.exit(1)
    return rows_by_email


def build_patch_payload(masterdata_row, new_row):
    """Retorna el dict de campos a incluir en el PATCH (solo los vacios en archivo1)."""
    payload = {}
    for source_col, vtex_field in FIELD_MAP.items():
        existing_value = (masterdata_row.get(vtex_field) or "").strip()
        if existing_value:
            continue
        new_value = (new_row.get(source_col) or "").strip()
        if new_value:
            payload[vtex_field] = new_value
    return payload


def build_create_payload(new_row, email_col, normalized_email):
    """Retorna el dict completo para crear el registro (POST) a partir de una fila de archivo2."""
    payload = {"email": normalized_email}
    for source_col, vtex_field in FIELD_MAP.items():
        payload[vtex_field] = (new_row.get(source_col) or "").strip()
    payload.update(CREATE_PAYLOAD_DEFAULTS)
    return payload


def classify_new_records(path, email_col, encoding, masterdata_rows):
    """
    Lee archivo2, clasifica cada fila y arma el patch_payload de las coincidencias.

    Retorna (coincidencias_actualizar, coincidencias_sin_cambios, a_crear,
             duplicados, sin_correo, correos_duplicados, fieldnames, field_fill_counts).
    """
    try:
        with open(path, "r", newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)
            if email_col not in (reader.fieldnames or []):
                print(
                    f"✗ La columna '{email_col}' no existe en {path}. "
                    f"Columnas disponibles: {reader.fieldnames}",
                    file=sys.stderr,
                )
                sys.exit(1)
            fieldnames = reader.fieldnames
            rows = list(reader)
    except FileNotFoundError:
        print(f"✗ Archivo no encontrado: {path}", file=sys.stderr)
        sys.exit(1)

    coincidencias_actualizar = []
    coincidencias_sin_cambios = []
    a_crear = []
    sin_correo = 0
    seen_emails = set()
    duplicate_emails = set()
    rows_by_email = {}
    field_fill_counts = {vtex_field: 0 for vtex_field in FIELD_MAP.values()}

    for row in rows:
        normalized = normalize_email(row.get(email_col))
        if not normalized:
            sin_correo += 1
            continue

        if normalized in seen_emails:
            duplicate_emails.add(normalized)
        seen_emails.add(normalized)

        masterdata_row = masterdata_rows.get(normalized)
        if masterdata_row is None:
            create_payload = build_create_payload(row, email_col, normalized)
            output_row = dict(row)
            output_row["create_payload"] = json.dumps(create_payload, ensure_ascii=False)
            a_crear.append(output_row)
            rows_by_email.setdefault(normalized, []).append((row, "a_crear"))
            continue

        payload = build_patch_payload(masterdata_row, row)
        record_id = masterdata_row.get(ID_COLUMN, "")

        if payload:
            for vtex_field in payload:
                field_fill_counts[vtex_field] += 1
            output_row = dict(row)
            output_row["id"] = record_id
            output_row["patch_payload"] = json.dumps(payload, ensure_ascii=False)
            coincidencias_actualizar.append(output_row)
            rows_by_email.setdefault(normalized, []).append((row, "coincidencia_actualizar"))
        else:
            output_row = dict(row)
            output_row["id"] = record_id
            coincidencias_sin_cambios.append(output_row)
            rows_by_email.setdefault(normalized, []).append((row, "coincidencia_sin_cambios"))

    duplicados = []
    for normalized, entries in rows_by_email.items():
        if len(entries) < 2:
            continue
        for row, categoria in entries:
            output_row = dict(row)
            output_row["categoria"] = categoria
            duplicados.append(output_row)

    return (
        coincidencias_actualizar,
        coincidencias_sin_cambios,
        a_crear,
        duplicados,
        sin_correo,
        duplicate_emails,
        fieldnames,
        field_fill_counts,
    )


def write_csv(path, rows, fieldnames, encoding):
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path, stats):
    lines = [
        "# Reporte de comparacion de correos vs Master Data",
        "",
        f"**Fecha de ejecucion:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- Correos unicos cargados desde archivo1 (masterdata): {stats['masterdata_emails']}",
        f"- Total de filas en archivo2: {stats['total_archivo2']}",
        f"- Coincidencias (ya existen en masterdata): {stats['coincidencias']}",
        f"  - Con payload generado (requieren PATCH): {stats['con_payload']}",
        f"  - Sin cambios necesarios (archivo1 ya tenia todo): {stats['sin_cambios']}",
        f"- A crear (no existen en masterdata): {stats['a_crear']}",
        f"- Filas de archivo2 con correo vacio (excluidas de todos los archivos): {stats['sin_correo']}",
        f"- Correos duplicados dentro de archivo2: {stats['duplicados']}",
        f"- Filas involucradas en esos duplicados (exportadas a _duplicados.csv): {stats['filas_duplicadas']}",
        "",
        "## Campos completados (en coincidencias con payload)",
        "",
    ]
    for vtex_field, count in stats["field_fill_counts"].items():
        lines.append(f"- {vtex_field}: {count}")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Compara dos CSV por correo electronico (case-insensitive) para detectar que registros de archivo2 ya existen en archivo1 (masterdata).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida
  python3 email_masterdata_diff.py archivo1.csv archivo2.csv salida --email-col1 email --email-col2 Correo
""",
    )
    parser.add_argument("archivo1", help="CSV con el estado actual de Master Data")
    parser.add_argument("archivo2", help="CSV con los datos nuevos a evaluar")
    parser.add_argument(
        "output_prefix",
        help=(
            "Prefijo para los archivos de salida (genera _coincidencias_actualizar.csv, "
            "_coincidencias_sin_cambios.csv, _crear.csv, _duplicados.csv, _REPORT.md)"
        ),
    )
    parser.add_argument(
        "--email-col1",
        default="email",
        help="Nombre de la columna de correo en archivo1 (default: email)",
    )
    parser.add_argument(
        "--email-col2",
        default="Correo",
        help="Nombre de la columna de correo en archivo2 (default: Correo)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding de los CSV de entrada/salida (default: utf-8)",
    )
    args = parser.parse_args()

    print(f"Leyendo masterdata actual: {args.archivo1} (columna '{args.email_col1}')...")
    masterdata_rows = load_masterdata_rows(args.archivo1, args.email_col1, args.encoding)
    print(f"✓ {len(masterdata_rows)} correos unicos cargados desde archivo1")

    print(f"Leyendo datos nuevos: {args.archivo2} (columna '{args.email_col2}')...")
    (
        coincidencias_actualizar,
        coincidencias_sin_cambios,
        a_crear,
        duplicados_rows,
        sin_correo,
        duplicados,
        fieldnames,
        field_fill_counts,
    ) = classify_new_records(args.archivo2, args.email_col2, args.encoding, masterdata_rows)

    actualizar_path = f"{args.output_prefix}_coincidencias_actualizar.csv"
    sin_cambios_path = f"{args.output_prefix}_coincidencias_sin_cambios.csv"
    a_crear_path = f"{args.output_prefix}_crear.csv"
    duplicados_path = f"{args.output_prefix}_duplicados.csv"
    report_path = f"{args.output_prefix}_REPORT.md"

    actualizar_fieldnames = list(fieldnames) + ["id", "patch_payload"]
    sin_cambios_fieldnames = list(fieldnames) + ["id"]
    a_crear_fieldnames = list(fieldnames) + ["create_payload"]
    duplicados_fieldnames = list(fieldnames) + ["categoria"]
    write_csv(actualizar_path, coincidencias_actualizar, actualizar_fieldnames, args.encoding)
    write_csv(sin_cambios_path, coincidencias_sin_cambios, sin_cambios_fieldnames, args.encoding)
    write_csv(a_crear_path, a_crear, a_crear_fieldnames, args.encoding)
    write_csv(duplicados_path, duplicados_rows, duplicados_fieldnames, args.encoding)

    total_coincidencias = len(coincidencias_actualizar) + len(coincidencias_sin_cambios)
    write_report(report_path, {
        "masterdata_emails": len(masterdata_rows),
        "total_archivo2": total_coincidencias + len(a_crear) + sin_correo,
        "coincidencias": total_coincidencias,
        "a_crear": len(a_crear),
        "sin_correo": sin_correo,
        "duplicados": len(duplicados),
        "filas_duplicadas": len(duplicados_rows),
        "con_payload": len(coincidencias_actualizar),
        "sin_cambios": len(coincidencias_sin_cambios),
        "field_fill_counts": field_fill_counts,
    })

    print(f"✓ Coincidencias con cambios a aplicar: {len(coincidencias_actualizar)} -> {actualizar_path}")
    print(f"✓ Coincidencias sin cambios necesarios: {len(coincidencias_sin_cambios)} -> {sin_cambios_path}")
    print(f"✓ A crear (no existen en masterdata): {len(a_crear)} -> {a_crear_path}")
    if duplicados:
        print(f"⚠ Correos duplicados dentro de archivo2: {len(duplicados)} ({len(duplicados_rows)} filas) -> {duplicados_path}")
    if sin_correo:
        print(f"⚠ Filas de archivo2 sin correo (excluidas): {sin_correo}")
    print(f"✓ Reporte: {report_path}")


if __name__ == "__main__":
    main()
