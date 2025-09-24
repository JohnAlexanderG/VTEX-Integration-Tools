#!/usr/bin/env python3
"""
VTEX Pricing — Bulk updater (PUT /pricing/prices/{itemId})

Admite objetos con o sin `costPrice` (precios manejados como enteros):
[
  {
    "_SkuId": 1,
    "_SKUReferenceCode": "000050",
    "basePrice": 17950
  },
  {
    "_SkuId": 2,
    "_SKUReferenceCode": "000051",
    "costPrice": 7917,
    "basePrice": 17950
  }
]

Comportamiento:
- Si hay `basePrice` y `costPrice` → se envían ambos.
- Si falta `costPrice` → se envía SOLO `basePrice` (VTEX derivará `costPrice` y `markup`).
- Flag opcional `--infer-cost-from-base` para forzar `costPrice = basePrice` cuando falte.

Uso:
  export VTEX_ACCOUNT_NAME=youraccount
  export X-VTEX-API-AppKey=xxx
  export X-VTEX-API-AppToken=yyy

  python3 vtex_price_updater_cost_optional.py \
    --input ./prices.json \
    --concurrency 3 \
    --batch-size 50

  # Para datasets grandes (1000+ items)
  python3 vtex_price_updater_cost_optional.py \
    --input ./large_prices.json \
    --batch-size 100 \
    --concurrency 2

  # Dry-run (no llama API)
  python3 vtex_price_updater_cost_optional.py --input ./prices.json --dry-run

Salidas:
  - ./price-update-success-{timestamp}.json (reporte detallado de éxitos con estadísticas)
  - ./price-update-errors-{timestamp}.json (reporte categorizado de errores)
  - ./price-update-errors-{timestamp}.csv (errores en formato CSV para análisis)
"""

import argparse
import json
import os
import sys
import time
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

try:
    import requests
except ImportError as e:
    print("This script requires the 'requests' library. Install with: pip install requests", file=sys.stderr)
    raise

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

API_BASE = "https://api.vtex.com"

# ---------- rate limiter ----------

class VTEXRateLimiter:
    """
    Rate limiter para VTEX API Pricing
    - Límite: 600 requests por minuto (10 por segundo)
    - Implementa sliding window para control preciso
    - Manejo adaptativo para 429 responses
    """
    
    def __init__(self, requests_per_minute: int = 600):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_minute / 60.0
        self.min_interval = 1.0 / self.requests_per_second  # ~0.1 seconds between requests
        self.request_times = deque()
        self.lock = threading.Lock()
        self.adaptive_delay = 0.0  # Extra delay when hitting 429s
        
    def wait_if_needed(self):
        """Espera si es necesario para respetar el rate limit"""
        with self.lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            
            # Check if we need to wait
            if len(self.request_times) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.request_times[0]) + 0.1  # Small buffer
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    now = time.time()
            
            # Add minimum interval between requests + adaptive delay
            total_delay = self.min_interval + self.adaptive_delay
            if self.request_times and now - self.request_times[-1] < total_delay:
                sleep_time = total_delay - (now - self.request_times[-1])
                time.sleep(sleep_time)
                now = time.time()
            
            # Record this request
            self.request_times.append(now)
    
    def handle_429_response(self):
        """Incrementa el delay adaptativo cuando recibimos 429"""
        with self.lock:
            self.adaptive_delay = min(self.adaptive_delay + 0.5, 5.0)  # Max 5 seconds extra delay
            print(f"⚠️  Rate limit detectado (429), incrementando delay a {self.adaptive_delay:.1f}s")
    
    def reset_adaptive_delay(self):
        """Resetea el delay adaptativo después de requests exitosos"""
        with self.lock:
            if self.adaptive_delay > 0:
                self.adaptive_delay = max(0, self.adaptive_delay - 0.1)

# ---------- helpers ----------

def norm_price(value: Any) -> int:
    """Normalize price strings like "$ 17,950" → 17950 (as integer)"""
    if value is None:
        raise ValueError("price is None")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    s = s.replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        raise ValueError("empty price string")
    # Convert to float first to handle decimal strings, then to int
    return int(float(s))


