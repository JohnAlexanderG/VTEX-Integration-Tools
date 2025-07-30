# Resumen
# Este script tomará dos archivos JSON de entrada:
# 1. old_data.json (vieja data con clave "SKU").
# 2. new_data.json (data actualizada con clave "MECA").
# 
# Lógica:
# - Cargar ambos archivos como listas de objetos.
# - Construir un diccionario de new_data usando el valor de "MECA" como clave.
# - Recorrer cada registro en old_data:
#   • Si SKU existe en new_map:
#       - Renombrar "SKU" a "RefId".
#       - Actualizar el campo "Categoría" usando el valor de "CATEGORIA" de new_data,
#         formateándolo en Camel Case por cada segmento separado por ">".
#       - Combinar el resto de campos del registro viejo.
#       - Añadir al resultado.
#   • Si SKU NO existe en new_map:
#       - Omitir el registro (se elimina del resultado).
# - Luego, iterar new_data y para cada MECA que no apareció en old_data:
#   • Crear un objeto mínimo con "RefId" y el campo "Categoría" formateado.
#   • Añadirlo al resultado (para mantener nuevos registros).
# - Exportar la lista resultante a output.json con indentación de 4 espacios.

import json
import sys

from pathlib import Path

def title_case_segment(segment: str) -> str:
    return " ".join(word.capitalize() for word in segment.split())

def format_categoria(cat: str) -> str:
    return ">".join(title_case_segment(seg) for seg in cat.split(">"))

def main(old_path: str, new_path: str, out_path: str):
    old_data = json.loads(Path(old_path).read_text(encoding='utf-8'))
    new_data = json.loads(Path(new_path).read_text(encoding='utf-8'))

    new_map = {item['MECA']: item for item in new_data}
    old_map = {item['SKU']: item for item in old_data}
    result = []

    # Procesar registros comunes y actualizar
    for sku, old_rec in old_map.items():
        if sku in new_map:
            upd = new_map[sku]
            merged = old_rec.copy()
            merged['RefId'] = sku
            # Actualizar categoría
            merged['Categoría'] = format_categoria(upd['CATEGORIA'])
            # Agregar campo Name desde DESCRIPCION del archivo nuevo
            merged['Name'] = upd['DESCRIPCION']
            # Renombrar Descripción a Description manteniendo el valor del archivo viejo
            if 'Descripción' in merged:
                merged['Description'] = merged.pop('Descripción')
            # Eliminar campo SKU original
            merged.pop('SKU', None)
            result.append(merged)
        # Si no existe en new_map, lo omitimos (se descarta)

    # Incluir nuevos registros no presentes en old_data
    for meca, new_rec in new_map.items():
        if meca not in old_map:
            minimal = {
                'RefId': meca,
                'Categoría': format_categoria(new_rec['CATEGORIA']),
                'Name': new_rec['DESCRIPCION'],
                'Description': ''
            }
            result.append(minimal)

    # Escribir JSON de salida
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=4), encoding='utf-8')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f"Uso: {sys.argv[0]} <old_data.json> <new_data.json> <output.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
