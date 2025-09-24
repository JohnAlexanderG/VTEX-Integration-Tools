#!/usr/bin/env python3
"""
VTEX Inventory Uploader (Concurrent)
------------------------------------
Actualiza inventario por SKU y bodega (warehouse) usando el endpoint:
PUT https://{accountName}.{environment}.com.br/api/logistics/pvt/inventory/skus/{skuId}/warehouses/{warehouseId}

Características principales:
- Lee un archivo JSON de entrada con una lista de objetos o NDJSON (1 objeto por línea).
- **Procesamiento concurrente** con ThreadPoolExecutor para mejor rendimiento.
- Control de tasa (rate limiting) compartido tipo *token bucket* con 10 RPS por defecto (≈600 RPM).
- Modo adaptativo frente a 429 (Too Many Requests): aplica backoff exponencial + reduce temporalmente el RPS.
- Manejo de reintentos con *exponential backoff with jitter* para errores transitorios (5xx, 429, timeouts).
- Cada worker tiene su propia requests.Session para evitar contención. Las sesiones se reutilizan (1 por worker).
- Soporta .env ubicado en el directorio padre (../.env) para credenciales y configuración.
- Exporta un CSV con los registros fallidos (thread-safe).
- Genera un archivo .md con un resumen del proceso.
- Salida de progreso clara en terminal con métricas y ETA aproximada.

Requisitos del .env (ubicado un nivel atrás, en la raíz del proyecto):
- VTEX_ACCOUNT_NAME=mi-tienda
- VTEX_ENVIRONMENT=vtexcommercestable (o el que corresponda, sin ".com.br")
- X-VTEX-API-AppKey=xxxxxxxx
- X-VTEX-API-AppToken=xxxxxxxx

Estructura de cada item en el JSON de entrada:
{
    "_SkuId": 1,
    "_SKUReferenceCode": "000050",
    "warehouseId": "220",
    "quantity": 96,
    "unlimitedQuantity": false
}

Uso:
    python3 vtex_inventory_uploader.py \
        --input ./data/inventory.json \
        --failures ./out/failures.csv \
        --summary ./out/summary.md \
        --rps 30 \
        --workers 8

Notas:
- Si el archivo es muy grande (~300k registros), prefiera NDJSON para menor consumo de memoria.
- Con --workers 8 y --rps 30, puede lograr cerca de 30 RPS real incluso con latencias de 100-200ms.
- El rate limiting es global (compartido entre todos los workers) para respetar límites de VTEX.
"""

import argparse
import csv
import json
import os
import sys
import time
import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, Generator, Optional, Tuple

import requests

# --------------- Utilidades de entorno (.env) ---------------

def load_env_from_parent(env_path: str = "../.env") -> Dict[str, str]:
    """Carga un archivo .env simple (KEY=VALUE) ignorando comentarios y líneas vacías."""
    env: Dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip().strip('"').strip("'")
    # Mezcla con variables de entorno del sistema (prioridad al sistema)
    env = {**env, **{k: v for k, v in os.environ.items()}}
    return env

# --------------- Lector de entrada grande (JSON / NDJSON) ---------------

def iter_input_items(input_path: str) -> Generator[Dict[str, Any], None, None]:
    """Genera items desde un archivo JSON grande.
    - Si el archivo empieza con '[' asume lista JSON y la carga por streaming simple.
    - Si no, asume NDJSON (1 objeto JSON por línea).
    """
    with open(input_path, "r", encoding="utf-8") as f:
        # Peek primeros caracteres para decidir el formato
        start = f.read(1)
        if not start:
            return
        f.seek(0)
        if start == "[":
            # Carga en memoria si no es gigantesco; para 300k puede ser grande.
            # Implementamos parse streaming simple sin dependencias externas.
            buf = ""
            depth = 0
            in_string = False
            escape = False
            # Saltar primer '['
            f.read(1)
            while True:
                ch = f.read(1)
                if not ch:
                    break
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    buf += ch
                    continue
                if ch == '"':
                    in_string = True
                    buf += ch
                    continue
                if ch == '{':
                    depth += 1
                    buf += ch
                    continue
                if ch == '}':
                    depth -= 1
                    buf += ch
                    if depth == 0 and buf.strip():
                        try:
                            yield json.loads(buf)
                        except Exception:
                            pass
                        buf = ""
                    continue
                # separadores entre objetos
                if depth == 0:
                    continue
                buf += ch
        else:
            # NDJSON
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Línea inválida: la omitimos
                    continue

