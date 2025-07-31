#!/usr/bin/env python3
"""
vtex_product_formatter.py

Formateador final de productos VTEX para creación de catálogo. Último paso del flujo 
de transformación de datos para integración con VTEX e-commerce platform.

Funcionalidad:
- Toma datos procesados del pipeline completo y los formatea para crear productos VTEX
- Incluye solo campos esenciales requeridos para creación exitosa de productos
- Genera LinkId SEO-friendly automáticamente si no está presente
- Valida longitud del campo Title (máximo 150 caracteres para SEO)
- Filtra productos listos vs no listos para creación
- Exporta productos no creables a archivo separado para revisión manual

Campos Requeridos VTEX:
- Name: Nombre del producto
- DepartmentId: ID del departamento (desde mapeo API VTEX)
- CategoryId: ID de la categoría (desde mapeo API VTEX) 
- BrandId: ID de la marca (desde mapeo API VTEX)
- RefId: ID de referencia del producto (SKU)
- IsVisible: Visibilidad del producto (default: true)
- Description: Descripción del producto
- IsActive: Estado activo del producto (default: true)

Campos Opcionales Recomendados:
- LinkId: URL SEO-friendly (generado automáticamente)
- DescriptionShort: Descripción corta
- KeyWords: Palabras clave de búsqueda
- Title: Título SEO (validado a 150 caracteres máximo)
- MetaTagDescription: Meta descripción
- ShowWithoutStock: Mostrar sin stock (default: true)

Ejecución:
    # Formateo básico
    python3 vtex_product_formatter.py productos.json vtex_ready.json --indent 4
    
    # Incluyendo productos no listos en archivo separado
    python3 vtex_product_formatter.py data.json formatted.json --include-not-ready

Ejemplo:
    python3 11_vtex_product_format_create/vtex_product_formatter.py final_data.json vtex_products.json
"""

import json
import argparse
import sys
from datetime import datetime
import re
import unicodedata


def normalize_text(text):
    """Normaliza texto removiendo acentos para generación de URLs."""
    if not text:
        return ""
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text


def generate_link_id(name, ref_id):
    """Genera LinkId SEO-friendly desde nombre del producto y RefId."""
    if not name:
        return f"product-{ref_id}".lower()
    
    # Normalizar y limpiar el nombre
    clean_name = normalize_text(str(name).lower())
    # Reemplazar espacios y caracteres especiales con guiones
    clean_name = re.sub(r'[^a-z0-9]+', '-', clean_name)
    # Remover guiones al inicio/final y múltiples guiones consecutivos
    clean_name = re.sub(r'^-+|-+$', '', clean_name)
    clean_name = re.sub(r'-+', '-', clean_name)
    
    return f"{clean_name}-{ref_id}".lower()


def validate_title_length(title):
    """Valida y trunca campo Title al límite de 150 caracteres de VTEX para SEO."""
    if not title:
        return ""
    
    title_str = str(title).strip()
    
    if len(title_str) <= 150:
        return title_str
    
    # Truncar a 150 caracteres, intentando cortar en límite de palabra
    truncated = title_str[:150]
    
    # Buscar último espacio dentro del límite para evitar cortar palabras
    last_space = truncated.rfind(' ')
    if last_space > 130:  # Solo usar límite de palabra si no es muy corto
        truncated = truncated[:last_space]
    
    return truncated.rstrip()


def format_for_vtex(product_data):
    """Formatea un producto individual para creación VTEX."""
    formatted = {}
    
    # Campos requeridos
    formatted["Name"] = product_data.get("Name", "")
    
    # Solo incluir DepartmentId y CategoryId si no son null
    department_id = product_data.get("DepartmentId")
    if department_id is not None:
        formatted["DepartmentId"] = department_id
        
    category_id = product_data.get("CategoryId")
    if category_id is not None:
        formatted["CategoryId"] = category_id
    
    formatted["BrandId"] = product_data.get("BrandId")
    formatted["RefId"] = str(product_data.get("RefId", ""))
    formatted["IsVisible"] = product_data.get("IsVisible", True)
    formatted["Description"] = product_data.get("Description", "")
    formatted["IsActive"] = product_data.get("IsActive", True)
    
    # Incluir CategoryPath para crear nuevas categorías cuando IDs no están disponibles
    if not formatted.get("DepartmentId") and not formatted.get("CategoryId") and product_data.get("CategoryPath"):
        formatted["CategoryPath"] = product_data.get("CategoryPath")
    
    # Generar LinkId si no está proporcionado
    if "LinkId" in product_data:
        formatted["LinkId"] = product_data["LinkId"]
    else:
        formatted["LinkId"] = generate_link_id(
            formatted["Name"], 
            formatted["RefId"]
        )
    
    # Campos opcionales con valores por defecto
    formatted["DescriptionShort"] = product_data.get("DescriptionShort", "")
    formatted["KeyWords"] = product_data.get("KeyWords", "")
    formatted["Title"] = validate_title_length(
        product_data.get("Title", formatted["Name"])
    )
    formatted["MetaTagDescription"] = product_data.get("MetaTagDescription", "")
    formatted["ShowWithoutStock"] = product_data.get("ShowWithoutStock", True)
    
    return formatted


