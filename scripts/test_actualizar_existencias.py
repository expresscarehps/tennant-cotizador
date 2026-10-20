"""
Pruebas automáticas para actualizar_existencias_tennant.py

Se corren ANTES de entregar cualquier parts.json actualizado a Carlos.
Uso: python3 test_actualizar_existencias.py
"""
import json
import os
import tempfile
import pandas as pd
from actualizar_existencias_tennant import actualizar

fallos = 0

def assert_test(cond, msg):
    global fallos
    if not cond:
        print(f"❌ FALLÓ: {msg}")
        fallos += 1
    else:
        print(f"✅ OK: {msg}")

# ── Preparar un parts.json de prueba ──
parts_prueba = {
    "4040849": {"d": "BLADE, SQGE, FRONT, 788L", "p": 20.8, "e": "1203954", "marca": "Tennant", "moneda": "USD", "q": 999},
    "9999999": {"d": "PIEZA SIN MOVIMIENTO EN ESTE CORTE", "p": 10.0, "e": "", "marca": "Tennant", "moneda": "USD", "q": 5},
}

with tempfile.TemporaryDirectory() as tmpdir:
    parts_path = os.path.join(tmpdir, 'parts_test.json')
    excel_path = os.path.join(tmpdir, 'inventario_test.xlsx')
    salida_path = os.path.join(tmpdir, 'parts_actualizado_test.json')

    with open(parts_path, 'w', encoding='utf-8') as f:
        json.dump(parts_prueba, f)

    # ── Caso normal: un material con movimiento ──
    df_normal = pd.DataFrame({
        'Material': [4040849],
        'tipo': ['Refacc'],
        'desc': ['BLADE, SQGE, FRONT, 788L'],
        'cantidad': [176]
    })
    df_normal.to_excel(excel_path, index=False)
    actualizar(parts_path, excel_path, salida_path)
    with open(salida_path, encoding='utf-8') as f:
        resultado = json.load(f)

    assert_test(resultado['4040849']['q'] == 176, 'Material con movimiento se actualiza a la cantidad real (176)')
    assert_test(resultado['9999999']['q'] == 0, 'Material que NO aparece en el Excel se resetea a 0 (sin existencia)')
    assert_test(resultado['4040849']['d'] == 'BLADE, SQGE, FRONT, 788L', 'Los demás campos (descripción) no se tocan')
    assert_test(resultado['4040849']['p'] == 20.8, 'El precio no se toca, solo la existencia')

    # ── Caso crítico: fila vacía al final del Excel (el bug real que encontramos) ──
    df_con_vacia = pd.DataFrame({
        'Material': [4040849, None],
        'tipo': ['Refacc', None],
        'desc': ['BLADE, SQGE, FRONT, 788L', None],
        'cantidad': [263, None]
    })
    df_con_vacia.to_excel(excel_path, index=False)
    actualizar(parts_path, excel_path, salida_path)
    with open(salida_path, encoding='utf-8') as f:
        resultado2 = json.load(f)

    assert_test(resultado2['4040849']['q'] == 263, 'Con una fila vacía al final del Excel, el material real igual se actualiza bien (no se rompe)')

    # ── Caso: el código no debe quedar con sufijo ".0" (el bug específico de hoy) ──
    assert_test('4040849' in resultado2, 'El código de Material no queda con sufijo ".0" (ej. "4040849.0")')
    assert_test('4040849.0' not in resultado2, 'Confirmar que NO existe una llave duplicada con ".0"')

    # ── Formato nuevo de Tennant (desde 19-oct-2026): la cantidad viene como "Unrestricted" ──
    df_unrestricted = pd.DataFrame({
        'Material': [4040849, 4040849 + 1],
        'tipo': ['Refacc', 'Refacc'],
        'desc': ['BLADE, SQGE, FRONT, 788L', 'OTRA'],
        'Base Unit of Measure': ['PC', 'PC'],
        'Unrestricted': [73.0, 5.0]
    })
    df_unrestricted.to_excel(excel_path, index=False)
    actualizar(parts_path, excel_path, salida_path)
    with open(salida_path, encoding='utf-8') as f:
        resultado3 = json.load(f)
    assert_test(resultado3['4040849']['q'] == 73, 'Formato nuevo: la columna "Unrestricted" se toma como cantidad (73)')
    assert_test(resultado3['9999999']['q'] == 0, 'Formato nuevo: lo que no aparece sigue quedando en 0')

    # ── Mayúsculas/espacios distintos en los encabezados ──
    df_raro = pd.DataFrame({' material ': [4040849], 'UNRESTRICTED': [12.0]})
    df_raro.to_excel(excel_path, index=False)
    actualizar(parts_path, excel_path, salida_path)
    with open(salida_path, encoding='utf-8') as f:
        resultado4 = json.load(f)
    assert_test(resultado4['4040849']['q'] == 12, 'Encabezados con otras mayúsculas o espacios también funcionan')

    # ── Si falta la columna de cantidad, el error debe ser claro (no un KeyError críptico) ──
    pd.DataFrame({'Material': [4040849], 'otra': [1]}).to_excel(excel_path, index=False)
    mensaje = ''
    try:
        actualizar(parts_path, excel_path, salida_path)
    except ValueError as e:
        mensaje = str(e)
    assert_test('cantidad' in mensaje and 'Columnas encontradas' in mensaje,
                'Sin columna de cantidad: el error dice qué falta y qué columnas llegaron')

print('\n' + '─'*50)
if fallos == 0:
    print('✅ TODAS LAS PRUEBAS PASARON — seguro correr una actualización real.')
else:
    print(f'❌ {fallos} prueba(s) fallaron — NO usar el script hasta corregir.')
    exit(1)
