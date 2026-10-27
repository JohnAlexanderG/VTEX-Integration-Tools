#!/usr/bin/env python3
"""
seller_portal_catalog_loader.py

Carga masiva de productos propios en una cuenta VTEX **Seller Portal** usando la
Catalog API - Seller Portal (beta). El Seller Portal no tiene importación por
hoja de cálculo: este script la reemplaza a partir de un XLSX/CSV.

    POST https://{cuenta}.vtexcommercestable.com.br/api/catalog-seller-portal/products
    PUT  https://{cuenta}.vtexcommercestable.com.br/api/catalog-seller-portal/products/{productId}

Documentación: https://developers.vtex.com/docs/api-reference/catalog-api-seller-portal

Flujo por corrida:
    1. Lee el archivo (una fila por SKU) y agrupa por `product_external_id`.
       Valida obligatorios, números, nombres (<=150) y consistencia de specs.
    2. Lee el árbol de categorías y las marcas de la cuenta seller y resuelve
       `category_path` / `brand` por nombre normalizado (sin acentos).
       Las categorías las define el marketplace: si no existen, la fila falla.
    3. Descarga cada URL de `image_urls` y la sube al app vtex.catalog-images
       (las imágenes deben vivir en {cuenta}.vtexassets.com). El nombre del
       archivo es determinista (sha1 de la URL), así que un 409 = ya subida.
    4. Por producto consulta `external-id={id}`: si no existe hace POST; si
       existe lo omite, o hace PUT con --update-existing (conservando SKU ids).
    5. Con los SKU ids creados aplica precio (Pricing API) y stock (Logistics).

Columnas del archivo (una fila por SKU):
    Producto : product_external_id*, product_name*, product_description, brand*,
               category_path* (ej. Hogar/Cocina/Ollas) o category_id,
               product_status (active|inactive, default active), slug
    SKU      : sku_external_id*, sku_name*, ean, manufacturer_code,
               sku_active (default true), weight*, width*, height*, length*
    Dinámicas: spec:<Nombre> (variaciones, ej. spec:Color) y attr:<Nombre>
               (atributos de producto, ej. attr:Material)
    Imágenes : image_urls* (URLs https separadas por |; al menos una por producto)
    Comercial: price, list_price, cost_price, stock (vacío = no se toca)

Credenciales requeridas en .env de la raíz del proyecto (o --env-file), de la
CUENTA SELLER (no del marketplace):
- X-VTEX-API-AppKey / X-VTEX-API-AppToken (rol con CatalogV2 Product/Brand/Category,
  Pricing y Logistics)
- VTEX_ACCOUNT_NAME
- VTEX_ENVIRONMENT (default: vtexcommercestable)

Ejecución:
    python3 seller_portal_catalog_loader.py productos.xlsx --check
    python3 seller_portal_catalog_loader.py productos.xlsx --dry-run
    python3 seller_portal_catalog_loader.py productos.xlsx
    python3 seller_portal_catalog_loader.py productos.xlsx --update-existing --create-missing-brands
    python3 seller_portal_catalog_loader.py productos.csv --env-file .env.glam --warehouse-id 1_1
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("❌ Error: falta requests. Instalar con: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ Error: falta python-dotenv. Instalar con: pip install python-dotenv")
    sys.exit(1)

PROGRESS_PREFIX = "__VTEX_JOB_PROGRESS__"
TOOL_ID = "step_79"
CATALOG_PATH = "/api/catalog-seller-portal"
MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_NAME_LENGTH = 150
BRAND_PAGE_SIZE = 50

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

PRODUCT_COLUMNS = ["product_external_id", "product_name", "brand"]
SKU_REQUIRED_COLUMNS = ["sku_external_id", "sku_name", "weight", "width", "height", "length"]


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

def emit_progress(phase: str, phase_label: str, percent: float, message: str = "") -> None:
    """Progreso en JSONL para la webapp (mismo prefijo que el paso 67)."""
    payload = {
        "tool_id": TOOL_ID,
        "phase": phase,
        "phase_label": phase_label,
        "percent": round(percent, 1),
        "message": message,
    }
    print(f"{PROGRESS_PREFIX}{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}", flush=True)


def normalize(text: Any) -> str:
    """Minúsculas, sin acentos y con espacios colapsados, para comparar nombres."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    without_accents = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def parse_number(value: str, field: str) -> Optional[float]:
    """Número opcional; acepta coma decimal. Vacío → None."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        raise ValueError(f"{field} no es numérico: '{raw}'")


def parse_bool(value: str, default: bool = True) -> bool:
    raw = normalize(value)
    if not raw:
        return default
    if raw in ("true", "1", "si", "yes", "activo", "active", "verdadero"):
        return True
    if raw in ("false", "0", "no", "inactivo", "inactive", "falso"):
        return False
    raise ValueError(f"valor booleano inválido: '{value}'")


def split_urls(value: str) -> List[str]:
    return [u.strip() for u in (value or "").split("|") if u.strip()]


def cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(path: str, sheet: Optional[str]) -> List[Dict[str, str]]:
    """Lee XLSX o CSV como lista de dicts con valores string."""
    if path.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            print("❌ Error: falta openpyxl. Instalar con: pip install openpyxl")
            sys.exit(1)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows_iter = ws.iter_rows(values_only=True)
        headers = [cell_to_str(h) for h in next(rows_iter, [])]
        rows = []
        for values in rows_iter:
            row = {headers[i]: cell_to_str(v) for i, v in enumerate(values) if i < len(headers) and headers[i]}
            if any(row.values()):
                rows.append(row)
        wb.close()
        return rows

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        return [
            {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            for row in reader
            if any((v or "").strip() for v in row.values())
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Agrupación y validación local
# ─────────────────────────────────────────────────────────────────────────────

def build_products(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Agrupa filas por producto y valida. Devuelve (productos válidos, errores por fila)."""
    errors: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Tuple[int, Dict[str, str]]]] = {}
    duplicate_problems: Dict[str, List[str]] = {}
    seen_sku_ids: Dict[str, int] = {}

    for index, row in enumerate(rows, start=2):  # fila 1 = encabezados
        product_id = row.get("product_external_id", "")
        if not product_id:
            errors.append({"row_number": index, "row": row, "error": "product_external_id vacío"})
            continue
        sku_id = row.get("sku_external_id", "")
        if sku_id and sku_id in seen_sku_ids:
            # Invalida el producto completo: crearlo sin ese SKU lo dejaría incompleto
            duplicate_problems.setdefault(product_id, []).append(
                f"fila {index}: sku_external_id '{sku_id}' repetido (fila {seen_sku_ids[sku_id]})")
        elif sku_id:
            seen_sku_ids[sku_id] = index
        grouped.setdefault(product_id, []).append((index, row))

    products = []
    for external_id, product_rows in grouped.items():
        product, product_errors = _build_product(external_id, product_rows)
        product_errors = duplicate_problems.get(external_id, []) + product_errors
        if product_errors:
            for row_number, row in product_rows:
                errors.append({"row_number": row_number, "row": row, "error": "; ".join(product_errors)})
        else:
            products.append(product)
    return products, errors


