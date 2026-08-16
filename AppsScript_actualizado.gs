function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    // ── Directorio de clientes: Bind ERP (Clientes + Prospectos) ──
    if (data.accion === 'listaClientesBind') {
      return listaClientesBind();
    }
    if (data.accion === 'agregarProspectoBind') {
      return agregarProspectoBind(data);
    }

    // ── Pedir el siguiente folio centralizado ──
    if (data.accion === 'obtenerFolio') {
      return obtenerFolioSiguiente();
    }

    // ── Guardar PDF en Google Drive ──
    if (data.accion === 'guardarPDF') {
      return guardarPDFEnDrive(data);
    }

    // ── Guardar fila en Google Sheets (como antes) ──
    const nombreHoja = data.hoja || 'Cotizaciones';
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let hoja = ss.getSheetByName(nombreHoja);

    if (!hoja) {
      hoja = ss.insertSheet(nombreHoja);
    }

    if (hoja.getLastRow() === 0) {
      hoja.appendRow([
        'Folio', 'Fecha', 'Cliente', 'Equipo', 'Moneda',
        'Total Tennant', 'Total IPC', 'Total Servicios', 'Gran Total',
        'Detalle de partidas'
      ]);
      hoja.getRange(1, 1, 1, 10).setFontWeight('bold');
    }

    hoja.appendRow([
      data.folio   || '',
      data.fecha   || '',
      data.cliente || '',
      data.equipo  || '',
      data.moneda  || '',
      data.tnn     || 0,
      data.ipc     || 0,
      data.srv     || 0,
      data.gran    || 0,
      data.detalle || ''
    ]);

    return ContentService.createTextOutput(JSON.stringify({ resultado: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({ resultado: 'error', mensaje: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ═══════════════════════════════════════════════════════════════
// BIND ERP — Directorio de clientes (Clientes + Prospectos)
// ═══════════════════════════════════════════════════════════════
// La API Key NUNCA va escrita aquí en el código. Vive en:
// Configuración del proyecto (ícono de engrane) → Propiedades del script
// → Agregar propiedad → nombre: BIND_API_KEY, valor: tu llave de Bind ERP.
const BIND_BASE = 'https://api.bind.com.mx';

function bindApiKey_() {
  return PropertiesService.getScriptProperties().getProperty('BIND_API_KEY');
}

function bindFetch_(path, method, payload) {
  const options = {
    method: method || 'get',
    headers: { 'Authorization': 'Bearer ' + bindApiKey_() },
    muteHttpExceptions: true
  };
  if (payload) {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(payload);
  }
  const resp = UrlFetchApp.fetch(BIND_BASE + path, options);
  const code = resp.getResponseCode();
  const text = resp.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('Bind ERP ' + path + ' respondió ' + code + ': ' + text.substring(0, 300));
  }
  const json = JSON.parse(text);
  // Las listas de Bind vienen paginadas estilo OData ({value:[...]});
  // si no trae esa envoltura, se asume que la respuesta ya es el arreglo.
  return Array.isArray(json) ? json : (json.value || json.items || json);
}

function listaClientesBind() {
  const salida = { resultado: 'ok', clientes: [], prospectos: [] };
  try {
    const clientes = bindFetch_('/api/Clients', 'get');
    salida.clientes = (clientes || []).map(function(c) {
      return { nombre: (c.ClientName || c.LegalName || '').trim(), tipo: 'Cliente' };
    }).filter(function(c) { return c.nombre; });
  } catch (e) {
    salida.errorClientes = e.toString();
  }
  try {
    const prospectos = bindFetch_('/api/Prospects', 'get');
    salida.prospectos = (prospectos || []).map(function(p) {
      return { nombre: (p.ClientName || p.LegalName || p.Name || '').trim(), tipo: 'Prospecto' };
    }).filter(function(p) { return p.nombre; });
  } catch (e) {
    salida.errorProspectos = e.toString();
  }
  return ContentService.createTextOutput(JSON.stringify(salida))
    .setMimeType(ContentService.MimeType.JSON);
}

function agregarProspectoBind(data) {
  try {
    bindFetch_('/api/Prospects', 'post', { ClientName: data.nombre });
    return ContentService.createTextOutput(JSON.stringify({ resultado: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({ resultado: 'error', mensaje: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function obtenerFolioSiguiente() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let config = ss.getSheetByName('Config');

  if (!config) {
    config = ss.insertSheet('Config');
    config.getRange('A1').setValue('Año');
    config.getRange('B1').setValue(0);
    config.getRange('A2').setValue('Último folio usado');
    config.getRange('B2').setValue(0);
    config.getRange('A1:A2').setFontWeight('bold');
  }

  const anioActual = new Date().getFullYear();
  const anioGuardado = config.getRange('B1').getValue();
  let consecutivo = config.getRange('B2').getValue() || 0;

  if (anioGuardado !== anioActual) {
    consecutivo = 0;
    config.getRange('B1').setValue(anioActual);
  }

  consecutivo = consecutivo + 1;
  config.getRange('B2').setValue(consecutivo);

  const folio = 'TNTREF' + String(consecutivo).padStart(4, '0') + anioActual;

  return ContentService.createTextOutput(JSON.stringify({ resultado: 'ok', folio: folio }))
    .setMimeType(ContentService.MimeType.JSON);
}

function guardarPDFEnDrive(data) {
  try {
    const nombreCarpeta = data.carpeta || 'Cotizaciones PDF';
    const carpetas = DriveApp.getFoldersByName(nombreCarpeta);
    const carpeta = carpetas.hasNext() ? carpetas.next() : DriveApp.createFolder(nombreCarpeta);

    const blob = Utilities.newBlob(
      Utilities.base64Decode(data.contenidoBase64),
      'application/pdf',
      data.nombreArchivo || 'cotizacion.pdf'
    );

    carpeta.createFile(blob);

    return ContentService.createTextOutput(JSON.stringify({ resultado: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({ resultado: 'error', mensaje: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  const accion = e.parameter && e.parameter.accion;
  if (accion === 'listaClientesBind') {
    return listaClientesBind();
  }
  if (accion === 'debugBind') {
    return debugBind();
  }
  return ContentService.createTextOutput(JSON.stringify({ estado: 'Apps Script funcionando correctamente' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// Muestra la respuesta cruda de Bind ERP, sin filtrar nada — solo para diagnóstico
function debugBind() {
  const options = {
    method: 'get',
    headers: { 'Authorization': 'Bearer ' + bindApiKey_() },
    muteHttpExceptions: true
  };
  const resp = UrlFetchApp.fetch(BIND_BASE + '/api/Clients', options);
  return ContentService.createTextOutput(JSON.stringify({
    codigo: resp.getResponseCode(),
    textoCrudo: resp.getContentText().substring(0, 1500)
  })).setMimeType(ContentService.MimeType.JSON);
}
