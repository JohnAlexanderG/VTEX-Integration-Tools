# tranform_font-ttf-woff

## Descripción

Conversor de fuentes TTF (TrueType Font) a WOFF2 (Web Open Font Format 2.0) de forma masiva o individual. Utiliza fontTools y compresión brotli para producir fuentes optimizadas para web con tamaños reducidos.

## Requisitos

- Python 3.6+
- Dependencias: `fonttools`, `brotli`

Instalar con:
```bash
pip install fonttools brotli
```

## Uso

```bash
python3 ttf2woff2_converter.py <input> [-o <output_dir>]
```

### Argumentos

- `input` - Ruta a un archivo TTF individual o directorio con archivos TTF
- `-o, --output` - Directorio de salida (default: directorio actual `.`)

### Ejemplos

```bash
# Convertir un archivo TTF
python3 ttf2woff2_converter.py font.ttf

# Convertir a directorio específico
python3 ttf2woff2_converter.py font.ttf -o ./woff2_fonts

# Convertir directorio completo
python3 ttf2woff2_converter.py ./fonts_directory -o ./output
python3 ttf2woff2_converter.py ./fonts -o ./woff2-fonts
```

## Formato de Entrada

### Archivo TTF individual
```
font.ttf
```

### Directorio con múltiples TTF
```
fonts/
  ├── Arial.ttf
  ├── Times.ttf
  └── Courier.ttf
```

## Formato de Salida

### Archivo WOFF2 individual
```
font.woff2
```

### Directorio con múltiples WOFF2
```
woff2_fonts/
  ├── Arial.woff2
  ├── Times.woff2
  └── Courier.woff2
```

## Características

- **Conversión individual o masiva**: Soporta un archivo o directorio completo
- **Compresión brotli**: Reduce tamaño típicamente 30-50% vs TTF
- **Muestra estadísticas**: Calcula y muestra reducción de tamaño
- **Manejo de errores**: Registra errores sin interrumpir proceso
- **Creación automática**: Crea directorio de salida si no existe
- **Progreso visual**: Indica número de archivo en proceso

## Lógica de Funcionamiento

1. Valida que input sea archivo TTF o directorio
2. Crea directorio de salida si no existe
3. Detecta archivos TTF a procesar:
   - Si es archivo TTF → lista contiene ese archivo
   - Si es directorio → busca todos los .ttf dentro
4. Para cada archivo TTF:
   - Carga fuente usando fontTools.ttLib.TTFont
   - Establece flavor a WOFF2
   - Guarda con compresión brotli
   - Calcula reducción de tamaño
5. Muestra resumen con conteos de éxito/error

## Salida en Consola

```
🔧 Configuración del conversor TTF a WOFF2:
   📁 Entrada: ./fonts
   📂 Salida: ./woff2-fonts

✅ Directorio de salida creado: ./woff2-fonts
📂 Escaneando directorio: ./fonts
🚀 Iniciando conversión de 3 archivo(s) TTF:
------------------------------------------------------------
🔄 [1/3] Procesando: Arial.ttf
   ✅ Convertido exitosamente
   📊 Tamaño: 1,234,567 bytes → 567,890 bytes (54.0% reducción)
   💾 Guardado en: ./woff2-fonts/Arial.woff2

🔄 [2/3] Procesando: Times.ttf
   ✅ Convertido exitosamente
   📊 Tamaño: 2,345,678 bytes → 1,123,456 bytes (52.1% reducción)
   💾 Guardado en: ./woff2-fonts/Times.woff2

🔄 [3/3] Procesando: Courier.ttf
   ✅ Convertido exitosamente
   📊 Tamaño: 1,456,789 bytes → 678,901 bytes (53.4% reducción)
   💾 Guardado en: ./woff2-fonts/Courier.woff2

============================================================
🏁 PROCESO COMPLETADO
   ✅ Conversiones exitosas: 3
   ❌ Conversiones fallidas: 0
   📂 Directorio de salida: ./woff2-fonts
============================================================
```

## Ventajas de WOFF2

- Compresión superior a WOFF1 (30-50% menor que TTF)
- Mejor compatibilidad con navegadores modernos
- Optimizado para descarga web
- Soporte para compresión brotli
- Estándar W3C

## Notas/Caveats

- Requiere fonttools y brotli instalados
- Soporta solo archivos .ttf (no .otf, .woff, etc.)
- Compresión puede tomar tiempo con fuentes grandes
- Errores en conversión no interrumpen el proceso (continúa con siguientes)
- Directorio de salida se crea si no existe
- Nombres de archivo se preservan (solo cambia extensión)
- Archivos TTF deben ser válidos (detecta y reporta errores)
- Buen uso para optimizar fonts en sitios web
