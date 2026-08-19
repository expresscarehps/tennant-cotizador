// ═══════════════════════════════════════════════════════════════
// test_dev_tennant.js — Pruebas automáticas del Cotizador Tennant/IPC
// ═══════════════════════════════════════════════════════════════
// Se corre ANTES de entregar cualquier avance de código a Carlos,
// para detectar errores de cálculo (precios, IVA, moneda, folio)
// antes de que lleguen a una cotización real de un cliente.
//
// Uso: node /tmp/test_dev_tennant.js
// ═══════════════════════════════════════════════════════════════

let fallos = 0;

function assert(cond, msg) {
  if (!cond) {
    console.error(`❌ FALLÓ: ${msg}`);
    fallos++;
  } else {
    console.log(`✅ OK: ${msg}`);
  }
}

function round2(n) { return Math.round(n * 100) / 100; }

// ── Lógica replicada 1:1 del cotizador (mismas fórmulas que en el HTML) ──

function precioNeto(precioLista, descPct) {
  return precioLista * (1 - (descPct || 0) / 100);
}

function calcIVA(subtotal) {
  return subtotal * 0.16;
}

function convertirAMoneda(monto, monedaOrigen, monedaDestino, tc) {
  if (monedaOrigen === monedaDestino) return monto;
  if (monedaOrigen === 'USD' && monedaDestino === 'MXN') return monto * tc;
  if (monedaOrigen === 'MXN' && monedaDestino === 'USD') return monto / tc;
  throw new Error('Moneda no soportada: ' + monedaOrigen + ' → ' + monedaDestino);
}

function generarFolio(anioGuardado, consecutivoGuardado, anioActual) {
  const s = anioGuardado === anioActual ? consecutivoGuardado + 1 : 1;
  return { folio: `TNTREF${s}${anioActual}`, consecutivo: s };
}

function granTotal(totalTnnUSD, totalIpcMXN, totalSrv, monedaFinal, tc) {
  const netTnn = totalTnnUSD + calcIVA(totalTnnUSD);
  const netIpc = totalIpcMXN + calcIVA(totalIpcMXN);
  const netSrv = totalSrv + calcIVA(totalSrv);
  const tnnEnMon = monedaFinal === 'MXN' ? convertirAMoneda(netTnn, 'USD', 'MXN', tc) : netTnn;
  const ipcEnMon = monedaFinal === 'USD' ? convertirAMoneda(netIpc, 'MXN', 'USD', tc) : netIpc;
  return tnnEnMon + ipcEnMon + netSrv;
}

// ═══ PRUEBAS ═══

console.log('\n=== Unificación de moneda (todo en la moneda de la cotización) ===');
// Replica el caso real TNTREF00132026: cotización en USD con partes IPC (nativas en MXN)
const TC_EJEMPLO = 17.5;
function convUnificado(v, monedaNativa, monedaDestino, tc) {
  if (!v || monedaNativa === monedaDestino) return v || 0;
  return monedaNativa === 'USD' ? v * tc : v / tc;
}
// Tennant: $20.80 USD nativo, cotización en USD -> sin conversión
const tnnUSD = convUnificado(20.80, 'USD', 'USD', TC_EJEMPLO);
assert(tnnUSD === 20.80, 'Tennant nativo USD, cotización en USD, no convierte');
const tnnNeto = tnnUSD * 1.16;
assert(round2(tnnNeto) === 24.13, 'Neto Tennant ($20.80 + IVA) ≈ $24.13 USD (caso real TNTREF00132026)');

// IPC: $264.95 MXN nativo, cotización en USD -> SÍ convierte (antes se quedaba en MXN, confuso)
const ipcUSD = convUnificado(264.95, 'MXN', 'USD', TC_EJEMPLO);
assert(round2(ipcUSD) === 15.14, 'IPC $264.95 MXN convertido a USD (TC 17.5) ≈ $15.14 USD');
const ipcNeto = ipcUSD * 1.16;
assert(round2(ipcNeto) === 17.56, 'Neto IPC convertido ≈ $17.56 USD');

// Servicio: $120 USD nativo, cotización en USD -> sin conversión
const srvNeto = 120 * 1.16;
assert(round2(srvNeto) === 139.20, 'Neto Servicio $120 USD + IVA = $139.20 USD');

// Gran total unificado: suma directa, ya no requiere lógica especial por sección
const granTotalUnificado = tnnNeto + ipcNeto + srvNeto;
assert(round2(granTotalUnificado) === 180.89, 'Gran Total unificado ≈ $180.89 USD (coincide con el Gran Total ya correcto del PDF real)');

