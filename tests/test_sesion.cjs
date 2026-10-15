const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Elemento {
  constructor(tipo) { this.tipo = tipo; this.children = []; this.listeners = {}; }
  append(...children) { this.children.push(...children); }
  insertBefore(child, before) { this.children.splice(this.children.indexOf(before), 0, child); }
  addEventListener(event, callback) { this.listeners[event] = callback; }
}
async function probar(rol, vistaGeneral = false) {
  const usuario = {nombre: 'persona@prueba.cl', rol_real: rol, rol: vistaGeneral ? 'general' : rol,
    vista_general: vistaGeneral, rol_nombre: vistaGeneral ? 'General (vista de Admin)' : rol,
    permisos: rol === 'administrador' && !vistaGeneral ? ['consultar', 'configurar'] : ['consultar']};
  let barra, destino;
  const encabezado = new Elemento('header');
  const inicio = new Elemento('a'); inicio.className = 'volver-inicio';
  encabezado.querySelector = () => inicio;
  encabezado.after = elemento => { barra = elemento; };
  const tarjetaConfiguraciones = {dataset: {permiso: 'configurar'}, hidden: true};
  const llamadas = [];
  const window = {fetch: async (ruta, opciones) => {
    llamadas.push({ruta, opciones});
    return {ok: true, status: 200, json: async () => ({usuario})};
  }};
  vm.runInNewContext(fs.readFileSync('web/js/sesion.js', 'utf8'), {
    window, fetch: (...args) => window.fetch(...args),
    location: {replace(ruta) { destino = ruta; }},
    document: {createElement: tipo => new Elemento(tipo), querySelector: () => encabezado, querySelectorAll: () => [tarjetaConfiguraciones]},
  });
  await window.PanelSesion.listo;
  const acciones = encabezado.children.find(n => n.className === 'acciones-encabezado');
  assert.equal(acciones.children[0], inicio);
  assert.equal(acciones.children.find(n => n.href === '/perfil').textContent, 'Mi perfil');
  assert.equal(barra.children.some(n => n.href === '/perfil'), false);
  assert.equal(barra.children.some(n => n.href === '/configuraciones'), false, 'Configuraciones se abre como panel del portal');
  assert.equal(tarjetaConfiguraciones.hidden, rol !== 'administrador' || vistaGeneral);
  const vista = barra.children.find(n => ['Ver como General', 'Volver a vista Admin'].includes(n.textContent));
  if (rol === 'administrador') {
    assert(vista);
    assert.equal(vista.textContent, vistaGeneral ? 'Volver a vista Admin' : 'Ver como General');
    await vista.listeners.click();
    const cambio = llamadas.find(c => c.ruta === '/api/sesion/vista');
    assert.equal(JSON.parse(cambio.opciones.body).general, !vistaGeneral);
    assert.equal(destino, '/Panel.html');
  } else {
    assert.equal(vista, undefined);
  }
}
(async () => {
  await probar('administrador'); await probar('administrador', true);
  await probar('auditor'); await probar('general');
  console.log('OK: tarjeta Configuraciones exclusiva de Admin, botón de vista General y regreso a Admin.');
})().catch(error => { console.error(error); process.exitCode = 1; });
