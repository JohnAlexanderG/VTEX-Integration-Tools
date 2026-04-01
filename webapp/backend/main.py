"""
VTEX Integration Tools — FastAPI Backend

Run with:
    uvicorn main:app --reload --port 8000
"""

import asyncio
import ftplib
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from dotenv import dotenv_values, load_dotenv, set_key
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

# Cargar .env desde la raíz del proyecto (3 niveles arriba de webapp/backend/)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from database import Base, engine, get_db                                    # noqa: E402
from models import Tenant, TenantConfig, User, UserRole                       # noqa: E402
from auth import (                                                             # noqa: E402
    create_access_token, decrypt_value, encrypt_value,
    hash_password, verify_password,
)
from dependencies import get_current_user, require_admin, require_superadmin  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

# webapp/backend/main.py → project root is 2 levels up
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Jobs are stored under /tmp/vtex_webapp/{job_id}/
JOBS_BASE = Path("/tmp/vtex_webapp")
JOBS_BASE.mkdir(exist_ok=True)

TEMPLATES_DIR = Path(__file__).parent / "templates"

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


@app.on_event("startup")
async def _startup():
    """Crear tablas si no existen al iniciar la aplicación."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        "name": "Consultar precios VTEX (Price Fetcher)",
        "shortName": "Consultar precios",
        "description": "Consulta la API de pricing VTEX para cada referenceCode en un CSV. Exporta un CSV con precios encontrados y un reporte Markdown con estadísticas.",
        "category": "tools",
        "script": "29_vtex_price_fetcher/vtex_price_fetcher.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "CSV con referenceCodes", "required": True,
             "accept": ".csv", "position": 0, "role": "input_file"},
            {"name": "output", "type": "text", "label": "CSV de salida (precios encontrados)",
             "default": "price_results.csv", "flag": "--output", "role": "output_file"},
            {"name": "report", "type": "text", "label": "Reporte Markdown",
             "default": "price_report.md", "flag": "--report", "role": "output_file"},
            {"name": "column", "type": "text", "label": "Columna de referenceCodes en el CSV",
             "default": "referenceCode", "flag": "--column"},
            {"name": "delay", "type": "number", "label": "Delay entre requests (seg)", "default": 0.2,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por request (seg)", "default": 30,
             "flag": "--timeout"},
        ],
    },
    {
        "id": "tool_price_deleter",
        "name": "Eliminar precios VTEX (Price Deleter)",
        "shortName": "Eliminar precios",
        "description": "Ejecuta DELETE en la API de pricing VTEX para cada referenceCode único del CSV generado por el Price Fetcher. Soporta modo dry-run para simular sin eliminar.",
        "category": "tools",
        "script": "29_vtex_price_fetcher/vtex_price_deleter.py",
        "requires_vtex": True,
        "inputs": [
            {"name": "input_file", "type": "file", "label": "CSV de precios (salida del Price Fetcher)",
             "required": True, "accept": ".csv", "position": 0, "role": "input_file"},
            {"name": "report", "type": "text", "label": "Reporte Markdown",
             "default": "price_delete_report.md", "flag": "--report", "role": "output_file"},
            {"name": "column", "type": "text", "label": "Columna de referenceCodes en el CSV",
             "default": "referenceCode", "flag": "--column"},
            {"name": "delay", "type": "number", "label": "Delay entre requests (seg)", "default": 0.5,
             "flag": "--delay"},
            {"name": "timeout", "type": "number", "label": "Timeout por request (seg)", "default": 30,
             "flag": "--timeout"},
            {"name": "dry_run", "type": "checkbox", "label": "Simular sin eliminar (dry-run)",
             "flag": "--dry-run"},
        ],
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
    {
        "id": "step_44",
        "name": "Paso 44 — Filtrar diferencias de inventario",
        "shortName": "Diferencias de inventario",
        "description": "Compara inventario ERP completo vs inventario VTEX actual. Exporta CSV y NDJSON con registros que necesitan actualización.",
        "category": "tools",
        "script": "44_stock_diff_filter/stock_diff_filter.py",
        "requires_vtex": False,
        "inputs": [
            {"name": "vtex_file", "type": "file",
             "label": "SKUs VTEX (.xls/.xlsx/.csv — cols: _SKUReferenceCode, _SkuId)",
             "required": True, "accept": ".xls,.xlsx,.csv", "position": 0, "role": "input_file"},
            {"name": "complete_file", "type": "file",
             "label": "Inventario completo ERP (.csv — cols: CODIGO SKU, CODIGO SUCURSAL, EXISTENCIA)",
             "required": True, "accept": ".csv", "position": 1, "role": "input_file"},
            {"name": "vtex_inventory_file", "type": "file",
             "label": "Inventario actual VTEX (.xls/.xlsx/.csv — cols: RefId, WarehouseId, TotalQuantity)",
             "required": True, "accept": ".xls,.xlsx,.csv", "position": 2, "role": "input_file"},
            {"name": "output_prefix", "type": "text",
             "label": "Prefijo de archivos de salida",
             "default": "stock_diff", "position": 3, "role": "output_file"},
            {"name": "processed", "type": "file",
             "label": "Inventario ya procesado (opcional, CSV — deduplicación extra)",
             "required": False, "accept": ".csv", "flag": "--processed", "role": "input_file"},
            {"name": "dry_run", "type": "checkbox",
             "label": "Dry run (analizar sin escribir archivos de salida)",
             "flag": "--dry-run"},
            {"name": "verbose", "type": "checkbox",
             "label": "Verbose (logs detallados con muestras de datos)",
             "flag": "--verbose"},
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


async def _run_job(
    job_id: str,
    tool: Dict,
    cmd: List[str],
    job_dir: Path,
    tenant_env: Optional[Dict[str, str]] = None,
) -> None:
    """Run the script as a subprocess and stream output to WebSocket clients."""
    job = jobs[job_id]
    job["status"] = "running"
    job["command"] = cmd

    await _broadcast(job_id, {"type": "status", "status": "running"})
    await _broadcast(job_id, {"type": "log", "stream": "system",
                               "text": f"$ {' '.join(cmd)}\n"})

    # Las credenciales del tenant sobreescriben las del entorno global
    subprocess_env = {**os.environ, "PYTHONUNBUFFERED": "1", **(tenant_env or {})}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=subprocess_env,
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
# Helpers internos para tenant config
# ─────────────────────────────────────────────────────────────────────────────

async def _get_tenant_config(tenant_id: int, db: AsyncSession) -> Optional[TenantConfig]:
    result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


def _build_tenant_env(tc: Optional[TenantConfig]) -> Dict[str, str]:
    """Construye el dict de env vars para el subprocess a partir del TenantConfig."""
    env: Dict[str, str] = {}
    if not tc:
        return env
    mapping = {
        "X-VTEX-API-AppKey":     tc.vtex_api_key,
        "X-VTEX-API-AppToken":   tc.vtex_api_token,
        "VTEX_ACCOUNT_NAME":     tc.vtex_account_name,
        "VTEX_ENVIRONMENT":      tc.vtex_environment,
        "FTP_SERVER":            tc.ftp_server,
        "FTP_USER":              tc.ftp_user,
        "FTP_PASSWORD":          tc.ftp_password,
        "FTP_PORT":              str(tc.ftp_port) if tc.ftp_port else None,
        "LAMBDA1_FUNCTION_NAME": tc.lambda_function,
        "AWS_REGION":            tc.aws_region,
    }
    # Campos que van cifrados con Fernet
    encrypted_fields = {"X-VTEX-API-AppToken", "FTP_PASSWORD"}
    for key, value in mapping.items():
        if value:
            env[key] = decrypt_value(value) if key in encrypted_fields else value
    return env


def _tenant_vtex_configured(tc: Optional[TenantConfig]) -> bool:
    return bool(tc and tc.vtex_api_key and tc.vtex_api_token and tc.vtex_account_name)


def _tenant_ftp_configured(tc: Optional[TenantConfig]) -> bool:
    return bool(tc and tc.ftp_server and tc.ftp_user and tc.ftp_password)


# ─────────────────────────────────────────────────────────────────────────────
# Auth endpoints  (públicos — sin JWT requerido)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/auth/tenants")
async def list_tenants_public(db: AsyncSession = Depends(get_db)):
    """Lista tenants activos para el selector de login."""
    result = await db.execute(
        select(Tenant.slug, Tenant.name).where(Tenant.is_active == True)
    )
    rows = result.all()
    return {"tenants": [{"slug": r.slug, "name": r.name} for r in rows]}


@app.post("/auth/login")
async def login(body: Dict[str, str], db: AsyncSession = Depends(get_db)):
    """
    Login con username + password + tenant_slug.
    Retorna un JWT con user_id, tenant_id y role.
    """
    username    = (body.get("username") or "").strip()
    password    = body.get("password") or ""
    tenant_slug = (body.get("tenant_slug") or "").strip()

    # Buscar tenant
    t_result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active == True)
    )
    tenant = t_result.scalar_one_or_none()
    if not tenant:
        return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

    # Buscar usuario dentro del tenant
    u_result = await db.execute(
        select(User).where(
            User.tenant_id == tenant.id,
            User.username  == username,
            User.is_active == True,
        )
    )
    user = u_result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return JSONResponse(status_code=401, content={"error": "Credenciales incorrectas"})

    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id":          user.id,
            "username":    user.username,
            "email":       user.email,
            "role":        user.role.value,
            "tenant_id":   user.tenant_id,
            "tenant_slug": tenant.slug,
            "tenant_name": tenant.name,
        },
    }


@app.get("/auth/me")
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = t_result.scalar_one_or_none()
    return {
        "id":          current_user.id,
        "username":    current_user.username,
        "email":       current_user.email,
        "role":        current_user.role.value,
        "tenant_id":   current_user.tenant_id,
        "tenant_slug": tenant.slug if tenant else None,
        "tenant_name": tenant.name if tenant else None,
    }


@app.post("/auth/change-password")
async def change_password(
    body: Dict[str, str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current  = body.get("current_password", "")
    new_pass = body.get("new_password", "")
    if not verify_password(current, current_user.hashed_password):
        return JSONResponse(status_code=400, content={"error": "Contraseña actual incorrecta"})
    if len(new_pass) < 8:
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos 8 caracteres"})
    await db.execute(
        sa_update(User).where(User.id == current_user.id).values(hashed_password=hash_password(new_pass))
    )
    await db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Gestión de usuarios  (admin de su tenant / superadmin global)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/users")
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin ve usuarios de su tenant. Superadmin puede ver todos."""
    query = select(User, Tenant.slug, Tenant.name).join(Tenant, User.tenant_id == Tenant.id)
    if current_user.role != UserRole.superadmin:
        query = query.where(User.tenant_id == current_user.tenant_id)
    rows = (await db.execute(query)).all()
    return {
        "users": [
            {
                "id":          r.User.id,
                "username":    r.User.username,
                "email":       r.User.email,
                "role":        r.User.role.value,
                "is_active":   r.User.is_active,
                "tenant_id":   r.User.tenant_id,
                "tenant_slug": r.slug,
                "tenant_name": r.name,
                "created_at":  r.User.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@app.post("/api/users")
async def create_user(
    body: Dict[str, Any],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    email    = (body.get("email") or "").strip() or None
    role_str = body.get("role", "operator")

    # Validaciones
    if not username or not password:
        return JSONResponse(status_code=400, content={"error": "username y password son requeridos"})
    if len(password) < 8:
        return JSONResponse(status_code=400, content={"error": "La contraseña debe tener al menos 8 caracteres"})

    # Rol: admin solo puede crear operator/admin dentro de su tenant
    try:
        role = UserRole(role_str)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"Rol inválido: {role_str}"})
    if current_user.role == UserRole.admin and role == UserRole.superadmin:
        return JSONResponse(status_code=403, content={"error": "No puedes crear un superadmin"})

    # Tenant: admin usa el suyo, superadmin puede especificar tenant_id
    tenant_id = current_user.tenant_id
    if current_user.role == UserRole.superadmin and "tenant_id" in body:
        tenant_id = int(body["tenant_id"])

    # Verificar duplicado
    dup = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.username == username)
    )
    if dup.scalar_one_or_none():
        return JSONResponse(status_code=409, content={"error": "El usuario ya existe en este tenant"})

    new_user = User(
        tenant_id=tenant_id,
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"ok": True, "id": new_user.id}


