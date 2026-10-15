/* La BD y el servidor calculan el volumen y la clasificación de cada ticket. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const distribucion = document.body.dataset.panel === 'volumenes';
  const tramos = distribucion ? globalThis.distribucionVolumen.tramos : [];
  const tramo = t => globalThis.distribucionVolumen.clasificar(t.volumen_m3);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const num = (v, d = 2) => v == null ? '—' : new Intl.NumberFormat('es-CL', {minimumFractionDigits:d, maximumFractionDigits:d}).format(v);
  const normalizar = v => String(v).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toUpperCase();
  const estados = {coincide:['Transacción es Consistente con las tolvas en Faena','verde','#2E9E6B'], no_coincide_menor:['Transacción No óptima con las tolvas en Faena','amarillo','#997000'], no_coincide_mayor:['Transacción No es Consistente con las tolvas en Faena','rojo','#a12424'], sin_evaluar:['Sin evaluar','gris','#5B6B7C']};
  const filtros = ['unidad','anio','trimestre','mes','edp','residuo','filtro-estado','volumen_tipo','buscar'];
  if (distribucion) filtros.push('tramo_volumen');
  const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  let datos = null, visibles = [], cargando = false, exportando = false, pagina = 0;
  const porPagina = 100;
  function parametros() {
    const p = new URLSearchParams();
    filtros.forEach(k => {if ($(k).value.trim()) p.set(k === 'filtro-estado' ? 'estado' : k, $(k).value.trim());});
    return p;
  }
  function botones() {
    $('unidad').disabled = cargando || exportando;
    $('actualizar').disabled = cargando;
    $('generar-pdf').disabled = $('descargar-compilado').disabled = cargando || exportando || !visibles.length;
    $('exportar').disabled = cargando || !visibles.length;
  }
  function opciones() {
    ['anio','mes','edp','residuo'].forEach(k => {
      const valor = $(k).value, titulo = $(k).options[0].textContent;
      const valores = [...new Set(datos.tickets.map(t => t[k]).filter(v => v != null))].sort((a,b) => k === 'residuo' ? a.localeCompare(b) : a-b);
      if (valor && ['anio', 'mes'].includes(k) && !valores.some(v => String(v) === valor)) valores.push(Number(valor));
      $(k).replaceChildren(new Option(titulo, ''));
      valores.forEach(v => $(k).add(new Option(k === 'mes' ? meses[v-1] : k === 'edp' ? 'EDP ' + v : String(v), v)));
      if (valores.some(v => String(v) === valor)) $(k).value = valor;
    });
    const capacidad = $('volumen_tipo').value;
    $('volumen_tipo').replaceChildren(new Option('Todas las capacidades', ''));
    datos.volumenes.forEach(v => $('volumen_tipo').add(new Option(v + ' m³', v)));
    if (datos.volumenes.some(v => String(v) === capacidad)) $('volumen_tipo').value = capacidad;
    $('unidad-titulo').textContent = 'CONTROL DE VOLUMEN · ' + datos.unidad.toUpperCase();
    $('unidad-descripcion').textContent = 'Compara el volumen de cada ticket con capacidades de ' + datos.volumenes.join(', ') + ' m³. ' +
      (datos.unidad === 'Andina' ? 'Cantidad (t) × 1.000 = peso (kg).' : 'Se usa Peso Total (kg) del ticket.');
    $('regla-capacidades').textContent = datos.volumenes.join(', ') + ' m³ · tolerancia ±' + datos.tolerancia_m3 + ' m³';
    $('kpi-total-nota').textContent = 'Filas de ' + datos.unidad + ' en la selección';
    $('kpi-verdes-nota').textContent = 'Dentro de ±3 m³ de ' + datos.volumenes.join(', ');
    $('kpi-amarillos-nota').textContent = 'Fuera de rangos y menor a ' + datos.umbral_m3 + ' m³ · amarillo';
    $('kpi-rojos-nota').textContent = 'Fuera de rangos y mayor a ' + datos.umbral_m3 + ' m³ · rojo';
    const ventanas = datos.volumenes.map(v => (v - datos.tolerancia_m3) + '–' + (v + datos.tolerancia_m3)).join(', ');
    $('nota-volumenes').textContent = 'Bandas de ' + datos.unidad + ': ' + ventanas + ' m³. Cada punto representa un ticket; pasa el cursor o enfócalo para ver su valor. Verde: coincide. Amarillo: fuera de rangos y menor a ' + datos.umbral_m3 + ' m³. Rojo: fuera de rangos y mayor a ' + datos.umbral_m3 + ' m³. Gris: sin evaluar; sin punto de volumen.';
    if (distribucion) {
      $('unidad-titulo').textContent = 'DISTRIBUCIÓN DE VOLUMEN · ' + datos.unidad.toUpperCase();
      $('unidad-descripcion').textContent = 'Distribución del volumen calculado de los tickets de ' + datos.unidad + ', con los mismos filtros del chequeo de densidades.';
      $('regla-capacidades').textContent = 'Tramos: <10 · 10–<20 · 20–30 · >30 m³';
      ['kpi-total-nota','kpi-verdes-nota','kpi-amarillos-nota','kpi-rojos-nota'].forEach(k => $(k).textContent = 'Tickets y porcentaje del total seleccionado');
      $('nota-volumenes').textContent = 'Cada punto representa un ticket, coloreado según su tramo de volumen. La clasificación usa el valor completo, antes de redondear. Los tickets sin volumen calculable no tienen punto.';
    }
    $('unidad-footer').textContent = 'Reporte Codelco · ' + datos.unidad;
  }
  function barras(id, grupos) {
    const maximo = Math.max(1, ...grupos.map(g => g[1]));
    $(id).innerHTML = grupos.map(([nombre, cantidad, color, clave]) => `<div class="barra-fila"><strong class="barra-etiqueta">${esc(nombre)}</strong><div class="barra" tabindex="0" data-grafico-clave="${esc(clave)}" aria-label="${esc(nombre)}: ${num(cantidad,0)} tickets"><div class="barra-pista"><span class="barra-relleno" style="background:${color};width:${cantidad/maximo*100}%"></span></div><span>${num(cantidad,0)} tickets</span></div></div>`).join('');
  }
  function dispersion() {
    const tickets = visibles.filter(t => t.volumen_m3 != null);
    if (!tickets.length) { $('grafico-volumenes').innerHTML = '<p class="vacio">Sin volúmenes calculables en esta selección.</p>'; return; }
    const ancho = 1100, alto = 300, izq = 65, arriba = 16, base = 248, largo = ancho-izq-25;
    const max = Math.max(Math.max(...datos.volumenes) + 6, ...tickets.map(t => t.volumen_m3 * 1.03));
    const y = v => base-(base-arriba)*v/max;
    let svg = `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="Volumen de ${tickets.length} tickets de ${esc(datos.unidad)} frente a capacidades de ${datos.volumenes.join(', ')} metros cúbicos">`;
    if (distribucion) {
      svg = svg.replace('Volumen por ticket y tolerancia de ±3 m³', 'Volumen por ticket y tramos de distribución');
      svg = svg.replace(/frente a capacidades de [^"]+/, 'por tramo de volumen');
      [10,20,30].forEach(v => {svg += `<line x1="${izq}" x2="${ancho-25}" y1="${y(v)}" y2="${y(v)}" stroke="#5B6B7C" stroke-dasharray="5 4"/><text x="${izq-9}" y="${y(v)+4}" text-anchor="end" font-size="12">${v} m³</text>`;});
      tramos.filter(g => g.id !== 'sin_volumen').forEach((g,i) => {
        const inferior = [0,10,20,30][i], superior = Math.min([10,20,30,max][i],max);
        if (inferior >= superior) return;
        svg += `<g class="banda-volumen" tabindex="0" data-grafico-clave="tramo:${g.id}" aria-label="${esc(g.nombre)}" style="color:${g.color}"><rect x="${izq}" y="${y(superior)}" width="${largo}" height="${y(inferior)-y(superior)}" fill="${g.color}" fill-opacity=".08"/></g>`;
      });
    } else datos.volumenes.forEach(v => { svg += `<g class="banda-volumen" tabindex="0" data-grafico-clave="capacidad:${v}" aria-label="Capacidad ${v} m³, rango ${v-3} a ${v+3} m³" style="color:#2E9E6B"><rect x="${izq}" y="${y(v+3)}" width="${largo}" height="${y(v-3)-y(v+3)}" fill="#2E9E6B" fill-opacity=".13"/><line x1="${izq}" x2="${ancho-25}" y1="${y(v)}" y2="${y(v)}" stroke="#2E9E6B" stroke-dasharray="5 4"/><text x="${izq-9}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="#176344">${v} m³</text></g>`; });
    svg += `<line x1="${izq}" x2="${ancho-25}" y1="${base}" y2="${base}" stroke="#bdcbd8"/><text x="${izq-9}" y="${base+4}" text-anchor="end" font-size="12">0</text><text x="${izq}" y="${arriba+10}" font-size="12" fill="#5B6B7C">Máximo de escala: ${num(max,1)} m³</text>`;
    tickets.forEach((t,i) => { const texto = `Ticket ${t.ticket || '(sin ID)'} · ${t.periodo} · EDP ${t.edp} · fila ${t.fila}: ${num(t.volumen_m3,3)} m³ · ${t.motivo}${t.residuo_es_estimado ? ' · Tipo de residuo estimado: ' + t.residuo : ''}`;
      svg += `<circle data-grafico-rangos="${esc(JSON.stringify(distribucion ? ['tramo:'+tramo(t)] : datos.volumenes.filter(v => Math.abs(t.volumen_m3-v) <= datos.tolerancia_m3).map(v => 'capacidad:'+v)))}" data-volumen="${t.volumen_m3}" data-grafico-clave="${distribucion ? 'tramo:'+tramo(t) : 'estado:'+t.estado}" tabindex="0" aria-label="${esc(texto)}" cx="${izq+largo*(i+.5)/tickets.length}" cy="${y(t.volumen_m3)}" r="3.2" fill="${distribucion ? tramos.find(g => g.id === tramo(t)).color : estados[t.estado][2]}" opacity=".8"></circle>`; });
    svg += `<text x="${izq}" y="283" font-size="12" fill="#5B6B7C">${num(tickets.length,0)} tickets en orden de período y fila. Todos los puntos están incluidos.</text></svg>`;
    $('grafico-volumenes').innerHTML = svg;
  }
  function comentarioTicket(t) {
    const editable = t.estado === 'no_coincide_mayor' && globalThis.window?.PanelSesion?.permite('revisar');
    const autor = t.comentario_autor ? `<small>${esc(t.comentario_autor)} · ${esc(new Date(t.comentario_actualizado).toLocaleString('es-CL'))}</small>` : '';
    if (!editable) return `<span class="comentario-texto">${esc(t.comentario || 'Sin comentario')}</span>${autor}`;
    return `<form data-comentario-id="${esc(t.id)}"><textarea aria-label="Comentario del ticket ${esc(t.ticket || '(sin ID)')}" maxlength="2000" rows="3" placeholder="Explica por qué este ticket está en rojo">${esc(t.comentario)}</textarea><span class="comentario-autor">${autor}</span><button type="submit">Guardar comentario</button><small role="status" aria-live="polite"></small></form>`;
  }
  $('filas').addEventListener('submit', async evento => {
    const formulario = evento.target.closest('[data-comentario-id]');
    if (!formulario) return;
    evento.preventDefault();
    const ticket = datos.tickets.find(t => t.id === formulario.dataset.comentarioId);
    const campo = formulario.querySelector('textarea'), boton = formulario.querySelector('button');
    const mensaje = formulario.querySelector('[role="status"]');
    campo.disabled = boton.disabled = true; mensaje.textContent = 'Guardando…';
    try {
      const respuesta = await fetch('/api/densidades/comentario', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({unidad:ticket.unidad, id:ticket.id, comentario:campo.value})});
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error || 'No se pudo guardar el comentario.');
      Object.assign(ticket, resultado); campo.value = resultado.comentario;
      const autor = formulario.querySelector('.comentario-autor');
      if (autor) autor.innerHTML = `<small>${esc(resultado.comentario_autor)} · ${esc(new Date(resultado.comentario_actualizado).toLocaleString('es-CL'))}</small>`;
      mensaje.textContent = 'Comentario guardado.';
    } catch (error) { mensaje.textContent = error.message; }
    finally { campo.disabled = boton.disabled = false; }
  });
  function tabla() {
    const inicio = pagina * porPagina;
    $('filas').innerHTML = visibles.slice(inicio,inicio+porPagina).map(t => {
      if (distribucion) {
        const estimado = t.residuo_es_estimado ? '<small>Tipo y densidad estimados</small>' : '';
        const nombreTramo = tramos.find(g => g.id === tramo(t)).nombre;
        return `<tr><td><strong>${esc(t.periodo)}</strong><small>EDP ${esc(t.edp)}</small></td><td>${esc(t.ticket || '(sin ID)')}<small>${esc(t.fecha || 'Sin fecha')}</small></td><td class="densidad-texto">${esc(t.residuo || 'Sin residuo')}${estimado}</td><td>${num(t.peso_kg)}</td><td>${num(t.densidad_kg_m3)}</td><td>${esc(nombreTramo)}</td></tr>`;
      }
      const original = t.residuo_original !== t.residuo ? '<small>Original: '+esc(t.residuo_original || '(sin tipo declarado)')+'</small>' : '';
      const estimacion = t.residuo_es_estimado ? '<small><strong>Tipo y densidad estimados</strong></small><details><summary>Ver estimación</summary><small>'+esc(t.criterio_estimacion_residuo)+'</small></details>' : '';
      return `<tr><td><strong>${esc(t.periodo)}</strong><small>EDP ${esc(t.edp)} · fila ${t.fila}</small></td><td>${esc(t.ticket || '(sin ID)')}<small>${esc(t.fecha || 'Sin fecha')}</small></td><td class="densidad-texto">${esc(t.residuo || 'Sin residuo')}${original}${estimacion}<small>${esc(t.retiro)}</small></td><td>${num(t.peso_kg)}</td><td title="Inferior: ${num(t.inferior_kg_m3)} / superior: ${num(t.superior_kg_m3)}">${num(t.densidad_kg_m3)}${t.residuo_es_estimado ? '<small>Según material estimado</small>' : ''}</td><td>${num(t.volumen_m3,3)}</td><td>${t.volumen_tipo == null ? '—' : t.volumen_tipo + ' m³'}</td><td>${num(t.diferencia_m3,3)}</td><td class="densidad-texto"><span class="semaforo ${estados[t.estado][1]}">${estados[t.estado][0]}</span><small>${esc(t.motivo)}${t.capacidades_compatibles.length > 1 ? ' Compatible también con: ' + t.capacidades_compatibles.filter(v => v !== t.volumen_tipo).join(', ') + ' m³.' : ''}</small></td><td class="densidad-texto densidad-comentario">${comentarioTicket(t)}</td></tr>`;
    }).join('') || `<tr><td colspan="${distribucion ? 6 : 10}" class="vacio">No hay tickets que coincidan con los filtros.</td></tr>`;
    $('cantidad-tickets').textContent = `${num(visibles.length,0)} tickets · mostrando ${visibles.length ? inicio+1 : 0}–${Math.min(inicio+porPagina,visibles.length)}. PDF y CSV incluyen toda la selección.`;
    let controles = $('paginacion');
    if (!controles) { controles = document.createElement('div'); controles.id = 'paginacion'; controles.className = 'densidad-paginacion'; $('filas').closest('.scroll').after(controles); }
    controles.replaceChildren();
    if (visibles.length > porPagina) {
      const previo = document.createElement('button'), siguiente = document.createElement('button');
      previo.textContent = 'Anterior'; previo.disabled = pagina === 0; previo.onclick = () => {pagina--; tabla();};
      siguiente.textContent = 'Siguiente'; siguiente.disabled = inicio+porPagina >= visibles.length; siguiente.onclick = () => {pagina++; tabla();};
      controles.append(previo, document.createTextNode(` Página ${pagina+1} de ${Math.ceil(visibles.length/porPagina)} `), siguiente);
    }
  }
  function renderizar() {
    if (!datos) return;
    const p = parametros();
    visibles = datos.tickets.filter(t => [...p].every(([k,v]) => k === 'tramo_volumen' ? tramo(t) === v : k === 'buscar' ? normalizar([t.ticket,t.retiro,t.residuo,t.residuo_original,t.archivo,t.fila].join(' ')).includes(normalizar(v)) : k === 'residuo' ? normalizar(t[k]) === normalizar(v) : String(k === 'trimestre' ? Math.ceil(Number(t.mes) / 3) : t[k]) === v));
    const sinMaestra = new Map();
    visibles.filter(t => !t.referencia_maestra).forEach(t => {const nombre = t.residuo || '(sin tipo declarado)'; sinMaestra.set(nombre, (sinMaestra.get(nombre) || 0) + 1);});
    const avisos = [...datos.maestra.avisos, ...datos.avisos_edp.filter(a => ['anio','trimestre','mes','edp'].every(k => !p.get(k) || String(k === 'trimestre' ? Math.ceil(Number(a.mes) / 3) : a[k]) === p.get(k))).map(a => a.mensaje),
      ...[...sinMaestra].map(([nombre, cantidad]) => `${datos.unidad}: ${nombre}, ${num(cantidad,0)} tickets sin correspondencia en AUX; revisar caso a caso.`)];
    const estimados = visibles.filter(t => t.residuo_es_estimado).length;
    if (estimados) avisos.push(`${num(estimados,0)} tickets usan un tipo de residuo estimado y la densidad de ese material en AUX. Los reportes conservan el original y el criterio de estimación.`);
    $('avisos').hidden = !avisos.length; $('avisos').innerHTML = avisos.map(a => '<p>'+esc(a)+'</p>').join('');
    const contar = e => visibles.filter(t => t.estado === e).length;
    $('kpi-total').textContent = num(visibles.length,0); $('kpi-verdes').textContent = num(contar('coincide'),0);
    $('kpi-amarillos').textContent = num(contar('no_coincide_menor'),0);
    $('kpi-rojos').textContent = num(contar('no_coincide_mayor'),0); $('kpi-pendientes').textContent = num(contar('sin_evaluar'),0);
    $('cobertura').textContent = `${num(visibles.filter(t => t.volumen_m3 != null).length,0)} tickets con volumen calculado de ${num(visibles.length,0)} seleccionados. Densidad utilizada: promedio de ambas densidades.`;
    barras('grafico-estados', Object.entries(estados).map(([k,v]) => [v[0],contar(k),v[2],"estado:"+k]));
    barras('grafico-capacidades', datos.volumenes.map(v => [v+' m³',visibles.filter(t => t.volumen_tipo === v).length,'#0E81C5','capacidad:'+v]));
    if (distribucion) {
      const grupos = tramos.map(g => ({...g, tickets:visibles.filter(t => tramo(t) === g.id)}));
      const ids = ['kpi-total','kpi-verdes','kpi-amarillos','kpi-rojos','kpi-pendientes'];
      grupos.forEach((g,i) => $(ids[i]).textContent = num(g.tickets.length,0) + ' · ' + num(visibles.length ? g.tickets.length / visibles.length * 100 : 0,1) + '%');
      const barrasTramos = (id, volumen) => {
        const lista = volumen ? grupos.filter(g => g.id !== 'sin_volumen') : grupos;
        const valores = lista.map(g => volumen ? g.tickets.reduce((s,t) => s+t.volumen_m3,0) : g.tickets.length);
        const maximo = Math.max(1,...valores);
        $(id).innerHTML = lista.map((g,i) => `<div class="barra-fila"><strong class="barra-etiqueta">${esc(g.nombre)}</strong><div class="barra" tabindex="0" data-grafico-clave="tramo:${g.id}" aria-label="${esc(g.nombre)}: ${num(valores[i],volumen ? 2 : 0)} ${volumen ? 'm³' : 'tickets'}"><div class="barra-pista"><span class="barra-relleno" style="background:${g.color};width:${valores[i]/maximo*100}%"></span></div><span>${num(valores[i],volumen ? 2 : 0)} ${volumen ? 'm³' : 'tickets'}${volumen ? '' : ' · '+num(visibles.length ? valores[i]/visibles.length*100 : 0,1)+'%'}</span></div></div>`).join('');
      };
      barrasTramos('grafico-estados',false); barrasTramos('grafico-capacidades',true);
      const calculables = visibles.filter(t => tramo(t) !== 'sin_volumen');
      $('cobertura').textContent = `${num(visibles.length,0)} tickets seleccionados · ${num(calculables.length,0)} con volumen calculable · volumen total: ${num(calculables.reduce((s,t) => s+t.volumen_m3,0),2)} m³. Los porcentajes incluyen los tickets sin volumen calculable.`;
    }
    dispersion(); tabla(); botones();
  }
  async function cargar() {
    cargando = true; botones(); $('estado').className = ''; $('estado').textContent = 'Cargando datos guardados…';
    try {
      const res = await fetch('/api/densidades?unidad=' + encodeURIComponent($('unidad').value), {cache:'no-store'}); const body = await res.json();
      if (!res.ok) throw new Error(body.error || 'No se pudieron cargar los datos.');
      await globalThis.window?.PanelSesion?.listo;
      datos = body; opciones(); pagina = 0;
      $('estado').textContent = globalThis.window?.PanelConsulta ? datos.tickets.length+' tickets disponibles' : 'Última actualización de la BD: '+new Date(datos.actualizado).toLocaleString('es-CL');
      $('maestra-origen').textContent = 'Fuente: '+(datos.maestra.archivo || 'No disponible')+' · '+datos.maestra.materiales.length+' materiales guardados en BD.';
      $('filas-maestra').innerHTML = datos.maestra.materiales.map(m => `<tr><td>${esc(m.material)}</td><td>${num(m.inferior_kg_m3)}</td><td>${num(m.superior_kg_m3)}</td><td>${num(m.densidad_kg_m3)}</td><td class="densidad-texto">${esc(m.hoja)}!${esc(m.celda_inferior)} / ${esc(m.celda_superior)}<small>${esc(m.error || '')}</small></td></tr>`).join('');
      renderizar();
    } catch (e) {datos = null; visibles = []; $('estado').className = 'error'; $('estado').textContent = e.message;
      $('filas').innerHTML = '<tr><td colspan="10" class="vacio">Datos no disponibles. Revisa el mensaje anterior.</td></tr>';
      if (distribucion) $('filas').rows[0].cells[0].colSpan = 6;
      ['kpi-total','kpi-verdes','kpi-amarillos','kpi-rojos','kpi-pendientes'].forEach(k => $(k).textContent = '—');
      ['grafico-estados','grafico-capacidades','grafico-volumenes','filas-maestra','cantidad-tickets','cobertura'].forEach(k => $(k).replaceChildren());
      $('avisos').hidden = true;
      if ($('paginacion')) $('paginacion').replaceChildren();
      $('maestra-origen').textContent = 'Maestra no disponible.';
    } finally {cargando = false; botones();}
  }
  function descargar(blob, nombre) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = nombre; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  async function generarPdf(compilado = false) {
    if (cargando || exportando || !visibles.length) return;
    exportando = true; botones(); const estado = $('pdf-estado'); estado.hidden = false; estado.textContent = compilado ? 'Generando un PDF por unidad, mes, año y EDP de la selección…' : 'Generando reporte PDF de toda la selección…';
    try { const r = await fetch((distribucion ? '/api/volumenes/' : '/api/densidades/') + (compilado ? 'compilado.zip?' : 'reporte.pdf?') + parametros()); if (!r.ok) {const body = await r.json(); throw new Error(body.error || 'No se pudo generar la descarga.');}
      descargar(await r.blob(), decodeURIComponent(r.headers.get('Content-Disposition').split("filename*=UTF-8''")[1])); estado.textContent = compilado ? 'Compilado ZIP generado con los PDF separados. Revisa las descargas del navegador.' : 'Reporte PDF generado.';
    } catch(e) {estado.textContent = e.message;} finally {exportando = false; botones();}
  }
  $('generar-pdf').addEventListener('click', () => generarPdf());
  $('descargar-compilado').addEventListener('click', () => generarPdf(true));
  $('exportar').addEventListener('click', () => {
    const campos = ['unidad','periodo','edp','fila','ticket','fecha','residuo','residuo_original','residuo_es_estimado','criterio_estimacion_residuo','retiro','peso_ton','peso_kg','inferior_kg_m3','superior_kg_m3','densidad_kg_m3','volumen_m3','volumen_tipo','volumen_cercano','diferencia_m3','estado','resultado','motivo','comentario','comentario_autor','comentario_actualizado','archivo','hoja_ticket','celda'];
    if (distribucion) campos.splice(campos.indexOf('volumen_m3')+1,0,'tramo_volumen');
    const celda = v => '"'+String(v ?? '').replace(/^[=+@-]/,'\'$&').replace(/"/g,'""')+'"';
    const csv = [campos.map(celda).join(';'), ...visibles.map(t => campos.map(k => celda(k === 'tramo_volumen' ? tramos.find(g => g.id === tramo(t)).nombre : k === 'resultado' ? estados[t.estado][0] : t[k])).join(';'))].join('\r\n');
    descargar(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}),(distribucion ? 'distribucion-volumen-' : 'chequeo-densidades-') + ($('unidad').value === 'Andina' ? 'andina' : 'salvador') + '.csv');
  });
  filtros.filter(k => k !== 'unidad').forEach(k => $(k).addEventListener(k === 'buscar' ? 'input' : 'change', () => {pagina = 0; renderizar();}));
  $('unidad').addEventListener('change', () => {filtros.filter(k => k !== 'unidad').forEach(k => $(k).value = ''); $('pdf-estado').hidden = true; cargar();});
  $('limpiar').onclick = () => {filtros.filter(k => k !== 'unidad').forEach(k => $(k).value = ''); pagina = 0; renderizar();};
  $('este-mes').onclick = () => {
    filtros.filter(k => k !== 'unidad').forEach(k => $(k).value = '');
    const partes = new Intl.DateTimeFormat('es-CL', {timeZone: 'America/Santiago', year: 'numeric', month: 'numeric'}).formatToParts(new Date());
    for (const [id, tipo] of [['anio', 'year'], ['mes', 'month']]) {
      const valor = String(Number(partes.find(p => p.type === tipo).value));
      if (![...$(id).options].some(o => o.value === valor)) $(id).add(new Option(id === 'mes' ? meses[Number(valor)-1] : valor, valor));
      $(id).value = valor;
    }
    pagina = 0; renderizar();
  };
  $('actualizar').onclick = cargar;
  cargar();
})();
