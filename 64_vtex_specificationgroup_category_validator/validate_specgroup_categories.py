#!/usr/bin/env python3
"""
validate_specgroup_categories.py
--------------------------------
Valida el CSV exitoso de creación de grupos de especificación contra el árbol
de categorías VTEX, dejando pasar solo filas cuyo CategoryId corresponde a una
categoría de tercer nivel.

Salida:
  - <prefix>_categoryid_tercer_nivel_correctos.csv -> filas válidas sin cambios
  - <prefix>_categoryid_no_coinciden.csv -> filas no aptas con columnas de auditoría

Uso:
  python3 validate_specgroup_categories.py <specgroup_success.csv> <tree-categories.json> [opciones]

Opciones:
  -o, --output-prefix     Prefijo para los archivos de salida
  --category-id-column    Columna con el ID de categoría (default: "CategoryId")
  --encoding              Encoding de entrada/salida (default: utf-8-sig)
  --output-dir            Directorio de salida (default: directorio del CSV de entrada)
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple


AUDIT_FIELDNAMES = [
    "CategoryLevel",
    "CategoryName",
    "ParentCategoryId",
    "ParentCategoryName",
    "CategoryPath",
    "ValidationReason",
]


def normalize_category_id(value: object) -> Optional[str]:
    """Normaliza IDs enteros para comparar CSV y JSON de forma estable."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        return str(int(text))
    except ValueError:
        return None


def read_csv_rows(filepath: str, encoding: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Lee un CSV y devuelve (rows, fieldnames) preservando encabezados."""
    with open(filepath, encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def read_category_tree(filepath: str, encoding: str) -> List[Dict]:
    """Lee el árbol de categorías VTEX en formato JSON."""
    with open(filepath, encoding=encoding, errors="replace") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("El árbol de categorías debe ser una lista JSON.")
    return data


def build_category_level_index(tree_rows: List[Dict]) -> Dict[str, Dict[str, str]]:
    """Construye un índice por ID con nivel, nombre, padre y ruta legible."""
    category_index: Dict[str, Dict[str, str]] = {}

    def visit(node: Dict, level: int, parent: Optional[Dict], path_parts: List[str]) -> None:
        category_id = normalize_category_id(node.get("id"))
        name = str(node.get("name") or "").strip()
        current_path = path_parts + ([name] if name else [])

        if category_id and category_id not in category_index:
            parent_id = normalize_category_id(parent.get("id")) if parent else None
            parent_name = str(parent.get("name") or "").strip() if parent else ""
            category_index[category_id] = {
                "level": str(level),
                "name": name,
                "parent_id": parent_id or "",
                "parent_name": parent_name,
                "path": " > ".join(current_path),
            }

        for child in node.get("children") or []:
            if isinstance(child, dict):
                visit(child, level + 1, node, current_path)

    for department in tree_rows:
        if isinstance(department, dict):
            visit(department, 1, None, [])

    return category_index


def classify_rows(
    rows: List[Dict[str, str]],
    category_column: str,
    category_index: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], Counter]:
    """Separa filas válidas de las que no apuntan a categorías de tercer nivel."""
    valid_rows: List[Dict[str, str]] = []
    invalid_rows: List[Dict[str, str]] = []
    reason_counts: Counter = Counter()

    for row in rows:
        raw_category_id = row.get(category_column, "")
        normalized_id = normalize_category_id(raw_category_id)

        if not normalized_id:
            audit_row = build_audit_row(row, "INVALID_CATEGORY_ID")
            invalid_rows.append(audit_row)
            reason_counts["INVALID_CATEGORY_ID"] += 1
            continue

        category_info = category_index.get(normalized_id)
        if not category_info:
            audit_row = build_audit_row(row, "CATEGORY_ID_NOT_IN_TREE")
            invalid_rows.append(audit_row)
            reason_counts["CATEGORY_ID_NOT_IN_TREE"] += 1
            continue

        level = category_info["level"]
        if level == "3":
            valid_rows.append(dict(row))
            continue

        reason = f"CATEGORY_ID_LEVEL_{level}"
        audit_row = build_audit_row(row, reason, category_info)
        invalid_rows.append(audit_row)
        reason_counts[reason] += 1

    return valid_rows, invalid_rows, reason_counts


def build_audit_row(
    source_row: Dict[str, str],
    reason: str,
    category_info: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Crea una fila de auditoría agregando el diagnóstico al registro original."""
    category_info = category_info or {}
    row = dict(source_row)
    row.update({
        "CategoryLevel": category_info.get("level", ""),
        "CategoryName": category_info.get("name", ""),
        "ParentCategoryId": category_info.get("parent_id", ""),
        "ParentCategoryName": category_info.get("parent_name", ""),
        "CategoryPath": category_info.get("path", ""),
        "ValidationReason": reason,
    })
    return row


def write_csv(filepath: str, rows: List[Dict[str, str]], fieldnames: List[str], encoding: str) -> None:
    """Escribe un CSV con los fieldnames dados."""
    with open(filepath, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Valida que CategoryId del CSV exitoso de grupos de especificación "
            "corresponda a categorías VTEX de tercer nivel."
        ),
    )
    parser.add_argument("specgroup_csv", help="CSV exitoso generado por vtex_specificationgroup_create")
    parser.add_argument("category_tree_json", help="Árbol JSON de categorías VTEX")
    parser.add_argument(
        "-o",
        "--output-prefix",
        default=None,
        help='Prefijo de salida (default: "resultado_YYYYMMDD_HHMMSS")',
    )
    parser.add_argument(
        "--category-id-column",
        default="CategoryId",
        help='Columna con el ID de categoría (default: "CategoryId")',
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding de entrada y salida (default: utf-8-sig)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directorio de salida (default: directorio del CSV de entrada)",
    )
    return parser.parse_args(argv)


