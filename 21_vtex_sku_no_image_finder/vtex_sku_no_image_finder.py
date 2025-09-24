#!/usr/bin/env python3
"""
VTEX — Find SKUs without images (with logging, resume & rate delay) and export to CSV
-----------------------------------------------------------------------------------
Este script recorre todos los SKU de una cuenta VTEX, detecta cuáles no tienen imágenes
asociadas, obtiene sus datos (incluyendo RefId) y exporta la lista a un archivo CSV.

Características:
- Logging estructurado en consola y archivo opcional
- Reintentos con backoff ante errores 429/5xx y respeto a cabecera X-RateLimit-Reset
- Reanudación con archivo checkpoint (JSON)
- Escritura de CSV idempotente (mantiene encabezado)
- Retardo configurable entre requests para evitar saturar el servidor

Salida CSV:
- SkuId
- RefId
- ProductId
- Name
- ImageCount

Requisitos:
- Python 3.8+
- requests (`pip install requests`)
- python-dotenv (`pip install python-dotenv`)
- Archivo .env en la raíz del proyecto con credenciales VTEX

Configuración del archivo .env:
Crea un archivo .env en la raíz del proyecto con:
VTEX_ACCOUNT_NAME=micuenta
X-VTEX-API-AppKey=MI_APP_KEY
X-VTEX-API-AppToken=MI_APP_TOKEN
VTEX_ENVIRONMENT=vtexcommercestable.com.br

Cómo ejecutarlo:
1. Guarda este archivo como `vtex_sku_no_image_finder.py`
2. Instala dependencias:
   pip install requests python-dotenv
3. Configura el archivo .env en la raíz del proyecto
4. Ejecuta:
   python vtex_sku_no_image_finder.py \
       --page-size 1000 \
       --output sin_imagenes.csv \
       --log-file ejecucion.log \
       --checkpoint progreso.json \
       --delay 0.2

Notas:
- Las credenciales VTEX se leen automáticamente del archivo .env en la raíz
- `--delay` define segundos entre requests (por defecto 0.2s).
- Puedes detener y reanudar el script sin perder progreso gracias a `--checkpoint`.
"""
from __future__ import annotations
import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

HEADER = ["SkuId", "RefId", "ProductId", "Name", "ImageCount"]


def setup_logger(log_file: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger("vtex-no-images")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


class VTEXClient:
    def __init__(self, account: str, environment: str, app_key: str, app_token: str, timeout: int = 30, logger: Optional[logging.Logger] = None, delay_between_requests: float = 0.2):
        self.account = account
        self.environment = environment
        self.base = f"https://{account}.{environment}"
        self.session = requests.Session()
        self.session.headers.update({
            "X-VTEX-API-AppKey": app_key,
            "X-VTEX-API-AppToken": app_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "sku-no-image-finder/1.2"
        })
        self.timeout = timeout
        self.log = logger or logging.getLogger("vtex-no-images")
        self.delay = delay_between_requests

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        max_attempts = 6
        backoff = 1.6
        delay_backoff = 0.8
        for attempt in range(1, max_attempts + 1):
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            if resp.status_code < 400:
                if self.delay > 0:
                    time.sleep(self.delay)
                return resp

            self.log.warning("HTTP %s on %s (attempt %s/%s)", resp.status_code, url, attempt, max_attempts)

            if resp.status_code in (429, 500, 502, 503, 504):
                sleep_for = delay_backoff
                try:
                    rl = float(resp.headers.get("X-RateLimit-Reset", "0") or 0)
                    if rl > 0:
                        sleep_for = max(sleep_for, rl)
                except Exception:
                    pass
                if attempt < max_attempts:
                    self.log.info("Backing off for %.2fs", sleep_for)
                    time.sleep(sleep_for)
                    delay_backoff *= backoff
                    continue

            try:
                resp.raise_for_status()
            except Exception:
                msg = f"HTTP {resp.status_code} for {url}: {resp.text[:800]}"
                self.log.error(msg)
                raise RuntimeError(msg)
        raise RuntimeError(f"Failed after {max_attempts} attempts: {url}")

    def list_sku_ids(self, page: int, page_size: int) -> List[int]:
        url = f"{self.base}/api/catalog_system/pvt/sku/stockkeepingunitids?page={page}&pagesize={page_size}"
        r = self._request("GET", url)
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response for SKU IDs (page {page}): {data}")
        return [int(v) for v in data if str(v).isdigit()]

    def get_sku_details(self, sku_id: int) -> Dict:
        url = f"{self.base}/api/catalog_system/pvt/sku/stockkeepingunitbyid/{sku_id}"
        r = self._request("GET", url)
        return r.json()

    def list_sku_files(self, sku_id: int) -> List[Dict]:
        url = f"{self.base}/api/catalog/pvt/stockkeepingunit/{sku_id}/file"
        r = self._request("GET", url)
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), list) else []


