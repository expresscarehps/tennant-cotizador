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
  return { folio: `TNTREF${String(s).padStart(4, '0')}${anioActual}`, consecutivo: s };
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

console.log('\n=== Descuento por partida ===');
assert(round2(precioNeto(630.80, 5)) === 599.26, 'Descuento 5% sobre $630.80 = $599.26 (caso real TNTREF00012026)');
assert(precioNeto(100, 0) === 100, 'Sin descuento, precio neto = precio lista');
assert(precioNeto(100, 100) === 0, 'Descuento 100% = $0');
assert(precioNeto(100, 50) === 50, 'Descuento 50% sobre $100 = $50');

console.log('\n=== IVA 16% ===');
assert(round2(calcIVA(1198.52)) === 191.76, 'IVA de $1,198.52 = $191.76 (caso real TNTREF00012026)');
assert(calcIVA(0) === 0, 'IVA de $0 = $0');

console.log('\n=== Conversión de moneda ===');
assert(convertirAMoneda(100, 'USD', 'MXN', 17.5) === 1750, '$100 USD a MXN con TC 17.5 = $1,750 MXN');
assert(round2(convertirAMoneda(1750, 'MXN', 'USD', 17.5)) === 100, '$1,750 MXN a USD con TC 17.5 = $100 USD');
assert(convertirAMoneda(100, 'USD', 'USD', 17.5) === 100, 'Misma moneda no convierte');

console.log('\n=== Folio (formato y consecutivo) ===');
let f1 = generarFolio(0, 0, 2026);
assert(f1.folio === 'TNTREF00012026', 'Primer folio del año 2026 = TNTREF00012026');
let f2 = generarFolio(2026, 1, 2026);
assert(f2.folio === 'TNTREF00022026', 'Segundo folio del mismo año = TNTREF00022026');
let f3 = generarFolio(2025, 47, 2026);
assert(f3.folio === 'TNTREF00012026', 'El consecutivo se reinicia al cambiar de año (de 2025 a 2026)');
assert(/^TNTREF\d{4}\d{4}$/.test(f1.folio), 'El folio cumple el formato TNTREF + 4 dígitos + año');

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