# --------------- Rate Limiter (Token Bucket + Adaptativo) ---------------

class TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: int):
        self.rate = float(rate_per_sec)
        self.capacity = int(capacity)
        self.tokens = float(capacity)
        self.timestamp = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            # recarga tokens
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.timestamp = now
            # si no alcanza, dormir hasta que alcance
            if self.tokens < tokens:
                needed = tokens - self.tokens
                sleep_time = needed / self.rate
                # Release lock during sleep to allow other threads
                self._lock.release()
                time.sleep(sleep_time)
                self._lock.acquire()
                # actualizar
                now2 = time.monotonic()
                elapsed2 = now2 - self.timestamp
                self.tokens = min(self.capacity, self.tokens + elapsed2 * self.rate)
                self.timestamp = now2
            self.tokens -= tokens

    def update_rate(self, new_rate: float):
        """Thread-safe rate update"""
        with self._lock:
            self.rate = max(1.0, float(new_rate))

# --------------- Cliente VTEX Logistics ---------------

class VtexInventoryClient:
    def __init__(self, account: str, environment: str, app_key: str, app_token: str,
                 shared_bucket: TokenBucket, base_rps: float = 10.0):
        self.account = account
        self.environment = environment
        self.app_key = app_key
        self.app_token = app_token
        self.base_rps = base_rps
        self.current_rps = base_rps
        self.bucket = shared_bucket  # Shared bucket across all workers
        self._rate_lock = threading.Lock()
        
        # Each worker gets its own session
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-VTEX-API-AppKey": self.app_key,
            "X-VTEX-API-AppToken": self.app_token,
        })
        # Construir URL base - agregar .com.br si no está presente
        if self.environment.endswith('.com.br'):
            self.base_url = f"https://{self.account}.{self.environment}"
        else:
            self.base_url = f"https://{self.account}.{self.environment}.com.br"
        self.last_429_at: Optional[float] = None

    def _adaptive_on_429(self, reset_after: Optional[float] = None):
        # Reduce temporalmente el RPS a la mitad por 60s (o el reset indicado), mínimo 1 RPS
        with self._rate_lock:
            self.last_429_at = time.monotonic()
            new_rps = max(1.0, self.current_rps / 2.0)
            self.current_rps = new_rps
            self.bucket.update_rate(new_rps)
            if reset_after is None:
                reset_after = 60.0
            return reset_after

    def _maybe_restore_rate(self):
        # Si ha pasado tiempo desde el último 429, recupera gradualmente hasta base_rps
        with self._rate_lock:
            if self.last_429_at is None:
                return
            elapsed = time.monotonic() - self.last_429_at
            if elapsed > 60:
                # Recuperación suave
                target = min(self.base_rps, self.current_rps * 1.25)
                if abs(target - self.current_rps) >= 0.5:
                    self.current_rps = target
                    self.bucket.update_rate(target)
                if math.isclose(self.current_rps, self.base_rps, rel_tol=0.05):
                    self.last_429_at = None

    def update_inventory(self, sku_id: int, warehouse_id: str, quantity: int, unlimited: bool,
                         timeout: int = 20) -> Tuple[int, str]:
        """Realiza el PUT de inventario. Retorna (status_code, response_text)."""
        url = f"{self.base_url}/api/logistics/pvt/inventory/skus/{sku_id}/warehouses/{warehouse_id}"
        payload = {
            "quantity": int(quantity),
            "unlimitedQuantity": bool(unlimited),
        }

        # Control de tasa por request (shared bucket)
        self.bucket.consume(1.0)

        try:
            resp = self.session.put(url, data=json.dumps(payload), timeout=timeout)
        except requests.RequestException as e:
            return (0, f"request_exception: {e}")

        # Manejo adaptativo 429
        if resp.status_code == 429:
            # Lee cabeceras de rate limit si existen
            reset_sec = None
            for k in ("x-vtex-ratelimit-reset", "X-VTEX-Ratelimit-Reset"):
                if k in resp.headers:
                    try:
                        reset_sec = float(resp.headers[k])
                    except Exception:
                        reset_sec = None
                    break
            delay = self._adaptive_on_429(reset_sec)
            # Dormir ligeramente para aliviar
            time.sleep(min(2.0, delay))

        # Intento de restauración gradual si no hay 429 recientes
        self._maybe_restore_rate()

        return (resp.status_code, resp.text)