def load_items(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Input JSON must be an object or a list of objects")
    return data


def env_or_fail(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing environment variable: {name}")
    return v


# ---------- core ----------

def put_price(account: str, app_key: str, app_token: str, item_id: str, base_price: int, cost_price: int | None, timeout: int = 30) -> requests.Response:
    url = f"{API_BASE}/{account}/pricing/prices/{item_id}"
    payload: Dict[str, Any] = {"basePrice": base_price}
    if cost_price is not None:
        payload["costPrice"] = cost_price
    headers = {
        "X-VTEX-API-AppKey": app_key,
        "X-VTEX-API-AppToken": app_token,
        "Content-Type": "application/json",
    }
    return requests.put(url, json=payload, headers=headers, timeout=timeout)


def process_items(items: Iterable[Dict[str, Any]], account: str, app_key: str, app_token: str, concurrency: int, max_retries: int, retry_backoff_ms: int, dry_run: bool, infer_cost_from_base: bool, batch_size: int = 50) -> Dict[str, Any]:
    successes: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    
    # Convert to list to get total count
    items_list = list(items) if not isinstance(items, list) else items
    total_items = len(items_list)
    
    print(f"🚀 Procesando {total_items} elementos en lotes de {batch_size}")
    print(f"📊 Configuración: concurrency={concurrency}, max_retries={max_retries}")
    
    # Initialize rate limiter - more conservative for large batches
    rate_limiter = VTEXRateLimiter(requests_per_minute=min(600, 300 if total_items > 500 else 600))
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def worker(item_data: tuple) -> Dict[str, Any]:
        it, item_index = item_data
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        sku_id = it.get("_SkuId")
        
        if sku_id is None:
            print(f"❌ Item {item_index + 1}: Error - falta _SkuId")
            return {"status": "failed", "reason": "missing _SkuId", "item": it, "timestamp": now, "index": item_index}
        
        # basePrice obligatorio
        try:
            base_price = norm_price(it.get("basePrice"))
        except Exception as e:
            print(f"❌ Item {item_index + 1} (SKU {sku_id}): Error - basePrice inválido: {e}")
            return {"status": "failed", "reason": f"invalid basePrice: {e}", "item": it, "timestamp": now, "index": item_index}
        
        # costPrice opcional
        cost_price_raw = it.get("costPrice", None)
        cost_price: int | None = None
        if cost_price_raw is not None and str(cost_price_raw).strip() != "":
            try:
                cost_price = norm_price(cost_price_raw)
            except Exception:
                cost_price = None  # ignorar si viene mal y dejar que VTEX derive
        if cost_price is None and infer_cost_from_base:
            cost_price = base_price

        if dry_run:
            body = {"basePrice": base_price}
            if cost_price is not None:
                body["costPrice"] = cost_price
            print(f"🧪 Item {item_index + 1} (SKU {sku_id}): DRY-RUN - PUT {API_BASE}/{account}/pricing/prices/{sku_id} | Body: {body}")
            return {
                "status": "dry-run",
                "request": {
                    "url": f"{API_BASE}/{account}/pricing/prices/{sku_id}",
                    "body": body,
                },
                "item": {
                    "_SkuId": sku_id, 
                    "_SKUReferenceCode": it.get("_SKUReferenceCode"),
                    "basePrice": base_price,
                    "costPrice": cost_price
                },
                "timestamp": now,
                "index": item_index,
            }

        # Apply rate limiting before making request
        if not dry_run:
            rate_limiter.wait_if_needed()

        attempt = 0
        while True:
            attempt += 1
            try:
                print(f"🔄 Item {item_index + 1} (SKU {sku_id}): Enviando PUT request (intento {attempt}) - basePrice: {base_price}" + (f", costPrice: {cost_price}" if cost_price is not None else ""))
                resp = put_price(account, app_key, app_token, str(sku_id), base_price, cost_price)
                
                if resp.status_code < 300:
                    rate_limiter.reset_adaptive_delay()
                    print(f"✅ Item {item_index + 1} (SKU {sku_id}): Éxito - HTTP {resp.status_code}")
                    return {
                        "status": "success", 
                        "code": resp.status_code, 
                        "item": {
                            "_SkuId": sku_id, 
                            "_SKUReferenceCode": it.get("_SKUReferenceCode"), 
                            "basePrice": base_price, 
                            "costPrice": cost_price
                        }, 
                        "timestamp": now,
                        "index": item_index
                    }
                elif resp.status_code == 429:
                    print(f"⚠️  Item {item_index + 1} (SKU {sku_id}): Rate limit (429) - intento {attempt}/{max_retries}")
                    rate_limiter.handle_429_response()
                    if attempt <= max_retries:
                        sleep_ms = retry_backoff_ms * (2 ** (attempt - 1))
                        print(f"   ⏳ Esperando {sleep_ms}ms antes del siguiente intento...")
                        time.sleep(sleep_ms / 1000.0)
                    else:
                        print(f"❌ Item {item_index + 1} (SKU {sku_id}): Falló - Rate limit excedido después de {max_retries} intentos")
                        return {"status": "failed", "code": resp.status_code, "error": "Rate limit exceeded after retries", "item": {"_SkuId": sku_id, "_SKUReferenceCode": it.get("_SKUReferenceCode")}, "timestamp": now, "index": item_index}
                elif resp.status_code in (500, 502, 503, 504) and attempt <= max_retries:
                    print(f"⚠️  Item {item_index + 1} (SKU {sku_id}): Error servidor (HTTP {resp.status_code}) - intento {attempt}/{max_retries}")
                    sleep_ms = retry_backoff_ms * (2 ** (attempt - 1))
                    print(f"   ⏳ Esperando {sleep_ms}ms antes del siguiente intento...")
                    time.sleep(sleep_ms / 1000.0)
                else:
                    try:
                        err = resp.json()
                    except Exception:
                        err = resp.text
                    print(f"❌ Item {item_index + 1} (SKU {sku_id}): Error HTTP {resp.status_code} - {str(err)[:100]}...")
                    return {"status": "failed", "code": resp.status_code, "error": err, "item": {"_SkuId": sku_id, "_SKUReferenceCode": it.get("_SKUReferenceCode")}, "timestamp": now, "index": item_index}
            except requests.RequestException as e:
                print(f"⚠️  Item {item_index + 1} (SKU {sku_id}): Error de conexión - {str(e)[:50]}... - intento {attempt}/{max_retries}")
                if attempt <= max_retries:
                    sleep_ms = retry_backoff_ms * (2 ** (attempt - 1))
                    print(f"   ⏳ Esperando {sleep_ms}ms antes del siguiente intento...")
                    time.sleep(sleep_ms / 1000.0)
                else:
                    print(f"❌ Item {item_index + 1} (SKU {sku_id}): Falló - Error de conexión después de {max_retries} intentos")
                    return {"status": "failed", "reason": str(e), "item": {"_SkuId": sku_id, "_SKUReferenceCode": it.get("_SKUReferenceCode")}, "timestamp": now, "index": item_index}

    # Process in batches with progress reporting
    processed = 0
    batch_num = 0
    
    for i in range(0, total_items, batch_size):
        batch_num += 1
        batch_items = items_list[i:i + batch_size]
        batch_count = len(batch_items)
        
        print(f"\n📦 Lote {batch_num}: procesando elementos {i+1}-{i+batch_count} de {total_items}")
        
        # Process batch with controlled concurrency
        effective_concurrency = min(concurrency, batch_count, 5)  # Max 5 concurrent for safety
        print(f"   🔧 Configuración del lote: {effective_concurrency} workers concurrentes")
        batch_start = time.time()
        
        # Add index to each item for tracking
        indexed_items = [(item, i + idx) for idx, item in enumerate(batch_items)]
        
        with ThreadPoolExecutor(max_workers=effective_concurrency) as exe:
            print(f"   🚀 Lanzando {len(indexed_items)} tareas en el thread pool...")
            futures = [exe.submit(worker, item_data) for item_data in indexed_items]
            
            batch_successes = 0
            batch_failures = 0
            completed_in_batch = 0
            
            for fut in as_completed(futures):
                res = fut.result()
                processed += 1
                completed_in_batch += 1
                
                if res.get("status") in ("success", "dry-run"):
                    successes.append(res)
                    batch_successes += 1
                else:
                    failures.append(res)
                    batch_failures += 1
                
                # Progress within batch - more frequent updates
                if completed_in_batch % 5 == 0 or completed_in_batch == batch_count or processed % 20 == 0:
                    progress_pct = (processed / total_items) * 100
                    batch_progress_pct = (completed_in_batch / batch_count) * 100
                    print(f"  ⏳ Progreso del lote: {completed_in_batch}/{batch_count} ({batch_progress_pct:.0f}%) | Global: {processed}/{total_items} ({progress_pct:.1f}%) - ✅ {len(successes)} exitosos, ❌ {len(failures)} fallidos")
        
        batch_time = time.time() - batch_start
        print(f"  🏁 Lote {batch_num} completado en {batch_time:.1f}s - ✅ {batch_successes} exitosos, ❌ {batch_failures} fallidos")
        
        # Add delay between batches for large datasets
        if i + batch_size < total_items and not dry_run:
            if total_items > 500:
                inter_batch_delay = 2.0  # 2 seconds between batches for large datasets
                print(f"  ⏸️  Pausa entre lotes: {inter_batch_delay}s (permitiendo que VTEX API se recupere)")
                time.sleep(inter_batch_delay)
            elif total_items > 100:
                inter_batch_delay = 1.0  # 1 second for medium datasets
                print(f"  ⏸️  Pausa entre lotes: {inter_batch_delay}s")
                time.sleep(inter_batch_delay)

    return {"successes": successes, "failures": failures}


# ---------- reporting ----------

def generate_success_report(successes: List[Dict[str, Any]], total_time: float, timestamp: str) -> Dict[str, Any]:
    """Genera un reporte detallado de éxitos"""
    success_items = [r for r in successes if r.get("status") == "success"]
    dry_run_items = [r for r in successes if r.get("status") == "dry-run"]
    
    total_successful = len(success_items)
    total_dry_run = len(dry_run_items)
    
    # Estadísticas de precios
    prices_with_cost = 0
    prices_without_cost = 0
    total_base_price = 0
    total_cost_price = 0
    
    for item in success_items + dry_run_items:
        item_data = item.get("item", {})
        base_price = item_data.get("basePrice", 0)
        cost_price = item_data.get("costPrice")
        
        total_base_price += base_price
        if cost_price is not None:
            prices_with_cost += 1
            total_cost_price += cost_price
        else:
            prices_without_cost += 1
    
    avg_base_price = int(total_base_price / (total_successful + total_dry_run)) if (total_successful + total_dry_run) > 0 else 0
    avg_cost_price = int(total_cost_price / prices_with_cost) if prices_with_cost > 0 else 0
    
    return {
        "execution_summary": {
            "timestamp": timestamp,
            "total_execution_time_seconds": round(total_time, 2),
            "requests_per_minute": round(((total_successful + total_dry_run) / total_time) * 60, 2) if total_time > 0 else 0,
            "total_processed": total_successful + total_dry_run,
            "successful_updates": total_successful,
            "dry_run_simulations": total_dry_run
        },
        "pricing_statistics": {
            "items_with_cost_price": prices_with_cost,
            "items_without_cost_price": prices_without_cost,
            "average_base_price": avg_base_price,
            "average_cost_price": avg_cost_price if avg_cost_price > 0 else None,
            "total_base_price_sum": total_base_price,
            "total_cost_price_sum": total_cost_price
        },
        "successful_items": [
            {
                "sku_id": item.get("item", {}).get("_SkuId"),
                "sku_reference_code": item.get("item", {}).get("_SKUReferenceCode"),
                "base_price": item.get("item", {}).get("basePrice"),
                "cost_price": item.get("item", {}).get("costPrice"),
                "http_status_code": item.get("code"),
                "timestamp": item.get("timestamp"),
                "status": item.get("status")
            }
            for item in success_items + dry_run_items
        ]
    }


def generate_error_report_json(failures: List[Dict[str, Any]], timestamp: str) -> Dict[str, Any]:
    """Genera un reporte detallado de errores en formato JSON"""
    
    # Categorizar errores
    error_categories = {
        "validation_errors": [],
        "rate_limit_errors": [],
        "server_errors": [],
        "connection_errors": [],
        "other_errors": []
    }
    
    for failure in failures:
        error_type = "other_errors"
        reason = failure.get("reason", "")
        code = failure.get("code")
        
        if "missing _SkuId" in reason or "invalid basePrice" in reason:
            error_type = "validation_errors"
        elif code == 429 or "Rate limit" in reason:
            error_type = "rate_limit_errors"
        elif code and code >= 500:
            error_type = "server_errors"
        elif "connection" in reason.lower() or "timeout" in reason.lower():
            error_type = "connection_errors"
        
        error_categories[error_type].append({
            "sku_id": failure.get("item", {}).get("_SkuId"),
            "sku_reference_code": failure.get("item", {}).get("_SKUReferenceCode"),
            "error_reason": reason,
            "http_status_code": code,
            "error_details": failure.get("error"),
            "timestamp": failure.get("timestamp"),
            "original_item": failure.get("item")
        })
    
    # Estadísticas de errores
    error_stats = {}
    for category, errors in error_categories.items():
        error_stats[category] = len(errors)
    
    return {
        "error_summary": {
            "timestamp": timestamp,
            "total_errors": len(failures),
            "error_breakdown": error_stats
        },
        "error_categories": error_categories
    }


def save_error_report_csv(failures: List[Dict[str, Any]], filename: str):
    """Guarda un reporte de errores en formato CSV"""
    import csv
    
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "sku_id", "sku_reference_code", "base_price", "cost_price", 
            "error_reason", "http_status_code", "error_details", "timestamp"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for failure in failures:
            item = failure.get("item", {})
            writer.writerow({
                "sku_id": item.get("_SkuId"),
                "sku_reference_code": item.get("_SKUReferenceCode"),
                "base_price": item.get("basePrice"),
                "cost_price": item.get("costPrice"),
                "error_reason": failure.get("reason", ""),
                "http_status_code": failure.get("code", ""),
                "error_details": str(failure.get("error", ""))[:200],  # Truncar error details
                "timestamp": failure.get("timestamp")
            })


def main():
    parser = argparse.ArgumentParser(description="Bulk update VTEX prices (basePrice with optional costPrice)")
    parser.add_argument("--input", required=True, help="Path to JSON file (object or list)")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel workers (default: 3, max 5 for safety)")
    parser.add_argument("--batch-size", type=int, default=50, help="Process items in batches (default: 50)")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries for 429/5xx (default: 3)")
    parser.add_argument("--retry-backoff-ms", type=int, default=750, help="Base backoff in ms (default: 750)")
    parser.add_argument("--dry-run", action="store_true", help="Print requests without calling the API")
    parser.add_argument("--infer-cost-from-base", action="store_true", help="If costPrice is missing, use basePrice as costPrice")

    args = parser.parse_args()

    print("🔧 Configurando credenciales VTEX...")
    account = env_or_fail("VTEX_ACCOUNT_NAME")
    app_key = env_or_fail("X-VTEX-API-AppKey")
    app_token = env_or_fail("X-VTEX-API-AppToken")
    print(f"   ✅ Account: {account}")
    print(f"   ✅ App Key: {app_key[:15]}...")
    print(f"   ✅ App Token: {'*' * 10}[OCULTO]")

    items = load_items(args.input)
    
    print(f"📁 Archivo cargado: {args.input}")
    print(f"   📊 Total de items encontrados: {len(items)}")
    
    if args.dry_run:
        print("🧪 Modo DRY-RUN activado - no se realizarán llamadas a la API")
    
    if args.infer_cost_from_base:
        print("💡 Flag activado: inferir costPrice desde basePrice cuando falte")
    
    print(f"⚙️  Configuración de procesamiento:")
    print(f"   🔀 Concurrencia: {args.concurrency} workers")
    print(f"   📦 Tamaño de lote: {args.batch_size} items")
    print(f"   🔄 Máx. reintentos: {args.max_retries}")
    print(f"   ⏰ Backoff inicial: {args.retry_backoff_ms}ms")
    
    start_time = time.time()
    results = process_items(
        items=items,
        account=account,
        app_key=app_key,
        app_token=app_token,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
        retry_backoff_ms=args.retry_backoff_ms,
        dry_run=args.dry_run,
        infer_cost_from_base=args.infer_cost_from_base,
        batch_size=args.batch_size,
    )

    total_time = time.time() - start_time
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ts_filename = ts.replace(":", "-").replace(".", "-")

    print(f"\n💾 Generando reportes detallados...")
    
    # Generar reporte de éxitos
    success_report = generate_success_report(results["successes"], total_time, ts)
    success_filename = f"price-update-success-{ts_filename}.json"
    with open(success_filename, "w", encoding="utf-8") as f:
        json.dump(success_report, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Reporte de éxitos: {success_filename} ({len(results['successes'])} items)")
    
    # Generar reportes de errores si hay fallos
    error_json_filename = None
    error_csv_filename = None
    if results["failures"]:
        # Reporte JSON detallado
        error_report_json = generate_error_report_json(results["failures"], ts)
        error_json_filename = f"price-update-errors-{ts_filename}.json"
        with open(error_json_filename, "w", encoding="utf-8") as f:
            json.dump(error_report_json, f, ensure_ascii=False, indent=2)
        print(f"   ❌ Reporte de errores JSON: {error_json_filename} ({len(results['failures'])} items)")
        
        # Reporte CSV para análisis
        error_csv_filename = f"price-update-errors-{ts_filename}.csv"
        save_error_report_csv(results["failures"], error_csv_filename)
        print(f"   📊 Reporte de errores CSV: {error_csv_filename} ({len(results['failures'])} items)")
    else:
        print(f"   🎉 No hay errores que reportar")

    ok = sum(1 for r in results["successes"] if r.get("status") == "success")
    dry = sum(1 for r in results["successes"] if r.get("status") == "dry-run")
    bad = len(results["failures"])
    total_processed = ok + dry + bad

    print(f"\n🎯 RESUMEN FINAL")
    print(f"  ⏱️  Tiempo total: {total_time:.1f}s")
    print(f"  📊 Total procesado: {total_processed}")
    print(f"  ✅ Exitosos: {ok}")
    if dry > 0:
        print(f"  🧪 Dry-run: {dry}")
    print(f"  ❌ Fallidos: {bad}")
    
    if total_processed > 0:
        success_rate = ((ok + dry) / total_processed) * 100
        requests_per_minute = (total_processed / total_time) * 60 if total_time > 0 else 0
        print(f"  📈 Tasa de éxito: {success_rate:.1f}%")
        print(f"  🚀 Velocidad: {requests_per_minute:.1f} requests/min")
    
    if bad > 0:
        print(f"\n⚠️  Ver detalles de errores en: {error_json_filename if results['failures'] else 'N/A'}")
        print(f"📊 Análisis de errores CSV: {error_csv_filename if results['failures'] else 'N/A'}")
    else:
        print(f"\n🎉 ¡Procesamiento completado sin errores!")
    
    print(f"\n📋 Archivos generados:")
    print(f"   📄 Reporte de éxitos: {success_filename}")
    if results["failures"]:
        print(f"   🔍 Reporte de errores (JSON): {error_json_filename}")
        print(f"   📊 Reporte de errores (CSV): {error_csv_filename}")


if __name__ == "__main__":
    main()
