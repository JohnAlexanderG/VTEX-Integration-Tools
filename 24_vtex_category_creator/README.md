# VTEX Category Creator

Crea automáticamente una jerarquía completa de categorías en VTEX (3 niveles) desde un archivo JSON plano.

## Características

- ✅ **Idempotente**: Re-ejecuciones omiten categorías existentes sin errores
- 🔍 **Verificación previa**: Compara con árbol existente antes de crear
- 🌳 **3 niveles jerárquicos**: Departamentos → Categorías → Subcategorías/Líneas
- ⚡ **Rate limiting inteligente**: 1s entre creaciones, sin delay para omisiones
- 🔄 **Retry automático**: Exponential backoff para errores 429
- 📊 **Reportes detallados**: JSON + Markdown con estadísticas por nivel
- 🧪 **Modo dry-run**: Simula operaciones sin crear nada real

## Prerequisitos

Archivo `.env` en la raíz del proyecto con:
```bash
X-VTEX-API-AppKey=tu_app_key
X-VTEX-API-AppToken=tu_app_token
VTEX_ACCOUNT_NAME=tu_cuenta
VTEX_ENVIRONMENT=vtexcommercestable  # opcional
```

## Estructura de Datos de Entrada

El script espera un archivo JSON con una lista de objetos con esta estructura:

```json
{
  "NVO COD CAT": "1",
  "CATEGORIA": "Decoración",
  "NVO COD SUBC": "1",
  "SUBCATEGORIA": "Velas",
  "NVO COD LINEA": "1",
  "LINEA": "Apagavelas"
}
```

**Mapeo a VTEX:**
- `CATEGORIA` → Departamento (Nivel 1, padre = null)
- `SUBCATEGORIA` → Categoría (Nivel 2, padre = Departamento)
- `LINEA` → Subcategoría/Línea (Nivel 3, padre = Categoría)

## Uso

### Modo Dry-Run (Recomendado para primera ejecución)

```bash
python3 24_vtex_category_creator/vtex_category_creator.py \
  01_csv_to_json/2025_11_24_ARBOL_CATEGORIA-VF.03.json \
  --dry-run
```

Esto simula la creación sin tocar VTEX. Útil para:
- Validar que el script lee correctamente tu JSON
- Ver cuántas categorías se crearían
- Verificar la jerarquía extraída

### Modo Producción (Creación Real)

```bash
python3 24_vtex_category_creator/vtex_category_creator.py \
  01_csv_to_json/2025_11_24_ARBOL_CATEGORIA-VF.03.json
```

### Opciones Avanzadas

```bash
# Con delay personalizado (útil si VTEX rate-limita)
python3 vtex_category_creator.py input.json --delay 2.0

# Con timeout mayor (para conexiones lentas)
python3 vtex_category_creator.py input.json --timeout 60

# Con prefijo de salida personalizado
python3 vtex_category_creator.py input.json --output-prefix mi_batch
```

### Ver Ayuda

```bash
python3 24_vtex_category_creator/vtex_category_creator.py --help
```

## Flujo de Procesamiento

1. **Inicialización**
   - Carga credenciales desde `.env`
   - Valida que existan todas las variables requeridas

2. **Fetch Árbol Existente** (omitido en dry-run)
   - Descarga categorías actuales de VTEX
   - Construye mapeo normalizado para matching rápido

3. **Extracción de Jerarquía**
   - Lee JSON plano de entrada
   - Extrae departamentos únicos (nivel 1)
   - Extrae categorías únicas (nivel 2)
   - Extrae líneas únicas (nivel 3)

4. **Procesamiento Secuencial**
   - **Nivel 1**: Crea departamentos (`FatherCategoryId = null`)
   - **Nivel 2**: Crea categorías (padre = ID del departamento)
   - **Nivel 3**: Crea líneas (padre = ID de la categoría)

5. **Exportación de Resultados**
   - Genera 3 archivos JSON (created, skipped, failed)
   - Genera reporte Markdown con estadísticas

## Archivos de Salida

Todos los archivos llevan timestamp `YYYYMMDD_HHMMSS`:

### `{timestamp}_category_creation_created.json`
Categorías creadas exitosamente:
```json
{
  "name": "Decoración",
  "level": 1,
  "father_id": null,
  "category_id": 123,
  "response": {...},
  "timestamp": "2025-11-27T12:00:00"
}
```

### `{timestamp}_category_creation_skipped.json`
Categorías omitidas (ya existían):
```json
{
  "name": "Velas",
  "level": 2,
  "father_id": 123,
  "category_id": 456,
  "reason": "Already exists in VTEX"
}
```

### `{timestamp}_category_creation_failed.json`
Categorías que fallaron:
```json
{
  "name": "Apagavelas",
  "level": 3,
  "father_id": 456,
  "error": "API Error: 429",
  "status_code": 429,
  "response": {...},
  "timestamp": "2025-11-27T12:00:01"
}
```

