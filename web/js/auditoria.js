(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const trimestres = ['', '1.er trimestre · Ene–Mar', '2.º trimestre · Abr–Jun', '3.er trimestre · Jul–Sep', '4.º trimestre · Oct–Dic'];
  const trimestre = registro => Math.ceil(Number(registro.mes) / 3);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  let catalogo = {fuentes: [], muestras: [], unidades: [], estados_pago: []}, muestra = null, ocupado = false;
  let listaTickets = null;
  let filasSeleccionadas = [];
  let periodoChequeo = null, periodoSeleccion = null;
  const permite = permiso => Boolean(window.PanelSesion?.permite(permiso));
  const nombreRespaldoValido = (nombre, esperado) => {
    const requerido = /^([0-9]+)_EDP([0-9]+)\.pdf$/.exec(esperado || '');
    const punto = nombre.lastIndexOf('.');
    const partes = /^([0-9]+)[ _-]*EDP[ _-]*([0-9]+)$/i.exec(nombre.slice(0, punto));
    return Boolean(requerido && punto > 0 && punto < nombre.length - 1 && partes &&
      partes[1] === requerido[1] && partes[2] === requerido[2]);
  };
  const tieneRespaldo = t => Boolean(t?.comprobado || t?.respaldo_ticket);
  const tieneCompletados = edp => Boolean(edp && ([...catalogo.muestras, ...catalogo.estados_pago].some(m =>
    m.unidad === edp.unidad && String(m.anio) === String(edp.anio) && String(m.mes) === String(edp.mes) &&
    String(m.edp) === String(edp.edp) && m.comprobados > 0) ||
    (muestra && !muestra.preview && muestra.unidad === edp.unidad && String(muestra.anio) === String(edp.anio) &&
      String(muestra.mes) === String(edp.mes) && String(muestra.edp) === String(edp.edp) && muestra.tickets.some(t => t.comprobado))));

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
    document.querySelectorAll('.auditoria button, .auditoria input, .auditoria select, .filtros-chequeo button, .filtros-chequeo select').forEach(n => { n.disabled = ocupado; });
    $('sortear').disabled = ocupado || !permite('revisar') || !catalogo.fuentes.some(f => f.id === $('fuente').value);
    $('cantidad').disabled = ocupado || !permite('revisar');
    $('listar-tickets').disabled = $('sortear').disabled;
    $('buscar-ticket').disabled = $('ticket-elegido').disabled = ocupado || !permite('revisar') || !listaTickets;
    $('agregar-ticket').disabled = ocupado || !permite('revisar') || !listaTickets || !$('ticket-elegido').value || filasSeleccionadas.length >= 5;
    $('revisar-ticket').disabled = ocupado || !permite('revisar') || !listaTickets || filasSeleccionadas.length < 3 || filasSeleccionadas.length > 5;
    document.querySelectorAll('[data-quitar-seleccion]').forEach(n => { n.disabled = ocupado || !permite('revisar'); });
    $('historial').disabled = ocupado || !$('historial').value;
    $('exportar').disabled = ocupado || !muestra;
    $('eliminar-muestra').hidden = !permite('revisar') || !muestra || Boolean(muestra.preview);
    $('eliminar-muestra').disabled = ocupado || !permite('revisar') || !muestra || Boolean(muestra.preview);
    const pdfMuestra = tieneCompletados(muestra), pdfEdp = tieneCompletados(edpChequeoSeleccionado());
    $('generar-pdf').disabled = ocupado || !pdfMuestra;
    $('generar-pdf').title = muestra && !pdfMuestra ? 'Este EDP todavía no tiene tickets comprobados para generar el PDF.' : '';
    $('aviso-pdf-muestra').hidden = !muestra || pdfMuestra;
    $('pdf-unidad').disabled = ocupado || !pdfEdp;
    $('pdf-unidad').title = edpChequeoSeleccionado() && !pdfEdp ? 'Este EDP todavía no tiene tickets comprobados para generar el PDF.' : 'Selecciona un único EDP con tickets comprobados.';
    $('descargar-compilado').disabled = ocupado || !$('chequeo-unidad').value ||
      !registrosChequeo().some(tieneCompletados);
    document.querySelectorAll('[data-comprobar]').forEach(n => {
      n.disabled = ocupado || !permite('comprobar') || muestra?.preview || !tieneRespaldo(muestra?.tickets.find(t => t.fila === Number(n.dataset.comprobar)));
    });
    document.querySelectorAll('[data-adjuntar]').forEach(n => {
      n.disabled = ocupado || !permite('revisar') || muestra?.preview || muestra?.tickets.find(t => t.fila === Number(n.dataset.adjuntar))?.comprobado;
    });
    document.querySelectorAll('[data-quitar]').forEach(n => {
      n.disabled = ocupado || !permite('modificar') || muestra?.preview;
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
    const periodo = id.startsWith('chequeo-') ? periodoChequeo : periodoSeleccion;
    const clave = id.replace(/^chequeo-/, '');
    if (periodo && ['anio', 'mes'].includes(clave)) {
      elegido = periodo[clave];
      if (!elementos.some(([v]) => String(v) === elegido)) elementos.push([elegido, clave === 'mes' ? meses[Number(elegido)] : elegido]);
    }
    $(id).replaceChildren(...elementos.map(([valor, texto]) => new Option(texto, String(valor))));
    if (!elementos.length) $(id).add(new Option(vacio, ''));
    if (elementos.some(([v]) => String(v) === String(elegido))) $(id).value = elegido;
  }
  function filtrar(nivel = 0, preferida = null) {
    limpiarTickets();
    const contextos = [...catalogo.fuentes, ...catalogo.muestras];
    if (nivel <= 0) opciones('unidad', [['', 'Todas las unidades'], ...[...new Set([...catalogo.unidades, ...contextos.map(f => f.unidad)])].map(v => [v,v])], preferida?.unidad || $('unidad').value, 'Sin unidades');
    let registros = contextos.filter(f => !$('unidad').value || f.unidad === $('unidad').value);
    if (nivel <= 1) opciones('anio', [['', 'Todos los años'], ...[...new Set(registros.map(f => f.anio))].sort((a,b) => b-a).map(v => [v,v])], preferida?.anio || $('anio').value, 'Sin años');
    registros = registros.filter(f => !$('anio').value || String(f.anio) === $('anio').value);
    if (nivel <= 2) opciones('trimestre', [['', 'Todos los trimestres'], ...[...new Set(registros.map(trimestre))].filter(v => v >= 1 && v <= 4).sort((a,b) => a-b).map(v => [v,trimestres[v]])], preferida ? trimestre(preferida) : $('trimestre').value);
    registros = registros.filter(f => !$('trimestre').value || String(trimestre(f)) === $('trimestre').value);
    if (nivel <= 3) opciones('mes', [['', 'Todos los meses'], ...[...new Set(registros.map(f => f.mes))].sort((a,b) => a-b).map(v => [v,meses[v]])], preferida?.mes || $('mes').value, 'Sin meses');
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
    filasSeleccionadas = [];
    $('buscar-ticket').value = '';
    opciones('ticket-elegido', [], '', 'Carga la lista de tickets');
    renderizarPreseleccion();
  }
  function renderizarPreseleccion() {
    const cantidad = filasSeleccionadas.length;
    $('seleccion-contador').textContent = `${cantidad} de 5 tickets preseleccionados${cantidad < 3 ? ' · Elige al menos 3.' : ' · Listos para revisar.'}`;
    $('tickets-preseleccionados').innerHTML = filasSeleccionadas.map(fila => {
      const t = listaTickets.tickets.find(t => t.fila === fila);
      return `<li><span>Ticket ${esc(t.ticket || 'sin número')} · Fila ${t.fila} · ${esc(t.fecha || 'Sin fecha')}</span><button type="button" class="enlace" data-quitar-seleccion="${fila}" aria-label="Quitar ticket ${esc(t.ticket || 'sin número')}, fila ${fila}">Quitar</button></li>`;
    }).join('');
  }
  function filtrarTickets() {
    const busqueda = $('buscar-ticket').value.trim().toLocaleLowerCase('es');
    const tickets = (listaTickets?.tickets || []).filter(t => !filasSeleccionadas.includes(t.fila)).map(t => [t.fila, `Ticket ${t.ticket || 'sin número'} · Fila ${t.fila} · ${t.fecha || 'Sin fecha'}`])
      .filter(([,nombre]) => nombre.toLocaleLowerCase('es').includes(busqueda));
    opciones('ticket-elegido', tickets, $('ticket-elegido').value, 'No hay tickets que coincidan');
    controles();
  }
  function coincide(f) { return (!$('unidad').value || f.unidad === $('unidad').value) && (!$('anio').value || String(f.anio) === $('anio').value) && (!$('trimestre').value || String(trimestre(f)) === $('trimestre').value) && (!$('mes').value || String(f.mes) === $('mes').value); }
  function registrosChequeo() {
    return catalogo.estados_pago.filter(e => ['unidad', 'anio', 'trimestre', 'mes', 'edp', 'estado'].every(k => {
      const valor = $('chequeo-' + k).value;
      return !valor || String(k === 'trimestre' ? trimestre(e) : e[k === 'estado' ? 'estado_codigo' : k]) === valor;
    }));
  }
  function edpChequeoSeleccionado() {
    const registros = registrosChequeo();
    return registros.length === 1 ? registros[0] : null;
  }
  function actualizarFiltrosChequeo() {
    const unidades = [...new Set([...catalogo.unidades, ...catalogo.estados_pago.map(e => e.unidad)])];
    opciones('chequeo-unidad', [['', 'Todas las unidades'], ...unidades.map(u => [u, u])], $('chequeo-unidad').value);
    let registros = catalogo.estados_pago.filter(e => !$('chequeo-unidad').value || e.unidad === $('chequeo-unidad').value);
    for (const [clave, todos] of [['anio', 'Todos los años'], ['trimestre', 'Todos los trimestres'], ['mes', 'Todos los meses'], ['edp', 'Todos los EDP']]) {
      const id = 'chequeo-' + clave;
      const valorRegistro = e => clave === 'trimestre' ? trimestre(e) : e[clave];
      const valores = [...new Set(registros.map(e => String(valorRegistro(e))))].filter(v => clave !== 'trimestre' || (Number(v) >= 1 && Number(v) <= 4)).sort((a, b) => clave === 'anio' ? b-a : a-b);
      opciones(id, [['', todos], ...valores.map(v => [v, clave === 'mes' ? meses[Number(v)] : clave === 'trimestre' ? trimestres[Number(v)] : v])], $(id).value);
      registros = registros.filter(e => !$(id).value || String(valorRegistro(e)) === $(id).value);
    }
  }
  function actualizarHistorial(preferida) {
    const registros = catalogo.muestras.filter(coincide).filter(m => !$('fuente').value || m.fuente === $('fuente').value);
    const vigentes = new Set(catalogo.estados_pago.map(e => e.muestra_vigente));
    opciones('historial', registros.map(m => [m.id, `EDP ${m.edp} · ${m.cantidad} tickets · ${m.comprobados} comprobados · ${vigentes.has(m.id) ? 'Vigente' : 'Histórica'} · ${m.id.slice(0,8)}`]), preferida, 'Sin muestras guardadas');
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
    if (!preferida && !$('unidad').options.length) preferida = catalogo.fuentes[0] || catalogo.muestras[0];
    filtrar(0, preferida);
    await abrirSeleccion();
    mensaje(`${catalogo.fuentes.length} Excel EDP disponibles. ${permite('comprobar') ? 'Las comprobaciones se guardan automáticamente en la BD.' : 'Consulta los tickets ya sorteados y sus estados desde las muestras guardadas.'}`);
  }
  async function recordarMuestra() {
    if (muestra.preview) { renderizar(); return; }
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
    if (window.PanelConsulta) { $('conexion-bd').hidden = true; return; }
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
    if (muestra && !muestra.preview) {
      if (catalogo.muestras.some(m => m.id === muestra.id)) {
        muestra = await consultar('/muestra?id=' + encodeURIComponent(muestra.id));
        renderizar();
      } else await abrirSeleccion();
    } else if (!muestra && $('historial').value) await abrirSeleccion();
  }
  function renderizarCobertura() {
    actualizarFiltrosChequeo();
    const registros = registrosChequeo();
    const unidades = $('chequeo-unidad').value ? [$('chequeo-unidad').value] : [...new Set(registros.map(e => e.unidad))];
    const maximo = Math.max(1, ...unidades.map(u => registros.filter(e => e.unidad === u).length));
    $('grafico-chequeos').innerHTML = unidades.map(unidad => {
      const edp = registros.filter(e => e.unidad === unidad);
      return `<div class="barra-fila"><div class="barra-etiqueta"><strong>${esc(unidad)}</strong>${edp.length} EDP</div><div class="barras">${[['completo', 'Chequeo completo'], ['parcial', 'Chequeo parcial'], ['sin_revision', 'Sin revisión']].map(([clase, etiqueta]) => {
        const n = edp.filter(e => e.estado_codigo === clase).length;
        return `<div class="barra" tabindex="0" data-grafico-clave="${esc(JSON.stringify([unidad,clase]))}" aria-label="${esc(unidad)}: ${etiqueta}, ${n} EDP"><div class="barra-pista"><span class="barra-relleno ${clase}" style="width:${n / maximo * 100}%"></span></div><span>${etiqueta}: ${n}</span></div>`;
      }).join('')}</div></div>`;
    }).join('');
    $('alcance-unidad').textContent = `${$('chequeo-unidad').value || 'Todas las unidades'} · ${registros.length} EDP según los filtros de chequeo.`;
    $('estados-pago').innerHTML = registros.length ? registros.map(e => `<tr><td>${esc(e.unidad)}</td><td>${esc(e.periodo)}</td><td>${esc(e.edp)}</td><td>${e.revisiones}</td><td>${e.comprobados}</td><td>${e.pendientes}</td><td><span class="semaforo ${esc(e.color)}">${esc(e.estado)}</span></td></tr>`).join('') : '<tr><td colspan="7" class="vacio">Sin EDP que coincidan con los filtros.</td></tr>';
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
    $('muestra-fecha').textContent = `${muestra.modo === 'manual' ? 'Muestra seleccionada manualmente' : 'Muestra aleatoria'} · ${muestra.preview ? 'Vista previa · Sin guardar' : 'Revisión ' + muestra.id.slice(0,8)}`;
    $('muestra-origen').textContent = `${muestra.archivo} → Hoja ${muestra.hoja} · Ítem ${muestra.item || (muestra.unidad === 'Andina' ? '1.1' : '2.5.a')}`;
    $('poblacion-hoja').textContent = `Tickets de la hoja ${muestra.hoja}`;
    $('muestra-avisos').innerHTML = muestra.avisos.map(a => `<p class="observaciones">${esc(a)}</p>`).join('');
    $('respaldo-edp').innerHTML = '<p class="nota-guardado">Las nuevas comprobaciones requieren el respaldo individual NumeroTicket_EDPNumeroEDP o NumeroTicket EDP NumeroEDP, con o sin guion, y la extensión de su formato (por ejemplo, .pdf o .jpg) en la carpeta Fuentes del EDP. Las comprobaciones anteriores conservan su respaldo histórico.</p>';
    $('tickets-auditoria').innerHTML = muestra.tickets.map((t,i) => `
      <article class="tarjeta ticket-auditoria" aria-labelledby="ticket-${t.fila}">
        <div class="titulo"><div><p class="eyebrow">TICKET ${i+1} DE ${muestra.tickets.length} · FILA EXCEL ${t.fila}</p><h3 id="ticket-${t.fila}">Ticket ${esc(t.ticket || 'sin número')}</h3></div>
          <span class="semaforo ${t.comprobado ? 'verde' : 'amarillo'}">${t.comprobado ? 'Comprobado manualmente' : 'Pendiente de comprobación'}</span></div>
        <div class="contenido ticket-contenido"><dl class="detalle-datos">${t.campos.map(c => `<div><dt>${esc(c.nombre)} <small>[${esc(c.celda)}]</small></dt><dd>${c.sin_resultado ? 'Sin resultado guardado' : esc(c.valor ? c.valor + (c.unidad === 't' ? ' t' : '') : '—')}</dd>${c.formula && c.unidad !== 't' && !/peso\s*total/i.test(c.nombre) ? `<small class="formula-ticket">Fórmula: ${esc(c.formula)}</small>` : ''}</div>`).join('')}</dl>
          <section class="respaldo-ticket" aria-label="Respaldos del ticket ${esc(t.ticket)}"><h4>Documentos de respaldo</h4>
            <ul class="lista-respaldos">${t.respaldo_ticket ? `<li><a href="/api/auditoria/respaldo-ticket?id=${encodeURIComponent(muestra.id)}&fila=${t.fila}" download>${esc(t.respaldo_ticket.nombre)}</a><span>${t.respaldo_ticket.historico ? 'Respaldo histórico' : 'Respaldo individual'} · ${Math.ceil(t.respaldo_ticket.bytes/1024)} KB</span></li>` : '<li class="sin-respaldos">No se encontró el respaldo individual requerido.</li>'}</ul>
            ${permite('revisar') ? `<label>Subir respaldo individual<input type="file" data-adjuntar="${t.fila}"></label>` : ''}
            <p class="nota-guardado">${t.respaldo_esperado ? `Nombre requerido: ${esc(t.respaldo_esperado.replace(/\.pdf$/, ''))} o ${esc(t.respaldo_esperado.replace(/_EDP/, ' EDP ').replace(/\.pdf$/, ''))}, con o sin guion + extensión del archivo · Cualquier formato de hasta 30 MB. Al elegir el archivo se sube automáticamente y se guarda en Fuentes, en la carpeta de este EDP.` : 'Este ticket no tiene un número válido para identificar su respaldo.'}</p>
            <label class="comprobacion-manual"><input type="checkbox" data-comprobar="${t.fila}" ${t.comprobado ? 'checked' : ''} ${!tieneRespaldo(t) || !permite('comprobar') ? 'disabled' : ''}><span>Comprobé manualmente que la información de este ticket coincide con la documentación de respaldo.${permite('comprobar') ? '' : ' Solo Auditor o Administrador puede cambiar esta casilla.'}</span></label>
            <p class="nota-guardado">${t.comprobado ? 'Ticket comprobado manualmente. Se usa el respaldo individual de Fuentes cuando está disponible; en su ausencia se conserva el respaldo guardado o histórico.' : t.respaldo_ticket ? 'Revisa el respaldo individual antes de marcar la casilla.' : 'Sube el respaldo individual con el nombre requerido para habilitar la comprobación.'}</p>
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
    if (window.PanelConsulta) {
      window.PanelConsultaDatos.descargarAuditoria(extension === 'pdf' ? 'zip' : extension, muestra);
      mensaje(extension === 'pdf' ? 'ZIP descargado con el reporte PDF y sus respaldos publicados.' : 'CSV de la revisión publicada descargado.');
      return;
    }
    if (extension === 'pdf' && !tieneCompletados(muestra)) throw new Error('Este EDP todavía no tiene tickets comprobados para generar el PDF. Auditor o Admin debe registrar una comprobación. Puedes descargar el CSV con los estados actuales.');
    mensaje(extension === 'pdf' ? 'Preparando PDF con todos los tickets completados del EDP…' : 'Preparando CSV de la muestra guardada…');
    const respuesta = await api('/reporte.' + (extension === 'pdf' ? 'zip' : extension) + '?id=' + encodeURIComponent(muestra.id));
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje(extension === 'pdf' ? 'ZIP generado con el reporte PDF y sus respaldos. Revisa las descargas del navegador.' : 'CSV generado. Revisa las descargas del navegador.');
  }
  ['unidad','anio','trimestre','mes'].forEach((id,i) => $(id).addEventListener('change', () => operar(async () => {
    if (id !== 'unidad') periodoSeleccion = null;
    filtrar(i+1); await abrirSeleccion(); mensaje('Selección actualizada. Puedes retomar una muestra o realizar un nuevo sorteo.');
  })));
  ['unidad', 'anio', 'trimestre', 'mes', 'edp', 'estado'].forEach(k => $('chequeo-' + k).addEventListener('change', () => {
    if (['anio', 'trimestre', 'mes'].includes(k)) periodoChequeo = null;
    renderizarCobertura(); controles();
  }));
  function mesActual() {
    const partes = new Intl.DateTimeFormat('es-CL', {timeZone: 'America/Santiago', year: 'numeric', month: 'numeric'}).formatToParts(new Date());
    return {anio: String(Number(partes.find(p => p.type === 'year').value)), mes: String(Number(partes.find(p => p.type === 'month').value))};
  }
  for (const actual of [false, true]) {
    $('chequeo-' + (actual ? 'este-mes' : 'limpiar')).addEventListener('click', () => {
      periodoChequeo = actual ? mesActual() : null;
      ['unidad', 'anio', 'trimestre', 'mes', 'edp', 'estado'].filter(k => !actual || k !== 'unidad').forEach(k => $('chequeo-' + k).value = '');
      renderizarCobertura(); controles();
    });
    $(actual ? 'este-mes' : 'limpiar').addEventListener('click', () => operar(async () => {
      periodoSeleccion = actual ? mesActual() : null;
      ['unidad', 'anio', 'trimestre', 'mes', 'fuente', 'historial'].filter(k => !actual || k !== 'unidad').forEach(k => $(k).value = '');
      filtrar(); await abrirSeleccion();
      mensaje(actual ? 'Selección filtrada por el mes actual.' : 'Filtros de selección limpiados.');
    }));
  }
  $('fuente').addEventListener('change', () => operar(async () => { limpiarTickets(); actualizarHistorial(); await abrirSeleccion(); mensaje('EDP seleccionado.'); }));
  $('historial').addEventListener('change', () => operar(async () => { await abrirSeleccion(); mensaje('Muestra guardada recuperada.'); }));
  $('actualizar').addEventListener('click', () => operar(() => cargar()));
  $('sortear').addEventListener('click', () => operar(async () => {
    if (!permite('revisar')) return;
    mensaje('Leyendo el Excel y sorteando la muestra…');
    muestra = await consultar('/sortear', {fuente:$('fuente').value, cantidad:Number($('cantidad').value)});
    await recordarMuestra(); mensaje(`${muestra.preview ? 'Vista previa sin guardar' : 'Muestra guardada'}: ${muestra.tickets.length} tickets de ${muestra.poblacion} registros.`);
  }));
  $('listar-tickets').addEventListener('click', () => operar(async () => {
    if (!permite('revisar')) return;
    limpiarTickets(); mensaje('Leyendo los tickets del EDP seleccionado…');
    listaTickets = await consultar('/tickets?id=' + encodeURIComponent($('fuente').value));
    filtrarTickets(); mensaje(`${listaTickets.tickets.length} tickets disponibles. Añade entre 3 y 5 a la selección.`);
  }));
  $('buscar-ticket').addEventListener('input', filtrarTickets);
  $('ticket-elegido').addEventListener('change', controles);
  $('agregar-ticket').addEventListener('click', () => {
    if (ocupado || !permite('revisar') || !listaTickets || filasSeleccionadas.length >= 5) return;
    const fila = Number($('ticket-elegido').value);
    if (!listaTickets.tickets.some(t => t.fila === fila) || filasSeleccionadas.includes(fila)) return;
    filasSeleccionadas.push(fila);
    renderizarPreseleccion(); filtrarTickets();
  });
  $('tickets-preseleccionados').addEventListener('click', event => {
    const boton = event.target.closest('[data-quitar-seleccion]');
    if (!boton || ocupado || !permite('revisar')) return;
    filasSeleccionadas = filasSeleccionadas.filter(fila => fila !== Number(boton.dataset.quitarSeleccion));
    renderizarPreseleccion(); filtrarTickets();
  });
  $('revisar-ticket').addEventListener('click', () => operar(async () => {
    if (!permite('revisar')) return;
    if (!listaTickets || filasSeleccionadas.length < 3 || filasSeleccionadas.length > 5) throw new Error('Preselecciona entre 3 y 5 tickets.');
    mensaje('Preparando los tickets seleccionados…');
    muestra = await consultar('/seleccionar', {fuente:listaTickets.fuente, filas:[...filasSeleccionadas], sha256:listaTickets.sha256});
    await recordarMuestra(); mensaje(`Muestra guardada: ${muestra.tickets.length} tickets elegidos manualmente. Revisa sus respaldos y registra las comprobaciones.`);
  }));
  $('tickets-auditoria').addEventListener('change', event => {
    const control = event.target;
    if (control.matches('[data-adjuntar]')) {
      const archivos = [...control.files];
      if (!archivos.length) return;
      operar(async () => {
        if (!permite('revisar') || !muestra || muestra.preview) return;
        let guardados = 0;
        let destino = '';
        try {
          const ticket = muestra.tickets.find(t => t.fila === Number(control.dataset.adjuntar));
          if (!ticket || ticket.comprobado) throw new Error('Selecciona un ticket pendiente para subir su respaldo.');
          if (!ticket.respaldo_esperado || archivos.some(a => !nombreRespaldoValido(a.name, ticket.respaldo_esperado))) {
            throw new Error(`El archivo debe llamarse exactamente ${ticket.respaldo_esperado?.replace(/\.pdf$/, '') || 'NumeroTicket_EDPNumeroEDP'} o NumeroTicket EDP NumeroEDP, con o sin guion, y la extensión de su formato.`);
          }
          for (const archivo of archivos) {
            mensaje(`Guardando ${archivo.name} en Fuentes, EDP ${muestra.edp}…`);
            muestra = await consultar('/adjuntar', {...await archivoJSON(archivo), muestra:muestra.id, fila:Number(control.dataset.adjuntar)});
            destino = muestra.tickets.find(t => t.fila === Number(control.dataset.adjuntar))?.respaldo_ticket?.archivo || '';
            guardados++; await recordarMuestra();
          }
          mensaje(`${guardados} documento(s) guardado(s) en ${destino ? 'Fuentes/' + destino : 'Fuentes, en la carpeta de este EDP'}. Ya puedes revisar el respaldo y marcar la casilla.`);
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
  $('eliminar-muestra').addEventListener('click', () => operar(async () => {
    if (!permite('revisar') || !muestra || muestra.preview) return;
    const identificador = muestra.id;
    if (!window.confirm(`¿Eliminar la muestra ${identificador.slice(0,8)} de ${muestra.unidad}, ${muestra.periodo}, EDP ${muestra.edp}? Se quitarán sus comprobaciones y adjuntos del historial y de los reportes. Los archivos de Fuentes se conservan.`)) return;
    await consultar('/eliminar', {muestra: identificador});
    muestra = null; renderizar();
    await cargar();
    mensaje('Muestra eliminada. El historial y los estados de chequeo se han actualizado.');
  }));
  $('descargar-compilado').addEventListener('click', () => operar(async () => {
    const unidad = $('chequeo-unidad').value;
    if (!unidad) throw new Error('Selecciona una unidad en los filtros de chequeo.');
    const parametros = new URLSearchParams({unidad});
    ['anio', 'trimestre', 'mes', 'edp', 'estado'].forEach(k => {
      if ($('chequeo-' + k).value) parametros.set(k, $('chequeo-' + k).value);
    });
    mensaje(`Preparando los PDF de ${unidad} según los filtros activos, organizados por año y mes…`);
    const respuesta = await api('/compilado.zip?' + parametros);
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje(`Compilado de ${unidad} generado según los filtros activos, en carpetas por año y mes. Revisa las descargas del navegador.`);
  }));
  $('pdf-unidad').addEventListener('click', () => operar(async () => {
    const edp = edpChequeoSeleccionado();
    if (!edp) throw new Error('Usa los filtros de chequeo para seleccionar un único EDP.');
    if (window.PanelConsulta) {
      window.PanelConsultaDatos.descargarAuditoria('zip', edp);
      mensaje('ZIP descargado con el reporte PDF y sus respaldos publicados.');
      return;
    }
    const parametros = new URLSearchParams();
    ['unidad', 'anio', 'mes', 'edp'].forEach(k => parametros.set(k, edp[k]));
    mensaje('Preparando PDF con todos los tickets completados del EDP…');
    const respuesta = await api('/unidad.zip?' + parametros);
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = decodeURIComponent(respuesta.headers.get('Content-Disposition').split("filename*=UTF-8''")[1]);
    document.body.appendChild(enlace); enlace.click(); enlace.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    mensaje('ZIP del EDP generado con el reporte PDF y sus respaldos. Revisa las descargas del navegador.');
  }));
  window.PanelSesion.listo.then(() => {
    if (permite('revisar')) {
      $('descripcion-auditoria').textContent = 'Selecciona un EDP, elige entre 3 y 5 tickets o sortea una muestra y registra tu revisión.';
      $('indicacion-auditoria').textContent = 'Elige manualmente o sortea 3, 4 o 5 tickets, o retoma una revisión del historial.';
    }
    if (window.PanelSesion.usuario || window.PanelConsulta) operar(() => cargar());
  });
  setInterval(() => {
    if (window.PanelConsulta) return;
    if (!ocupado && !document.hidden && !document.activeElement?.matches('input, select')) operar(actualizarChequeos);
  }, 15000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !ocupado) operar(actualizarChequeos);
  });
})();
