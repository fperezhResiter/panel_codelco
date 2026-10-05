(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const fecha = v => new Date(v).toLocaleString('es-CL');
  const respaldoEsperado = unidad => unidad === 'Andina' ? '1.1 Retiro RINSP.pdf' : '2.5a TICKET INTERNO.pdf';
  let catalogo = {fuentes: [], muestras: [], unidades: [], estados_pago: []}, muestra = null, ocupado = false;
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
    $('pdf-unidad').disabled = ocupado || !catalogo.estados_pago.some(e => e.unidad === $('unidad').value);
    $('descargar-compilado').disabled = ocupado || !catalogo.estados_pago.some(coincide);
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
    renderizarCobertura();
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
    const vigentes = new Set(catalogo.estados_pago.map(e => e.muestra_vigente));
    opciones('historial', registros.map(m => [m.id, `${fecha(m.creado)} · EDP ${m.edp} · ${m.cantidad} tickets · ${m.comprobados} comprobados · ${vigentes.has(m.id) ? 'Vigente' : 'Histórica'} · ${m.id.slice(0,8)}`]), preferida, 'Sin muestras guardadas');
  }
  async function abrirSeleccion() {
    muestra = null; renderizar();
    if ($('historial').value) muestra = await consultar('/muestra?id=' + encodeURIComponent($('historial').value));
    renderizar();
  }
  async function cargar(preferida = null) {
    const nuevo = await consultar('');
    if (!Array.isArray(nuevo.estados_pago)) throw new Error('Reinicia Iniciar_Panel para cargar el gráfico y el reporte de unidad actualizados.');
    catalogo = nuevo;
    renderizarConexion();
    $('avisos').hidden = !catalogo.avisos.length;
    $('avisos').innerHTML = catalogo.avisos.map(v => `<p>${esc(v)}</p>`).join('');
    if (!preferida && !$('unidad').value) preferida = catalogo.fuentes[0] || catalogo.muestras[0];
    filtrar(0, preferida);
    await abrirSeleccion();
    mensaje(`${catalogo.fuentes.length} Excel EDP disponibles. Las comprobaciones se guardan automáticamente en la BD.`);
  }
  async function recordarMuestra() {
    const resumen = {...muestra, cantidad:muestra.tickets.length, comprobados:muestra.tickets.filter(t => t.comprobado).length};
    catalogo.muestras = [resumen, ...catalogo.muestras.filter(m => m.id !== muestra.id)];
    actualizarHistorial(muestra.id);
    renderizar();
    catalogo = await consultar('');
    renderizarConexion();
    actualizarHistorial(muestra.id);
    renderizarCobertura();
  }
  function renderizarConexion() {
    const conexion = catalogo.conexion_bd;
    $('conexion-bd').textContent = conexion ? `${conexion.mensaje}. ${conexion.nota || ''}${conexion.pendientes ? ` ${conexion.pendientes} cambio(s) esperando sincronización de sus archivos.` : ''}` : 'Reinicia el servidor para conectar la BD compartida.';
    $('conexion-bd').className = conexion?.pendientes ? 'observaciones' : 'respaldo-disponible';
    $('conexion-bd').title = conexion?.carpeta || '';
  }
  async function actualizarChequeos() {
    const actual = muestra?.id || $('historial').value;
    catalogo = await consultar('');
    renderizarConexion();
    actualizarHistorial(actual);
    renderizarCobertura();
    if (muestra) {
      muestra = await consultar('/muestra?id=' + encodeURIComponent(muestra.id));
      renderizar();
    } else if ($('historial').value) await abrirSeleccion();
  }
  function renderizarCobertura() {
    const registros = catalogo.estados_pago;
    const unidades = [...new Set([...catalogo.unidades, ...registros.map(e => e.unidad)])];
    const maximo = Math.max(1, ...unidades.map(u => registros.filter(e => e.unidad === u).length));
    $('grafico-chequeos').innerHTML = unidades.map(unidad => {
      const edp = registros.filter(e => e.unidad === unidad);
      return `<div class="barra-fila"><div class="barra-etiqueta"><strong>${esc(unidad)}</strong>${edp.length} EDP</div><div class="barras">${[['completo', 'Chequeo completo'], ['parcial', 'Chequeo parcial'], ['sin_revision', 'Sin revisión']].map(([clase, etiqueta]) => {
        const n = edp.filter(e => e.estado_codigo === clase).length;
        return `<div class="barra" aria-label="${esc(unidad)}: ${etiqueta}, ${n} EDP"><div class="barra-pista"><span class="barra-relleno ${clase}" style="width:${n / maximo * 100}%"></span></div><span>${etiqueta}: ${n}</span></div>`;
      }).join('')}</div></div>`;
    }).join('');
    const seleccion = registros.filter(e => e.unidad === $('unidad').value);
    $('alcance-unidad').textContent = `${$('unidad').value || 'Unidad'} · ${seleccion.length} EDP de todos los años y meses. El PDF incluye este resumen y todas sus revisiones guardadas.`;
    $('estados-pago').innerHTML = seleccion.length ? seleccion.map(e => `<tr><td>${esc(e.periodo)}</td><td>${esc(e.edp)}</td><td>${e.revisiones}</td><td>${e.comprobados}</td><td>${e.pendientes}</td><td><span class="semaforo ${esc(e.color)}">${esc(e.estado)}</span></td></tr>`).join('') : '<tr><td colspan="6" class="vacio">Sin EDP para esta unidad.</td></tr>';
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
    $('muestra-origen').textContent = `${muestra.archivo} → Hoja ${muestra.hoja} · Ítem ${muestra.item || (muestra.unidad === 'Andina' ? '1.1' : '2.5.a')}`;
    $('poblacion-hoja').textContent = `Tickets de la hoja ${muestra.hoja}`;
    $('muestra-avisos').innerHTML = muestra.avisos.map(a => `<p class="observaciones">${esc(a)}</p>`).join('');
    $('respaldo-edp').innerHTML = muestra.respaldo_edp ? `<p class="respaldo-disponible"><strong>Respaldo del EDP disponible:</strong> <a href="/api/auditoria/respaldo-edp?id=${encodeURIComponent(muestra.id)}" download>${esc(muestra.respaldo_edp.nombre)}</a>. Puedes comprobar los tickets sin subir otro archivo. ${muestra.respaldo_edp.guardado ? 'Se conserva una copia del PDF utilizado en esta revisión.' : 'Encontrado en la carpeta del EDP.'}</p>` : `<p class="nota-guardado">No se encontró ${esc(respaldoEsperado(muestra.unidad))} para esta revisión. Adjunta un respaldo por ticket para habilitar la casilla.</p>`;
    $('tickets-auditoria').innerHTML = muestra.tickets.map((t,i) => `
      <article class="tarjeta ticket-auditoria" aria-labelledby="ticket-${t.fila}">
        <div class="titulo"><div><p class="eyebrow">TICKET ${i+1} DE ${muestra.tickets.length} · FILA EXCEL ${t.fila}</p><h3 id="ticket-${t.fila}">Ticket ${esc(t.ticket || 'sin número')}</h3></div>
          <span class="semaforo ${t.comprobado ? 'verde' : 'amarillo'}">${t.comprobado ? 'Comprobado manualmente' : 'Pendiente de comprobación'}</span></div>
        <div class="contenido ticket-contenido"><dl class="detalle-datos">${t.campos.map(c => `<div><dt>${esc(c.nombre)} <small>[${esc(c.celda)}]</small></dt><dd>${c.sin_resultado ? 'Sin resultado guardado' : esc(c.valor ? c.valor + (c.unidad === 't' ? ' t' : '') : '—')}</dd>${c.formula && c.unidad !== 't' && !/peso\s*total/i.test(c.nombre) ? `<small class="formula-ticket">Fórmula: ${esc(c.formula)}</small>` : ''}</div>`).join('')}</dl>
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
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
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
    await recordarMuestra(); mensaje(`Muestra guardada: ${muestra.tickets.length} tickets de ${muestra.poblacion} registros.`);
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
    await recordarMuestra(); mensaje('Ticket seleccionado. Revisa la documentación y registra tu comprobación manual.');
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
            guardados++; await recordarMuestra();
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
          await recordarMuestra(); mensaje('Comprobación manual guardada.');
        } catch (error) { control.checked = !marcado; throw error; }
      });
    }
  });
  $('tickets-auditoria').addEventListener('click', event => {
    const boton = event.target.closest('[data-quitar]');
    if (!boton) return;
    operar(async () => {
      muestra = await consultar('/quitar', {muestra:muestra.id, fila:Number(boton.dataset.fila), documento:boton.dataset.quitar});
      await recordarMuestra(); mensaje('Respaldo quitado. La comprobación de ese ticket quedó pendiente.');
    });
  });
  $('generar-pdf').addEventListener('click', () => operar(() => descargar('pdf')));
  $('exportar').addEventListener('click', () => operar(() => descargar('csv')));
  $('descargar-compilado').addEventListener('click', () => operar(async () => {
    const parametros = new URLSearchParams();
    ['unidad', 'anio', 'mes'].forEach(k => parametros.set(k, $(k).value));
    mensaje('Preparando un PDF por EDP de la unidad, año y mes seleccionados…');
    const respuesta = await api('/compilado.zip?' + parametros);
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje('Compilado ZIP generado con un PDF por EDP, incluidas las revisiones guardadas. Revisa las descargas del navegador.');
  }));
  $('pdf-unidad').addEventListener('click', () => operar(async () => {
    const unidad = $('unidad').value;
    mensaje(`Preparando reporte PDF completo de ${unidad}…`);
    const respuesta = await api('/unidad.pdf?unidad=' + encodeURIComponent(unidad));
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje(`PDF completo de ${unidad} generado. Revisa las descargas del navegador.`);
  }));
  operar(() => cargar());
  setInterval(() => {
    if (!ocupado && !document.hidden && !document.activeElement?.matches('input, select')) operar(actualizarChequeos);
  }, 15000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !ocupado) operar(actualizarChequeos);
  });
})();