### `{timestamp}_category_creation_report.md`
Reporte en Markdown con:
- Resumen general (totales, tiempos)
- Estadísticas por nivel
- Tablas de categorías creadas/omitidas/fallidas
- Análisis de errores agrupados
- Recomendaciones

## Comportamiento Idempotente

El script está diseñado para ser **completamente idempotente**:

```bash
# Primera ejecución - crea todo
python3 vtex_category_creator.py input.json
# Resultado: 1632 creados, 0 omitidos, 0 fallidos

# Segunda ejecución - omite todo
python3 vtex_category_creator.py input.json
# Resultado: 0 creados, 1632 omitidos, 0 fallidos
```

Esto es posible gracias a:
- Normalización Unicode para matching robusto (ej: "Decoración" = "decoracion")
- Verificación contra árbol VTEX antes de cada creación
- Sin delays para categorías omitidas (solo para creaciones)

## Normalización de Nombres

Para garantizar matching confiable, el script:
1. Normaliza a NFKD (descompone caracteres)
2. Elimina marcas diacríticas (acentos)
3. Convierte a minúsculas
4. Elimina espacios en blanco extra

Ejemplo:
- `"Decoración"` → `"decoracion"`
- `"ELECTRÓNICA"` → `"electronica"`
- `"Niños & Niñas"` → `"ninos & ninas"`

## Estimación de Tiempos

Con configuración por defecto (1s delay entre creaciones):

| Escenario | Categorías | Tiempo Estimado |
|-----------|-----------|-----------------|
| Todo nuevo (peor caso) | 1632 | ~27 minutos |
| 50% existente | 816 nuevas | ~14 minutos |
| Todo existente (re-run) | 0 nuevas | ~3 minutos |

Tiempos en dry-run: <1 segundo (no hay API calls)

## Manejo de Errores

### Rate Limiting (429)
- Retry automático con exponential backoff
- Máximo 3 reintentos por categoría
- Factores de espera: 1s → 2s → 4s

### Padre No Encontrado
- Si un departamento falla, sus categorías hijas también fallan
- Se registra el error con contexto completo
- El proceso continúa con el siguiente departamento

### Timeouts
- Timeout por defecto: 30 segundos
- Configurable con `--timeout`
- Categoría marcada como fallida, proceso continúa

### Errores de API (400, 500, etc.)
- Se registra respuesta completa del servidor
- Categoría marcada como fallida
- Proceso continúa

## Campos de Categoría VTEX

Cada categoría creada incluye:

```json
{
  "Name": "Decoración",                    // Nombre visible
  "Keywords": "Decoración",                // Para búsqueda
  "Title": "Decoración",                   // Título SEO
  "Description": "Productos de Decoración", // Auto-generada
  "FatherCategoryId": null,                // null = nivel 1
  "IsActive": true,                        // Activa
  "ShowInStoreFront": true                 // Visible en tienda
}
```

**IMPORTANTE**: El campo `Id` NO se incluye - VTEX lo auto-genera.

## Troubleshooting

### Error: "Credenciales VTEX faltantes"
- Verifica que `.env` existe en la raíz del proyecto
- Verifica nombres exactos: `X-VTEX-API-AppKey`, `X-VTEX-API-AppToken`, `VTEX_ACCOUNT_NAME`

### Error: "FileNotFoundError"
- Verifica que el path del JSON es correcto
- Usa paths relativos desde la raíz del proyecto

### Error: "JSON inválido"
- Verifica que el archivo es JSON válido
- Usa `python3 -m json.tool archivo.json` para validar

### Muchas categorías fallan con "Parent not found"
- Ejecuta primero con `--dry-run` para ver la jerarquía
- Verifica que los nombres de departamentos/categorías son consistentes

### Rate limiting constante (429)
- Aumenta el delay: `--delay 2.0`
- Verifica que no hay otros procesos usando la API VTEX

## Integración con CLAUDE.md

Este script sigue todos los patrones documentados en `CLAUDE.md`:

- **Arquitectura**: Clase `VTEXCategoryCreator` similar a `VTEXProductCreator`
- **Credenciales**: Carga desde `.env` en raíz del proyecto
- **Rate Limiting**: 1s delays con exponential backoff
- **Normalización**: Unicode normalization para matching
- **Exports**: Multi-formato (JSON + Markdown)
- **Logging**: Emoji indicators con progreso cada 10 items

## Próximos Pasos

Después de crear las categorías:

1. **Verificar en VTEX Admin**
   - Portal → Catálogo → Categorías
   - Revisar jerarquía creada

2. **Mapear IDs a Productos**
   - Ejecutar `06_map_category_ids` con tu archivo de productos
   - Esto asignará `DepartmentId` y `CategoryId` a cada producto

3. **Continuar con Pipeline**
   - Seguir con steps 07-15 para crear productos y SKUs
   - Las categorías ya están creadas y listas

## Soporte

Para issues o preguntas, contacta al equipo de desarrollo.