class Checkpoint:
    def __init__(self, path: Optional[str]):
        self.path = Path(path) if path else None
        self.state = {"page": 1, "index": 0}
        if self.path and self.path.exists():
            try:
                self.state.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass

    @property
    def page(self) -> int:
        return int(self.state.get("page", 1))

    @property
    def index(self) -> int:
        return int(self.state.get("index", 0))

    def save(self, page: int, index: int) -> None:
        if not self.path:
            return
        self.state["page"] = page
        self.state["index"] = index
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def write_csv_header_if_needed(output_path: str) -> None:
    need_header = not os.path.exists(output_path) or os.path.getsize(output_path) == 0
    if need_header:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)


def append_row(output_path: str, row: List) -> None:
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def find_and_export(client: VTEXClient, page_size: int, output_path: str, ckpt: Checkpoint, logger: logging.Logger) -> int:
    write_csv_header_if_needed(output_path)
    total_found = 0
    total_processed = 0
    page = ckpt.page
    start_time = time.time()

    logger.info("🚀 Iniciando búsqueda de SKUs sin imágenes")
    logger.info("📁 Archivo de salida: %s", output_path)
    logger.info("📊 Tamaño de página: %s SKUs", page_size)
    
    if ckpt.page > 1 or ckpt.index > 0:
        logger.info("🔄 Reanudando desde página %s, índice %s", ckpt.page, ckpt.index)

    while True:
        page_start_time = time.time()
        logger.info("📄 Obteniendo lista de SKUs para página %s...", page)
        
        ids = client.list_sku_ids(page, page_size)
        if not ids:
            logger.info("✅ No hay más SKUs en página %s. Proceso terminado.", page)
            break

        start_index = ckpt.index if ckpt.page == page else 0
        skus_in_page = len(ids) - start_index
        logger.info("📋 Página %s: %s SKUs totales, procesando desde índice %s (%s SKUs restantes)", 
                   page, len(ids), start_index, skus_in_page)

        page_found = 0
        for i in range(start_index, len(ids)):
            sku_id = ids[i]
            current_sku_index = i + 1
            
            # Log de progreso cada 50 SKUs o al final de la página
            if (current_sku_index % 50 == 0) or (current_sku_index == len(ids)):
                progress_pct = (current_sku_index / len(ids)) * 100
                elapsed = time.time() - page_start_time
                logger.info("⏳ Página %s: %s/%s SKUs procesados (%.1f%%) - %.1fs transcurridos", 
                           page, current_sku_index, len(ids), progress_pct, elapsed)
            
            try:
                files = client.list_sku_files(sku_id)
                img_count = len(files)
                total_processed += 1
                
                if img_count == 0:
                    details = client.get_sku_details(sku_id)
                    ref_id = details.get("ProductRefId", "")
                    product_name = (details.get("Name") or "").strip()
                    
                    append_row(output_path, [sku_id, ref_id, details.get("ProductId", ""), product_name, img_count])
                    total_found += 1
                    page_found += 1
                    logger.info("❌ SKU %s sin imágenes (RefId: %s) — registrado [Total sin imágenes: %s]", 
                               sku_id, ref_id or "N/A", total_found)
                else:
                    logger.debug("✅ SKU %s tiene %s imagen(es)", sku_id, img_count)
                    
            except Exception as e:
                logger.error("💥 Error procesando SKU %s: %s", sku_id, e)
                ckpt.save(page, i)
                raise
            ckpt.save(page, i + 1)

        page_time = time.time() - page_start_time
        total_time = time.time() - start_time
        
        logger.info("📊 Página %s completada: %s SKUs sin imágenes encontrados en %.1fs", 
                   page, page_found, page_time)
        logger.info("📈 Progreso total: %s SKUs procesados, %s sin imágenes (%.1f%%) - %.1fm transcurridos", 
                   total_processed, total_found, 
                   (total_found/total_processed*100) if total_processed > 0 else 0, 
                   total_time/60)

        ckpt.save(page + 1, 0)
        page += 1

    total_time = time.time() - start_time
    logger.info("🎉 Proceso completado en %.1fm", total_time/60)
    logger.info("📊 Resumen final: %s SKUs procesados, %s sin imágenes (%.1f%%)", 
               total_processed, total_found, 
               (total_found/total_processed*100) if total_processed > 0 else 0)

    return total_found


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find VTEX SKUs without images and export to CSV (logs, resume, delay)")
    p.add_argument("--page-size", type=int, default=1000)
    p.add_argument("--output", default="skus_without_images.csv")
    p.add_argument("--log-file", default=None)
    p.add_argument("--checkpoint", default="vtex_no_images_checkpoint.json")
    p.add_argument("--delay", type=float, default=0.2, help="Delay in seconds between requests (default 0.2s)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    # Load environment variables from root .env file
    load_dotenv()
    
    # Get VTEX credentials from environment
    account = os.getenv('VTEX_ACCOUNT_NAME')
    app_key = os.getenv('X-VTEX-API-AppKey')
    app_token = os.getenv('X-VTEX-API-AppToken')
    environment = os.getenv('VTEX_ENVIRONMENT', 'vtexcommercestable.com.br')
    
    # Ensure environment has the correct format
    if environment and not environment.endswith('.com.br'):
        environment = f"{environment}.com.br"
    
    if not all([account, app_key, app_token]):
        print("❌ Error: Missing VTEX credentials in .env file")
        print("Required environment variables:")
        print("- VTEX_ACCOUNT_NAME")
        print("- X-VTEX-API-AppKey")
        print("- X-VTEX-API-AppToken")
        print("- VTEX_ENVIRONMENT (optional, defaults to vtexcommercestable.com.br)")
        return 1
    
    args = parse_args(argv)
    logger = setup_logger(args.log_file)
    
    # Log initial configuration
    logger.info("🔧 Configuración inicial:")
    logger.info("   📦 Cuenta VTEX: %s", account)
    logger.info("   🌍 Entorno: %s", environment)
    logger.info("   📄 Tamaño de página: %s", args.page_size)
    logger.info("   📁 Archivo de salida: %s", args.output)
    logger.info("   ⏱️  Delay entre requests: %ss", args.delay)
    if args.log_file:
        logger.info("   📝 Log file: %s", args.log_file)
    if args.checkpoint:
        logger.info("   💾 Checkpoint file: %s", args.checkpoint)
    
    ckpt = Checkpoint(args.checkpoint)
    client = VTEXClient(account, environment, app_key, app_token, logger=logger, delay_between_requests=args.delay)

    try:
        total = find_and_export(client, args.page_size, args.output, ckpt, logger)
    except KeyboardInterrupt:
        logger.warning("⚠️  Proceso interrumpido por el usuario. Progreso guardado en checkpoint.")
        logger.info("💡 Para reanudar, ejecuta el script nuevamente con los mismos parámetros.")
        return 130
    except Exception:
        logger.exception("💥 Ejecución detenida por error. Para reanudar, ejecuta el script nuevamente.")
        return 2

    logger.info("✅ Proceso completado exitosamente!")
    logger.info("📋 SKUs sin imágenes encontrados: %s", total)
    logger.info("📁 Archivo CSV generado: %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
