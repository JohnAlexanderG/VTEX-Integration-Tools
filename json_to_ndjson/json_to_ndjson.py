#!/usr/bin/env python3
"""
Conversor streaming de JSON (array) a NDJSON
-------------------------------------------
Convierte archivos JSON con un gran array de objetos en **NDJSON** (un objeto JSON por línea)
para permitir procesamiento eficiente en memoria y en streaming.

✔ No carga todo el archivo en memoria
✔ Tolerante a archivos NDJSON (idempotente): si ya es NDJSON, simplemente lo normaliza/sanea
✔ Permite seleccionar campos a conservar o descartar
✔ Reporte de progreso opcional

Uso:
    # Conversión simple (detecta formato de entrada automáticamente)
    python3 json_to_ndjson.py --input ./data/inventory.json --output ./data/inventory.ndjson

    # Mantener únicamente ciertos campos
    python3 json_to_ndjson.py -i inventory.json -o inventory.ndjson --keep _SkuId,warehouseId,quantity,unlimitedQuantity

    # Excluir ciertos campos
    python3 json_to_ndjson.py -i inventory.json -o inventory.ndjson --drop foo,bar,baz

    # Requerir llaves mínimas (si faltan, se descarta la línea y se cuenta como inválida)
    python3 json_to_ndjson.py -i inventory.json -o inventory.ndjson --require _SkuId,warehouseId,quantity

    # Excluir objetos con un warehouseId específico
    python3 json_to_ndjson.py -i inventory.json -o inventory.ndjson --exclude-warehouse 220

Notas:
- **NDJSON**: un objeto JSON por línea, sin corchetes ni comas entre elementos.
- Este formato es ideal para archivos muy grandes (ej. 300k+ registros) porque permite leer/escribir
  secuencialmente con muy bajo uso de memoria.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Dict, Any, Generator, Iterable, Optional

# ----------------------- Lectura de entrada (auto-detección) -----------------------

def _iter_json_array_stream(fp) -> Generator[Dict[str, Any], None, None]:
    """Parsea un array JSON [ {...}, {...}, ... ] en streaming, sin cargar todo en memoria.
    Implementación ligera que cuenta llaves y respeta strings con escapes.
    """
    # Saltar espacios iniciales y el primer '['
    while True:
        ch = fp.read(1)
        if not ch:
            return
        if ch.isspace():
            continue
        if ch == '[':
            break
        # Si no empieza con '[' asumimos que no es array válido
        raise ValueError("El archivo no parece ser un array JSON válido (no inicia con '[')")

    buf = []
    depth = 0
    in_str = False
    escape = False

    def flush_obj():
        nonlocal buf
        s = ''.join(buf).strip()
        if s:
            try:
                yield_obj = json.loads(s)
                if isinstance(yield_obj, dict):
                    yield yield_obj
            except Exception:
                # objeto inválido: lo ignoramos
                pass
        buf = []

    while True:
        ch = fp.read(1)
        if not ch:
            # fin de archivo
            break
        if in_str:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            buf.append(ch)
            continue
        if ch == '{':
            depth += 1
            buf.append(ch)
            continue
        if ch == '}':
            depth -= 1
            buf.append(ch)
            if depth == 0:
                # Consumimos posibles espacios y comas luego del objeto
                # pero primero emitimos el objeto
                for obj in flush_obj():
                    yield obj
            continue
        if depth == 0:
            # fuera de objetos: ignorar comas/espacios hasta ']' final
            if ch == ']':
                break
            else:
                continue
        buf.append(ch)


def _iter_ndjson(fp) -> Generator[Dict[str, Any], None, None]:
    """Itera NDJSON (un objeto JSON por línea). Líneas inválidas se omiten."""
    for line in fp:
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            # línea inválida: ignorar
            continue


def iter_input(path: str) -> Iterable[Dict[str, Any]]:
    """Detecta formato de entrada: si inicia con '[' => array JSON, en otro caso => NDJSON."""
    with open(path, 'r', encoding='utf-8') as fp:
        # Peek primer char no-espacio
        pos = fp.tell()
        first = None
        while True:
            ch = fp.read(1)
            if not ch:
                break
            if ch.isspace():
                continue
            first = ch
            break
        fp.seek(pos)
        if first == '[':
            yield from _iter_json_array_stream(fp)
        else:
            yield from _iter_ndjson(fp)

# ----------------------- Transformaciones -----------------------

def _apply_keep_drop(obj: Dict[str, Any], keep: Optional[set], drop: Optional[set]) -> Dict[str, Any]:
    if keep:
        obj = {k: v for k, v in obj.items() if k in keep}
    if drop:
        for k in list(obj.keys()):
            if k in drop:
                obj.pop(k, None)
    return obj


def _has_required(obj: Dict[str, Any], required: Optional[set]) -> bool:
    if not required:
        return True
    return all(k in obj for k in required)


def _should_exclude_by_warehouse(obj: Dict[str, Any], exclude_warehouse: Optional[str]) -> bool:
    """Retorna True si el objeto debe ser excluido por el warehouseId."""
    if not exclude_warehouse:
        return False
    warehouse_id = obj.get('warehouseId')
    # Comparar como string para manejar tanto números como strings
    return str(warehouse_id) == str(exclude_warehouse)

# ----------------------- Escritura NDJSON -----------------------

def write_ndjson(items: Iterable[Dict[str, Any]], out_path: str,
                 keep: Optional[set] = None, drop: Optional[set] = None,
                 required: Optional[set] = None, exclude_warehouse: Optional[str] = None,
                 progress: bool = True) -> None:
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    total = 0
    kept = 0
    invalid = 0
    filtered = 0
    t0 = time.time()

    with open(out_path, 'w', encoding='utf-8') as out:
        for obj in items:
            total += 1
            if not _has_required(obj, required):
                invalid += 1
                continue
            if _should_exclude_by_warehouse(obj, exclude_warehouse):
                filtered += 1
                continue
            obj = _apply_keep_drop(obj, keep, drop)
            out.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
            out.write('\n')
            kept += 1
            if progress and kept % 10000 == 0:
                dt = time.time() - t0
                rate = kept / dt if dt > 0 else 0.0
                print(f"[progreso] escritos={kept} descartados={invalid} filtrados={filtered} total_leidos={total} rate~{rate:.0f} lps")

    if progress:
        dt = time.time() - t0
        rate = kept / dt if dt > 0 else 0.0
        print(f"[fin] escritos={kept} descartados={invalid} filtrados={filtered} total_leidos={total} tiempo={dt:.1f}s rate~{rate:.0f} lps")

# ----------------------- CLI -----------------------

def _parse_set(arg: Optional[str]) -> Optional[set]:
    if not arg:
        return None
    return {s.strip() for s in arg.split(',') if s.strip()}


def main():
    p = argparse.ArgumentParser(description='Conversor streaming de JSON (array) a NDJSON')
    p.add_argument('-i', '--input', required=True, help='Ruta al archivo de entrada (JSON array o NDJSON)')
    p.add_argument('-o', '--output', required=False, help='Ruta de salida NDJSON (por defecto reemplaza extensión por .ndjson)')
    p.add_argument('--keep', help='Lista de claves a conservar, separadas por coma')
    p.add_argument('--drop', help='Lista de claves a eliminar, separadas por coma')
    p.add_argument('--require', help='Lista de claves obligatorias; si faltan, se descarta el objeto')
    p.add_argument('--exclude-warehouse', help='Valor de warehouseId a excluir del archivo de salida')
    p.add_argument('--no-progress', action='store_true', help='Desactiva la impresión de progreso')

    args = p.parse_args()
    in_path = args.input
    out_path = args.output or (os.path.splitext(in_path)[0] + '.ndjson')

    keep = _parse_set(args.keep)
    drop = _parse_set(args.drop)
    required = _parse_set(args.require)
    exclude_warehouse = args.exclude_warehouse

    items = iter_input(in_path)
    write_ndjson(items, out_path, keep=keep, drop=drop, required=required, 
                 exclude_warehouse=exclude_warehouse, progress=not args.no_progress)

    print(f"NDJSON generado: {out_path}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[WARN] Proceso interrumpido por el usuario.', file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
