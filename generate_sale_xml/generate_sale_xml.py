#!/usr/bin/env python3
# generate_sale_xml.py

import argparse
import json
import unicodedata
from datetime import datetime
from typing import Any, Dict, Tuple


def escape_xml(text: Any) -> str:
    """Escape special XML characters."""
    if text is None:
        return ""
    text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def cents_to_units(value: Any):
    """Convert VTEX cents to currency units (e.g. 12095000 -> 120950)."""
    if value is None:
        return 0
    try:
        units = float(value) / 100.0
        if units.is_integer():
            return int(units)
        return round(units, 2)
    except Exception:
        return 0


def format_date(iso_date: str) -> str:
    """
    Convert ISO datetime like '2026-01-10T20:18:33.3981030+00:00'
    to 'YYYY-MM-DD HH:MM:SS'
    """
    if not iso_date:
        return ""
    try:
        # Strip timezone and fractional seconds
        clean = iso_date.split("+")[0]
        if "." in clean:
            clean = clean.split(".")[0]
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_date


def split_receiver_name(full_name: str) -> Tuple[str, str]:
    if not full_name:
        return ("", "")
    parts = full_name.strip().split()
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


def normalize_text(text: str) -> str:
    """Lowercase, trim, remove accents, collapse spaces."""
    if not text:
        return ""
    t = text.strip().lower()
    t = "".join(
        c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)
    )
    t = " ".join(t.split())
    return t


def get_carrier_service(order_data: Dict[str, Any]) -> str:
    """
    Map VTEX courier/service to expected carrier-service value.
    Uses courierName from shippingData.logisticsInfo[0].deliveryIds[0].courierName
    with normalization.
    """
    service_map = {
        normalize_text("Envío siguiente día"): "Siguiente dia",
        normalize_text("Envío Express"): "Tres horas",
        normalize_text("Coordinadora"): "Tradicional",
    }

    shipping_data = order_data.get("shippingData", {}) or {}
    logistics_info = shipping_data.get("logisticsInfo", []) or []
    if logistics_info:
        delivery_ids = (logistics_info[0] or {}).get("deliveryIds", []) or []
        if delivery_ids:
            courier_name = (delivery_ids[0] or {}).get("courierName", "") or ""
            return service_map.get(normalize_text(courier_name), courier_name)

    return ""


def get_warehouse_code(order_data: Dict[str, Any]) -> str:
    shipping_data = order_data.get("shippingData", {}) or {}
    logistics_info = shipping_data.get("logisticsInfo", []) or []
    if logistics_info:
        delivery_ids = (logistics_info[0] or {}).get("deliveryIds", []) or []
        if delivery_ids:
            return str((delivery_ids[0] or {}).get("warehouseId", "001") or "001")
    return "001"


def get_shipping_value_cents(order_data: Dict[str, Any]) -> int:
    for t in order_data.get("totals", []) or []:
        if (t or {}).get("id") == "Shipping":
            return int((t or {}).get("value", 0) or 0)
    return 0


def calculate_total_units(order_data: Dict[str, Any]):
    total_cents = 0
    for t in order_data.get("totals", []) or []:
        total_cents += int((t or {}).get("value", 0) or 0)
    return cents_to_units(total_cents)


def pick_order_num(order_data: Dict[str, Any]) -> str:
    """
    Prefer 'sequence' (matches sample_output.xml).
    Fallback: try last 6 digits from marketplaceOrderId/orderId numeric part.
    """
    seq = order_data.get("sequence")
    if seq:
        return str(seq)

    # fallback: extract digits from marketplaceOrderId or orderId
    for key in ("marketplaceOrderId", "orderId"):
        val = order_data.get(key) or ""
        digits = "".join(ch for ch in str(val) if ch.isdigit())
        if len(digits) >= 6:
            return digits[-6:]
    return ""


