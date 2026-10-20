"""
Actualiza el campo de existencia ("q") en parts.json a partir del Excel
semanal de inventario CEDIS que manda Tennant.

Uso:
  python actualizar_existencias_tennant.py parts.json Inventarios_Tennant_XX.xlsx parts_actualizado.json

Reglas:
- Si un Material SÍ aparece en el Excel -> su "q" se actualiza a la cantidad del Excel.
- Si un Material NO aparece en el Excel -> se asume sin existencia (q=0), porque el
  reporte de Tennant solo lista lo que sí tiene en existencia (confirmado: no trae ceros).
- Si el Excel trae un Material que NO existe en parts.json (código nuevo que no está
  en el catálogo), se reporta aparte para que Carlos decida si hay que agregarlo.
- La columna de cantidad puede llamarse "cantidad" (formato anterior) o "Unrestricted"
  (formato desde el 19-oct-2026). Se aceptan ambas, sin importar mayúsculas.
"""
import sys
import json
import pandas as pd

# Nombres que Tennant ha usado para cada columna (en minúsculas) -> nombre interno
ALIAS_COLUMNAS = {
    'material': 'Material',
    'cantidad': 'cantidad',
    'unrestricted': 'cantidad',
}


def normalizar_columnas(df):
    """Renombra las columnas conocidas a los nombres internos y avisa con claridad
    si falta alguna indispensable (Material o cantidad)."""
    nuevas = {}
    for col in df.columns:
        clave = str(col).strip().lower()
        if clave in ALIAS_COLUMNAS and ALIAS_COLUMNAS[clave] not in nuevas.values():
            nuevas[col] = ALIAS_COLUMNAS[clave]
    df = df.rename(columns=nuevas)
    faltan = [c for c in ('Material', 'cantidad') if c not in df.columns]
    if faltan:
        raise ValueError(
            f"El Excel no trae la(s) columna(s) {faltan}. "
            f"Columnas encontradas: {[str(c) for c in df.columns]}"
        )
    return df


def actualizar(parts_path, excel_path, salida_path):
    with open(parts_path, encoding='utf-8') as f:
        parts = json.load(f)

    df = normalizar_columnas(pd.read_excel(excel_path))
    df = df.dropna(subset=['Material', 'cantidad'])
    df['Material'] = df['Material'].astype('int64').astype(str)

    encontrados = 0
    no_en_catalogo = []

    # Paso 1: todo a 0 (sin existencia), salvo lo que se actualice abajo
    for material in parts:
        parts[material]['q'] = 0

    # Paso 2: aplicar las cantidades reales del Excel
    for _, fila in df.iterrows():
        material = str(fila['Material'])
        cantidad = int(fila['cantidad'])
        if material in parts:
            parts[material]['q'] = cantidad
            encontrados += 1
        else:
            no_en_catalogo.append((material, fila.get('desc', ''), cantidad))

    with open(salida_path, 'w', encoding='utf-8') as f:
        json.dump(parts, f, ensure_ascii=False, separators=(',', ':'))

    print(f"✅ Materiales actualizados con existencia real: {encontrados}")
    print(f"⚠️  Materiales del Excel que NO están en el catálogo (parts.json): {len(no_en_catalogo)}")
    if no_en_catalogo:
        print("   Primeros 10 ejemplos:")
        for m, d, c in no_en_catalogo[:10]:
            print(f"   - {m} | {d} | cantidad: {c}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Uso: python actualizar_existencias_tennant.py parts.json Inventarios_Tennant.xlsx parts_actualizado.json")
        sys.exit(1)
    actualizar(sys.argv[1], sys.argv[2], sys.argv[3])