@app.put("/api/users/{user_id}")
async def update_user(
    user_id: int,
    body: Dict[str, Any],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        return JSONResponse(status_code=404, content={"error": "Usuario no encontrado"})
    # Admin solo puede modificar usuarios de su tenant
    if current_user.role == UserRole.admin and target.tenant_id != current_user.tenant_id:
        return JSONResponse(status_code=403, content={"error": "Sin permisos"})

    if "is_active" in body:
        target.is_active = bool(body["is_active"])
    if "email" in body:
        target.email = body["email"] or None
    if "role" in body:
        try:
            new_role = UserRole(body["role"])
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Rol inválido"})
        if current_user.role == UserRole.admin and new_role == UserRole.superadmin:
            return JSONResponse(status_code=403, content={"error": "No puedes asignar superadmin"})
        target.role = new_role
    if "password" in body and body["password"]:
        if len(body["password"]) < 8:
            return JSONResponse(status_code=400, content={"error": "Contraseña muy corta"})
        target.hashed_password = hash_password(body["password"])

    await db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Gestión de tenants  (solo superadmin)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/tenants")
async def list_tenants(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Tenant))).scalars().all()
    return {
        "tenants": [
            {
                "id":         t.id,
                "name":       t.name,
                "slug":       t.slug,
                "is_active":  t.is_active,
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ]
    }


@app.post("/api/tenants")
async def create_tenant(
    body: Dict[str, Any],
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    name = (body.get("name") or "").strip()
    slug = (body.get("slug") or "").strip().lower()
    if not name or not slug:
        return JSONResponse(status_code=400, content={"error": "name y slug son requeridos"})
    dup = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if dup.scalar_one_or_none():
        return JSONResponse(status_code=409, content={"error": "El slug ya existe"})
    tenant = Tenant(name=name, slug=slug)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return {"ok": True, "id": tenant.id}


@app.put("/api/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    body: Dict[str, Any],
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return JSONResponse(status_code=404, content={"error": "Tenant no encontrado"})
    if "name" in body:
        tenant.name = body["name"]
    if "is_active" in body:
        tenant.is_active = bool(body["is_active"])
    await db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# REST Endpoints — Tools y Jobs (protegidos por JWT)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/tools")
def get_tools(current_user: User = Depends(get_current_user)):
    """Return the full tools configuration."""
    return {"tools": TOOLS}


@app.get("/api/tools/{tool_id}")
def get_tool(tool_id: str, current_user: User = Depends(get_current_user)):
    tool = TOOLS_BY_ID.get(tool_id)
    if not tool:
        return JSONResponse(status_code=404, content={"error": "Tool not found"})
    return tool


@app.get("/api/tools/{tool_id}/template/{input_name}")
def download_template(
    tool_id: str,
    input_name: str,
    current_user: User = Depends(get_current_user),
):
    """Return a downloadable template file for a tool's file input."""
    filename_base = f"{tool_id}_{input_name}"
    for ext in (".csv", ".json"):
        path = TEMPLATES_DIR / (filename_base + ext)
        if path.exists():
            return FileResponse(path, filename=path.name, media_type="application/octet-stream")
    return JSONResponse(status_code=404, content={"error": "Template not found"})


@app.post("/api/tools/{tool_id}/run")
async def run_tool(
    tool_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start executing a tool.

    Multipart form data:
      params         – JSON string: {field_name: value}
      file__{name}   – uploaded file for field `name` (e.g. file__input_file)
    """
    tool = TOOLS_BY_ID.get(tool_id)
    if not tool:
        return JSONResponse(status_code=404, content={"error": "Tool not found"})

    # Obtener config del tenant actual
    tc = await _get_tenant_config(current_user.tenant_id, db)
    tenant_env = _build_tenant_env(tc)

    if tool.get("requires_vtex") and not _tenant_vtex_configured(tc):
        return JSONResponse(
            status_code=400,
            content={"error": "Credenciales VTEX no configuradas. Ve a Configuración."},
        )

    job_id  = str(uuid.uuid4())
    # Jobs aislados por tenant: /tmp/vtex_webapp/{tenant_id}/{job_id}/
    job_dir = JOBS_BASE / str(current_user.tenant_id) / job_id
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
        if key.startswith("file__") and isinstance(value, StarletteUploadFile):
            field_name = key[6:]  # strip "file__"
            filename   = value.filename or field_name
            safe_name  = f"_input_{filename}"
            dest       = job_dir / safe_name
            content    = await value.read()
            dest.write_bytes(content)
            file_paths[field_name] = str(dest)

    # Validate required file inputs are present
    for inp in tool["inputs"]:
        if inp.get("type") == "file" and inp.get("required") and inp["name"] not in file_paths:
            return JSONResponse(
                status_code=400,
                content={"error": f"El archivo requerido '{inp['label']}' no fue recibido. Por favor vuelve a seleccionar el archivo e intenta de nuevo."},
            )

    # For output files: redirect them into job_dir
    for inp in tool["inputs"]:
        if inp.get("role") == "output_file":
            name     = inp["name"]
            filename = params_dict.get(name) or inp.get("default", f"{name}_output")
            out_path = job_dir / Path(filename).name
            params_dict[name] = str(out_path)

    cmd = _build_command(tool, params_dict, file_paths)

    # Create job record (incluye tenant_id y user_id para aislamiento)
    jobs[job_id] = {
        "id":          job_id,
        "tenant_id":   current_user.tenant_id,
        "user_id":     current_user.id,
        "tool_id":     tool_id,
        "tool_name":   tool["name"],
        "status":      "pending",
        "created_at":  datetime.utcnow().isoformat(),
        "finished_at": None,
        "exit_code":   None,
        "command":     cmd,
        "output_files": [],
        "job_dir":     str(job_dir),
    }
    log_buffer[job_id] = []

    # Run in background con las credenciales del tenant
    asyncio.create_task(_run_job(job_id, tool, cmd, job_dir, tenant_env))

    return {"job_id": job_id}


@app.get("/api/jobs")
def list_jobs(current_user: User = Depends(get_current_user)):
    """Lista jobs. Superadmin ve todos; los demás solo los de su tenant."""
    all_jobs = sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)
    if current_user.role == UserRole.superadmin:
        visible = all_jobs
    else:
        visible = [j for j in all_jobs if j.get("tenant_id") == current_user.tenant_id]
    return {"jobs": visible[:50]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    # Verificar que el job pertenece al tenant del usuario
    if current_user.role != UserRole.superadmin and job.get("tenant_id") != current_user.tenant_id:
        return JSONResponse(status_code=403, content={"error": "Sin permisos"})
    return job


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job:
        return {"ok": True}
    if current_user.role != UserRole.superadmin and job.get("tenant_id") != current_user.tenant_id:
        return JSONResponse(status_code=403, content={"error": "Sin permisos"})
    jobs.pop(job_id, None)
    job_dir = Path(job["job_dir"])
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    log_buffer.pop(job_id, None)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/files/{filename}")
def download_file(
    job_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if current_user.role != UserRole.superadmin and job.get("tenant_id") != current_user.tenant_id:
        return JSONResponse(status_code=403, content={"error": "Sin permisos"})
    path = Path(job["job_dir"]) / filename
    if not path.exists() or not path.is_file():
        return JSONResponse(status_code=404, content={"error": "File not found"})
    return FileResponse(path=str(path), filename=filename)


# Config ──────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve la config VTEX/FTP del tenant del usuario logueado."""
    tc = await _get_tenant_config(current_user.tenant_id, db)
    values: Dict[str, Any] = {}
    if tc:
        token = tc.vtex_api_token or ""
        values = {
            "X-VTEX-API-AppKey":     tc.vtex_api_key    or "",
            "X-VTEX-API-AppToken":   (token[:4] + "●●●●●●●●") if len(token) > 4 else ("●●●●●●●●" if token else ""),
            "VTEX_ACCOUNT_NAME":     tc.vtex_account_name or "",
            "VTEX_ENVIRONMENT":      tc.vtex_environment  or "vtexcommercestable",
            "FTP_SERVER":            tc.ftp_server         or "",
            "FTP_USER":              tc.ftp_user           or "",
            "FTP_PASSWORD":          "●●●●●●●●"           if tc.ftp_password else "",
            "FTP_PORT":              str(tc.ftp_port)      if tc.ftp_port else "21",
            "LAMBDA1_FUNCTION_NAME": tc.lambda_function    or "",
            "AWS_REGION":            tc.aws_region         or "us-east-1",
        }
    return {"configured": _tenant_vtex_configured(tc), "values": values}


@app.put("/api/config")
async def update_config(
    body: Dict[str, str],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la config VTEX/FTP del tenant. Cifra tokens sensibles con Fernet."""
    tc = await _get_tenant_config(current_user.tenant_id, db)
    if not tc:
        tc = TenantConfig(tenant_id=current_user.tenant_id)
        db.add(tc)

    field_map = {
        "X-VTEX-API-AppKey":     ("vtex_api_key",      False),
        "X-VTEX-API-AppToken":   ("vtex_api_token",    True),
        "VTEX_ACCOUNT_NAME":     ("vtex_account_name", False),
        "VTEX_ENVIRONMENT":      ("vtex_environment",  False),
        "FTP_SERVER":            ("ftp_server",        False),
        "FTP_USER":              ("ftp_user",          False),
        "FTP_PASSWORD":          ("ftp_password",      True),
        "FTP_PORT":              ("ftp_port",          False),
        "LAMBDA1_FUNCTION_NAME": ("lambda_function",   False),
        "AWS_REGION":            ("aws_region",        False),
    }
    for env_key, value in body.items():
        if env_key not in field_map:
            continue
        attr, should_encrypt = field_map[env_key]
        # No sobreescribir con placeholder de máscara
        if value and "●" not in value:
            if env_key == "FTP_PORT":
                setattr(tc, attr, int(value) if value.isdigit() else 21)
            else:
                setattr(tc, attr, encrypt_value(value) if should_encrypt else value)

    tc.updated_at = datetime.utcnow()
    await db.commit()
    tc = await _get_tenant_config(current_user.tenant_id, db)
    return {"ok": True, "configured": _tenant_vtex_configured(tc)}


# ─────────────────────────────────────────────────────────────────────────────
# FTP Deploy — Stock Diff → Pipeline de inventario
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/ftp-status")
async def ftp_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check whether FTP + AWS credentials are configured for the deploy pipeline."""
    tc = await _get_tenant_config(current_user.tenant_id, db)
    return {
        "ftp_configured":  _tenant_ftp_configured(tc),
        "lambda_function": tc.lambda_function if tc else "demo-lambda",
        "aws_region":      tc.aws_region      if tc else "us-east-1",
    }


@app.post("/api/jobs/{job_id}/ftp-deploy")
async def ftp_deploy(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload the stock-diff NDJSON output to FTP then invoke Lambda1 (demo-lambda)
    so the full inventory pipeline runs automatically.

    Steps:
      1. Find *_to_update.ndjson in the job output dir
      2. Rename to nivelej_YYYYMMDD_HHmmss.ndjson  (matches Lambda1 + S3 trigger patterns)
      3. Upload to FTP root via ftplib
      4. Invoke demo-lambda via boto3 with {"include": "<exact-filename>", "exclude": ""}
    """
    import boto3
    import botocore.exceptions

    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job no encontrado"})
    if current_user.role != UserRole.superadmin and job.get("tenant_id") != current_user.tenant_id:
        return JSONResponse(status_code=403, content={"error": "Sin permisos"})
    if job["status"] != "completed":
        return JSONResponse(status_code=400, content={"error": "El job todavía no ha completado"})

    # ── 1. Locate NDJSON output ───────────────────────────────────────────────
    job_dir = Path(job["job_dir"])
    ndjson_candidates = sorted(job_dir.glob("*_to_update.ndjson"))
    if not ndjson_candidates:
        return JSONResponse(
            status_code=404,
            content={"error": "No se encontró archivo *_to_update.ndjson en los outputs del job"},
        )
    ndjson_path = ndjson_candidates[0]

    # ── 2. Build remote filename ──────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_filename = f"nivelej_{timestamp}.ndjson"

    # ── 3. FTP credentials (desde tenant_config en BD) ───────────────────────
    tc = await _get_tenant_config(current_user.tenant_id, db)
    tenant_env_ftp = _build_tenant_env(tc)
    ftp_server      = tenant_env_ftp.get("FTP_SERVER", "")
    ftp_user        = tenant_env_ftp.get("FTP_USER", "")
    ftp_password    = tenant_env_ftp.get("FTP_PASSWORD", "")
    ftp_port        = int(tenant_env_ftp.get("FTP_PORT", "21"))
    lambda_function = tenant_env_ftp.get("LAMBDA1_FUNCTION_NAME", "demo-lambda")
    aws_region      = tenant_env_ftp.get("AWS_REGION", "us-east-1")

    if not all([ftp_server, ftp_user, ftp_password]):
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "Credenciales FTP no configuradas. "
                    "Agrega FTP_SERVER, FTP_USER y FTP_PASSWORD al archivo .env"
                )
            },
        )

    # ── 4. Upload to FTP ──────────────────────────────────────────────────────
    try:
        with ftplib.FTP() as ftp:
            ftp.connect(ftp_server, ftp_port, timeout=30)
            ftp.login(ftp_user, ftp_password)
            ftp.set_pasv(True)
            with open(ndjson_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_filename}", f)
    except ftplib.all_errors as exc:
        return JSONResponse(status_code=500, content={"error": f"Error FTP: {exc}"})

    # ── 5. Invoke Lambda1 ─────────────────────────────────────────────────────
    lambda_invoked = False
    lambda_response: dict | None = None
    lambda_error: str | None = None
    try:
        lambda_client = boto3.client("lambda", region_name=aws_region)
        payload = {"include": remote_filename, "exclude": ""}
        response = lambda_client.invoke(
            FunctionName=lambda_function,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
        )
        raw = response["Payload"].read()
        lambda_response = json.loads(raw) if raw else {}
        lambda_invoked = True
    except botocore.exceptions.NoCredentialsError:
        lambda_error = "AWS sin credenciales. Configura ~/.aws/credentials o variables de entorno AWS."
    except botocore.exceptions.ClientError as exc:
        lambda_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        lambda_error = str(exc)

    return {
        "ok": True,
        "source_file": ndjson_path.name,
        "remote_filename": remote_filename,
        "ftp_server": ftp_server,
        "lambda_invoked": lambda_invoked,
        "lambda_function": lambda_function,
        "lambda_response": lambda_response,
        "lambda_error": lambda_error,
    }


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str, token: str = ""):
    """
    WebSocket para streaming de logs.
    El token JWT se pasa como query param: /ws/{job_id}?token=xxx
    """
    from jose import JWTError
    from auth import decode_token as _decode

    # Validar token
    try:
        payload  = _decode(token)
        tid      = int(payload["tenant_id"])
        role_str = payload.get("role", "operator")
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001)
        return

    # Verificar que el job pertenece al tenant
    job = jobs.get(job_id)
    if job and role_str != UserRole.superadmin.value:
        if job.get("tenant_id") != tid:
            await websocket.close(code=4003)
            return

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
