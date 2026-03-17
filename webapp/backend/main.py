"""
VTEX Integration Tools — FastAPI Backend

Run with:
    uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from dotenv import dotenv_values, set_key
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

# webapp/backend/main.py → project root is 2 levels up
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Jobs are stored under /tmp/vtex_webapp/{job_id}/
JOBS_BASE = Path("/tmp/vtex_webapp")
JOBS_BASE.mkdir(exist_ok=True)

# Find Python executable (prefer project venv)
_VENV_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python3"
PYTHON_EXEC = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else "python3"

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="VTEX Integration Tools", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory state
# ─────────────────────────────────────────────────────────────────────────────

# job_id → job dict
jobs: Dict[str, Dict[str, Any]] = {}

# job_id → list of connected WebSockets
ws_clients: Dict[str, List[WebSocket]] = {}

# Buffered log messages per job for late-connecting clients
# job_id → list of message dicts
log_buffer: Dict[str, List[Dict]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Tools Configuration
# ─────────────────────────────────────────────────────────────────────────────
#
# Each tool defines:
#   id          – unique string
#   name        – full display name
#   shortName   – short label
#   description – help text
#   category    – "pipeline" | "tools"
#   step        – integer order in pipeline (pipeline tools only)
#   script      – path relative to PROJECT_ROOT
#   requires_vtex – bool: needs .env VTEX credentials
#   inputs      – list of form field definitions (see below)
#
# Input field definition:
#   name      – parameter name (used as key in form data)
#   type      – "file" | "text" | "number" | "checkbox" | "select"
#   label     – display label
#   required  – bool
#   accept    – MIME/extension filter for file inputs
#   default   – default value
#   flag      – CLI flag string (e.g. "--indent"). If absent → positional.
#   position  – positional index (0-based). Used when flag is absent.
#   role      – "input_file" | "output_file" | "param" (default)
#   options   – list of strings for select type

TOOLS: List[Dict[str, Any]] = [
    # ── Pipeline ──────────────────────────────────────────────────────────────
    {
        "id": "step_01",
        "name": "Paso 01 — Convertir archivo a JSON",
        "shortName": "Convertir a JSON",
        "description": "Convierte archivos CSV, XLS, XLSX o XLSB a formato JSON.",
        "category": "pipeline",
        "step": 1,
        "script": "01_csv_to_json/csv_to_json.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo de entrada", "required": True,
             "accept": ".csv,.xls,.xlsx,.xlsb", "position": 0, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "default": "output.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "step_02",
        "name": "Paso 02 — Transformar campos JSON",
        "shortName": "Transformar campos",
        "description": "Normaliza nombres de campos. Separa claves compuestas en campos independientes.",
        "category": "pipeline",
        "step": 2,
        "script": "02_data-transform/transform_json_script.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo JSON de entrada", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "default": "transformed.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "step_03",
        "name": "Paso 03 — Procesar jerarquía de categorías",
        "shortName": "Procesar categorías",
        "description": "Combina CATEGORIA, SUBCATEGORIA y LINEA en una jerarquía unificada con separador '>'.",
        "category": "pipeline",
        "step": 3,
        "script": "03_transform_json_category/transform_json_category.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo JSON de entrada", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "default": "categorized.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
            {"name": "csv_export", "type": "checkbox", "label": "Exportar CSV adicional", "flag": "--csv-export"},
        ],
    },
    {
        "id": "step_04",
        "name": "Paso 04 — Unificar datasets",
        "shortName": "Unificar datasets",
        "description": "Fusiona datos antiguos (campo SKU) con datos nuevos (campo MECA).",
        "category": "pipeline",
        "step": 4,
        "script": "04_unificar_json/unificar_json.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "old_data", "type": "file", "label": "Datos antiguos (.json, campo SKU)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "new_data", "type": "file", "label": "Datos nuevos (.json, campo MECA)", "required": True,
             "accept": ".json", "position": 1, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "default": "unified.json",
             "position": 2, "role": "output_file"},
        ],
    },
    {
        "id": "step_05",
        "name": "Paso 05 — Comparar datasets (detectar faltantes)",
        "shortName": "Detectar faltantes",
        "description": "Identifica registros en el dataset antiguo ausentes en el nuevo (SKU vs RefId).",
        "category": "pipeline",
        "step": 5,
        "script": "05_compare_json_to_csv/compare_json_to_csv.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "old_data", "type": "file", "label": "Datos antiguos (.json)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "new_data", "type": "file", "label": "Datos nuevos (.json)", "required": True,
             "accept": ".json", "position": 1, "role": "input_file"},
            {"name": "output_csv", "type": "text", "label": "CSV de salida", "default": "missing_records.csv",
             "position": 2, "role": "output_file"},
        ],
    },
    {
        "id": "step_06",
        "name": "Paso 06 — Mapear IDs de categorías VTEX",
        "shortName": "Mapear categorías",
        "description": "Consulta API VTEX y asigna DepartmentId y CategoryId a los productos.",
        "category": "pipeline",
        "step": 6,
        "script": "06_map_category_ids/map_category_ids.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON con campo CategoryPath", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo de salida",
             "default": "categorized_with_ids.json", "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "step_07",
        "name": "Paso 07 — Extraer marcas de CSV",
        "shortName": "Extraer marcas",
        "description": "Extrae marcas de CSV (columnas TIPO, SKU, OPCIONES). Crea lookup SKU → Marca.",
        "category": "pipeline",
        "step": 7,
        "script": "07_csv_to_json_marca/csv_to_json_marca.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_csv", "type": "file", "label": "CSV de marcas (columnas: TIPO, SKU, OPCIONES)",
             "required": True, "accept": ".csv", "position": 0, "role": "input_file"},
            {"name": "output_json", "type": "text", "label": "JSON de salida", "default": "marcas.json",
             "position": 1, "role": "output_file"},
        ],
    },
    {
        "id": "step_08",
        "name": "Paso 08 — Resolver BrandId de VTEX",
        "shortName": "Resolver BrandId",
        "description": "Pipeline: SKU → marca (marcas.json) → BrandId VTEX (via API). Matching normalizado.",
        "category": "pipeline",
        "step": 8,
        "script": "08_vtex_brandid_matcher/vtex_brandid_matcher.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "marcas_file", "type": "file", "label": "JSON de marcas (salida paso 07)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "data_file", "type": "file", "label": "JSON de productos (salida paso 06)", "required": True,
             "accept": ".json", "position": 1, "role": "input_file"},
            {"name": "output_json", "type": "text", "label": "JSON de salida", "default": "data_brandid.json",
             "flag": "--output_json", "role": "output_file"},
            {"name": "output_csv", "type": "text", "label": "CSV de no-encontrados",
             "default": "no_brandid_found.csv", "flag": "--output_csv", "role": "output_file"},
            {"name": "output_report", "type": "text", "label": "Reporte Markdown",
             "default": "brand_matching_report.md", "flag": "--output_report", "role": "output_file"},
        ],
    },
    {
        "id": "step_09",
        "name": "Paso 09 — Generar reporte de preparación",
        "shortName": "Reporte VTEX",
        "description": "Clasifica productos: listos / requieren categoría / no se pueden crear.",
        "category": "pipeline",
        "step": 9,
        "script": "09_generate_vtex_report/generate_vtex_report.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de productos (salida paso 08)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Reporte Markdown", "default": "vtex_report.md",
             "flag": "--output", "role": "output_file"},
        ],
    },
    {
        "id": "step_11",
        "name": "Paso 11 — Formatear productos para VTEX",
        "shortName": "Formatear productos",
        "description": "Da formato final para la API de creación VTEX. Genera LinkId SEO-friendly.",
        "category": "pipeline",
        "step": 11,
        "script": "11_vtex_product_format_create/vtex_product_formatter.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON listos para crear (salida paso 09)",
             "required": True, "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo de salida",
             "default": "vtex_formatted.json", "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
            {"name": "include_not_ready", "type": "checkbox", "label": "Incluir productos no listos",
             "flag": "--include-not-ready"},
        ],
    },
    {
        "id": "step_12",
        "name": "Paso 12 — Crear productos en VTEX",
        "shortName": "Crear productos",
        "description": "Creación masiva de productos via API VTEX. Rate limiting 1s, reintentos con backoff.",
        "category": "pipeline",
        "step": 12,
        "script": "12_vtex_product_create/vtex_product_create.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON formateado (salida paso 11)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "delay", "type": "number", "label": "Delay entre requests (seg)", "default": 1.0,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por request (seg)", "default": 30,
             "flag": "--timeout"},
        ],
    },
    {
        "id": "step_13",
        "name": "Paso 13 — Extraer respuestas de creación",
        "shortName": "Extraer respuestas",
        "description": "Extrae el campo 'response' de los resultados de creación de productos.",
        "category": "pipeline",
        "step": 13,
        "script": "13_extract_json_response/extract_response.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de productos exitosos (salida paso 12)",
             "required": True, "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo de salida",
             "default": "extracted_responses.json", "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "step_14",
        "name": "Paso 14 — Transformar a formato SKU",
        "shortName": "Formato SKU",
        "description": "Convierte respuestas de productos al formato SKU VTEX con dimensiones y EAN.",
        "category": "pipeline",
        "step": 14,
        "script": "14_to_vtex_skus/to_vtex_skus.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de respuestas (salida paso 13)",
             "required": True, "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "dimensions", "type": "file", "label": "JSON con dimensiones (Height, Length, Width, WeightKg)",
             "required": True, "accept": ".json", "position": 1, "role": "input_file"},
            {"name": "ean", "type": "file", "label": "JSON con lookup EAN por RefId", "required": True,
             "accept": ".json", "position": 2, "role": "input_file"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "default": "vtex_skus.json",
             "position": 3, "role": "output_file"},
        ],
    },
    {
        "id": "step_15",
        "name": "Paso 15 — Crear SKUs en VTEX",
        "shortName": "Crear SKUs",
        "description": "Creación masiva de SKUs en VTEX. Rate limiting 1s, reintentos con backoff.",
        "category": "pipeline",
        "step": 15,
        "script": "15_vtex_sku_create/vtex_sku_create.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de SKUs (salida paso 14)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "delay", "type": "number", "label": "Delay entre requests (seg)", "default": 1.0,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por request (seg)", "default": 30,
             "flag": "--timeout"},
        ],
    },
    {
        "id": "step_16",
        "name": "Paso 16 — Combinar imágenes con SKUs",
        "shortName": "Combinar imágenes",
        "description": "Combina datos de SKUs con URLs de imágenes desde CSV externo.",
        "category": "pipeline",
        "step": 16,
        "script": "16_merge_sku_images/merge_sku_images.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "json_input", "type": "file", "label": "JSON con productos y RefId", "required": True,
             "accept": ".json", "flag": "--json-input", "role": "input_file"},
            {"name": "csv_input", "type": "file", "label": "CSV con columnas SKU, PRODUCTO, URL",
             "required": True, "accept": ".csv", "flag": "--csv-input", "role": "input_file"},
            {"name": "output_json", "type": "text", "label": "JSON de salida", "default": "sku_images.json",
             "flag": "--output-json", "role": "output_file"},
            {"name": "validate_urls", "type": "checkbox", "label": "Validar URLs via HTTP HEAD",
             "flag": "--validate-urls"},
            {"name": "url_timeout", "type": "number", "label": "Timeout de validación (seg)", "default": 5,
             "flag": "--url-timeout"},
        ],
    },
    {
        "id": "step_17",
        "name": "Paso 17 — Subir imágenes a VTEX",
        "shortName": "Subir imágenes",
        "description": "Carga masiva de imágenes a SKUs VTEX desde URLs.",
        "category": "pipeline",
        "step": 17,
        "script": "17_upload_sku_images/upload_sku_images.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de imágenes (salida paso 16)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "delay", "type": "number", "label": "Delay entre uploads (seg)", "default": 1.0,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por upload (seg)", "default": 30,
             "flag": "--timeout"},
        ],
    },
    {
        "id": "step_18",
        "name": "Paso 18 — Eliminar archivos de SKU",
        "shortName": "Eliminar archivos",
        "description": "Elimina archivos/imágenes asociados a SKUs en VTEX.",
        "category": "pipeline",
        "step": 18,
        "script": "18_delete_sku_files/delete_sku_files.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON con lista de SKU IDs", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "dry_run", "type": "checkbox", "label": "Simular sin ejecutar (dry-run)",
             "flag": "--dry-run"},
        ],
    },
    {
        "id": "step_24",
        "name": "Paso 24 — Crear jerarquía de categorías",
        "shortName": "Crear categorías",
        "description": "Crea estructura 3 niveles en VTEX (Dept→Cat→Subcat). Idempotente. ⚠️ Ejecutar ANTES del paso 06.",
        "category": "pipeline",
        "step": 24,
        "script": "24_vtex_category_creator/vtex_category_creator.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON con campos CATEGORIA, SUBCATEGORIA, LINEA",
             "required": True, "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "dry_run", "type": "checkbox",
             "label": "Simular sin crear (recomendado ejecutar primero)", "flag": "--dry-run"},
            {"name": "delay", "type": "number", "label": "Delay entre creaciones (seg)", "default": 1.0,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por request (seg)", "default": 30,
             "flag": "--timeout"},
        ],
    },
    # ── Utility Tools ─────────────────────────────────────────────────────────
    {
        "id": "tool_xlsb_to_csv",
        "name": "Convertir XLSB a CSV",
        "shortName": "XLSB → CSV",
        "description": "Convierte archivos XLSB a formato CSV.",
        "category": "tools",
        "script": "01_csv_to_json/xlsb_to_csv.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo XLSB", "required": True,
             "accept": ".xlsb", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo CSV de salida", "default": "output.csv",
             "position": 1, "role": "output_file"},
            {"name": "header_row", "type": "number", "label": "Fila de cabeceras (0-based)", "default": 0,
             "flag": "--header-row"},
        ],
    },
    {
        "id": "tool_xlsx_to_csv",
        "name": "Convertir XLSX/XLS a CSV",
        "shortName": "XLSX → CSV",
        "description": "Convierte archivos XLSX o XLS a formato CSV.",
        "category": "tools",
        "script": "01_csv_to_json/xlsx_to_csv.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo XLSX/XLS", "required": True,
             "accept": ".xlsx,.xls", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo CSV de salida", "default": "output.csv",
             "position": 1, "role": "output_file"},
            {"name": "header_row", "type": "number", "label": "Fila de cabeceras (0-based)", "default": 0,
             "flag": "--header-row"},
        ],
    },
    {
        "id": "tool_status_filter",
        "name": "Filtrar por estado",
        "shortName": "Filtrar estado",
        "description": "Filtra registros de CSV o JSON por valor del campo de estado.",
        "category": "tools",
        "script": "19_csv_json_status_filter/csv_json_status_filter.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo de entrada (.csv o .json)", "required": True,
             "accept": ".csv,.json", "position": 0, "role": "input_file"},
            {"name": "status", "type": "text", "label": "Valor de estado a filtrar", "flag": "--status"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "flag": "--output",
             "role": "output_file"},
        ],
    },
    {
        "id": "tool_update_sku_csv",
        "name": "Actualizar SKUs desde CSV",
        "shortName": "Actualizar SKUs",
        "description": "Actualiza SKUs existentes en VTEX desde un CSV con datos actualizados.",
        "category": "tools",
        "script": "20_vtex_update_sku_from_csv/vtex_update_sku_from_csv.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "CSV con datos a actualizar", "required": True,
             "accept": ".csv", "position": 0, "role": "input_file"},
        ],
    },
    {
        "id": "tool_sku_no_image",
        "name": "Encontrar SKUs sin imagen",
        "shortName": "SKUs sin imagen",
        "description": "Identifica SKUs en VTEX que no tienen imágenes asociadas.",
        "category": "tools",
        "script": "21_vtex_sku_no_image_finder/vtex_sku_no_image_finder.py",
        "requires_vtex": True,
        "inputs": [],
    },
    {
        "id": "tool_price_updater",
        "name": "Actualizar precios",
        "shortName": "Actualizar precios",
        "description": "Actualiza precios (costo y venta) de productos en VTEX.",
        "category": "tools",
        "script": "22_vtex_price_updater/vtex_price_updater_cost_optional.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo con datos de precios", "required": True,
             "position": 0, "role": "input_file"},
        ],
    },
    {
        "id": "tool_inventory_uploader",
        "name": "Subir inventario",
        "shortName": "Subir inventario",
        "description": "Carga datos de stock/inventario a VTEX.",
        "category": "tools",
        "script": "23_vtex_inventory_uploader/vtex_inventory_uploader.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo con datos de inventario", "required": True,
             "position": 0, "role": "input_file"},
        ],
    },
    {
        "id": "tool_price_fetcher",
        "name": "Obtener precios de VTEX",
        "shortName": "Obtener precios",
        "description": "Obtiene precios del catálogo VTEX.",
        "category": "tools",
        "script": "29_vtex_price_fetcher/vtex_price_fetcher.py",
        "requires_vtex": True,
        "inputs": [],
    },
    {
        "id": "tool_price_diff",
        "name": "Comparar diferencias de precios",
        "shortName": "Diff de precios",
        "description": "Compara precios entre ERP y VTEX para identificar actualizaciones necesarias.",
        "category": "tools",
        "script": "45_price_diff_filter/price_diff_filter.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "vtex_skus_file", "type": "file", "label": "Referencia de SKUs VTEX", "required": True,
             "position": 0, "role": "input_file"},
            {"name": "erp_prices_file", "type": "file", "label": "Precios ERP (.csv/.xlsx)", "required": True,
             "accept": ".csv,.xlsx", "position": 1, "role": "input_file"},
            {"name": "vtex_prices_file", "type": "file", "label": "Precios VTEX (.csv/.xlsx)", "required": True,
             "accept": ".csv,.xlsx", "position": 2, "role": "input_file"},
            {"name": "output_prefix", "type": "text", "label": "Prefijo para archivos de salida", "position": 3},
            {"name": "dry_run", "type": "checkbox", "label": "Simular sin ejecutar", "flag": "--dry-run"},
        ],
    },
    {
        "id": "tool_xlsx_diff",
        "name": "Comparar archivos XLSX",
        "shortName": "Diff XLSX",
        "description": "Extrae registros nuevos entre dos archivos Excel (headers en fila 2).",
        "category": "tools",
        "script": "46_xlsx_diff_filter/xlsx_diff_filter.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "base_file", "type": "file", "label": "Archivo base (.xlsx)", "required": True,
             "accept": ".xlsx", "position": 0, "role": "input_file"},
            {"name": "new_file", "type": "file", "label": "Archivo nuevo (.xlsx)", "required": True,
             "accept": ".xlsx", "position": 1, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo de salida",
             "default": "new_records.xlsx", "position": 2, "role": "output_file"},
            {"name": "key_column", "type": "text", "label": "Columna clave de comparación",
             "flag": "--key-column"},
            {"name": "sheet", "type": "text", "label": "Nombre de la hoja", "flag": "--sheet"},
            {"name": "verbose", "type": "checkbox", "label": "Logs detallados", "flag": "--verbose"},
        ],
    },
    {
        "id": "tool_dynamodb_to_json",
        "name": "Convertir DynamoDB CSV a JSON",
        "shortName": "DynamoDB → JSON",
        "description": "Deserializa formato AttributeValue de DynamoDB exportado como CSV a JSON plano.",
        "category": "tools",
        "script": "43_dynamodb_to_json/dynamodb_to_json.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "CSV con columna de datos DynamoDB",
             "required": True, "accept": ".csv", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "JSON de salida", "default": "output.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
            {"name": "vtex_data_column", "type": "text", "label": "Nombre de columna de datos",
             "default": "data", "flag": "--vtex-data-column"},
        ],
    },
    {
        "id": "tool_to_dynamojson",
        "name": "Generar JSON para DynamoDB",
        "shortName": "CSV → DynamoDB",
        "description": "Genera JSON formato DynamoDB batch-write desde CSV o Excel. Inferencia automática de tipos.",
        "category": "tools",
        "script": "to_dynamojson/dynamojson_from_tabular.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo de entrada (.csv, .xlsx, .xls)",
             "required": True, "accept": ".csv,.xlsx,.xls", "position": 0, "role": "input_file"},
            {"name": "table_name", "type": "text", "label": "Nombre de la tabla DynamoDB",
             "flag": "--table-name"},
            {"name": "output", "type": "text", "label": "Archivo de salida", "flag": "--output",
             "role": "output_file"},
            {"name": "ndjson", "type": "checkbox", "label": "Formato NDJSON", "flag": "--ndjson"},
            {"name": "all_as_string", "type": "checkbox", "label": "Todo como String",
             "flag": "--all-as-string"},
            {"name": "exclude_cols", "type": "text", "label": "Columnas a excluir (separadas por coma)",
             "flag": "--exclude-cols"},
            {"name": "vtex_data_column", "type": "text", "label": "Columna de datos VTEX",
             "flag": "--vtex-data-column"},
        ],
    },
    {
        "id": "tool_filtrar_sku",
        "name": "Filtrar SKUs por referencia",
        "shortName": "Filtrar SKUs",
        "description": "Compara dos JSON por _SKUReferenceCode. Outputs: coincidencias (JSON) y no-encontrados (CSV).",
        "category": "tools",
        "script": "filtrar_sku/filtrar_sku.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "archivo1", "type": "file", "label": "Referencia con _SkuId (.json)", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "archivo2", "type": "file", "label": "Datos a filtrar (.json)", "required": True,
             "accept": ".json", "position": 1, "role": "input_file"},
            {"name": "tipo", "type": "select", "label": "Tipo de datos", "default": "precios",
             "flag": "--tipo", "options": ["precios", "inventario"]},
        ],
    },
    {
        "id": "tool_translate_keys",
        "name": "Traducir campos a inglés",
        "shortName": "Traducir campos",
        "description": "Traduce campos en español a inglés en un JSON. Elimina duplicados.",
        "category": "tools",
        "script": "translate_keys/translate_keys.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo JSON de entrada", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "JSON de salida", "default": "translated.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "tool_extract_refid_ean",
        "name": "Extraer RefId y EAN",
        "shortName": "Extraer RefId/EAN",
        "description": "Extrae solo los campos RefId y EAN de un JSON de productos.",
        "category": "tools",
        "script": "extract_refid_ean/extract_refid_ean.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "JSON de productos", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "JSON de salida", "default": "refid_ean.json",
             "position": 1, "role": "output_file"},
            {"name": "indent", "type": "number", "label": "Indentación JSON", "default": 4, "flag": "--indent"},
        ],
    },
    {
        "id": "tool_json_to_csv",
        "name": "JSON a CSV",
        "shortName": "JSON → CSV",
        "description": "Convierte un array JSON a CSV usando las claves del objeto como cabeceras.",
        "category": "tools",
        "script": "json_to_csv/json_to_csv.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "Archivo JSON de entrada", "required": True,
             "accept": ".json", "position": 0, "role": "input_file"},
            {"name": "output_file", "type": "text", "label": "Archivo CSV de salida", "default": "output.csv",
             "position": 1, "role": "output_file"},
        ],
    },
]

TOOLS_BY_ID: Dict[str, Dict] = {t["id"]: t for t in TOOLS}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _send_to_buffer(job_id: str, msg: Dict) -> None:
    log_buffer.setdefault(job_id, []).append(msg)


async def _broadcast(job_id: str, msg: Dict) -> None:
    """Broadcast a message to all WebSocket clients watching this job."""
    _send_to_buffer(job_id, msg)
    dead = []
    for ws in ws_clients.get(job_id, []):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.get(job_id, []).remove(ws)


def _get_env() -> Dict[str, str]:
    if ENV_FILE.exists():
        return dict(dotenv_values(str(ENV_FILE)))
    return {}


def _vtex_configured() -> bool:
    env = _get_env()
    return all(env.get(k) for k in ["X-VTEX-API-AppKey", "X-VTEX-API-AppToken", "VTEX_ACCOUNT_NAME"])


def _build_command(tool: Dict, params: Dict[str, str], file_paths: Dict[str, str]) -> List[str]:
    """
    Build the subprocess command list for a tool execution.

    params: field_name → value string
    file_paths: field_name → absolute path of uploaded file
    """
    # Merge all values: file paths take precedence for file inputs
    values: Dict[str, Any] = {}
    for inp in tool["inputs"]:
        name = inp["name"]
        if inp["type"] == "file":
            if name in file_paths:
                values[name] = file_paths[name]
        elif inp["type"] == "checkbox":
            values[name] = name in params and params[name] in ("true", "1", "on", "yes")
        elif inp["type"] == "number":
            raw = params.get(name)
            if raw is not None and raw != "":
                values[name] = raw
            elif "default" in inp:
                values[name] = str(inp["default"])
        else:
            raw = params.get(name)
            if raw is not None and raw != "":
                values[name] = raw
            elif "default" in inp:
                values[name] = str(inp["default"])

    cmd = [PYTHON_EXEC, str(PROJECT_ROOT / tool["script"])]

    # Collect positional args sorted by position
    positional: Dict[int, str] = {}
    for inp in tool["inputs"]:
        name = inp["name"]
        if "position" in inp and "flag" not in inp:
            if name in values and values[name] is not None:
                positional[inp["position"]] = str(values[name])

    for pos in sorted(positional.keys()):
        cmd.append(positional[pos])

    # Flagged args
    for inp in tool["inputs"]:
        name = inp["name"]
        flag = inp.get("flag")
        if not flag:
            continue
        if inp["type"] == "checkbox":
            if values.get(name):
                cmd.append(flag)
        else:
            val = values.get(name)
            if val is not None and str(val) != "":
                cmd.extend([flag, str(val)])

    return cmd


async def _run_job(job_id: str, tool: Dict, cmd: List[str], job_dir: Path) -> None:
    """Run the script as a subprocess and stream output to WebSocket clients."""
    job = jobs[job_id]
    job["status"] = "running"
    job["command"] = cmd

    await _broadcast(job_id, {"type": "status", "status": "running"})
    await _broadcast(job_id, {"type": "log", "stream": "system",
                               "text": f"$ {' '.join(cmd)}\n"})

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        job["pid"] = proc.pid

        async def read_stream(stream, stream_name: str):
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                await _broadcast(job_id, {"type": "log", "stream": stream_name, "text": text})

        await asyncio.gather(
            read_stream(proc.stdout, "stdout"),
            read_stream(proc.stderr, "stderr"),
        )
        await proc.wait()
        exit_code = proc.returncode
    except Exception as exc:
        await _broadcast(job_id, {"type": "log", "stream": "stderr",
                                   "text": f"\n[ERROR] {exc}\n"})
        exit_code = -1

    # Collect output files from job_dir
    output_files = []
    for f in job_dir.iterdir():
        if f.is_file() and not f.name.startswith("_input_"):
            output_files.append(f.name)

    job["exit_code"] = exit_code
    job["status"] = "completed" if exit_code == 0 else "failed"
    job["finished_at"] = datetime.utcnow().isoformat()
    job["output_files"] = output_files

    await _broadcast(job_id, {"type": "outputs", "files": output_files})
    await _broadcast(job_id, {
        "type": "status",
        "status": job["status"],
        "exit_code": exit_code,
    })


# ─────────────────────────────────────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/tools")
def get_tools():
    """Return the full tools configuration."""
    return {"tools": TOOLS}


@app.get("/api/tools/{tool_id}")
def get_tool(tool_id: str):
    tool = TOOLS_BY_ID.get(tool_id)
    if not tool:
        return JSONResponse(status_code=404, content={"error": "Tool not found"})
    return tool


@app.post("/api/tools/{tool_id}/run")
async def run_tool(tool_id: str, request: Request):
    """
    Start executing a tool.

    Multipart form data:
      params         – JSON string: {field_name: value}
      file__{name}   – uploaded file for field `name` (e.g. file__input_file)
    """
    tool = TOOLS_BY_ID.get(tool_id)
    if not tool:
        return JSONResponse(status_code=404, content={"error": "Tool not found"})

    if tool.get("requires_vtex") and not _vtex_configured():
        return JSONResponse(
            status_code=400,
            content={"error": "VTEX credentials not configured. Go to Settings."},
        )

    job_id = str(uuid.uuid4())
    job_dir = JOBS_BASE / job_id
    job_dir.mkdir(parents=True)

    form = await request.form()

    # Parse params JSON
    try:
        params_dict: Dict[str, str] = json.loads(form.get("params", "{}"))  # type: ignore
    except Exception:
        params_dict = {}

    # Save uploaded files — they arrive as file__{field_name}
    file_paths: Dict[str, str] = {}
    for key, value in form.multi_items():
        if key.startswith("file__") and isinstance(value, UploadFile) and value.filename:
            field_name = key[6:]  # strip "file__"
            safe_name = f"_input_{value.filename}"
            dest = job_dir / safe_name
            content = await value.read()
            dest.write_bytes(content)
            file_paths[field_name] = str(dest)

    # For output files: redirect them into job_dir
    for inp in tool["inputs"]:
        if inp.get("role") == "output_file":
            name = inp["name"]
            filename = params_dict.get(name) or inp.get("default", f"{name}_output")
            # Use just the basename, placed in job_dir
            out_path = job_dir / Path(filename).name
            params_dict[name] = str(out_path)

    cmd = _build_command(tool, params_dict, file_paths)

    # Create job record
    jobs[job_id] = {
        "id": job_id,
        "tool_id": tool_id,
        "tool_name": tool["name"],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "exit_code": None,
        "command": cmd,
        "output_files": [],
        "job_dir": str(job_dir),
    }
    log_buffer[job_id] = []

    # Run in background
    asyncio.create_task(_run_job(job_id, tool, cmd, job_dir))

    return {"job_id": job_id}


@app.get("/api/jobs")
def list_jobs():
    job_list = sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return {"jobs": job_list[:50]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    return job


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    job = jobs.pop(job_id, None)
    if job:
        job_dir = Path(job["job_dir"])
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        log_buffer.pop(job_id, None)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/files/{filename}")
def download_file(job_id: str, filename: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    path = Path(job["job_dir"]) / filename
    if not path.exists() or not path.is_file():
        return JSONResponse(status_code=404, content={"error": "File not found"})
    return FileResponse(path=str(path), filename=filename)


# Config ──────────────────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config():
    env = _get_env()
    # Mask token
    if "X-VTEX-API-AppToken" in env and env["X-VTEX-API-AppToken"]:
        masked = env["X-VTEX-API-AppToken"]
        env["X-VTEX-API-AppToken"] = masked[:4] + "●●●●●●●●" if len(masked) > 4 else "●●●●●●●●"
    return {
        "configured": _vtex_configured(),
        "values": env,
    }


@app.put("/api/config")
async def update_config(body: Dict[str, str]):
    ENV_FILE.touch(exist_ok=True)
    for key, value in body.items():
        set_key(str(ENV_FILE), key, value)
    return {"ok": True, "configured": _vtex_configured()}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    ws_clients.setdefault(job_id, []).append(websocket)

    # Replay buffered messages for this job
    for msg in log_buffer.get(job_id, []):
        try:
            await websocket.send_json(msg)
        except Exception:
            break

    # If job already finished, send final status
    job = jobs.get(job_id)
    if job and job["status"] in ("completed", "failed"):
        try:
            await websocket.send_json({"type": "status", "status": job["status"],
                                        "exit_code": job.get("exit_code")})
        except Exception:
            pass

    try:
        while True:
            # Keep connection alive; client may send pings
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        clients = ws_clients.get(job_id, [])
        if websocket in clients:
            clients.remove(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