# --------------- Proceso principal ---------------

def exponential_backoff(base: float, factor: float, attempt: int, jitter: float = 0.2, max_sleep: float = 30.0) -> float:
    sleep = min(max_sleep, base * (factor ** attempt))
    # jitter proporcional
    return sleep * (1 - jitter/2 + random.random() * jitter)


# --------------- Shared Progress Tracking ---------------

class ProgressTracker:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failures = 0
        self.attempted = 0
        self._lock = threading.Lock()
    
    def increment_total(self):
        with self._lock:
            self.total += 1
    
    def increment_attempted(self):
        with self._lock:
            self.attempted += 1
    
    def increment_success(self):
        with self._lock:
            self.success += 1
    
    def increment_failures(self):
        with self._lock:
            self.failures += 1
    
    def get_stats(self):
        with self._lock:
            return self.total, self.success, self.failures, self.attempted


# --------------- Worker Function ---------------

def worker_process_item(item: Dict[str, Any], client: VtexInventoryClient, 
                       progress: ProgressTracker, fail_writer_lock: threading.Lock, 
                       fail_writer: csv.writer) -> None:
    """Worker function to process a single inventory item"""
    progress.increment_total()
    
    # Validación mínima
    try:
        sku_id = int(item.get("_SkuId"))
        warehouse_id = str(item.get("warehouseId"))
        quantity = int(item.get("quantity"))
        unlimited = bool(item.get("unlimitedQuantity", False))
    except Exception:
        progress.increment_failures()
        with fail_writer_lock:
            fail_writer.writerow([
                item.get("_SkuId"), item.get("_SKUReferenceCode"), item.get("warehouseId"),
                item.get("quantity"), item.get("unlimitedQuantity"),
                -1, "validation_error"
            ])
        return

    # Reintentos para errores transitorios
    max_attempts = 5
    attempt = 0
    done = False
    status, text = 0, ""
    
    while attempt < max_attempts and not done:
        progress.increment_attempted()
        status, text = client.update_inventory(sku_id, warehouse_id, quantity, unlimited)

        if status in (200, 201, 204):
            progress.increment_success()
            done = True
            break
        elif status in (408, 409, 425, 429, 500, 502, 503, 504, 0):
            # backoff exponencial con jitter
            sleep = exponential_backoff(base=0.5, factor=2.0, attempt=attempt, jitter=0.3, max_sleep=45.0)
            time.sleep(sleep)
            attempt += 1
            continue
        else:
            # Errores 4xx no transitorios: registrar y abortar reintentos
            progress.increment_failures()
            with fail_writer_lock:
                fail_writer.writerow([
                    item.get("_SkuId"), item.get("_SKUReferenceCode"), warehouse_id,
                    quantity, unlimited, status, text[:500]
                ])
            done = True
            break

    if not done:
        # Se agotaron reintentos
        progress.increment_failures()
        with fail_writer_lock:
            fail_writer.writerow([
                item.get("_SkuId"), item.get("_SKUReferenceCode"), warehouse_id,
                quantity, unlimited, status, f"retries_exhausted: {text[:500]}"
            ])


