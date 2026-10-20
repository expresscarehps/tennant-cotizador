"""
Avisa a n8n el resultado de la preparación de existencias (para el correo de aprobación).
Variables de entorno: N8N_WEBHOOK_URL, PRUEBAS (success/failure/skipped), PREPARAR (success/failure/skipped),
RAMA (nombre de la rama con el resultado, vacío si no se creó), RUN_URL, ARCHIVO.
"""
import json
import os
import urllib.request


def leer(ruta, defecto=''):
    try:
        with open(ruta, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return defecto


resumen = {}
try:
    resumen = json.loads(leer('resumen.json', '{}') or '{}')
except ValueError:
    pass

log_pruebas = leer('pruebas.log')
payload = {
    'ok': os.environ.get('PRUEBAS') == 'success' and os.environ.get('PREPARAR') == 'success'
          and bool(os.environ.get('RAMA')),
    'pruebas': os.environ.get('PRUEBAS', ''),
    'preparar': os.environ.get('PREPARAR', ''),
    'rama': os.environ.get('RAMA', ''),
    'archivo': os.environ.get('ARCHIVO', ''),
    'run_url': os.environ.get('RUN_URL', ''),
    'resumen': resumen,
    'log_pruebas': '\n'.join(log_pruebas.strip().splitlines()[-25:]),
}
url = os.environ.get('N8N_WEBHOOK_URL', '')
if not url or url.startswith('PENDIENTE'):
    print('Sin URL de n8n configurada; no se envía aviso.')
    print(json.dumps(payload, ensure_ascii=False)[:2000])
else:
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        print('Aviso enviado a n8n:', r.status)
