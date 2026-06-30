"""
sku_spec_matcher.py
-------------------
Cruza el archivo de especificaciones contra el listado de productos creados en VTEX,
usando el campo SKU (especificaciones) vs SKU reference code (productos).
Si se entrega el árbol de categorías VTEX, el Category ID se resuelve desde
Categoria/Subcategoria/Linea para tomar siempre el tercer nivel del árbol.
Si no se entrega el árbol, el Category ID se toma de la fila del producto.
Si un SKU reference code está duplicado en productos, se conserva una sola
coincidencia y se prefiere la fila cuya categoría coincide con el spec.

Salida:
  - <prefix>_encontrados.csv    → specs con SKU encontrado + Category ID válido
  - <prefix>_no_encontrados.csv → specs con SKU NO encontrado en productos
  - <prefix>_category_ids.csv   → Category ID encontrados sin repetir
  - <prefix>_category_resolution_conflicts.csv → matches sin Category ID hoja confiable
  - <prefix>_category_id_corrections.csv → Category ID corregidos o aceptados por auditoría
  - <prefix>_reporte.md         → resumen ejecutivo

Uso:
  python3 sku_spec_matcher.py <especificaciones.csv> <productos.csv> [tree-categories.json] [opciones]

Opciones:
  -o, --output-prefix   Prefijo para los archivos de salida (default: "resultado_YYYYMMDD_HHMMSS")
  --sep-specs           Separador del CSV de especificaciones (default: auto-detect)
  --sep-products        Separador del CSV de productos       (default: auto-detect)
  --col-sku             Columna SKU en specs           (default: "SKU")
  --col-spec-department Columna nivel 1 en specs       (default: "Categoria")
  --col-spec-category   Columna nivel 2 en specs       (default: "Subcategoria")
  --col-spec-line       Columna nivel 3 en specs       (default: "Linea")
  --col-ref             Columna referencia en productos (default: "SKU reference code")
  --col-category-id     Columna Category ID en productos (default: "Category ID")
  --encoding            Encoding de los CSV (default: utf-8-sig)

Ejemplos:
  python3 sku_spec_matcher.py especificaciones.csv productos.csv
  python3 sku_spec_matcher.py especificaciones.csv productos.csv tree-categories.json
  python3 sku_spec_matcher.py especificaciones.csv productos.csv -o salida_20260526
  python3 sku_spec_matcher.py especificaciones.csv productos.csv --col-ref "referenceCode"
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from unicodedata import category, normalize
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers de I/O
# ---------------------------------------------------------------------------

def detect_separator(filepath: str, encoding: str) -> str:
    """Detecta si el archivo usa tabulador o coma como separador."""
    with open(filepath, encoding=encoding, errors="replace") as f:
        sample = f.read(4096)
    tabs = sample.count("\t")
    commas = sample.count(",")
    return "\t" if tabs >= commas else ","


def read_csv(filepath: str, encoding: str, separator: Optional[str]) -> Tuple[List[Dict], str]:
    """Lee un CSV y devuelve (rows, separator_used)."""
    sep = separator or detect_separator(filepath, encoding)
    rows = []
    with open(filepath, encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=sep)
        for row in reader:
            rows.append(dict(row))
    return rows, sep


def write_csv(filepath: str, rows: List[Dict], fieldnames: List[str], encoding: str) -> None:
    """Escribe un CSV con los fieldnames dados."""
    with open(filepath, "w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def normalize_match_value(value: str) -> str:
    """Normaliza texto para comparar categorías sin depender de mayúsculas o acentos."""
    decomposed = normalize("NFKD", value or "")
    without_accents = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return " ".join(without_accents.casefold().split())


def read_category_tree(filepath: str, encoding: str) -> List[Dict]:
    """Lee el árbol de categorías VTEX en formato JSON."""
    with open(filepath, encoding=encoding, errors="replace") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("El árbol de categorías debe ser una lista JSON.")
    return data


def build_category_tree_lookup(tree_rows: List[Dict]) -> Dict:
    """Construye índices para resolver Categoria/Subcategoria/Linea contra hojas VTEX."""
    paths: Dict[Tuple[str, str, str], List[Dict]] = {}
    leaf_by_id: Dict[str, Dict] = {}

    for department in tree_rows:
        for category_row in department.get("children") or []:
            for line_row in category_row.get("children") or []:
                leaf_id = str(line_row.get("id", "")).strip()
                if not leaf_id:
                    continue
                key = (
                    normalize_match_value(department.get("name", "")),
                    normalize_match_value(category_row.get("name", "")),
                    normalize_match_value(line_row.get("name", "")),
                )
                paths.setdefault(key, []).append({
                    "Department ID": str(department.get("id", "")).strip(),
                    "Department": department.get("name", ""),
                    "Tree Category ID": str(category_row.get("id", "")).strip(),
                    "Tree Category": category_row.get("name", ""),
                    "Resolved Category ID": leaf_id,
                    "Resolved Category": line_row.get("name", ""),
                })
                leaf_by_id.setdefault(leaf_id, paths[key][-1])

    return {"paths": paths, "leaf_by_id": leaf_by_id, "leaf_ids": set(leaf_by_id)}


def resolve_tree_category(
    spec_row: Dict,
    category_tree_lookup: Dict,
    col_spec_department: str,
    col_spec_category: str,
    col_spec_line: str,
) -> Tuple[Optional[Dict], str]:
    raw_path = [
        spec_row.get(col_spec_department, "").strip(),
        spec_row.get(col_spec_category, "").strip(),
        spec_row.get(col_spec_line, "").strip(),
    ]
    if not all(raw_path):
        return None, "Incomplete category path in specs"

    key = tuple(normalize_match_value(value) for value in raw_path)
    matches = category_tree_lookup["paths"].get(key, [])
    if len(matches) == 1:
        return matches[0], "Tree path resolved"
    if len(matches) > 1:
        return None, "Ambiguous category path in tree"
    return None, "Category path not found in tree"


def build_category_audit_row(
    spec_row: Dict,
    product_row: Dict,
    col_ref: str,
    col_category_id: str,
    reason: str,
    tree_match: Optional[Dict] = None,
    resolved_category_id: str = "",
) -> Dict:
    row = dict(spec_row)
    product_category_id = product_row.get(col_category_id, "").strip()
    row["Category ID"] = resolved_category_id or product_category_id
    row["Department ID"] = product_row.get("Department ID", "").strip()
    row["Department"] = product_row.get("Department", "").strip()
    row["Product Category ID"] = product_category_id
    row["Product Category"] = product_row.get("Category", "").strip()
    row["SKU reference code"] = product_row.get(col_ref, "").strip()
    row["Resolved Category ID"] = resolved_category_id
    row["Resolved Category"] = (tree_match or {}).get("Resolved Category", "")
    row["Tree Category ID"] = (tree_match or {}).get("Tree Category ID", "")
    row["Tree Category"] = (tree_match or {}).get("Tree Category", "")
    row["Tree Department ID"] = (tree_match or {}).get("Department ID", "")
    row["Tree Department"] = (tree_match or {}).get("Department", "")
    row["Resolution Reason"] = reason
    return row


def product_category_score(spec_row: Dict, product_row: Dict) -> int:
    """Puntúa qué tan bien coincide un producto duplicado con la categoría del spec."""
    spec_categoria = normalize_match_value(spec_row.get("Categoria", ""))
    spec_subcategoria = normalize_match_value(spec_row.get("Subcategoria", ""))
    spec_linea = normalize_match_value(spec_row.get("Linea", ""))
    product_department = normalize_match_value(product_row.get("Department", ""))
    product_category = normalize_match_value(product_row.get("Category", ""))

    score = 0
    if spec_categoria and spec_categoria == product_department:
        score += 4
    if spec_linea and spec_linea == product_category:
        score += 6
    if spec_subcategoria and spec_subcategoria == product_category:
        score += 3
    if spec_categoria and spec_categoria == product_category:
        score += 2
    if spec_linea and spec_linea == product_department:
        score += 1
    return score


def select_product_for_spec(spec_row: Dict, product_rows: List[Dict]) -> Tuple[Dict, bool]:
    """
    Escoge una sola fila de producto para un SKU.

    Si el SKU reference code está duplicado, usa Categoria/Subcategoria/Linea
    para preferir el producto que pertenece a la categoría correcta. Si no hay
    una señal clara, conserva el primer producto encontrado para mantener un
    resultado determinístico.
    """
    if len(product_rows) == 1:
        return product_rows[0], False

    scored = [(product_category_score(spec_row, product_row), idx, product_row)
              for idx, product_row in enumerate(product_rows)]
    best_score, _, best_product = max(scored, key=lambda item: (item[0], -item[1]))
    has_clear_category_match = best_score > 0
    return best_product, has_clear_category_match


def has_department_category_id_conflict(product_row: Dict, col_category_id: str) -> bool:
    """Detecta productos cuyo Category ID apunta al mismo nodo que Department ID."""
    department_id = product_row.get("Department ID", "").strip()
    category_id = product_row.get(col_category_id, "").strip()
    return bool(department_id and category_id and department_id == category_id)


def match_specs(
    specs_rows: List[Dict],
    products_rows: List[Dict],
    col_sku: str,
    col_ref: str,
    col_category_id: str,
    category_tree_lookup: Optional[Dict] = None,
    col_spec_department: str = "Categoria",
    col_spec_category: str = "Subcategoria",
    col_spec_line: str = "Linea",
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], Dict[str, int]]:
    """
    Cruza especificaciones contra productos por SKU reference code.
    Si hay árbol de categorías, el Category ID se resuelve desde el árbol.

    Devuelve (encontrados válidos, no_encontrados, conflictos, correcciones, estadísticas).
    """
    # Índice SKU reference code → fila(s) de producto
    products_index: Dict[str, List[Dict]] = {}
    for row in products_rows:
        ref = row.get(col_ref, "").strip()
        if ref:
            products_index.setdefault(ref, []).append(row)

    encontrados: List[Dict] = []
    no_encontrados: List[Dict] = []
    category_resolution_conflicts: List[Dict] = []
    category_id_corrections: List[Dict] = []
    stats = {
        "product_refs_duplicated": sum(1 for rows in products_index.values() if len(rows) > 1),
        "spec_rows_with_duplicate_ref": 0,
        "duplicate_ref_rows_removed": 0,
        "duplicate_ref_rows_resolved_by_category": 0,
        "department_category_id_conflicts": 0,
        "category_tree_paths_resolved": 0,
        "category_tree_paths_unresolved": 0,
        "category_id_corrected_by_tree": 0,
        "category_id_accepted_from_product_leaf": 0,
        "product_category_id_not_leaf": 0,
    }

    for spec_row in specs_rows:
        sku = spec_row.get(col_sku, "").strip()
        if sku in products_index:
            product_matches = products_index[sku]
            prod_row, resolved_by_category = select_product_for_spec(spec_row, product_matches)
            if len(product_matches) > 1:
                stats["spec_rows_with_duplicate_ref"] += 1
                stats["duplicate_ref_rows_removed"] += len(product_matches) - 1
                if resolved_by_category:
                    stats["duplicate_ref_rows_resolved_by_category"] += 1

            merged = dict(spec_row)
            product_category_id = prod_row.get(col_category_id, "").strip()

            if category_tree_lookup:
                tree_match, tree_status = resolve_tree_category(
                    spec_row,
                    category_tree_lookup,
                    col_spec_department,
                    col_spec_category,
                    col_spec_line,
                )
                if tree_match:
                    stats["category_tree_paths_resolved"] += 1
                    resolved_category_id = tree_match["Resolved Category ID"]
                    merged["Category ID"] = resolved_category_id
                    if product_category_id != resolved_category_id:
                        stats["category_id_corrected_by_tree"] += 1
                        if has_department_category_id_conflict(prod_row, col_category_id):
                            stats["department_category_id_conflicts"] += 1
                        category_id_corrections.append(build_category_audit_row(
                            spec_row,
                            prod_row,
                            col_ref,
                            col_category_id,
                            "Tree path resolved; product Category ID differed",
                            tree_match=tree_match,
                            resolved_category_id=resolved_category_id,
                        ))
                    encontrados.append(merged)
                elif product_category_id in category_tree_lookup["leaf_by_id"]:
                    fallback_tree_match = category_tree_lookup["leaf_by_id"][product_category_id]
                    stats["category_tree_paths_unresolved"] += 1
                    stats["category_id_accepted_from_product_leaf"] += 1
                    merged["Category ID"] = product_category_id
                    category_id_corrections.append(build_category_audit_row(
                        spec_row,
                        prod_row,
                        col_ref,
                        col_category_id,
                        f"{tree_status}; product Category ID matched a tree leaf",
                        tree_match=fallback_tree_match,
                        resolved_category_id=product_category_id,
                    ))
                    encontrados.append(merged)
                else:
                    stats["category_tree_paths_unresolved"] += 1
                    stats["product_category_id_not_leaf"] += 1
                    if has_department_category_id_conflict(prod_row, col_category_id):
                        stats["department_category_id_conflicts"] += 1
                    category_resolution_conflicts.append(build_category_audit_row(
                        spec_row,
                        prod_row,
                        col_ref,
                        col_category_id,
                        tree_status,
                    ))
            elif has_department_category_id_conflict(prod_row, col_category_id):
                stats["department_category_id_conflicts"] += 1
                category_resolution_conflicts.append(build_category_audit_row(
                    spec_row,
                    prod_row,
                    col_ref,
                    col_category_id,
                    "Department ID equals Category ID",
                ))
            else:
                merged["Category ID"] = product_category_id
                encontrados.append(merged)
        else:
            no_encontrados.append(dict(spec_row))

    return encontrados, no_encontrados, category_resolution_conflicts, category_id_corrections, stats


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------

def _unique_values(rows: List[Dict], col: str) -> List[str]:
    seen: Dict[str, None] = {}
    for r in rows:
        v = r.get(col, "").strip()
        if v:
            seen[v] = None
    return list(seen)


def build_unique_category_rows(encontrados: List[Dict]) -> List[Dict]:
    return [{"Category ID": value} for value in _unique_values(encontrados, "Category ID")]


def write_markdown_report(
    filepath: str,
    specs_csv: str,
    products_csv: str,
    category_tree_json: Optional[str],
    col_sku: str,
    col_ref: str,
    col_category_id: str,
    specs_total: int,
    products_total: int,
    encontrados: List[Dict],
    no_encontrados: List[Dict],
    category_resolution_conflicts: List[Dict],
    category_id_corrections: List[Dict],
    out_found: str,
    out_missing: str,
    out_category_ids: str,
    out_category_resolution_conflicts: str,
    out_category_id_corrections: str,
    match_stats: Dict[str, int],
    encoding: str,
    generated_at: datetime,
) -> None:
    unique_found   = _unique_values(encontrados,   col_sku)
    unique_missing = _unique_values(no_encontrados, col_sku)
    unique_category_ids = _unique_values(encontrados, "Category ID")
    unique_conflict_skus = _unique_values(category_resolution_conflicts, col_sku)
    total_unique   = len(unique_found) + len(unique_missing) + len(unique_conflict_skus)
    pct_found   = len(unique_found)   / max(total_unique, 1) * 100
    pct_missing = len(unique_missing) / max(total_unique, 1) * 100
    category_source = "árbol de categorías VTEX" if category_tree_json else f"columna `{col_category_id}` del producto coincidente"

    lines: List[str] = []

    lines += [
        "# Reporte SKU Spec Matcher",
        "",
        "| | |",
        "|---|---|",
        f"| **Generado** | {generated_at.strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| **Especificaciones** | `{specs_csv}` |",
        f"| **Productos VTEX** | `{products_csv}` |",
        f"| **Árbol categorías** | `{category_tree_json or 'No usado'}` |",
        f"| **Cruce** | `{col_sku}` (specs) → `{col_ref}` (productos) |",
        f"| **Category ID tomado de** | {category_source} |",
        "",
        "---",
        "",
        "## Métricas",
        "",
        "| Métrica | Filas | SKUs únicos | % |",
        "|---------|------:|------------:|--:|",
        f"| Total especificaciones | {specs_total} | — | — |",
        f"| Total productos VTEX | {products_total} | — | — |",
        f"| ✅ Encontrados válidos | {len(encontrados)} | {len(unique_found)} | {pct_found:.1f}% |",
        f"| ❌ No encontrados | {len(no_encontrados)} | {len(unique_missing)} | {pct_missing:.1f}% |",
        f"| Category IDs únicos encontrados | {len(unique_category_ids)} | — | — |",
        f"| Conflictos de resolución de categoría | {len(category_resolution_conflicts)} | {len(unique_conflict_skus)} | — |",
        f"| Category ID corregidos/aceptados con auditoría | {len(category_id_corrections)} | — | — |",
        f"| Category ID corregidos por path del árbol | {match_stats['category_id_corrected_by_tree']} | — | — |",
        f"| Fallback aceptados desde productos por ID hoja | {match_stats['category_id_accepted_from_product_leaf']} | — | — |",
        f"| Paths resueltos por árbol | {match_stats['category_tree_paths_resolved']} | — | — |",
        f"| Paths no resueltos por árbol | {match_stats['category_tree_paths_unresolved']} | — | — |",
        f"| Department ID igual a Category ID | {match_stats['department_category_id_conflicts']} | — | — |",
        f"| SKU reference code duplicados en productos | {match_stats['product_refs_duplicated']} | — | — |",
        f"| Filas extra omitidas por duplicado | {match_stats['duplicate_ref_rows_removed']} | — | — |",
        "",
        "---",
        "",
        "## Archivos generados",
        "",
        "| Archivo | Contenido |",
        "|---------|-----------|",
        f"| `{out_found}` | Especificaciones encontradas + `Category ID` válido |",
        f"| `{out_missing}` | Especificaciones con SKU no encontrado |",
        f"| `{out_category_ids}` | Category ID válidos sin repetir |",
        f"| `{out_category_resolution_conflicts}` | Matches sin Category ID hoja confiable |",
        f"| `{out_category_id_corrections}` | Category ID corregidos o aceptados por auditoría |",
        f"| `{os.path.basename(filepath)}` | Este reporte |",
        "",
        "---",
        "",
        "## SKUs no encontrados",
        "",
    ]

    if unique_missing:
        lines.append(
            f"**{len(unique_missing)} SKU(s)** sin match — ver `{out_missing}` para detalle completo."
        )
        lines.append("")
        lines.append(f"| {col_sku} |")
        lines.append("|------|")
        for sku in sorted(unique_missing):
            lines.append(f"| {sku} |")
        lines.append("")
    else:
        lines.append("> ✅ Todos los SKUs fueron encontrados en VTEX.")
        lines.append("")

    lines += [
        "---",
        "",
        "*Generado automáticamente por `sku_spec_matcher.py`*",
    ]

    with open(filepath, "w", encoding=encoding) as f:
        f.write("\n".join(lines))


def print_summary(
    specs_total: int,
    encontrados: List[Dict],
    no_encontrados: List[Dict],
    col_sku: str,
    out_found: str,
    out_missing: str,
    out_category_ids: str,
    out_category_resolution_conflicts: str,
    out_category_id_corrections: str,
    out_report: str,
    category_rows: List[Dict],
    category_resolution_conflicts: List[Dict],
    category_id_corrections: List[Dict],
    match_stats: Dict[str, int],
) -> None:
    unique_found   = _unique_values(encontrados,   col_sku)
    unique_missing = _unique_values(no_encontrados, col_sku)
    unique_conflict_skus = _unique_values(category_resolution_conflicts, col_sku)

    print("\n" + "=" * 65)
    print("  RESUMEN SKU SPEC MATCHER")
    print("=" * 65)
    print(f"  Total filas especificaciones   : {specs_total:>6}")
    print(f"  Filas encontradas válidas      : {len(encontrados):>6}  ({len(unique_found)} SKUs únicos)")
    print(f"  Filas no encontradas (SKU)     : {len(no_encontrados):>6}  ({len(unique_missing)} SKUs únicos)")
    print(f"  Conflictos categoría           : {len(category_resolution_conflicts):>6}  ({len(unique_conflict_skus)} SKUs únicos)")
    print(f"  Correcciones/auditoría cat.    : {len(category_id_corrections):>6}")
    print(f"  Corregidos por path árbol      : {match_stats['category_id_corrected_by_tree']:>6}")
    print(f"  Fallback producto ID hoja      : {match_stats['category_id_accepted_from_product_leaf']:>6}")
    print(f"  SKU refs duplicados productos  : {match_stats['product_refs_duplicated']:>6}")
    print(f"  Filas extra omitidas duplicado : {match_stats['duplicate_ref_rows_removed']:>6}")
    print(f"  Duplicados resueltos categoría : {match_stats['duplicate_ref_rows_resolved_by_category']:>6}")
    print(f"  Paths resueltos por árbol      : {match_stats['category_tree_paths_resolved']:>6}")
    print(f"  Paths no resueltos por árbol   : {match_stats['category_tree_paths_unresolved']:>6}")
    print(f"  Dept ID = Category ID          : {match_stats['department_category_id_conflicts']:>6}")
    print("-" * 65)
    print(f"  ✅  Encontrados    → {out_found}")
    print(f"  ❌  No encontrados → {out_missing}")
    print(f"  #   Category IDs   → {out_category_ids} ({len(category_rows)} únicos)")
    print(f"  ⚠️   Conflictos cat → {out_category_resolution_conflicts} ({len(category_resolution_conflicts)} filas)")
    print(f"  🔎  Auditoría cat. → {out_category_id_corrections} ({len(category_id_corrections)} filas)")
    print(f"  📄  Reporte        → {out_report}")
    print("=" * 65 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cruza especificaciones contra productos VTEX por SKU reference code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("specs_csv",    help="Archivo CSV de especificaciones")
    parser.add_argument("products_csv", help="Archivo CSV de productos creados en VTEX")
    parser.add_argument("category_tree_json", nargs="?",
                        help="Árbol JSON de categorías VTEX para resolver Categoria/Subcategoria/Linea")
    parser.add_argument("-o", "--output-prefix", default=None,
                        help='Prefijo de salida (default: "resultado_YYYYMMDD_HHMMSS")')
    parser.add_argument("--sep-specs",    default=None, help="Separador CSV specs (auto-detect)")
    parser.add_argument("--sep-products", default=None, help="Separador CSV productos (auto-detect)")
    parser.add_argument("--col-sku",         default="SKU",
                        help='Columna SKU en specs (default: "SKU")')
    parser.add_argument("--col-spec-department", default="Categoria",
                        help='Columna nivel 1 en specs (default: "Categoria")')
    parser.add_argument("--col-spec-category", default="Subcategoria",
                        help='Columna nivel 2 en specs (default: "Subcategoria")')
    parser.add_argument("--col-spec-line", default="Linea",
                        help='Columna nivel 3 en specs (default: "Linea")')
    parser.add_argument("--col-ref",         default="SKU reference code",
                        help='Columna referencia en productos (default: "SKU reference code")')
    parser.add_argument("--col-category-id", default="Category ID",
                        help='Columna Category ID en productos (default: "Category ID")')
    parser.add_argument("--encoding", default="utf-8-sig",
                        help="Encoding de los CSV (default: utf-8-sig)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # Validar archivos de entrada
    input_files = [(args.specs_csv, "especificaciones"), (args.products_csv, "productos")]
    if args.category_tree_json:
        input_files.append((args.category_tree_json, "árbol de categorías"))
    for path, label in input_files:
        if not os.path.isfile(path):
            print(f"❌  No se encontró el archivo de {label}: {path}", file=sys.stderr)
            return 1

    # Leer CSVs
    print(f"📂  Leyendo especificaciones : {args.specs_csv}")
    specs_rows, sep_s = read_csv(args.specs_csv, args.encoding, args.sep_specs)
    print(f"    Separador: {'TAB' if sep_s == chr(9) else repr(sep_s)}  |  {len(specs_rows)} filas")

    print(f"📂  Leyendo productos        : {args.products_csv}")
    products_rows, sep_p = read_csv(args.products_csv, args.encoding, args.sep_products)
    print(f"    Separador: {'TAB' if sep_p == chr(9) else repr(sep_p)}  |  {len(products_rows)} filas")

    category_tree_lookup = None
    if args.category_tree_json:
        try:
            print(f"📂  Leyendo árbol categorías : {args.category_tree_json}")
            category_tree_rows = read_category_tree(args.category_tree_json, args.encoding)
            category_tree_lookup = build_category_tree_lookup(category_tree_rows)
            ambiguous_paths = sum(
                1 for matches in category_tree_lookup["paths"].values()
                if len(matches) > 1
            )
            print(
                f"    Paths hoja: {len(category_tree_lookup['paths'])}  |  "
                f"IDs hoja: {len(category_tree_lookup['leaf_ids'])}  |  "
                f"Ambiguos: {ambiguous_paths}"
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"❌  No se pudo leer el árbol de categorías: {exc}", file=sys.stderr)
            return 1

    # Verificar columnas requeridas
    checks = [
        (specs_rows,    args.col_sku,         "especificaciones"),
        (products_rows, args.col_ref,         "productos"),
        (products_rows, args.col_category_id, "productos"),
    ]
    if category_tree_lookup:
        checks.extend([
            (specs_rows, args.col_spec_department, "especificaciones"),
            (specs_rows, args.col_spec_category, "especificaciones"),
            (specs_rows, args.col_spec_line, "especificaciones"),
        ])
    ok = True
    for rows, col, label in checks:
        if rows and col not in rows[0]:
            print(
                f"❌  Columna '{col}' no encontrada en {label}.\n"
                f"    Disponibles: {list(rows[0].keys())}",
                file=sys.stderr,
            )
            ok = False
    if not ok:
        return 1

    # Ejecutar cruce
    print(f"\n🔍  Cruzando '{args.col_sku}' (specs) con '{args.col_ref}' (productos)...")
    encontrados, no_encontrados, category_resolution_conflicts, category_id_corrections, match_stats = match_specs(
        specs_rows, products_rows,
        col_sku=args.col_sku,
        col_ref=args.col_ref,
        col_category_id=args.col_category_id,
        category_tree_lookup=category_tree_lookup,
        col_spec_department=args.col_spec_department,
        col_spec_category=args.col_spec_category,
        col_spec_line=args.col_spec_line,
    )

    # Nombres de salida
    now = datetime.now()
    prefix = args.output_prefix or f"resultado_{now.strftime('%Y%m%d_%H%M%S')}"
    out_found   = f"{prefix}_encontrados.csv"
    out_missing = f"{prefix}_no_encontrados.csv"
    out_category_ids = f"{prefix}_category_ids.csv"
    out_category_resolution_conflicts = f"{prefix}_category_resolution_conflicts.csv"
    out_category_id_corrections = f"{prefix}_category_id_corrections.csv"
    out_report  = f"{prefix}_reporte.md"

    # Fieldnames
    spec_fields  = list(specs_rows[0].keys()) if specs_rows else []
    found_fields = list(dict.fromkeys(spec_fields + ["Category ID"]))
    category_rows = build_unique_category_rows(encontrados)
    audit_fields = list(dict.fromkeys(
        found_fields + [
            "Department ID",
            "Department",
            "Product Category ID",
            "Product Category",
            "SKU reference code",
            "Resolved Category ID",
            "Resolved Category",
            "Tree Category ID",
            "Tree Category",
            "Tree Department ID",
            "Tree Department",
            "Resolution Reason",
        ]
    ))

    # Escribir salidas
    write_csv(out_found,   encontrados,    found_fields,  args.encoding)
    write_csv(out_missing, no_encontrados, spec_fields,   args.encoding)
    write_csv(out_category_ids, category_rows, ["Category ID"], args.encoding)
    write_csv(out_category_resolution_conflicts, category_resolution_conflicts, audit_fields, args.encoding)
    write_csv(out_category_id_corrections, category_id_corrections, audit_fields, args.encoding)
    write_markdown_report(
        filepath=out_report,
        specs_csv=args.specs_csv,
        products_csv=args.products_csv,
        category_tree_json=args.category_tree_json,
        col_sku=args.col_sku,
        col_ref=args.col_ref,
        col_category_id=args.col_category_id,
        specs_total=len(specs_rows),
        products_total=len(products_rows),
        encontrados=encontrados,
        no_encontrados=no_encontrados,
        category_resolution_conflicts=category_resolution_conflicts,
        category_id_corrections=category_id_corrections,
        out_found=out_found,
        out_missing=out_missing,
        out_category_ids=out_category_ids,
        out_category_resolution_conflicts=out_category_resolution_conflicts,
        out_category_id_corrections=out_category_id_corrections,
        match_stats=match_stats,
        encoding=args.encoding,
        generated_at=now,
    )

    print_summary(
        specs_total=len(specs_rows),
        encontrados=encontrados,
        no_encontrados=no_encontrados,
        col_sku=args.col_sku,
        out_found=out_found,
        out_missing=out_missing,
        out_category_ids=out_category_ids,
        out_category_resolution_conflicts=out_category_resolution_conflicts,
        out_category_id_corrections=out_category_id_corrections,
        out_report=out_report,
        category_rows=category_rows,
        category_resolution_conflicts=category_resolution_conflicts,
        category_id_corrections=category_id_corrections,
        match_stats=match_stats,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