def process_file(input_path: str, failures_csv: str, summary_md: str, base_rps: float, num_workers: int = 8) -> None:
    env = load_env_from_parent()

    account = env.get("VTEX_ACCOUNT_NAME")
    environment = env.get("VTEX_ENVIRONMENT", "vtexcommercestable")
    app_key = env.get("X-VTEX-API-AppKey")
    app_token = env.get("X-VTEX-API-AppToken")

    if not all([account, app_key, app_token]):
        print("[ERROR] Faltan variables en ../.env: VTEX_ACCOUNT_NAME, X-VTEX-API-AppKey, X-VTEX-API-AppToken", file=sys.stderr)
        sys.exit(1)

    # Create shared TokenBucket for rate limiting across all workers
    shared_bucket = TokenBucket(rate_per_sec=base_rps, capacity=max(5, int(base_rps)))
    
    # Progress tracking
    progress = ProgressTracker()
    first_ts = datetime.now()

    os.makedirs(os.path.dirname(failures_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(summary_md) or ".", exist_ok=True)

    # Prepara CSV de fallos con thread safety
    fail_fh = open(failures_csv, "w", newline="", encoding="utf-8")
    fail_writer = csv.writer(fail_fh)
    fail_writer.writerow([
        "_SkuId", "_SKUReferenceCode", "warehouseId", "quantity", "unlimitedQuantity",
        "status_code", "error_message"
    ])
    fail_writer_lock = threading.Lock()

    print("\n=== VTEX Inventory Uploader (Concurrent) ===")
    print(f"Account: {account} | Env: {environment} | Base RPS: {base_rps} | Workers: {num_workers}")
    print(f"Input: {input_path}")
    print("----------------------------------------------")

    # Contar rápidamente (si es NDJSON cuenta líneas; si es array, no contamos para ahorrar memoria)
    estimated_total: Optional[int] = None
    try:
        with open(input_path, "r", encoding="utf-8") as cfh:
            head = cfh.read(1)
            if head != "[":
                # NDJSON -> conteo de líneas
                cfh.seek(0)
                estimated_total = sum(1 for _ in cfh)
    except Exception:
        pass

    if estimated_total:
        print(f"Registros estimados: ~{estimated_total}")
    else:
        print("Registros estimados: desconocido (JSON array)")

    # Progress reporting setup
    last_report = time.monotonic()
    last_total = 0

    def create_worker_client():
        """Create a client instance for each worker with shared bucket"""
        return VtexInventoryClient(account, environment, app_key, app_token, shared_bucket, base_rps)

    # Set up bounded in-flight concurrency and pre-create clients
    max_in_flight = max(32, num_workers * 4)

    # Process items concurrently with bounded in-flight futures
    clients = [create_worker_client() for _ in range(num_workers)]

    def drain_completed(futures_set, blocking=False):
        nonlocal last_report, last_total
        drained = 0
        if not futures_set:
            return
        
        try:
            # Use timeout only when not blocking, otherwise wait indefinitely
            timeout = None if blocking else 0.1
            for f in as_completed(list(futures_set), timeout=timeout):
                try:
                    f.result()
                except Exception as e:
                    print(f"[WARN] Worker exception: {e}")
                    progress.increment_failures()
                futures_set.remove(f)
                drained += 1
                # don't drain everything every time when not blocking; keep loop snappy
                if not blocking and drained >= num_workers:
                    break
        except:
            # Timeout or other exception from as_completed - that's ok when not blocking
            if blocking:
                # If we're supposed to be blocking, something went wrong
                raise

        # progress print independent of submission cadence
        now = time.monotonic()
        if now - last_report >= 2.0:
            total, success, failures, _ = progress.get_stats()
            processed_since_report = total - last_total
            elapsed = now - last_report
            rps = processed_since_report / elapsed if elapsed > 0 else 0.0

            if estimated_total and total > 0:
                remaining = max(0, estimated_total - total)
                effective_rps = max(0.1, rps)
                eta_sec = remaining / effective_rps
                eta_str = str(timedelta(seconds=int(eta_sec)))
            else:
                eta_str = "N/A"

            current_rate = shared_bucket.rate
            print(f"[Progreso] total={total} ok={success} fail={failures} rps~{rps:.1f} ETA={eta_str} currRPS={current_rate:.1f}")
            last_report = now
            last_total = total

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = set()
        idx = 0
        for item in iter_input_items(input_path):
            # apply backpressure: keep futures bounded
            while len(futures) >= max_in_flight:
                drain_completed(futures)

            client = clients[idx % num_workers]
            idx += 1
            fut = executor.submit(worker_process_item, item, client, progress, fail_writer_lock, fail_writer)
            futures.add(fut)
            # opportunistically drain and print progress
            drain_completed(futures)

        # after submitting all, wait for completion while continuing to print progress
        while futures:
            drain_completed(futures, blocking=True)

    # Final stats
    _, success, failures, attempted = progress.get_stats()
    
    fail_fh.flush()
    fail_fh.close()

    end_ts = datetime.now()
    duration = end_ts - first_ts
    avg_rps = success / duration.total_seconds() if duration.total_seconds() > 0 else 0.0

    # Resumen MD
    with open(summary_md, "w", encoding="utf-8") as md:
        md.write("# Resumen de carga de inventario (VTEX) - Concurrent\n\n")
        md.write(f"**Fecha inicio:** {first_ts.isoformat()}\n\n")
        md.write(f"**Fecha fin:** {end_ts.isoformat()}\n\n")
        md.write(f"**Duración:** {str(duration)}\n\n")
        md.write(f"**Account/Env:** {account}/{environment}\n\n")
        md.write(f"**Workers:** {num_workers}\n\n")
        md.write(f"**Intentados:** {attempted}\n\n")
        md.write(f"**Éxitos:** {success}\n\n")
        md.write(f"**Fallidos:** {failures}\n\n")
        md.write(f"**RPS base:** {base_rps}\n\n")
        md.write(f"**RPS promedio efectivo:** {avg_rps:.2f}\n\n")
        md.write(f"**Archivo fallidos (CSV):** {failures_csv}\n\n")
        md.write(f"**Input:** {input_path}\n\n")
        md.write("---\n")
        if failures > 0:
            md.write("Se encontraron fallos. Revise el CSV para reintentos focalizados.\n")
        else:
            md.write("Proceso completado sin fallos registrados.\n")

    print("----------------------------------------------")
    print("Proceso finalizado.")
    print(f"Intentados: {attempted} | Éxitos: {success} | Fallidos: {failures}")
    print(f"Resumen: {summary_md}")
    print(f"Fallidos CSV: {failures_csv}")


# --------------- CLI ---------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga de inventario a VTEX Logistics (PUT por SKU/Bodega) - Versión Concurrente")
    parser.add_argument("--input", required=True, help="Ruta al archivo JSON o NDJSON de entrada")
    parser.add_argument("--failures", default=f"./failures_{int(time.time())}.csv", help="Ruta de salida para el CSV de fallidos")
    parser.add_argument("--summary", default=f"./summary_{int(time.time())}.md", help="Ruta de salida para el resumen .md")
    parser.add_argument("--rps", type=float, default=10.0, help="Requests por segundo (por defecto 10 ≈ 600 RPM)")
    parser.add_argument("--workers", type=int, default=8, help="Número de workers concurrentes (por defecto 8)")

    args = parser.parse_args()

    # Medición de tiempo total de ejecución
    script_start_time = time.time()

    try:
        process_file(args.input, args.failures, args.summary, base_rps=args.rps, num_workers=args.workers)
    except KeyboardInterrupt:
        print("\n[WARN] Proceso interrumpido por el usuario.")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Mostrar tiempo total de ejecución
        script_end_time = time.time()
        total_execution_time = script_end_time - script_start_time
        hours = int(total_execution_time // 3600)
        minutes = int((total_execution_time % 3600) // 60)
        seconds = total_execution_time % 60
        
        print("----------------------------------------------")
        if hours > 0:
            print(f"Tiempo total de ejecución: {hours}h {minutes}m {seconds:.2f}s")
        elif minutes > 0:
            print(f"Tiempo total de ejecución: {minutes}m {seconds:.2f}s")
        else:
            print(f"Tiempo total de ejecución: {seconds:.2f}s")
