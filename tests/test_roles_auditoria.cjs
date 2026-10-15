// Verifica el código real de auditoría con los tres roles y controles dinámicos.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('web/pages/Panel_Auditoria_EDP.html', 'utf8');
class Elemento {
  constructor(id) { this.id = id; this.options = []; this.listeners = {}; this._value = ''; this.dataset = {}; }
  get value() { return this.options.length ? (this.options.some(o => o.value === this._value) ? this._value : this.options[0].value) : this._value; }
  set value(v) { this._value = String(v); }
  replaceChildren(...options) { this.options = options; this._value = options[0]?.value || ''; }
  add(option) { this.options.push(option); }
  addEventListener(event, callback) { this.listeners[event] = callback; }
}
async function probar(rol) {
  const elementos = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(([, id]) => [id, new Elemento(id)]));
  const $ = id => elementos.get(id);
  const comprobar = new Elemento('casilla'); comprobar.dataset.comprobar = '2';
  const adjuntar = new Elemento('archivo'), quitar = new Elemento('quitar'); adjuntar.dataset.adjuntar = '2';
  const document = {
    getElementById: $,
    querySelectorAll: selector => selector.startsWith('.auditoria') ? [...elementos.values(), comprobar, adjuntar, quitar] : selector === '[data-comprobar]' ? [comprobar] : selector === '[data-adjuntar]' ? [adjuntar] : selector === '[data-quitar]' ? [quitar] : [],
    addEventListener() {}, activeElement: null,
  };
  const muestra = {id: 'guardada', fuente: 'fuente', unidad: 'El Salvador', anio: 2026, mes: 5, edp: 47,
    archivo: 'EDP.xlsx', hoja: 'Tickets', poblacion: 8, avisos: [], modo: 'manual',
    respaldo_edp: {nombre: 'Respaldo.pdf', guardado: true},
    tickets: [{fila: 2, ticket: '123', comprobado: false, campos: [], documentos: [], respaldo_esperado: '123_EDP47.pdf', respaldo_ticket: {nombre: '123_EDP47.pdf', bytes: 20}}]};
  const catalogo = {unidades: ['El Salvador'], fuentes: [{...muestra, id: 'fuente', nombre: 'EDP.xlsx', origen: 'Fuentes'}],
    muestras: [{...muestra, comprobados: 1}], estados_pago: [{...muestra, muestra_vigente: 'guardada', estado_codigo: 'sin_revision', color: 'rojo'}], avisos: []};
  let refrescar;
  const consultas = [];
  const lista = {fuente: 'fuente', sha256: 'version', tickets: Array.from({length: 8}, (_, i) => ({fila: i + 2, ticket: String(100 + i), fecha: '2026-05-01'}))};
  let seleccionEnviada;
  let confirmar = false, eliminada;
  let respaldoEnviado;
  const fetch = async (ruta, opciones) => {
    consultas.push(ruta);
    let resultado = ruta.includes('/tickets?') ? lista : ruta.includes('/muestra') ? muestra : catalogo;
    if (ruta.includes('/seleccionar')) {
      seleccionEnviada = JSON.parse(opciones.body);
      resultado = {...muestra, tickets: seleccionEnviada.filas.map(fila => ({...muestra.tickets[0], fila, ticket: String(98 + fila)}))};
    }
    if (ruta.endsWith('/eliminar')) {
      eliminada = JSON.parse(opciones.body);
      catalogo.muestras = [];
      catalogo.estados_pago[0].comprobados = 0;
      resultado = {eliminada: eliminada.muestra};
    }
    if (ruta.endsWith('/adjuntar')) {
      respaldoEnviado = JSON.parse(opciones.body);
      resultado = structuredClone(muestra);
      resultado.tickets[0].respaldo_ticket.archivo = 'Codelco El Salvador/2026/2026 -05 EDP 47/123_EDP47.pdf';
    }
    return {ok: true, json: async () => structuredClone(resultado)};
  };
  const permisos = rol === 'general' ? [] : rol === 'auditor' ? ['comprobar', 'revisar'] : ['comprobar', 'revisar', 'modificar'];
  vm.runInNewContext(fs.readFileSync('web/js/auditoria.js', 'utf8'), {
    window: {confirm: () => confirmar, PanelSesion: {usuario: {rol}, permite: p => permisos.includes(p), listo: Promise.resolve()}},
    document, fetch, URLSearchParams, Option: class {constructor(text, value) {this.text = text; this.value = String(value);}},
    FileReader: class {readAsDataURL() {this.result = 'data:application/pdf;base64,JVBERi0='; this.onload();}},
    setInterval(fn) { refrescar = fn; },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(Boolean(comprobar.disabled), rol === 'general', `${rol}: casilla`);
  assert.equal(Boolean(adjuntar.disabled), rol === 'general', `${rol}: adjuntar`);
  assert.equal(Boolean(quitar.disabled), rol !== 'administrador', `${rol}: quitar`);
  assert.equal($('chequeo-unidad').disabled, false, `${rol}: filtros disponibles`);
  assert.equal($('exportar').disabled, false, `${rol}: CSV disponible`);
  assert.equal($('generar-pdf').disabled, false, `${rol}: PDF disponible`);
  assert.equal($('eliminar-muestra').hidden, rol === 'general');
  assert.equal($('eliminar-muestra').disabled, rol === 'general');
  catalogo.muestras[0].comprobados = 0;
  await $('actualizar').listeners.click();
  assert.equal($('generar-pdf').disabled, true, `${rol}: PDF sin comprobados bloqueado`);
  assert.equal($('aviso-pdf-muestra').hidden, false, `${rol}: motivo visible`);
  assert.equal($('pdf-unidad').disabled, true, `${rol}: PDF de EDP sin comprobados bloqueado`);
  assert.equal($('exportar').disabled, false, `${rol}: CSV de pendientes disponible`);
  const antesPdf = consultas.length;
  await $('generar-pdf').listeners.click();
  assert.equal(consultas.length, antesPdf, 'Sin comprobados no solicita un PDF que dará error');
  catalogo.muestras.push({...muestra, id: 'historia', comprobados: 1});
  await $('actualizar').listeners.click();
  assert.equal($('generar-pdf').disabled, false, `${rol}: comprobación histórica habilita PDF`);
  assert.equal($('aviso-pdf-muestra').hidden, true);
  for (const id of ['sortear', 'cantidad', 'listar-tickets']) {
    assert.equal($(id).disabled, rol === 'general', `${rol}: permiso de ${id}`);
  }
  assert.equal($('revisar-ticket').disabled, true, `${rol}: sin lista cargada`);
  if (rol === 'general') {
    const antes = consultas.length;
    await $('sortear').listeners.click();
    await $('listar-tickets').listeners.click();
    await $('revisar-ticket').listeners.click();
    await $('eliminar-muestra').listeners.click();
    assert.equal(consultas.length, antes, 'General no solicita sorteos ni selecciones');
    refrescar(); await new Promise(resolve => setImmediate(resolve));
    assert($('muestra-fecha').textContent.includes('Revisión guardada'), 'General consulta la revisión guardada');
    assert.equal(comprobar.disabled, true);
    assert.equal(adjuntar.disabled, true);
  } else {
    const control = {files: [{name: 'otro.pdf', size: 20}], dataset: {adjuntar: '2'}, value: 'otro.pdf',
      matches: selector => selector === '[data-adjuntar]'};
    const antesSubir = consultas.length;
    $('tickets-auditoria').listeners.change({target: control});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(consultas.length, antesSubir, 'El nombre incorrecto se rechaza antes de enviar el archivo');
    assert($('estado').textContent.includes('123_EDP47'));
    control.files = [{name: '123_EDP47.pdf', size: 20}];
    $('tickets-auditoria').listeners.change({target: control});
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(respaldoEnviado, {nombre: '123_EDP47.pdf', contenido: 'JVBERi0=', muestra: 'guardada', fila: 2});
    assert($('estado').textContent.includes('Fuentes/Codelco El Salvador/2026/2026 -05 EDP 47/123_EDP47.pdf'));
    control.files = [{name: '123_EDP47.jpg', size: 20}];
    $('tickets-auditoria').listeners.change({target: control});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(respaldoEnviado.nombre, '123_EDP47.jpg', 'Admite otra extension con el mismo nombre base');
    assert.equal(respaldoEnviado.fila, 2);
    for (const nombre of ['123 EDP 47.jpg', '123-EDP-47.png', '123 - EDP 47.docx', '123EDP47.jpg', '123 edp 47.jpg']) {
      control.files = [{name: nombre, size: 20}];
      $('tickets-auditoria').listeners.change({target: control});
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(respaldoEnviado.nombre, nombre, 'Conserva el nombre alternativo aceptado');
    }
    for (const nombre of ['123 EDP 48.jpg', '124-EDP-47.jpg', '123 EDP 47 copia.jpg', '123 EDP 47']) {
      const antes = consultas.length;
      control.files = [{name: nombre, size: 20}];
      $('tickets-auditoria').listeners.change({target: control});
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(consultas.length, antes, 'Rechaza nombres que no corresponden al ticket y EDP');
    }

    assert(!$('tickets-auditoria').innerHTML.includes('accept=".pdf"'), 'El selector permite cualquier formato');
    await $('listar-tickets').listeners.click();
    for (let i = 0; i < 5; i++) {
      $('ticket-elegido').value = String(i + 2);
      $('agregar-ticket').listeners.click();
      assert.equal($('revisar-ticket').disabled, i < 2, `${rol}: mínimo de tres tickets`);
    }
    assert.equal($('agregar-ticket').disabled, true, 'Máximo cinco tickets');
    $('agregar-ticket').listeners.click();
    assert($('seleccion-contador').textContent.startsWith('5 de 5'));
    $('buscar-ticket').value = '107';
    $('buscar-ticket').listeners.input();
    assert($('seleccion-contador').textContent.startsWith('5 de 5'), 'Buscar conserva la preselección');
    $('tickets-preseleccionados').listeners.click({target: {closest: () => ({dataset: {quitarSeleccion: '3'}})}});
    assert($('seleccion-contador').textContent.startsWith('4 de 5'));
    $('ticket-elegido').value = '9';
    $('agregar-ticket').listeners.click();
    await $('revisar-ticket').listeners.click();
    assert.deepEqual(seleccionEnviada, {fuente: 'fuente', filas: [2, 4, 5, 6, 9], sha256: 'version'});
    assert($('tickets-auditoria').innerHTML.includes('TICKET 5 DE 5'), 'Se muestran juntos en las tarjetas de revisión');
    assert.equal($('kpi-muestra').textContent, 5);
    await $('fuente').listeners.change();
    assert($('seleccion-contador').textContent.startsWith('0 de 5'), 'Cambiar EDP limpia la selección');
    assert.equal($('revisar-ticket').disabled, true);
    const antes = consultas.length;
    await $('eliminar-muestra').listeners.click();
    assert.equal(consultas.length, antes, 'Cancelar conserva la muestra');
    confirmar = true;
    await $('eliminar-muestra').listeners.click();
    assert.deepEqual(eliminada, {muestra: 'guardada'}, 'Elimina únicamente la muestra abierta');
    assert.equal($('revision').hidden, true);
    assert.equal($('eliminar-muestra').hidden, true);
    assert.equal($('exportar').disabled, true);
    assert.equal($('historial').value, '');
  }
}
(async () => {
  for (const rol of ['general', 'auditor', 'administrador']) await probar(rol);
  assert.match(html, /id="sortear"[^>]*data-permiso="revisar"[^>]*hidden/);
  assert.match(html, /class="tarjeta seleccion-ticket"[^>]*data-permiso="revisar"[^>]*hidden/);
  console.log('OK: permisos de sorteo, selección, controles dinámicos y consulta de General.');
})().catch(error => { console.error(error); process.exitCode = 1; });