def filter_ready_products(products):
    """Filtra productos que están listos para creación VTEX."""
    ready_products = []
    not_ready = []
    
    for product in products:
        # Verificar si el producto tiene campos requeridos
        has_department = product.get("DepartmentId") is not None
        has_category = product.get("CategoryId") is not None  
        has_brand = product.get("BrandId") is not None
        has_ref_id = product.get("RefId")
        has_name = product.get("Name")
        has_category_path = product.get("CategoryPath")
        
        # VTEX permite dos escenarios:
        # 1. Categoría existente: tiene DepartmentId, CategoryId y BrandId
        # 2. Nueva categoría: tiene BrandId y CategoryPath (para crear categoría)
        scenario_1 = has_department and has_category and has_brand and has_ref_id and has_name
        scenario_2 = has_brand and has_category_path and has_ref_id and has_name and not has_department and not has_category
        
        if scenario_1 or scenario_2:
            ready_products.append(product)
        else:
            # Incluir datos completos del producto
            not_ready.append(product)
    
    return ready_products, not_ready


def main():
    parser = argparse.ArgumentParser(
        description="Format processed JSON data for VTEX product creation"
    )
    parser.add_argument("input_file", help="Input JSON file with processed product data")
    parser.add_argument("output_file", help="Output JSON file formatted for VTEX")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation (default: 2)")
    parser.add_argument("--include-not-ready", action="store_true", 
                       help="Include products not ready for creation in separate file")
    
    args = parser.parse_args()
    
    try:
        # Cargar datos de entrada
        with open(args.input_file, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Manejar tanto producto individual como array de productos
        if isinstance(input_data, dict):
            products = [input_data]
        else:
            products = input_data
        
        # Filtrar productos listos
        ready_products, not_ready = filter_ready_products(products)
        
        # Formatear productos listos para VTEX
        formatted_products = [format_for_vtex(product) for product in ready_products]
        
        # Guardar productos formateados
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_products, f, ensure_ascii=False, indent=args.indent)
        
        # Generar reporte
        print(f"✅ Processed {len(products)} products")
        print(f"✅ Ready for VTEX creation: {len(formatted_products)}")
        print(f"⚠️  Not ready for creation: {len(not_ready)}")
        print(f"✅ Output saved to: {args.output_file}")
        
        # Siempre guardar productos no listos en archivo separado
        if not_ready:
            not_ready_file = args.output_file.replace('.json', '_cannot_create.json')
            with open(not_ready_file, 'w', encoding='utf-8') as f:
                json.dump(not_ready, f, ensure_ascii=False, indent=args.indent)
            print(f"⚠️  Productos que no se pueden crear guardados en: {not_ready_file}")
            
            print("\n⚠️  Productos no listos para creación:")
            for product in not_ready[:5]:  # Mostrar primeros 5
                missing = []
                if not product.get("DepartmentId"):
                    missing.append("DepartmentId")
                if not product.get("CategoryId"):
                    missing.append("CategoryId")
                if not product.get("BrandId"):
                    missing.append("BrandId")
                if not product.get("RefId"):
                    missing.append("RefId")
                if not product.get("Name"):
                    missing.append("Name")
                print(f"   - {product.get('RefId', 'N/A')}: Faltan {', '.join(missing)}")
            if len(not_ready) > 5:
                print(f"   ... y {len(not_ready) - 5} más")
    
    except FileNotFoundError:
        print(f"❌ Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in input file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()