def _first(product_rows: List[Tuple[int, Dict[str, str]]], column: str) -> str:
    for _, row in product_rows:
        if row.get(column):
            return row[column]
    return ""


def _build_product(external_id: str, product_rows: List[Tuple[int, Dict[str, str]]]) -> Tuple[Dict[str, Any], List[str]]:
    problems: List[str] = []
    headers = list(dict.fromkeys(k for _, row in product_rows for k in row.keys()))
    spec_columns = [h for h in headers if h.lower().startswith("spec:") and h[5:].strip()]
    attr_columns = [h for h in headers if h.lower().startswith("attr:") and h[5:].strip()]

    for column in PRODUCT_COLUMNS:
        if not _first(product_rows, column):
            problems.append(f"falta {column}")
    if not _first(product_rows, "category_path") and not _first(product_rows, "category_id"):
        problems.append("falta category_path o category_id")

    name = _first(product_rows, "product_name")
    if len(name) > MAX_NAME_LENGTH:
        problems.append(f"product_name supera {MAX_NAME_LENGTH} caracteres")

    status = normalize(_first(product_rows, "product_status")) or "active"
    if status not in ("active", "inactive"):
        problems.append(f"product_status inválido: '{status}' (usar active o inactive)")

    skus = []
    for row_number, row in product_rows:
        sku_problems = [f"fila {row_number}: falta {c}" for c in SKU_REQUIRED_COLUMNS if not row.get(c)]
        if len(row.get("sku_name", "")) > MAX_NAME_LENGTH:
            sku_problems.append(f"fila {row_number}: sku_name supera {MAX_NAME_LENGTH} caracteres")
        try:
            weight = parse_number(row.get("weight", ""), "weight")
            dims = {d: parse_number(row.get(d, ""), d) for d in ("width", "height", "length")}
            price = parse_number(row.get("price", ""), "price")
            list_price = parse_number(row.get("list_price", ""), "list_price")
            cost_price = parse_number(row.get("cost_price", ""), "cost_price")
            stock = parse_number(row.get("stock", ""), "stock")
            is_active = parse_bool(row.get("sku_active", ""), default=True)
        except ValueError as e:
            sku_problems.append(f"fila {row_number}: {e}")
            weight, dims, price, list_price, cost_price, stock, is_active = None, {}, None, None, None, None, True
        if stock is not None and (stock < 0 or not float(stock).is_integer()):
            sku_problems.append(f"fila {row_number}: stock debe ser entero >= 0")
        if (list_price is not None or cost_price is not None) and price is None:
            sku_problems.append(f"fila {row_number}: list_price/cost_price requieren price")

        urls = split_urls(row.get("image_urls", ""))
        bad_urls = [u for u in urls if urlparse(u).scheme != "https"]
        if bad_urls:
            sku_problems.append(f"fila {row_number}: URLs de imagen deben ser https ({bad_urls[0]})")

        problems.extend(sku_problems)
        skus.append({
            "row_number": row_number,
            "row": row,
            "external_id": row.get("sku_external_id", ""),
            "name": row.get("sku_name", ""),
            "ean": row.get("ean", ""),
            "manufacturer_code": row.get("manufacturer_code", ""),
            "is_active": is_active,
            "weight": int(round(weight)) if weight is not None else None,
            "dimensions": dims,
            "specs": {c[5:].strip(): row[c] for c in spec_columns if row.get(c)},
            "image_urls": urls,
            "price": price,
            "list_price": list_price,
            "cost_price": cost_price,
            "stock": int(stock) if stock is not None else None,
        })

    # Specs: en productos con varios SKUs cada SKU debe definir todas las
    # variaciones y la combinación no se puede repetir.
    spec_names: List[str] = []
    for sku in skus:
        for spec_name in sku["specs"]:
            if spec_name not in spec_names:
                spec_names.append(spec_name)
    if len(skus) > 1:
        if not spec_names:
            problems.append("producto con varios SKUs sin columnas spec:<Nombre> que los diferencien")
        combos = set()
        for sku in skus:
            missing = [s for s in spec_names if s not in sku["specs"]]
            if missing:
                problems.append(f"fila {sku['row_number']}: falta valor de spec {', '.join(missing)}")
            combo = tuple(sku["specs"].get(s, "") for s in spec_names)
            if combo in combos:
                problems.append(f"fila {sku['row_number']}: combinación de specs repetida {combo}")
            combos.add(combo)

    image_urls: List[str] = []
    for sku in skus:
        for url in sku["image_urls"]:
            if url not in image_urls:
                image_urls.append(url)
    if not image_urls:
        problems.append("el producto no tiene ninguna URL en image_urls")

    attributes = []
    for column in attr_columns:
        value = _first(product_rows, column)
        if value:
            attributes.append({"name": column[5:].strip(), "value": value})

    product = {
        "external_id": external_id,
        "name": name,
        "description": _first(product_rows, "product_description"),
        "brand": _first(product_rows, "brand"),
        "category_path": _first(product_rows, "category_path"),
        "category_id": _first(product_rows, "category_id"),
        "status": status,
        "slug": _first(product_rows, "slug"),
        "attributes": attributes,
        "spec_names": spec_names,
        "image_urls": image_urls,
        "skus": skus,
    }
    return product, problems


