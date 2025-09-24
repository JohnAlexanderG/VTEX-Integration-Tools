#!/usr/bin/env python3
"""
Debug script to test a single SKU update and see the exact API request/response.
"""
import json
import sys
from pathlib import Path
import requests

# Add parent directory to path to import the main script
sys.path.append(str(Path(__file__).parent))
from vtex_update_sku_from_csv import VtexConfig, put_sku, build_headers, bool_from_str, coerce_numeric

def get_sku_info(cfg: VtexConfig, sku_id: str):
    """Get SKU information from VTEX API"""
    url = f"https://{cfg.account}.{cfg.env}.com.br/api/catalog/pvt/stockkeepingunit/{sku_id}"
    headers = build_headers(cfg)
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    return None

def debug_sku_update(sku_id: str):
    """Test updating a single SKU with debug information"""
    
    print(f"🔍 Debugging SKU update for: {sku_id}")
    print("=" * 50)
    
    # Load config
    try:
        cfg = VtexConfig.load_from_env()
        print(f"✅ Config loaded - Account: {cfg.account}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # First, get current SKU info to find ProductId
    print(f"📥 Getting current SKU info...")
    sku_info = get_sku_info(cfg, sku_id)
    if sku_info:
        print(f"✅ SKU exists - ProductId: {sku_info.get('ProductId')}")
        print(f"   Current Name: {sku_info.get('SkuName')}")
        print(f"   Current Status: Active={sku_info.get('IsActive')}")
        product_id = sku_info.get('ProductId')
    else:
        print(f"❌ SKU {sku_id} not found or error getting info")
        return
    
    # Sample payload (you can modify these values) - NOW INCLUDING ProductId AND RefId
    payload = {
        "ProductId": product_id,  # Required by API
        "IsActive": False,
        "ActivateIfPossible": True,
        "Name": f"Test Product {sku_id}",
        "RefId": f"TEST-{sku_id}",  # Important to prevent RefId deletion
        "PackagedHeight": 10.0,
        "PackagedLength": 15.0,
        "PackagedWidth": 20.0,
        "PackagedWeightKg": 0.5
    }
    
    print(f"📦 Payload to send:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()
    
    # Show headers (without sensitive data)
    headers = build_headers(cfg)
    safe_headers = {k: v if 'API' not in k else f"{v[:10]}..." for k, v in headers.items()}
    print(f"🔧 Headers:")
    print(json.dumps(safe_headers, indent=2))
    print()
    
    # Show URL
    url = f"https://{cfg.account}.{cfg.env}.com.br/api/catalog/pvt/stockkeepingunit/{sku_id}"
    print(f"🌐 URL: {url}")
    print()
    
    # Make the request
    print("🚀 Making API request...")
    try:
        resp = put_sku(cfg, sku_id, payload)
        print(f"📥 Response Status: {resp.status_code}")
        print(f"📥 Response Headers: {dict(resp.headers)}")
        
        try:
            response_json = resp.json()
            print(f"📥 Response Body (JSON):")
            print(json.dumps(response_json, indent=2, ensure_ascii=False))
        except:
            print(f"📥 Response Body (Text):")
            print(resp.text)
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 debug_single_sku.py <SKU_ID>")
        print("Example: python3 debug_single_sku.py 18182")
        sys.exit(1)
    
    debug_sku_update(sys.argv[1])