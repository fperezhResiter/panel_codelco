(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const fecha = v => new Date(v).toLocaleString('es-CL');
  let catalogo = {fuentes: [], muestras: [], unidades: []}, muestra = null, ocupado = false;
  let listaTickets = null;
  const tieneRespaldo = t => Boolean(t?.documentos.length || muestra?.respaldo_edp);

  async function api(ruta, datos) {
    const respuesta = await fetch('/api/auditoria' + ruta, datos === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(datos)
    });
    if (!respuesta.ok) {
      const error = await respuesta.json().catch(() => ({}));
      throw new Error(error.error || 'No se pudo completar la operación. Reinicia el servidor si acabas de actualizar el panel.');
    }
    return respuesta;
  }
  const consultar = async (ruta, datos) => (await api(ruta, datos)).json();
  function mensaje(texto, error = false) { $('estado').textContent = texto; $('estado').className = error ? 'error' : ''; }
  function controles() {
    document.querySelectorAll('.auditoria button, .auditoria input, .auditoria select').forEach(n => { n.disabled = ocupado; });
    $('sortear').disabled = ocupado || !catalogo.fuentes.some(f => f.id === $('fuente').value);
    $('listar-tickets').disabled = $('sortear').disabled;
    $('buscar-ticket').disabled = $('ticket-elegido').disabled = ocupado || !listaTickets;
    $('revisar-ticket').disabled = ocupado || !listaTickets || !$('ticket-elegido').value;
    $('historial').disabled = ocupado || !$('historial').value;
    $('generar-pdf').disabled = $('exportar').disabled = ocupado || !muestra;
    document.querySelectorAll('[data-comprobar]').forEach(n => {
      n.disabled = ocupado || !tieneRespaldo(muestra?.tickets.find(t => t.fila === Number(n.dataset.comprobar)));
    });
  }
  async function operar(accion) {
    if (ocupado) return;
    ocupado = true; controles();
    try { await accion(); }
    catch (error) { mensaje(error.message === 'Failed to fetch' ? 'No hay conexión con el servidor. Comprueba que Iniciar_Panel esté ejecutándose.' : error.message, true); }
    finally { ocupado = false; controles(); }
  }
  function opciones(id, elementos, elegido, vacio) {
    $(id).replaceChildren(...elementos.map(([valor, texto]) => new Option(texto, String(valor))));
    if (!elementos.length) $(id).add(new Option(vacio, ''));
    if (elementos.some(([v]) => String(v) === String(elegido))) $(id).value = elegido;
  }
  function filtrar(nivel = 0, preferida = null) {
    limpiarTickets();
    const contextos = [...catalogo.fuentes, ...catalogo.muestras];
    if (nivel <= 0) opciones('unidad', [...new Set([...catalogo.unidades, ...contextos.map(f => f.unidad)])].map(v => [v,v]), preferida?.unidad || $('unidad').value, 'Sin unidades');
    let registros = contextos.filter(f => f.unidad === $('unidad').value);
    if (nivel <= 1) opciones('anio', [...new Set(registros.map(f => f.anio))].sort((a,b) => b-a).map(v => [v,v]), preferida?.anio || $('anio').value, 'Sin años');
    registros = registros.filter(f => String(f.anio) === $('anio').value);
    if (nivel <= 2) opciones('mes', [...new Set(registros.map(f => f.mes))].sort((a,b) => a-b).map(v => [v,meses[v]]), preferida?.mes || $('mes').value, 'Sin meses');
    const fuentes = catalogo.fuentes.filter(coincide);
    // Mantener accesibles las revisiones aunque se mueva o quite su Excel original.
    for (const anterior of catalogo.muestras.filter(coincide)) {
      if (!fuentes.some(f => f.id === anterior.fuente)) fuentes.push({id:anterior.fuente, edp:anterior.edp,
        nombre:anterior.archivo.split('/').pop(), origen:'Solo historial'});
    }
    opciones('fuente', fuentes.map(f => [f.id, `EDP ${f.edp} · ${f.nombre} · ${f.origen}`]), preferida?.id || $('fuente').value, 'Sin Excel para este período');
    actualizarHistorial();
  }
  function limpiarTickets() {
    listaTickets = null;
    $('buscar-ticket').value = '';
    opciones('ticket-elegido', [], '', 'Carga la lista de tickets');
  }
  function filtrarTickets() {
    const busqueda = $('buscar-ticket').value.trim().toLocaleLowerCase('es');
    const tickets = (listaTickets?.tickets || []).map(t => [t.fila, `Ticket ${t.ticket || 'sin número'} · Fila ${t.fila} · ${t.fecha || 'Sin fecha'}`])
      .filter(([,nombre]) => nombre.toLocaleLowerCase('es').includes(busqueda));
    opciones('ticket-elegido', tickets, $('ticket-elegido').value, 'No hay tickets que coincidan');
    controles();
  }
  function coincide(f) { return f.unidad === $('unidad').value && String(f.anio) === $('anio').value && String(f.mes) === $('mes').value; }
  function actualizarHistorial(preferida) {
    const registros = catalogo.muestras.filter(coincide).filter(m => !$('fuente').value || m.fuente === $('fuente').value);
    opciones('historial', registros.map(m => [m.id, `${fecha(m.creado)} · EDP ${m.edp} · ${m.cantidad} tickets · ${m.comprobados} comprobados · ${m.id.slice(0,8)}`]), preferida, 'Sin muestras guardadas');
  }
  async function abrirSeleccion() {
    muestra = null; renderizar();
    if ($('historial').value) muestra = await consultar('/muestra?id=' + encodeURIComponent($('historial').value));
    renderizar();
  }
  async function cargar(preferida = null) {
    catalogo = await consultar('');
    $('avisos').hidden = !catalogo.avisos.length;
    $('avisos').innerHTML = catalogo.avisos.map(v => `<p>${esc(v)}</p>`).join('');
    if (!preferida && !$('unidad').value) preferida = catalogo.fuentes[0] || catalogo.muestras[0];
    filtrar(0, preferida);
    await abrirSeleccion();
    mensaje(`${catalogo.fuentes.length} Excel EDP disponibles. Las muestras y los respaldos se guardan automáticamente.`);
  }
  function recordarMuestra() {
    const resumen = {...muestra, cantidad:muestra.tickets.length, comprobados:muestra.tickets.filter(t => t.comprobado).length};
    catalogo.muestras = [resumen, ...catalogo.muestras.filter(m => m.id !== muestra.id)];
    actualizarHistorial(muestra.id);
    renderizar();
  }
  function renderizar() {
    $('revision').hidden = !muestra; $('sin-muestra').hidden = Boolean(muestra);
    if (!muestra) { $('tickets-auditoria').replaceChildren(); return; }
    const comprobados = muestra.tickets.filter(t => t.comprobado).length;
    $('kpi-poblacion').textContent = muestra.poblacion;
    $('kpi-muestra').textContent = muestra.tickets.length;
    $('kpi-comprobados').textContent = comprobados;
    $('kpi-pendientes').textContent = muestra.tickets.length - comprobados;
    $('muestra-titulo').textContent = `${muestra.unidad} · ${muestra.periodo} · EDP ${muestra.edp}`;
    $('muestra-fecha').textContent = `${muestra.modo === 'manual' ? 'Ticket seleccionado manualmente' : 'Muestra aleatoria'} · Creada: ${fecha(muestra.creado)} · Revisión ${muestra.id.slice(0,8)} · Último cambio: ${fecha(muestra.actualizado)}`;
    $('muestra-origen').textContent = `${muestra.archivo} → ${muestra.hoja}`;
    $('muestra-avisos').innerHTML = muestra.avisos.map(a => `<p class="observaciones">${esc(a)}</p>`).join('');
    $('respaldo-edp').innerHTML = muestra.respaldo_edp ? `<p class="respaldo-disponible"><strong>Respaldo del EDP disponible:</strong> <a href="/api/auditoria/respaldo-edp?id=${encodeURIComponent(muestra.id)}" download>${esc(muestra.respaldo_edp.nombre)}</a>. Puedes comprobar los tickets sin subir otro archivo. ${muestra.respaldo_edp.guardado ? 'Se conserva una copia del PDF utilizado en esta revisión.' : 'Encontrado en la carpeta del EDP.'}</p>` : '<p class="nota-guardado">No se encontró 2.5a TICKET INTERNO.pdf para esta revisión. Adjunta un respaldo por ticket para habilitar la casilla.</p>';
    $('tickets-auditoria').innerHTML = muestra.tickets.map((t,i) => `
      <article class="tarjeta ticket-auditoria" aria-labelledby="ticket-${t.fila}">
        <div class="titulo"><div><p class="eyebrow">TICKET ${i+1} DE ${muestra.tickets.length} · FILA EXCEL ${t.fila}</p><h3 id="ticket-${t.fila}">Ticket ${esc(t.ticket || 'sin número')}</h3></div>
          <span class="semaforo ${t.comprobado ? 'verde' : 'amarillo'}">${t.comprobado ? 'Comprobado manualmente' : 'Pendiente de comprobación'}</span></div>
        <div class="contenido ticket-contenido"><dl class="detalle-datos">${t.campos.map(c => `<div><dt>${esc(c.nombre)} <small>[${esc(c.celda)}]</small></dt><dd>${c.sin_resultado ? 'Sin resultado guardado' : esc(c.valor || '—')}</dd>${c.formula && !/peso\s*total/i.test(c.nombre) ? `<small class="formula-ticket">Fórmula: ${esc(c.formula)}</small>` : ''}</div>`).join('')}</dl>
          <section class="respaldo-ticket" aria-label="Respaldos del ticket ${esc(t.ticket)}"><h4>Documentos de respaldo</h4>
            <ul class="lista-respaldos">${t.documentos.length ? t.documentos.map(d => `<li><a href="/api/auditoria/documento?id=${encodeURIComponent(d.id)}" download>${esc(d.nombre)}</a><span>${Math.ceil(d.bytes/1024)} KB · ${esc(fecha(d.creado))}</span><button type="button" class="enlace" data-quitar="${esc(d.id)}" data-fila="${t.fila}" aria-label="Quitar ${esc(d.nombre)}">Quitar</button></li>`).join('') : '<li class="sin-respaldos">Todavía no hay documentos adjuntos.</li>'}</ul>
            <label>Adjuntar documentación de este ticket<input type="file" data-adjuntar="${t.fila}" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.doc,.docx,.xls,.xlsx,.csv,.txt"></label>
            <p class="nota-guardado">PDF, imágenes, Word, Excel, CSV o texto · Máximo 30 MB por archivo.</p>
            <label class="comprobacion-manual"><input type="checkbox" data-comprobar="${t.fila}" ${t.comprobado ? 'checked' : ''} ${!tieneRespaldo(t) ? 'disabled' : ''}><span>Comprobé manualmente que la información de este ticket coincide con la documentación de respaldo.</span></label>
            <p class="nota-guardado">${t.comprobado_en ? 'Confirmado: ' + esc(fecha(t.comprobado_en)) : muestra.respaldo_edp ? 'Puedes usar el PDF del EDP indicado arriba; no es necesario subir otro archivo.' : t.documentos.length ? 'Revisa los documentos antes de marcar la casilla.' : 'Adjunta al menos un documento para habilitar la casilla.'}</p>
          </section>
        </div>
      </article>`).join('');
    controles();
  }
  async function archivoJSON(archivo) {
    if (!archivo || !archivo.size || archivo.size > 30 * 1024 * 1024) throw new Error('Selecciona un archivo con contenido de hasta 30 MB.');
    const contenido = await new Promise((resolve, reject) => {
      const lector = new FileReader();
      lector.onload = () => resolve(lector.result.split(',')[1]);
      lector.onerror = () => reject(new Error('No se pudo leer el archivo seleccionado.'));
      lector.readAsDataURL(archivo);
    });
    return {nombre:archivo.name, contenido};
  }
  async function descargar(extension) {
    mensaje(`Preparando ${extension.toUpperCase()} de la muestra guardada…`);
    const respuesta = await api('/reporte.' + extension + '?id=' + encodeURIComponent(muestra.id));
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = `auditoria-${muestra.unidad}-${muestra.periodo}-EDP${muestra.edp}-${muestra.id.slice(0,8)}.${extension}`;
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje(`${extension.toUpperCase()} generado. Revisa las descargas del navegador.`);
  }
  ['unidad','anio','mes'].forEach((id,i) => $(id).addEventListener('change', () => operar(async () => {
    filtrar(i+1); await abrirSeleccion(); mensaje('Selección actualizada. Puedes retomar una muestra o realizar un nuevo sorteo.');
  })));
  $('fuente').addEventListener('change', () => operar(async () => { limpiarTickets(); actualizarHistorial(); await abrirSeleccion(); mensaje('EDP seleccionado.'); }));
  $('historial').addEventListener('change', () => operar(async () => { await abrirSeleccion(); mensaje('Muestra guardada recuperada.'); }));
  $('actualizar').addEventListener('click', () => operar(() => cargar()));
  $('sortear').addEventListener('click', () => operar(async () => {
    mensaje('Leyendo el Excel y sorteando la muestra…');
    muestra = await consultar('/sortear', {fuente:$('fuente').value, cantidad:Number($('cantidad').value)});
    recordarMuestra(); mensaje(`Muestra guardada: ${muestra.tickets.length} tickets de ${muestra.poblacion} registros.`);
  }));
  $('listar-tickets').addEventListener('click', () => operar(async () => {
    limpiarTickets(); mensaje('Leyendo los tickets del EDP seleccionado…');
    listaTickets = await consultar('/tickets?id=' + encodeURIComponent($('fuente').value));
    filtrarTickets(); mensaje(`${listaTickets.tickets.length} tickets disponibles. Selecciona el que deseas revisar.`);
  }));
  $('buscar-ticket').addEventListener('input', filtrarTickets);
  $('ticket-elegido').addEventListener('change', controles);
  $('revisar-ticket').addEventListener('click', () => operar(async () => {
    mensaje('Preparando el ticket seleccionado…');
    muestra = await consultar('/seleccionar', {fuente:listaTickets.fuente, fila:Number($('ticket-elegido').value), sha256:listaTickets.sha256});
    recordarMuestra(); mensaje('Ticket seleccionado. Revisa la documentación y registra tu comprobación manual.');
  }));
  $('tickets-auditoria').addEventListener('change', event => {
    const control = event.target;
    if (control.matches('[data-adjuntar]')) {
      const archivos = [...control.files];
      operar(async () => {
        let guardados = 0;
        try {
          for (const archivo of archivos) {
            mensaje(`Guardando ${archivo.name}…`);
            muestra = await consultar('/adjuntar', {...await archivoJSON(archivo), muestra:muestra.id, fila:Number(control.dataset.adjuntar)});
            guardados++; recordarMuestra();
          }
          mensaje(`${guardados} documento(s) guardado(s). Ya puedes revisar los respaldos y marcar la casilla.`);
        } catch (error) { throw new Error(`${guardados} documento(s) guardado(s). ${error.message}`); }
        finally { control.value = ''; }
      });
    } else if (control.matches('[data-comprobar]')) {
      const marcado = control.checked;
      operar(async () => {
        try {
          muestra = await consultar('/comprobar', {muestra:muestra.id, fila:Number(control.dataset.comprobar), comprobado:marcado});
          recordarMuestra(); mensaje('Comprobación manual guardada.');
        } catch (error) { control.checked = !marcado; throw error; }
      });
    }
  });
  $('tickets-auditoria').addEventListener('click', event => {
    const boton = event.target.closest('[data-quitar]');
    if (!boton) return;
    operar(async () => {
      muestra = await consultar('/quitar', {muestra:muestra.id, fila:Number(boton.dataset.fila), documento:boton.dataset.quitar});
      recordarMuestra(); mensaje('Respaldo quitado. La comprobación de ese ticket quedó pendiente.');
    });
  });
  $('generar-pdf').addEventListener('click', () => operar(() => descargar('pdf')));
  $('exportar').addEventListener('click', () => operar(() => descargar('csv')));
  operar(() => cargar());
})();