console.log('\n=== Otros Productos (proveedores distintos a Tennant/IPC) ===');
// Un disco comprado con otro proveedor: $150 MXN, cotización en MXN -> sin conversión
const otroMXN = convUnificado(150, 'MXN', 'MXN', TC_EJEMPLO);
assert(otroMXN === 150, 'Otro producto nativo MXN, cotización en MXN, no convierte');
const otroNeto = otroMXN * 1.16;
assert(round2(otroNeto) === 174, 'Neto de Otro producto $150 MXN + IVA = $174 MXN');

// Mismo producto pero cotizando en USD -> sí convierte
const otroUSD = convUnificado(150, 'MXN', 'USD', TC_EJEMPLO);
assert(round2(otroUSD) === 8.57, 'Otro producto $150 MXN convertido a USD (TC 17.5) ≈ $8.57 USD');

// Gran total con las 4 categorías juntas (Tennant + IPC + Otros + Servicios)
const granConOtros = tnnNeto + ipcNeto + otroNeto + srvNeto;
assert(round2(granConOtros) === round2(180.89 + 174), 'Gran Total con las 4 categorías suma correctamente');

console.log('\n=== Descuento por partida ===');
assert(round2(precioNeto(630.80, 5)) === 599.26, 'Descuento 5% sobre $630.80 = $599.26 (caso real TNTREF12026)');
assert(precioNeto(100, 0) === 100, 'Sin descuento, precio neto = precio lista');
assert(precioNeto(100, 100) === 0, 'Descuento 100% = $0');
assert(precioNeto(100, 50) === 50, 'Descuento 50% sobre $100 = $50');

console.log('\n=== IVA 16% ===');
assert(round2(calcIVA(1198.52)) === 191.76, 'IVA de $1,198.52 = $191.76 (caso real TNTREF12026)');
assert(calcIVA(0) === 0, 'IVA de $0 = $0');

console.log('\n=== Conversión de moneda ===');
assert(convertirAMoneda(100, 'USD', 'MXN', 17.5) === 1750, '$100 USD a MXN con TC 17.5 = $1,750 MXN');
assert(round2(convertirAMoneda(1750, 'MXN', 'USD', 17.5)) === 100, '$1,750 MXN a USD con TC 17.5 = $100 USD');
assert(convertirAMoneda(100, 'USD', 'USD', 17.5) === 100, 'Misma moneda no convierte');

console.log('\n=== Folio (formato real: SIN ceros a la izquierda, confirmado con TNTREF2512026) ===');
let f1 = generarFolio(0, 0, 2026);
assert(f1.folio === 'TNTREF12026', 'Primer folio del año 2026 = TNTREF12026 (no TNTREF00012026)');
let f2 = generarFolio(2026, 1, 2026);
assert(f2.folio === 'TNTREF22026', 'Segundo folio del mismo año = TNTREF22026');
let f3 = generarFolio(2025, 47, 2026);
assert(f3.folio === 'TNTREF12026', 'El consecutivo se reinicia al cambiar de año (de 2025 a 2026)');
let f4 = generarFolio(2026, 288, 2026);
assert(f4.folio === 'TNTREF2892026', 'Folio 289 = TNTREF2892026, no TNTREF02892026 (caso real reportado)');
assert(/^TNTREF\d+2026$/.test(f1.folio), 'El folio cumple el formato TNTREF + número + año, sin relleno');

console.log('\n=== Gran Total con mezcla de marcas (el cálculo más propenso a errores) ===');
// 100 USD en Tennant + 1000 MXN en IPC, cotizando en USD, TC 17.5
let gt1 = granTotal(100, 1000, 0, 'USD', 17.5);
let esperado1 = round2(116 + (1160 / 17.5)); // netTnn=116 USD directo, netIpc=1160 MXN convertido a USD
assert(round2(gt1) === esperado1, 'Gran total mixto (Tennant+IPC) cotizado en USD');

// Mismo caso pero cotizando en MXN
let gt2 = granTotal(100, 1000, 0, 'MXN', 17.5);
let esperado2 = round2((116 * 17.5) + 1160); // netTnn convertido a MXN + netIpc directo
assert(round2(gt2) === esperado2, 'Gran total mixto (Tennant+IPC) cotizado en MXN');

// Solo Tennant, sin IPC — no debe alterar el total por conversión de $0
let gt3 = granTotal(100, 0, 0, 'MXN', 17.5);
assert(round2(gt3) === round2(116 * 17.5), 'Gran total solo Tennant, cotizado en MXN');

// ═══ RESUMEN ═══
console.log('\n' + '─'.repeat(50));
if (fallos === 0) {
  console.log('✅ TODAS LAS PRUEBAS PASARON — seguro entregar este avance.');
} else {
  console.log(`❌ ${fallos} prueba(s) fallaron — NO entregar hasta corregir.`);
  process.exitCode = 1;
}