def validate_input_files(specgroup_csv: str, category_tree_json: str) -> bool:
    input_files = [
        (specgroup_csv, "CSV de grupos de especificación"),
        (category_tree_json, "árbol de categorías"),
    ]

    for path, label in input_files:
        if not os.path.isfile(path):
            print(f"ERROR: No se encontró el archivo de {label}: {path}", file=sys.stderr)
            return False

    return True


def print_summary(
    total_rows: int,
    valid_rows: List[Dict[str, str]],
    invalid_rows: List[Dict[str, str]],
    reason_counts: Counter,
    out_valid: str,
    out_invalid: str,
) -> None:
    print("\nResumen de validación:")
    print(f"  Filas leídas       : {total_rows}")
    print(f"  Tercer nivel OK    : {len(valid_rows)}")
    print(f"  No coinciden       : {len(invalid_rows)}")

    if reason_counts:
        print("  Razones:")
        for reason, count in sorted(reason_counts.items()):
            print(f"    - {reason}: {count}")

    print("\nArchivos generados:")
    print(f"  - Correctos     : {out_valid}")
    print(f"  - No coinciden  : {out_invalid}")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not validate_input_files(args.specgroup_csv, args.category_tree_json):
        return 1

    try:
        print(f"Leyendo CSV de grupos       : {args.specgroup_csv}")
        rows, fieldnames = read_csv_rows(args.specgroup_csv, args.encoding)

        if args.category_id_column not in fieldnames:
            print(
                f"ERROR: CSV must have '{args.category_id_column}' column. "
                f"Found: {fieldnames}",
                file=sys.stderr,
            )
            return 1

        print(f"Leyendo árbol de categorías : {args.category_tree_json}")
        category_tree_rows = read_category_tree(args.category_tree_json, args.encoding)
        category_index = build_category_level_index(category_tree_rows)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    valid_rows, invalid_rows, reason_counts = classify_rows(
        rows=rows,
        category_column=args.category_id_column,
        category_index=category_index,
    )

    now = datetime.now()
    prefix = args.output_prefix or f"resultado_{now.strftime('%Y%m%d_%H%M%S')}"
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(args.specgroup_csv))
    os.makedirs(output_dir, exist_ok=True)

    out_valid = os.path.join(output_dir, f"{prefix}_categoryid_tercer_nivel_correctos.csv")
    out_invalid = os.path.join(output_dir, f"{prefix}_categoryid_no_coinciden.csv")

    audit_fieldnames = list(dict.fromkeys(fieldnames + AUDIT_FIELDNAMES))
    write_csv(out_valid, valid_rows, fieldnames, args.encoding)
    write_csv(out_invalid, invalid_rows, audit_fieldnames, args.encoding)

    print_summary(
        total_rows=len(rows),
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        reason_counts=reason_counts,
        out_valid=out_valid,
        out_invalid=out_invalid,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