# ─────────────────────────────────────────────────────────────────────────────
# Cliente VTEX (cuenta seller)
# ─────────────────────────────────────────────────────────────────────────────

class SellerPortalClient:
    def __init__(self, account: str, environment: str, app_key: str, app_token: str,
                 timeout: float, delay: float):
        self.account = account
        self.app_key = app_key
        self.app_token = app_token
        self.timeout = timeout
        self.delay = delay
        self.base_url = f"https://{account}.{environment}.com.br"
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-VTEX-API-AppKey": app_key,
            "X-VTEX-API-AppToken": app_token,
        })
        self.local_token: Optional[str] = None

    def request(self, method: str, url: str, session: Optional[requests.Session] = None,
                **kwargs) -> Tuple[Optional[requests.Response], str]:
        """Request con reintentos (429/5xx/red) y backoff exponencial.
        Devuelve (respuesta, error_de_red)."""
        http = session or self.session
        last_error = ""
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = http.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as e:
                last_error = f"error de red: {e}"
                resp = None
            if resp is not None and resp.status_code not in RETRY_STATUS:
                return resp, ""
            if attempt < MAX_RETRIES:
                wait = max(self.delay, 1.0) * (2 ** attempt)
                reason = f"HTTP {resp.status_code}" if resp is not None else last_error
                print(f"   ⏳ {reason} en {method} {url}; reintento {attempt + 1}/{MAX_RETRIES} en {wait:.1f}s")
                time.sleep(wait)
        return resp, last_error

    def catalog_url(self, path: str) -> str:
        return f"{self.base_url}{CATALOG_PATH}{path}"

    # Catálogo ────────────────────────────────────────────────────────────────

    def get_category_tree(self) -> Tuple[Optional[requests.Response], str]:
        return self.request("GET", self.catalog_url("/category-tree"))

    def list_brands(self) -> List[Dict[str, Any]]:
        brands: List[Dict[str, Any]] = []
        start = 1
        while True:
            resp, err = self.request("GET", self.catalog_url("/brands"),
                                     params={"from": start, "to": start + BRAND_PAGE_SIZE - 1})
            if resp is None or resp.status_code != 200:
                raise RuntimeError(f"No se pudo listar marcas: {err or _describe(resp)}")
            body = resp.json()
            page = body.get("data") or []
            brands.extend(page)
            total = (body.get("_metadata") or {}).get("total", 0)
            if not page or len(brands) >= total:
                return brands
            start += BRAND_PAGE_SIZE

    def create_brand(self, name: str) -> Tuple[Optional[str], str]:
        resp, err = self.request("POST", self.catalog_url("/brands"), json={"name": name, "isActive": True})
        time.sleep(self.delay)
        if resp is not None and resp.status_code in (200, 201):
            return str(resp.json().get("id")), ""
        return None, err or _describe(resp)

    def get_product_by_external_id(self, external_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
        resp, err = self.request("GET", self.catalog_url(f"/products/external-id={external_id}"))
        if resp is None:
            return None, err
        if resp.status_code == 404:
            return None, ""
        if resp.status_code == 200:
            return resp.json(), ""
        return None, _describe(resp)

    def create_product(self, body: Dict[str, Any]) -> Tuple[Optional[requests.Response], str]:
        resp, err = self.request("POST", self.catalog_url("/products"), json=body)
        time.sleep(self.delay)
        return resp, err

    def update_product(self, product_id: str, body: Dict[str, Any]) -> Tuple[Optional[requests.Response], str]:
        resp, err = self.request("PUT", self.catalog_url(f"/products/{product_id}"), json=body)
        time.sleep(self.delay)
        return resp, err

    # Imágenes (vtex.catalog-images) ──────────────────────────────────────────

    def login_local_token(self) -> str:
        url = f"https://api.vtexcommercestable.com.br/api/vtexid/apptoken/login?an={self.account}"
        resp, err = self.request("POST", url, session=requests.Session(),
                                 json={"appkey": self.app_key, "apptoken": self.app_token},
                                 headers={"Content-Type": "application/json"})
        if resp is None or resp.status_code != 200 or not resp.json().get("token"):
            raise RuntimeError(f"No se pudo obtener token local (apptoken/login): {err or _describe(resp)}")
        self.local_token = resp.json()["token"]
        return self.local_token

    def upload_image(self, file_name: str, content: bytes, content_type: str) -> Tuple[Optional[str], str]:
        """Sube una imagen; un 409 (ya existe) se toma como éxito y reutiliza su URL."""
        if not self.local_token:
            self.login_local_token()
        url = f"https://app.io.vtex.com/vtex.catalog-images/v0/{self.account}/master/images/save/{file_name}"
        for attempt in range(2):
            resp, err = self.request("POST", url, session=requests.Session(),
                                     headers={"VtexIdclientAutCookie": self.local_token},
                                     files={"file": (file_name, content, content_type)})
            if resp is not None and resp.status_code == 401 and attempt == 0:
                self.login_local_token()  # token vencido
                continue
            break
        time.sleep(self.delay)
        if resp is None:
            return None, err
        if resp.status_code in (200, 201, 409):
            full_url = _extract_asset_url(resp)
            if full_url:
                return full_url, ""
            return None, f"HTTP {resp.status_code} sin URL en la respuesta: {resp.text[:200]}"
        return None, _describe(resp)

    # Precio y stock ──────────────────────────────────────────────────────────

    def put_price(self, sku_id: str, body: Dict[str, Any]) -> Tuple[bool, str]:
        url = f"https://api.vtex.com/{self.account}/pricing/prices/{sku_id}"
        resp, err = self.request("PUT", url, json=body)
        time.sleep(self.delay)
        if resp is not None and resp.status_code in (200, 201, 204):
            return True, ""
        return False, err or _describe(resp)

    def list_warehouses(self) -> Tuple[Optional[requests.Response], str]:
        return self.request("GET", f"{self.base_url}/api/logistics/pvt/configuration/warehouses")

    def put_inventory(self, sku_id: str, warehouse_id: str, quantity: int) -> Tuple[bool, str]:
        url = f"{self.base_url}/api/logistics/pvt/inventory/skus/{sku_id}/warehouses/{warehouse_id}"
        resp, err = self.request("PUT", url, json={"quantity": quantity, "unlimitedQuantity": False})
        time.sleep(self.delay)
        if resp is not None and resp.status_code in (200, 201, 204):
            return True, ""
        return False, err or _describe(resp)


def _describe(resp: Optional[requests.Response]) -> str:
    if resp is None:
        return "sin respuesta"
    return f"HTTP {resp.status_code}: {resp.text[:300]}"


def _extract_asset_url(resp: requests.Response) -> Optional[str]:
    try:
        body = resp.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for key in ("fullUrl", "url"):
            if isinstance(body.get(key), str) and body[key].startswith("https://"):
                return body[key]
    if isinstance(body, str) and body.startswith("https://"):
        return body
    match = re.search(r"https://[^\s\"']+\.vtexassets\.com/[^\s\"']+", resp.text or "")
    return match.group(0) if match else None


# ─────────────────────────────────────────────────────────────────────────────
# Carga
# ─────────────────────────────────────────────────────────────────────────────

class CatalogLoader:
    def __init__(self, client: SellerPortalClient, args: argparse.Namespace):
        self.client = client
        self.args = args
        self.categories_by_path: Dict[str, str] = {}
        self.category_ids: set = set()
        self.brands_by_name: Dict[str, str] = {}
        self.image_cache: Dict[str, Tuple[Optional[str], str]] = {}
        self.image_log: List[Dict[str, str]] = []
        self.warehouse_id: Optional[str] = args.warehouse_id or None
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.payloads: List[Dict[str, Any]] = []

    # Lecturas de referencia ──────────────────────────────────────────────────

    def load_lookups(self) -> None:
        resp, err = self.client.get_category_tree()
        if resp is None or resp.status_code != 200:
            raise RuntimeError(f"No se pudo leer el árbol de categorías: {err or _describe(resp)}")
        for root in resp.json().get("roots") or []:
            self._index_category(root, [])
        print(f"📂 Categorías disponibles en la cuenta: {len(self.category_ids)}")

        for brand in self.client.list_brands():
            self.brands_by_name[normalize(brand.get("name"))] = str(brand.get("id"))
        print(f"🏷️  Marcas disponibles en la cuenta: {len(self.brands_by_name)}")

    def _index_category(self, node: Dict[str, Any], parents: List[str]) -> None:
        value = node.get("value") or {}
        path = parents + [normalize(value.get("name"))]
        category_id = str(value.get("id"))
        self.categories_by_path["/".join(path)] = category_id
        self.category_ids.add(category_id)
        for child in node.get("children") or []:
            self._index_category(child, path)

    def resolve_category(self, product: Dict[str, Any]) -> Tuple[Optional[str], str]:
        if product["category_id"]:
            if product["category_id"] in self.category_ids:
                return product["category_id"], ""
            return None, f"category_id {product['category_id']} no existe en el árbol de la cuenta"
        parts = [normalize(p) for p in re.split(r"[/>]", product["category_path"]) if p.strip()]
        category_id = self.categories_by_path.get("/".join(parts))
        if category_id:
            return category_id, ""
        return None, f"categoría '{product['category_path']}' no existe (las define el marketplace)"

    def resolve_brand(self, product: Dict[str, Any]) -> Tuple[Optional[str], str]:
        key = normalize(product["brand"])
        if key in self.brands_by_name:
            return self.brands_by_name[key], ""
        if not self.args.create_missing_brands:
            return None, f"marca '{product['brand']}' no existe (usar --create-missing-brands para crearla)"
        if self.args.dry_run:
            return f"<nueva marca: {product['brand']}>", ""
        brand_id, err = self.client.create_brand(product["brand"])
        if brand_id:
            print(f"   🏷️  Marca creada: {product['brand']} (id {brand_id})")
            self.brands_by_name[key] = brand_id
            return brand_id, ""
        return None, f"no se pudo crear la marca '{product['brand']}': {err}"

    # Imágenes ────────────────────────────────────────────────────────────────

    def resolve_image(self, source_url: str) -> Tuple[Optional[str], str]:
        """URL externa → (URL en vtexassets, error). Cachea por URL dentro de la corrida."""
        if source_url in self.image_cache:
            return self.image_cache[source_url]
        result = self._transfer_image(source_url)
        self.image_cache[source_url] = result
        self.image_log.append({"source_url": source_url, "vtex_url": result[0] or "", "error": result[1]})
        return result

    def _transfer_image(self, source_url: str) -> Tuple[Optional[str], str]:
        digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:16]
        if self.args.dry_run:
            # URL ilustrativa: en real la extensión sale del Content-Type descargado
            return f"https://{self.client.account}.vtexassets.com/assets/vtex.catalog-images/products/{digest}", ""
        try:
            resp = requests.get(source_url, timeout=self.args.timeout, stream=True)
        except requests.RequestException as e:
            return None, f"no se pudo descargar {source_url}: {e}"
        if resp.status_code != 200:
            return None, f"descarga {source_url}: HTTP {resp.status_code}"
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        extension = IMAGE_EXTENSIONS.get(content_type)
        if not extension:
            return None, f"{source_url} no es una imagen soportada (Content-Type '{content_type}')"
        content = b""
        for chunk in resp.iter_content(64 * 1024):
            content += chunk
            if len(content) > MAX_IMAGE_BYTES:
                return None, f"{source_url} supera {MAX_IMAGE_BYTES // (1024 * 1024)} MB"
        return self.client.upload_image(f"{digest}{extension}", content, content_type)

    # Producto ────────────────────────────────────────────────────────────────

    def build_body(self, product: Dict[str, Any], brand_id: str, category_id: str,
                   image_urls: Dict[str, str]) -> Dict[str, Any]:
        images = []
        for source_url in product["image_urls"]:
            vtex_url = image_urls[source_url]
            images.append({"id": _image_id(vtex_url), "url": vtex_url, "alt": product["name"]})

        product_specs = []
        for spec_name in product["spec_names"]:
            values: List[str] = []
            for sku in product["skus"]:
                value = sku["specs"].get(spec_name)
                if value and value not in values:
                    values.append(value)
            product_specs.append({"name": spec_name, "values": values})

        skus = []
        for sku in product["skus"]:
            # El SKU referencia sus imágenes por URL completa de vtexassets, no por id
            sku_images = [image_urls[u] for u in sku["image_urls"]] or [i["url"] for i in images]
            body_sku: Dict[str, Any] = {
                "name": sku["name"],
                "externalId": sku["external_id"],
                "isActive": sku["is_active"],
                "weight": sku["weight"],
                "dimensions": sku["dimensions"],
                "specs": [{"name": n, "value": v} for n, v in sku["specs"].items()],
                "images": sku_images,
            }
            if sku["ean"]:
                body_sku["ean"] = sku["ean"]
            if sku["manufacturer_code"]:
                body_sku["manufacturerCode"] = sku["manufacturer_code"]
            skus.append(body_sku)

        body: Dict[str, Any] = {
            "externalId": product["external_id"],
            "status": product["status"],
            "name": product["name"],
            "brandId": brand_id,
            "categoryIds": [category_id],
            "specs": product_specs,
            "attributes": product["attributes"],
            "slug": product["slug"] or f"/{slugify(product['name'])}",
            "images": images,
            "skus": skus,
            "origin": self.client.account,
        }
        if product["description"]:
            body["description"] = product["description"]
        if not body["slug"].startswith("/"):
            body["slug"] = f"/{body['slug']}"
        return body

    def merge_existing(self, body: Dict[str, Any], existing: Dict[str, Any], keep_slug: bool) -> Dict[str, Any]:
        """Para PUT: conserva ids, origin y SKUs que no vienen en el archivo."""
        body = dict(body)
        body["id"] = existing.get("id")
        body["origin"] = existing.get("origin") or body["origin"]
        if keep_slug and existing.get("slug"):
            body["slug"] = existing["slug"]
        existing_skus = {str(s.get("externalId")): s for s in existing.get("skus") or [] if s.get("externalId")}
        sent = set()
        for sku in body["skus"]:
            match = existing_skus.get(sku["externalId"])
            if match:
                sku["id"] = match.get("id")
                sent.add(sku["externalId"])
        body["skus"] += [s for ext_id, s in existing_skus.items() if ext_id not in sent]
        return body

    def process_product(self, product: Dict[str, Any]) -> None:
        sku_status = {sku["external_id"]: _empty_result(product, sku) for sku in product["skus"]}

        def fail(message: str, stage: str = "product_status") -> None:
            print(f"   ❌ {message}")
            for sku in product["skus"]:
                sku_status[sku["external_id"]]["product_status"] = "failed"
                sku_status[sku["external_id"]][stage] = "failed"
                sku_status[sku["external_id"]]["message"] = message
                self.errors.append({"row_number": sku["row_number"], "row": sku["row"], "error": message})
            self.results.extend(sku_status.values())

        category_id, err = self.resolve_category(product)
        if not category_id:
            return fail(err)
        brand_id, err = self.resolve_brand(product)
        if not brand_id:
            return fail(err)

        existing, err = self.client.get_product_by_external_id(product["external_id"])
        if err:
            return fail(f"no se pudo consultar si el producto existe: {err}")
        if existing and not self.args.update_existing:
            print(f"   ⏭️  Ya existe (productId {existing.get('id')}); se omite. Usa --update-existing para actualizar.")
            for result in sku_status.values():
                result["product_id"] = existing.get("id", "")
                result["product_status"] = "skipped_exists"
                result["sku_id"] = _sku_id_map(existing).get(result["sku_external_id"], "")
            self.results.extend(sku_status.values())
            return

        image_urls: Dict[str, str] = {}
        for source_url in product["image_urls"]:
            vtex_url, err = self.resolve_image(source_url)
            if not vtex_url:
                return fail(f"imagen: {err}", stage="images_status")
            image_urls[source_url] = vtex_url
        for result in sku_status.values():
            result["images_status"] = "dry_run" if self.args.dry_run else "ok"

        body = self.build_body(product, brand_id, category_id, image_urls)
        if existing:
            body = self.merge_existing(body, existing, keep_slug=not product["slug"])
        action = "update" if existing else "create"

        if self.args.dry_run:
            self.payloads.append({"action": action, "productId": existing.get("id") if existing else None, "body": body})
            print(f"   🧪 DRY-RUN: {'PUT' if existing else 'POST'} producto con {len(product['skus'])} SKU(s)")
            for result in sku_status.values():
                result["product_status"] = f"dry_run_{action}"
                result["product_id"] = existing.get("id", "") if existing else ""
            self.results.extend(sku_status.values())
            return

        if existing:
            resp, err = self.client.update_product(str(existing.get("id")), body)
        else:
            resp, err = self.client.create_product(body)
        if resp is None or resp.status_code not in (200, 201, 204):
            return fail(f"{'PUT' if existing else 'POST'} producto: {err or _describe(resp)}")

        saved = _json_or_none(resp)
        if not saved or not saved.get("skus"):
            saved, _ = self.client.get_product_by_external_id(product["external_id"])
        saved = saved or {}
        product_id = saved.get("id") or (existing or {}).get("id", "")
        sku_ids = _sku_id_map(saved)
        print(f"   ✅ Producto {'actualizado' if existing else 'creado'} (productId {product_id})")

        for sku in product["skus"]:
            result = sku_status[sku["external_id"]]
            result["product_id"] = product_id
            result["product_status"] = "updated" if existing else "created"
            result["sku_id"] = sku_ids.get(sku["external_id"], "")
            if not result["sku_id"]:
                result["message"] = "no se encontró el skuId en la respuesta; precio/stock no aplicados"
                continue
            self.apply_commercial(sku, result)
        self.results.extend(sku_status.values())

    def apply_commercial(self, sku: Dict[str, Any], result: Dict[str, Any]) -> None:
        if sku["price"] is not None and not self.args.skip_price:
            body = {"basePrice": sku["price"]}
            if sku["list_price"] is not None:
                body["listPrice"] = sku["list_price"]
            if sku["cost_price"] is not None:
                body["costPrice"] = sku["cost_price"]
            ok, err = self.client.put_price(result["sku_id"], body)
            result["price_status"] = "ok" if ok else "failed"
            if not ok:
                self._record_partial_error(sku, result, f"precio: {err}")

        if sku["stock"] is not None and not self.args.skip_stock:
            warehouse_id, err = self.get_warehouse()
            if not warehouse_id:
                result["stock_status"] = "failed"
                self._record_partial_error(sku, result, f"stock: {err}")
                return
            ok, err = self.client.put_inventory(result["sku_id"], warehouse_id, sku["stock"])
            result["stock_status"] = "ok" if ok else "failed"
            if not ok:
                self._record_partial_error(sku, result, f"stock: {err}")

    def _record_partial_error(self, sku: Dict[str, Any], result: Dict[str, Any], message: str) -> None:
        print(f"   ⚠️  SKU {sku['external_id']}: {message}")
        result["message"] = "; ".join(filter(None, [result["message"], message]))
        self.errors.append({"row_number": sku["row_number"], "row": sku["row"],
                            "error": f"{message} (producto creado, skuId {result['sku_id']})"})

    def get_warehouse(self) -> Tuple[Optional[str], str]:
        if self.warehouse_id:
            return self.warehouse_id, ""
        resp, err = self.client.list_warehouses()
        if resp is None or resp.status_code != 200:
            return None, f"no se pudo listar warehouses (usar --warehouse-id): {err or _describe(resp)}"
        active = [w for w in resp.json() or [] if w.get("isActive", True)]
        if not active:
            return None, "la cuenta no tiene warehouses activos (usar --warehouse-id)"
        self.warehouse_id = str(active[0].get("id"))
        print(f"🏬 Warehouse para stock: {self.warehouse_id} ({active[0].get('name', '')})")
        return self.warehouse_id, ""


