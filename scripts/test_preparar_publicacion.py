"""
Pruebas automáticas para preparar_publicacion.py (validaciones, fecha y resumen).
Uso: python3 test_preparar_publicacion.py
"""
import datetime
import json
import os
import tempfile
import pandas as pd
from preparar_publicacion import preparar, fecha_desde_nombre, fecha_texto

fallos = 0


def assert_test(cond, msg):
    global fallos
    if not cond:
        print(f"❌ FALLÓ: {msg}")
        fallos += 1
    else:
        print(f"✅ OK: {msg}")


def parte(d, q=0):
    return {"d": d, "p": 10.0, "e": "", "marca": "Tennant", "moneda": "USD", "q": q}


# ── Fechas desde el nombre del archivo ──
assert_test(fecha_desde_nombre('Inventarios Tennant 19-oct-26.xlsx') == datetime.date(2026, 10, 19), 'Fecha "19-oct-26" (minúsculas, español)')
assert_test(fecha_desde_nombre('Inventarios_Tennant_31-Aug-26.xlsx') == datetime.date(2026, 8, 31), 'Fecha "31-Aug-26" (inglés)')
assert_test(fecha_desde_nombre('incoming/Inventarios_Tennant_5-oct-26.xlsx') == datetime.date(2026, 10, 5), 'Fecha de un día con un solo dígito y con carpeta')
assert_test(fecha_desde_nombre('inventario.xlsx') is None, 'Nombre sin fecha -> None')
assert_test(fecha_texto(datetime.date(2026, 10, 19)) == '19 de octubre de 2026', 'Texto de la fecha en español')

with tempfile.TemporaryDirectory() as tmp:
    parts_path = os.path.join(tmp, 'parts.json')
    meta_path = os.path.join(tmp, 'cedis_meta.json')
    resumen_path = os.path.join(tmp, 'resumen.json')

    # 10 partes; 6 con existencia antes
    base = {str(1000 + i): parte(f'PIEZA {i}', 5 if i < 6 else 0) for i in range(10)}

    def escribir_parts():
        with open(parts_path, 'w', encoding='utf-8') as f:
            json.dump(base, f)

    def excel(nombre, filas, col='Unrestricted'):
        ruta = os.path.join(tmp, nombre)
        pd.DataFrame({'Material': [int(m) for m, _ in filas], 'tipo': 'Refacc', col: [c for _, c in filas]}).to_excel(ruta, index=False)
        return ruta

    # ── Caso bueno ──
    escribir_parts()
    with open(meta_path, 'w') as f:
        json.dump({'fecha_iso': '2026-10-05'}, f)
    x = excel('Inventarios Tennant 19-oct-26.xlsx', [('1000', 7), ('1001', 5), ('1002', 5), ('1003', 5), ('1004', 5), ('1008', 2), ('5555', 9)])
    r = preparar(x, parts_path, meta_path, resumen_path)
    nuevo = json.load(open(parts_path))
    meta = json.load(open(meta_path))
    assert_test(r['ok'] and not r['bloqueantes'], 'Caso normal: pasa todas las validaciones')
    assert_test(nuevo['1000']['q'] == 7 and nuevo['1005']['q'] == 0 and nuevo['1008']['q'] == 2, 'Las existencias se actualizan (7), se ponen en 0 (1005) y reaparecen (1008)')
    assert_test(meta['fecha_iso'] == '2026-10-19' and meta['fecha_texto'] == '19 de octubre de 2026', 'cedis_meta.json trae la fecha correcta')
    assert_test(r['a_cero'] == 1 and r['vuelven'] == 1 and r['solo_cantidad'] == 1 and r['cambian'] == 3, 'Resumen: 1 a cero, 1 vuelve, 1 solo cambia cantidad')
    assert_test(r.get('no_en_catalogo') == 1, 'Resumen: 1 código del Excel no está en el catálogo (5555)')
    assert_test(json.load(open(resumen_path))['con_existencia_ahora'] == 6, 'El resumen se guarda en el archivo indicado')

    # ── Inventario más viejo que el publicado: bloquea y NO toca archivos ──
    escribir_parts()
    with open(meta_path, 'w') as f:
        json.dump({'fecha_iso': '2026-10-19'}, f)
    antes_parts = open(parts_path).read()
    x = excel('Inventarios Tennant 5-oct-26.xlsx', [('1000', 1)] + [(str(1000 + i), 5) for i in range(1, 6)])
    r = preparar(x, parts_path, meta_path, resumen_path)
    assert_test(not r['ok'] and any('MÁS VIEJO' in b for b in r['bloqueantes']), 'Inventario más viejo: se bloquea')
    assert_test(open(parts_path).read() == antes_parts, 'Al bloquear, parts.json queda intacto')
    assert_test(json.load(open(meta_path))['fecha_iso'] == '2026-10-19', 'Al bloquear, cedis_meta.json queda intacto')

    # ── Casi todo desaparece: fuera de rango razonable ──
    escribir_parts()
    x = excel('Inventarios Tennant 26-oct-26.xlsx', [('1000', 1)])
    r = preparar(x, parts_path, meta_path, resumen_path)
    assert_test(not r['ok'] and any('fuera del rango' in b for b in r['bloqueantes']), '6 partes con existencia -> 1: se bloquea por rango')

    # ── Excel sin columna de cantidad ──
    escribir_parts()
    ruta = os.path.join(tmp, 'Inventarios Tennant 26-oct-26.xlsx')
    pd.DataFrame({'Material': [1000], 'otra': [1]}).to_excel(ruta, index=False)
    r = preparar(ruta, parts_path, meta_path, resumen_path)
    assert_test(not r['ok'] and any('no pudo procesar' in b for b in r['bloqueantes']), 'Excel sin columna de cantidad: se bloquea con mensaje')

    # ── Nombre sin fecha ──
    escribir_parts()
    x = excel('inventario.xlsx', [(str(1000 + i), 5) for i in range(6)])
    r = preparar(x, parts_path, meta_path, resumen_path)
    assert_test(not r['ok'] and any('fecha' in b for b in r['bloqueantes']), 'Nombre sin fecha: se bloquea')

    # ── Formato viejo (columna cantidad) sigue funcionando ──
    escribir_parts()
    with open(meta_path, 'w') as f:
        json.dump({'fecha_iso': '2026-10-05'}, f)
    x = excel('Inventarios Tennant 12-oct-26.xlsx', [(str(1000 + i), 5) for i in range(6)], col='cantidad')
    r = preparar(x, parts_path, meta_path, resumen_path)
    assert_test(r['ok'], 'El formato anterior (columna "cantidad") sigue funcionando')

print('\n' + '─' * 50)
if fallos == 0:
    print('✅ TODAS LAS PRUEBAS PASARON')
else:
    print(f'❌ {fallos} prueba(s) fallaron')
    raise SystemExit(1)