def order_to_xml(order_data: Dict[str, Any]) -> str:
    order_num = pick_order_num(order_data)
    creation_date = format_date(order_data.get("creationDate", "") or "")

    client_profile = order_data.get("clientProfileData", {}) or {}
    first_name = escape_xml(client_profile.get("firstName", "") or "")
    last_name = escape_xml(client_profile.get("lastName", "") or "")
    corporate_name = escape_xml(client_profile.get("corporateName", "") or "")
    trade_name = escape_xml(client_profile.get("tradeName", "") or "")

    # Document info
    document_type = escape_xml(client_profile.get("documentType", "") or "")
    document = escape_xml(client_profile.get("document", "") or "")

    # Email/phone
    email = escape_xml(client_profile.get("email", "") or "")
    phone = escape_xml(client_profile.get("phone", "") or "")

    # Shipping address
    shipping_data = order_data.get("shippingData", {}) or {}
    address = shipping_data.get("address", {}) or {}

    receiver_name = address.get("receiverName", "") or ""
    ship_first_name, ship_last_name = split_receiver_name(receiver_name)

    street = escape_xml(address.get("street", "") or "")
    complement = escape_xml(address.get("complement", "") or "")
    city = escape_xml(address.get("city", "") or "")
    state = escape_xml(address.get("state", "") or "")
    country = escape_xml(address.get("country", "CO") or "CO")

    # Logistics
    warehouse = escape_xml(get_warehouse_code(order_data))
    carrier_code = "901156044"
    carrier_service = escape_xml(get_carrier_service(order_data))

    # Deliver-before (shippingEstimateDate)
    deliver_before = ""
    logistics_info = shipping_data.get("logisticsInfo", []) or []
    if logistics_info:
        ship_est = (logistics_info[0] or {}).get("shippingEstimateDate", "") or ""
        deliver_before = format_date(ship_est)

    # Payment
    payment_method = ""
    payment_transaction_id = ""
    paid_amount = 0

    payment_data = order_data.get("paymentData", {}) or {}
    transactions = payment_data.get("transactions", []) or []
    if transactions:
        tx = transactions[0] or {}
        payment_transaction_id = tx.get("transactionId") or ""
        payments = tx.get("payments", []) or []
        if payments:
            p0 = payments[0] or {}
            payment_method = escape_xml(p0.get("paymentSystemName", "") or "")
            paid_amount = cents_to_units(p0.get("value", 0) or 0)

    # Totals
    total = calculate_total_units(order_data)

    # Build XML
    xml_lines = ["<sale>"]
    xml_lines.append(f"\t<order-num>{escape_xml(order_num)}</order-num>")
    xml_lines.append(f"\t<created>{escape_xml(creation_date)}</created>")
    xml_lines.append("\t<channel>web</channel>")
    xml_lines.append("\t<po></po>")
    xml_lines.append(
        f"\t<deliver-after>{escape_xml(creation_date.split(' ')[0] if creation_date else '')}</deliver-after>"
    )
    xml_lines.append(
        f"\t<deliver-before>{escape_xml(deliver_before.split(' ')[0] if deliver_before else '')}</deliver-before>"
    )

    # Bill-to
    xml_lines.append("\t<bill-to>")
    xml_lines.append(f"\t\t<first-name>{first_name}</first-name>")
    xml_lines.append(f"\t\t<last-name>{last_name}</last-name>")
    xml_lines.append(f"\t\t<company>{escape_xml((trade_name + ' ' + corporate_name).strip())}</company>")
    xml_lines.append(f"\t\t<client-id-type>{document_type}</client-id-type>")
    xml_lines.append(f"\t\t<client-id>{document}</client-id>")
    xml_lines.append("\t\t<client-type>Regimen Comun</client-type>")
    xml_lines.append(f"\t\t<email>{email}</email>")
    xml_lines.append(f"\t\t<phone>{phone}</phone>")
    xml_lines.append("\t\t<address>")
    xml_lines.append(f"\t\t\t<line1>{street}</line1>")
    xml_lines.append(f"\t\t\t<line2>{complement}</line2>")
    xml_lines.append(f"\t\t\t<city>{city}</city>")
    xml_lines.append(f"\t\t\t<state>{state}</state>")
    xml_lines.append("\t\t\t<zip></zip>")
    xml_lines.append(f"\t\t\t<country>{country}</country>")
    xml_lines.append("\t\t</address>")
    xml_lines.append("\t</bill-to>")

    # Ship-to
    xml_lines.append("\t<ship-to>")
    xml_lines.append(f"\t\t<first-name>{escape_xml(ship_first_name)}</first-name>")
    xml_lines.append(f"\t\t<last-name>{escape_xml(ship_last_name)}</last-name>")
    xml_lines.append(f"\t\t<company>{escape_xml((trade_name + ' ' + corporate_name).strip())}</company>")
    xml_lines.append(f"\t\t<email>{email}</email>")
    xml_lines.append(f"\t\t<phone>{phone}</phone>")
    xml_lines.append("\t\t<address>")
    xml_lines.append(f"\t\t\t<line1>{street}</line1>")
    xml_lines.append(f"\t\t\t<line2>{complement}</line2>")
    xml_lines.append(f"\t\t\t<city>{city}</city>")
    xml_lines.append(f"\t\t\t<state>{state}</state>")
    xml_lines.append("\t\t\t<zip></zip>")
    xml_lines.append(f"\t\t\t<country>{country}</country>")
    xml_lines.append("\t\t</address>")
    xml_lines.append("\t</ship-to>")

    # Logistics
    xml_lines.append(f"\t<ship-from>{warehouse}</ship-from>")
    xml_lines.append(f"\t<carrier>{carrier_code}</carrier>")
    xml_lines.append(f"\t<carrier-service>{carrier_service}</carrier-service>")

    # Products
    for item in order_data.get("items", []) or []:
        item = item or {}
        ref_id = escape_xml(item.get("refId", "") or "")
        ean = escape_xml(item.get("ean", "") or "")
        qty = int(item.get("quantity", 0) or 0)
        unit_price = cents_to_units(item.get("sellingPrice", 0) or 0)
        tax_free = cents_to_units(item.get("tax", 0) or 0)

        xml_lines.append("\t<product>")
        xml_lines.append(f"\t\t<sku>{ref_id}</sku>")
        xml_lines.append(f"\t\t<ean>{ean if ean else ref_id}</ean>")
        xml_lines.append(f"\t\t<quantity>{qty}</quantity>")
        xml_lines.append(f"\t\t<unit-price>{unit_price}</unit-price>")
        xml_lines.append(f"\t\t<tax-free>{tax_free}</tax-free>")
        xml_lines.append("\t</product>")

    # Add shipping product
    shipping_cents = get_shipping_value_cents(order_data)
    if shipping_cents > 0:
        shipping_price = cents_to_units(shipping_cents)
        xml_lines.append("\t<product>")
        xml_lines.append("\t\t<sku>476288</sku>")
        xml_lines.append("\t\t<ean>476288</ean>")
        xml_lines.append("\t\t<quantity>1</quantity>")
        xml_lines.append(f"\t\t<unit-price>{shipping_price}</unit-price>")
        xml_lines.append("\t</product>")

    # Totals & payment
    xml_lines.append(f"\t<total>{total}</total>")
    xml_lines.append(f"\t<payment-method>{escape_xml(payment_method)}</payment-method>")
    xml_lines.append("\t<payment-terms>Prepagado</payment-terms>")
    xml_lines.append(f"\t<payment-transaction-id>{escape_xml(payment_transaction_id)}</payment-transaction-id>")
    xml_lines.append(f"\t<paid>{paid_amount}</paid>")
    xml_lines.append("</sale>")

    return "\n".join(xml_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate sale XML (sample_output.xml format) from VTEX order JSON (response-order.json)."
    )
    parser.add_argument(
        "-i", "--input", default="response-order.json", help="Input JSON file (default: response-order.json)"
    )
    parser.add_argument(
        "-o", "--output", default=None, help="Output XML file (default: venta_<order-num>.xml)"
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        order_data = json.load(f)

    xml_content = order_to_xml(order_data)

    order_num = pick_order_num(order_data) or "order"
    out_path = args.output or f"venta_{order_num}.xml"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    print(f"✅ XML generado: {out_path}")


if __name__ == "__main__":
    main()