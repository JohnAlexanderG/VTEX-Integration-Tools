# generate_sale_xml

## Descripción

Genera archivos XML de ventas en formato compatible con sistemas legacy (formato `sample_output.xml`) a partir de respuestas de órdenes de VTEX en formato JSON. Transforma datos de pedido completo incluyendo cliente, envío, productos y pagos.

## Requisitos

- Python 3.6+ (librerías estándar: argparse, json, unicodedata, datetime, typing)
- Sin dependencias externas

## Uso

```bash
python3 generate_sale_xml.py [-i <input.json>] [-o <output.xml>]
```

### Argumentos

- `-i, --input` - Archivo JSON de entrada (default: `response-order.json`)
- `-o, --output` - Archivo XML de salida (default: `venta_<order_number>.xml`)

### Ejemplos

```bash
# Usar archivos por defecto
python3 generate_sale_xml.py

# Especificar entrada y salida
python3 generate_sale_xml.py -i order_response.json -o venta_500561.xml

# Procesar múltiples archivos
for file in *.json; do
  python3 generate_sale_xml.py -i "$file" -o "$(basename $file .json).xml"
done
```

## Formato de Entrada

Archivo JSON con respuesta completa de orden de VTEX. Estructura esperada:

```json
{
  "orderId": "500561",
  "sequence": "500561",
  "creationDate": "2026-01-10T20:18:33.3981030+00:00",
  "clientProfileData": {
    "firstName": "Juan",
    "lastName": "Pérez",
    "documentType": "CC",
    "document": "1234567890",
    "corporateName": "Empresa S.A.",
    "tradeName": "Tienda",
    "email": "juan@example.com",
    "phone": "+57 1234567"
  },
  "shippingData": {
    "address": {
      "receiverName": "Juan Carlos Pérez",
      "street": "Calle 10",
      "complement": "Apto 201",
      "city": "Bogotá",
      "state": "DC",
      "country": "CO"
    },
    "logisticsInfo": [
      {
        "shippingEstimateDate": "2026-01-15T00:00:00.0000000Z",
        "deliveryIds": [
          {
            "courierName": "Coordinadora",
            "warehouseId": "001"
          }
        ]
      }
    ]
  },
  "paymentData": {
    "transactions": [
      {
        "transactionId": "ABC123456",
        "payments": [
          {
            "paymentSystemName": "Tarjeta de Crédito",
            "value": 12095000
          }
        ]
      }
    ]
  },
  "items": [
    {
      "refId": "000050",
      "ean": "1234567890",
      "quantity": 2,
      "sellingPrice": 5000000,
      "tax": 50000
    }
  ],
  "totals": [
    {
      "id": "Items",
      "value": 10000000
    },
    {
      "id": "Shipping",
      "value": 2000000
    },
    {
      "id": "Tax",
      "value": 100000
    }
  ]
}
```

## Formato de Salida

Archivo XML en formato `sample_output.xml` con estructura:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sale>
  <order-num>500561</order-num>
  <created>2026-01-10 20:18:33</created>
  <channel>web</channel>
  <po></po>
  <deliver-after>2026-01-10</deliver-after>
  <deliver-before>2026-01-15</deliver-before>

  <bill-to>
    <first-name>Juan</first-name>
    <last-name>Pérez</last-name>
    <company>Tienda Empresa S.A.</company>
    <client-id-type>CC</client-id-type>
    <client-id>1234567890</client-id>
    <client-type>Regimen Comun</client-type>
    <email>juan@example.com</email>
    <phone>+57 1234567</phone>
    <address>
      <line1>Calle 10</line1>
      <line2>Apto 201</line2>
      <city>Bogotá</city>
      <state>DC</state>
      <zip></zip>
      <country>CO</country>
    </address>
  </bill-to>

  <ship-to>
    <first-name>Juan</first-name>
    <last-name>Carlos Pérez</last-name>
    <company>Tienda Empresa S.A.</company>
    <email>juan@example.com</email>
    <phone>+57 1234567</phone>
    <address>
      <line1>Calle 10</line1>
      <line2>Apto 201</line2>
      <city>Bogotá</city>
      <state>DC</state>
      <zip></zip>
      <country>CO</country>
    </address>
  </ship-to>

  <ship-from>001</ship-from>
  <carrier>901156044</carrier>
  <carrier-service>Tradicional</carrier-service>

  <product>
    <sku>000050</sku>
    <ean>1234567890</ean>
    <quantity>2</quantity>
    <unit-price>50000</unit-price>
    <tax-free>500</tax-free>
  </product>

  <product>
    <sku>476288</sku>
    <ean>476288</ean>
    <quantity>1</quantity>
    <unit-price>20000</unit-price>
  </product>

  <total>120950</total>
  <payment-method>Tarjeta de Crédito</payment-method>
  <payment-terms>Prepagado</payment-terms>
  <payment-transaction-id>ABC123456</payment-transaction-id>
  <paid>120950</paid>
</sale>
```

## Conversiones Aplicadas

### Fechas
- ISO 8601 (ej: `2026-01-10T20:18:33.3981030+00:00`) → YYYY-MM-DD HH:MM:SS
- Timezone y segundos fraccionarios se eliminan

### Precios
- VTEX usa centavos; se divide por 100 para convertir a unidades
- Ej: `12095000` centavos → `120950` unidades

### Almacén
- `warehouseId` del primer `deliveryId`, o `001` si no existe

### Courier/Servicio
- Normalización y mapeo de nombres de couriers a servicios
- Ej: "Coordinadora" → "Tradicional"

### Producto de Envío
- Se agrega SKU especial `476288` si hay costo de envío

## Lógica de Funcionamiento

1. Lee JSON de orden de VTEX
2. Extrae información de cliente (nombres, documento, email, teléfono)
3. Extrae dirección de envío y divide nombre en nombre/apellido
4. Obtiene información logística (almacén, courier, fechas)
5. Procesa información de pago (método, monto)
6. Itera sobre items y genera elementos `<product>`
7. Si hay costo de envío, agrega producto especial de envío
8. Calcula totales y genera XML estructurado
9. Escapa caracteres XML especiales (< > & " ')

## Notas/Caveats

- El nombre del receptor se divide en nombre/apellido por primer espacio
- El nombre de la empresa es fusión de `tradeName` y `corporateName`
- Se preservan acentos y caracteres especiales (UTF-8)
- SKU de envío hardcodeado a `476288`
- Código de carrier hardcodeado a `901156044` (Banco Pichincha - Colombia)
- Si faltan datos, se usa valores vacíos (`""`) o defaults (`001`)
- JSON malformado en campos causa errores; validar entrada
- Fechas sin timezone se asumen UTC