def _empty_result(product: Dict[str, Any], sku: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "row_number": sku["row_number"],
        "product_external_id": product["external_id"],
        "product_id": "",
        "sku_external_id": sku["external_id"],
        "sku_id": "",
        "product_status": "pending",
        "images_status": "",
        "price_status": "" if sku["price"] is not None else "not_requested",
        "stock_status": "" if sku["stock"] is not None else "not_requested",
        "message": "",
    }


def _image_id(vtex_url: str) -> str:
    return vtex_url.rstrip("/").rsplit("/", 1)[-1]


def _sku_id_map(product: Optional[Dict[str, Any]]) -> Dict[str, str]:
    return {str(s.get("externalId")): str(s.get("id")) for s in (product or {}).get("skus") or []
            if s.get("externalId") and s.get("id")}


def _json_or_none(resp: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        body = resp.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


# ─────────────────────────────────────────────────────────────────────────────
# Verificación de permisos (--check)
# ─────────────────────────────────────────────────────────────────────────────

def run_check(client: SellerPortalClient) -> bool:
    """Prueba lecturas de cada API para detectar llaves sin permisos (403)."""
    print("🔎 Verificando credenciales y permisos de la cuenta seller...\n")
    checks = [
        ("Catálogo: árbol de categorías (Category Read)", "GET", client.catalog_url("/category-tree"), (200,)),
        ("Catálogo: marcas (Brand Read)", "GET", client.catalog_url("/brands?from=1&to=1"), (200,)),
        ("Catálogo: SKUs (Product Read)", "GET", client.catalog_url("/skus/_search?from=1&to=1"), (200,)),
        ("Pricing: lectura de precios", "GET", f"https://api.vtex.com/{client.account}/pricing/prices/0", (200, 404)),
        ("Logistics: warehouses", "GET", f"{client.base_url}/api/logistics/pvt/configuration/warehouses", (200,)),
    ]
    all_ok = True
    for label, method, url, ok_codes in checks:
        resp, err = client.request(method, url)
        ok = resp is not None and resp.status_code in ok_codes
        all_ok &= ok
        detail = f"HTTP {resp.status_code}" if resp is not None else err
        print(f"   {'✅' if ok else '❌'} {label}: {detail}")
    try:
        client.login_local_token()
        print("   ✅ Imágenes: token local (apptoken/login)")
    except RuntimeError as e:
        all_ok = False
        print(f"   ❌ Imágenes: {e}")
    print("\nℹ️  Los permisos de escritura (Product/Brand Write, precios, inventario) no se pueden")
    print("   probar sin escribir; valida con una corrida real de 1 producto en estado inactive.")
    print(f"\n{'✅ Credenciales OK' if all_ok else '❌ Faltan permisos: revisa el rol de la API key en License Manager'}")
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# Salidas
# ─────────────────────────────────────────────────────────────────────────────

RESULT_FIELDS = ["row_number", "product_external_id", "product_id", "sku_external_id", "sku_id",
                 "product_status", "images_status", "price_status", "stock_status", "message"]


def write_outputs(loader: CatalogLoader, output_dir: str, input_columns: List[str],
                  invalid_errors: List[Dict[str, Any]], products_count: int, elapsed: float) -> None:
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    invalid_results = [{
        **{field: "" for field in RESULT_FIELDS},
        "row_number": e["row_number"],
        "product_external_id": e["row"].get("product_external_id", ""),
        "sku_external_id": e["row"].get("sku_external_id", ""),
        "product_status": "invalid",
        "message": e["error"],
    } for e in invalid_errors]
    results = sorted(loader.results + invalid_results, key=lambda r: r["row_number"])
    errors = sorted(invalid_errors + loader.errors, key=lambda e: e["row_number"])

    results_path = os.path.join(output_dir, f"seller_portal_results_{stamp}.csv")
    with open(results_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"📄 Resultados: {results_path}")

    if errors:
        errors_path = os.path.join(output_dir, f"seller_portal_errors_{stamp}.csv")
        with open(errors_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["row_number", "error"] + input_columns, extrasaction="ignore")
            writer.writeheader()
            for e in errors:
                writer.writerow({"row_number": e["row_number"], "error": e["error"], **e["row"]})
        print(f"📄 Errores: {errors_path}")

    if loader.image_log and not loader.args.dry_run:
        images_path = os.path.join(output_dir, f"seller_portal_image_map_{stamp}.csv")
        with open(images_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["source_url", "vtex_url", "error"])
            writer.writeheader()
            writer.writerows(loader.image_log)
        print(f"📄 Mapa de imágenes: {images_path}")

    if loader.payloads:
        payloads_path = os.path.join(output_dir, f"seller_portal_payloads_{stamp}.json")
        with open(payloads_path, "w", encoding="utf-8") as f:
            json.dump(loader.payloads, f, ensure_ascii=False, indent=4)
        print(f"📄 Payloads (dry-run): {payloads_path}")

    def count(field: str, value: str) -> int:
        return sum(1 for r in results if r[field] == value)

    report_path = os.path.join(output_dir, f"seller_portal_report_{stamp}.md")
    mode = "DRY-RUN (sin escrituras)" if loader.args.dry_run else "Real"
    lines = [
        "# Carga de catálogo Seller Portal",
        "",
        f"- **Cuenta seller:** {loader.client.account}",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Modo:** {mode}",
        f"- **Duración:** {elapsed:.1f}s",
        "",
        "## Resumen",
        "",
        "| Concepto | Cantidad |",
        "|---|---|",
        f"| Productos válidos procesados | {products_count} |",
        f"| SKUs creados | {count('product_status', 'created')} |",
        f"| SKUs actualizados | {count('product_status', 'updated')} |",
        f"| SKUs omitidos (producto ya existía) | {count('product_status', 'skipped_exists')} |",
        f"| SKUs simulados (dry-run) | {sum(1 for r in results if r['product_status'].startswith('dry_run'))} |",
        f"| SKUs con error de producto o imagen | {sum(1 for r in results if 'failed' in (r['product_status'], r['images_status']))} |",
        f"| Filas inválidas (validación local) | {len(invalid_errors)} |",
        f"| Precios aplicados / fallidos | {count('price_status', 'ok')} / {count('price_status', 'failed')} |",
        f"| Stock aplicado / fallido | {count('stock_status', 'ok')} / {count('stock_status', 'failed')} |",
        f"| Imágenes transferidas | {sum(1 for i in loader.image_log if i['vtex_url'])} |",
        "",
    ]
    if errors:
        lines += ["## Errores (primeros 50)", "", "| Fila | Error |", "|---|---|"]
        lines += [f"| {e['row_number']} | {str(e['error']).replace('|', '/')} |" for e in errors[:50]]
        lines.append("")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📄 Reporte: {report_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga masiva de productos propios en VTEX Seller Portal (Catalog API - Seller Portal)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Ejecución:")[1] if "Ejecución:" in __doc__ else "",
    )
    parser.add_argument("input_file", help="XLSX o CSV con una fila por SKU")
    parser.add_argument("--sheet", help="Hoja del XLSX (default: la primera)")
    parser.add_argument("--dry-run", action="store_true", help="Solo lecturas: valida, resuelve y genera payloads")
    parser.add_argument("--check", action="store_true", help="Solo verifica credenciales y permisos")
    parser.add_argument("--update-existing", action="store_true", help="Actualiza (PUT) productos que ya existen")
    parser.add_argument("--create-missing-brands", action="store_true", help="Crea marcas que no existan")
    parser.add_argument("--skip-price", action="store_true", help="No aplica precios")
    parser.add_argument("--skip-stock", action="store_true", help="No aplica stock")
    parser.add_argument("--warehouse-id", help="Warehouse para stock (default: el primero activo)")
    parser.add_argument("--delay", type=float, default=1.0, help="Segundos entre escrituras (default 1.0)")
    parser.add_argument("--timeout", type=float, default=30, help="Timeout por request en segundos")
    parser.add_argument("--output-dir", default="seller_portal_output", help="Directorio de salida")
    parser.add_argument("--env-file", help="Archivo .env alternativo (credenciales de la cuenta seller)")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=args.env_file or os.path.join(project_root, ".env"))
    app_key = os.getenv("X-VTEX-API-AppKey")
    app_token = os.getenv("X-VTEX-API-AppToken")
    account = os.getenv("VTEX_ACCOUNT_NAME")
    environment = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")
    if not all([app_key, app_token, account]):
        print("❌ Faltan credenciales: X-VTEX-API-AppKey, X-VTEX-API-AppToken y VTEX_ACCOUNT_NAME")
        return 1

    client = SellerPortalClient(account, environment, app_key, app_token, args.timeout, args.delay)
    print(f"🏪 Cuenta seller: {account}")

    if args.check:
        return 0 if run_check(client) else 1

    if not os.path.exists(args.input_file):
        print(f"❌ No existe el archivo: {args.input_file}")
        return 1

    started = time.time()
    emit_progress("validate", "Validando archivo", 2)
    rows = read_rows(args.input_file, args.sheet)
    input_columns = list(dict.fromkeys(k for row in rows for k in row.keys()))
    products, invalid_errors = build_products(rows)
    print(f"📥 Filas leídas: {len(rows)} | Productos válidos: {len(products)} | Filas inválidas: {len(invalid_errors)}")
    for e in invalid_errors[:20]:
        print(f"   ⚠️  Fila {e['row_number']}: {e['error']}")

    loader = CatalogLoader(client, args)
    if products:
        emit_progress("lookups", "Leyendo categorías y marcas", 5)
        try:
            loader.load_lookups()
        except RuntimeError as e:
            print(f"❌ {e}")
            return 1

        total = len(products)
        for index, product in enumerate(products, start=1):
            print(f"\n[{index}/{total}] {product['external_id']} — {product['name']} ({len(product['skus'])} SKU)")
            loader.process_product(product)
            emit_progress("products", "Procesando productos", 5 + 93 * index / total,
                          f"{index}/{total} productos")

    write_outputs(loader, args.output_dir, input_columns, invalid_errors, len(products), time.time() - started)
    emit_progress("done", "Finalizado", 100)

    failed = invalid_errors or loader.errors
    any_ok = any(r["product_status"] in ("created", "updated", "skipped_exists")
                 or r["product_status"].startswith("dry_run") for r in loader.results)
    print(f"\n{'⚠️  Finalizado con errores' if failed else '✅ Finalizado sin errores'}")
    # Exit 1 (job fallido en WebOps) solo si hubo errores y ningún producto salió bien
    return 1 if failed and not any_ok else 0


if __name__ == "__main__":
    sys.exit(main())
