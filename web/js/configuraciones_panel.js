'use strict';
(() => {
  const $ = id => document.getElementById(id), config = PortalConfig;
  function casilla(contenedor, texto, tipo, valor, incluida) {
    const label = document.createElement('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.checked = incluida;
    input.addEventListener('change', () => { config.seleccionar(tipo, valor, input.checked); $('config-estado').textContent = config.aviso(); });
    label.append(input, document.createTextNode(texto)); contenedor.append(label);
  }
  function render() {
    const estado = config.estado();
    $('config-regiones').replaceChildren();
    const regiones = [...new Set([...estado.catalogo, ...estado.regiones])].sort();
    for (const region of regiones) casilla($('config-regiones'), region, 'regiones', region, config.incluida(region));
    if (!regiones.length) $('config-regiones').textContent = 'Carga las regiones desde Excel para configurar la selección.';
    $('config-todas').disabled = $('config-ninguna').disabled = !regiones.length;
    $('config-vistas').replaceChildren();
    for (const [id, [titulo, vistas]] of Object.entries(config.paneles)) {
      const grupo = document.createElement('fieldset'), leyenda = document.createElement('legend');
      grupo.className = 'config-grupo'; leyenda.textContent = titulo; grupo.append(leyenda);
      for (const [vista, texto] of vistas) casilla(grupo, texto, 'ocultos', id + '.' + vista, !estado.ocultos.includes(id + '.' + vista));
      $('config-vistas').append(grupo);
    }
    $('config-centros').replaceChildren();
    for (const centro of [...new Set([...estado.centros, ...estado.cecos])].sort()) casilla($('config-centros'), centro, 'cecos', centro, config.cecoIncluido(centro));
    if (!$('config-centros').children.length) $('config-centros').textContent = 'Los centros se cargarán desde Reportabilidad.';
    $('config-estado').textContent = config.aviso();
  }
  async function cargar() {
    $('config-recargar').disabled = true; $('config-carga').textContent = 'Cargando regiones de los reportes…';
    const hoy = new Date(), fecha = `${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}-${String(hoy.getDate()).padStart(2,'0')}`;
    const urls = ['/api/reporte?fecha='+fecha, '/api/seguimiento-km-hr?inicio=2026-08-04&fecha='+fecha, '/api/programa-mantencion?mes='+fecha.slice(0,7)];
    const resultados = await Promise.allSettled(urls.map(async url => {
      const respuesta = await fetch(url, {cache:'no-store'}), datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.error || 'No se pudo consultar el Excel.');
      config.registrar([...(datos.regiones || []).map(r=>r.region), ...(datos.equipos || []).map(e=>e.region), ...(datos.historico || []).flatMap(m=>(m.regiones || []).map(r=>r.region))], url.includes('/api/reporte?') ? (datos.regiones || []).flatMap(r=>r.cecos.map(c=>c.ceco)) : []);
    }));
    const errores = resultados.filter(r=>r.status==='rejected');
    $('config-carga').textContent = errores.length ? `Se cargaron ${3-errores.length} de 3 fuentes. Se mantienen las regiones conocidas. ${errores.map(e=>e.reason.message).join(' ')}` : 'Regiones actualizadas desde los tres orígenes de datos.';
    $('config-recargar').disabled = false; render();
  }
  $('config-todas').onclick = () => config.regionesTodas(true);
  $('config-ninguna').onclick = () => config.regionesTodas(false);
  $('config-restaurar').onclick = () => config.restaurarVistas();
  $('config-recargar').onclick = cargar;
  window.addEventListener('portal-config', render);
  render(); cargar();
})();
