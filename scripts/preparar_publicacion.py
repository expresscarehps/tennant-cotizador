"""
Prepara la publicación de existencias CEDIS Tennant a partir del Excel que llega
por correo (se corre dentro de la GitHub Action, pero también se puede correr a mano).

Qué hace:
  1. Lee la fecha del inventario desde el nombre del archivo
     (ej. "Inventarios Tennant 19-oct-26.xlsx" -> 19 de octubre de 2026).
  2. Corre actualizar_existencias_tennant.py para generar el parts.json nuevo.
  3. Valida el resultado (ver VALIDACIONES) y arma un resumen para el correo de aprobación.
  4. Escribe data/cedis_meta.json con la fecha, para que el cotizador la muestre solo.

Uso:
  python preparar_publicacion.py --excel incoming/Inventarios_Tennant_19-oct-26.xlsx \
      --parts data/parts.json --meta data/cedis_meta.json --resumen resumen.json

Si alguna validación "bloqueante" falla, resumen["ok"] = False, NO se modifica
parts.json ni cedis_meta.json y el programa termina con código 2.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from actualizar_existencias_tennant import actualizar  # noqa: E402

# ── VALIDACIONES (umbrales propuestos; se pueden ajustar) ──
MIN_RATIO_CON_EXISTENCIA = 0.5   # bloqueante: menos de la mitad de las partes con existencia que la corrida anterior
MAX_RATIO_CON_EXISTENCIA = 1.5   # bloqueante: más de 1.5 veces
MAX_NO_EN_CATALOGO_AVISO = 400   # aviso: muchos códigos del Excel que no están en el catálogo

MESES = {
    'ene': 1, 'jan': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'aug': 8, 'sep': 9, 'sept': 9, 'set': 9, 'oct': 10,
    'nov': 11, 'dic': 12, 'dec': 12,
}
MESES_TEXTO = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def fecha_desde_nombre(nombre):
    """'Inventarios Tennant 19-oct-26.xlsx' -> datetime.date(2026, 10, 19). None si no se puede."""
    m = re.search(r'(\d{1,2})[-_ ]([A-Za-z]{3,4})[-_ ](\d{2,4})', os.path.basename(nombre))
    if not m:
        return None
    dia, mes_txt, anio = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    mes = MESES.get(mes_txt)
    if not mes:
        return None
    if anio < 100:
        anio += 2000
    try:
        return datetime.date(anio, mes, dia)
    except ValueError:
        return None


def fecha_texto(fecha):
    return f"{fecha.day} de {MESES_TEXTO[fecha.month - 1]} de {fecha.year}"


def _con_existencia(parts):
    return sum(1 for v in parts.values() if v.get('q', 0) > 0)


def preparar(excel, parts_path, meta_path, resumen_path):
    resumen = {'ok': True, 'bloqueantes': [], 'avisos': [], 'archivo': os.path.basename(excel)}

    def bloquear(msg):
        resumen['ok'] = False
        resumen['bloqueantes'].append(msg)

    with open(parts_path, encoding='utf-8') as f:
        antes = json.load(f)

    # 1) Fecha del inventario
    fecha = fecha_desde_nombre(excel)
    if fecha is None:
        bloquear(f"No pude leer la fecha del nombre del archivo: {os.path.basename(excel)}")
    else:
        resumen['fecha_iso'] = fecha.isoformat()
        resumen['fecha_texto'] = fecha_texto(fecha)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding='utf-8') as f:
                    previa = json.load(f).get('fecha_iso')
                if previa:
                    resumen['fecha_anterior'] = previa
                    if fecha.isoformat() < previa:
                        bloquear(f"El inventario ({fecha.isoformat()}) es MÁS VIEJO que el publicado ({previa}).")
                    elif fecha.isoformat() == previa:
                        resumen['avisos'].append(f"Ya hay un inventario publicado con esa misma fecha ({previa}).")
            except (ValueError, OSError):
                resumen['avisos'].append("No pude leer data/cedis_meta.json anterior.")

    # 2) Generar el parts.json nuevo en un archivo temporal (no se toca el real todavía)
    tmpdir = tempfile.mkdtemp()
    salida_tmp = os.path.join(tmpdir, 'parts_nuevo.json')
    nuevo = None
    try:
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            actualizar(parts_path, excel, salida_tmp)
        resumen['log_script'] = buf.getvalue().strip()
        with open(salida_tmp, encoding='utf-8') as f:
            nuevo = json.load(f)
    except Exception as e:  # columnas faltantes, archivo dañado, etc.
        bloquear(f"El script no pudo procesar el Excel: {e}")

    if nuevo is not None:
        # 3) Validaciones sobre el resultado
        if set(antes) != set(nuevo):
            bloquear("Cambió la lista de partes del catálogo (no debería: solo se actualizan existencias).")
        if any(k.endswith('.0') for k in nuevo):
            bloquear("Hay códigos con sufijo '.0' en el resultado.")
        otros = sum(1 for k in antes if k in nuevo for c in antes[k]
                    if c != 'q' and antes[k][c] != nuevo[k].get(c))
        if otros:
            bloquear(f"Cambiaron {otros} campos que NO son la existencia (precio, descripción, etc.).")
        if any((not isinstance(v.get('q'), int)) or v['q'] < 0 for v in nuevo.values()):
            bloquear("Hay existencias negativas o que no son números enteros.")

        n_antes, n_ahora = _con_existencia(antes), _con_existencia(nuevo)
        resumen.update({'partes_total': len(nuevo), 'con_existencia_antes': n_antes,
                        'con_existencia_ahora': n_ahora})
        if n_antes:
            ratio = n_ahora / n_antes
            if ratio < MIN_RATIO_CON_EXISTENCIA or ratio > MAX_RATIO_CON_EXISTENCIA:
                bloquear(f"Partes con existencia: {n_antes} -> {n_ahora} (fuera del rango razonable "
                         f"{int(MIN_RATIO_CON_EXISTENCIA*100)}%-{int(MAX_RATIO_CON_EXISTENCIA*100)}%).")

        cambian = [k for k in antes if antes[k].get('q', 0) != nuevo[k]['q']]
        a_cero = [k for k in cambian if nuevo[k]['q'] == 0]
        vuelven = [k for k in cambian if antes[k].get('q', 0) == 0]

        def ejemplo(k):
            return {'codigo': k, 'descripcion': nuevo[k].get('d', ''), 'antes': antes[k].get('q', 0),
                    'ahora': nuevo[k]['q']}

        resumen.update({
            'cambian': len(cambian), 'a_cero': len(a_cero), 'vuelven': len(vuelven),
            'solo_cantidad': len(cambian) - len(a_cero) - len(vuelven),
            'ejemplos_a_cero': [ejemplo(k) for k in a_cero[:10]],
            'ejemplos_vuelven': [ejemplo(k) for k in vuelven[:10]],
        })
        m = re.search(r'NO están en el catálogo[^:]*:\s*(\d+)', resumen.get('log_script', ''))
        if m:
            resumen['no_en_catalogo'] = int(m.group(1))
            if int(m.group(1)) > MAX_NO_EN_CATALOGO_AVISO:
                resumen['avisos'].append(f"{m.group(1)} códigos del Excel no están en el catálogo (son muchos).")

        # 4) Solo si todo está bien, escribir los archivos reales
        if resumen['ok']:
            shutil.copyfile(salida_tmp, parts_path)
            os.makedirs(os.path.dirname(os.path.abspath(meta_path)), exist_ok=True)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'fecha_iso': resumen['fecha_iso'],
                    'fecha_texto': resumen['fecha_texto'],
                    'archivo': resumen['archivo'],
                    'partes_con_existencia': n_ahora,
                }, f, ensure_ascii=False, indent=2)
                f.write('\n')
    shutil.rmtree(tmpdir, ignore_errors=True)

    with open(resumen_path, 'w', encoding='utf-8') as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    return resumen


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--excel', required=True)
    ap.add_argument('--parts', default='data/parts.json')
    ap.add_argument('--meta', default='data/cedis_meta.json')
    ap.add_argument('--resumen', default='resumen.json')
    a = ap.parse_args()
    r = preparar(a.excel, a.parts, a.meta, a.resumen)
    print(json.dumps({k: r[k] for k in r if k not in ('log_script',)}, ensure_ascii=False, indent=2))
    sys.exit(0 if r['ok'] else 2)
