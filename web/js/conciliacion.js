/* Presentación del reporte. La extracción y los cálculos se realizan en app/. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const numero = (valor, decimales = 2) => valor == null ? '—' : new Intl.NumberFormat('es-CL', {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales
  }).format(valor);
  const pesos = valor => valor == null ? '—' : '$ ' + numero(valor);
  const escapar = valor => String(valor ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
  const estados = {cuadra: ['Cuadra', 'verde'], diferencia: ['Con diferencia', 'rojo'], incompleto: ['Sin conciliar', 'amarillo']};
  const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  const filtros = ['unidad', 'anio', 'mes', 'edp', 'filtro-estado'];
  let datos = null, visibles = [], cargando = false, generandoPdf = false;

  function opciones(id, opciones) {
    const actual = $(id).value, primero = $(id).options[0].textContent;
    $(id).replaceChildren(new Option(primero, ''));
    opciones.forEach(([valor, texto]) => $(id).add(new Option(texto, valor)));
    if (opciones.some(([v]) => String(v) === actual)) $(id).value = actual;
  }
  function prepararFiltros() {
    opciones('unidad', datos.unidades.map(u => [u, u]));
    ['anio','edp'].forEach(k => opciones(k, [...new Set(datos.registros.map(r => r[k]).filter(v => v != null))]
      .sort((a,b) => a-b).map(v => [v, k === 'edp' ? 'EDP ' + v : String(v)])));
    opciones('mes', [...new Set(datos.registros.map(r => r.mes).filter(v => v != null))]
      .sort((a,b) => a-b).map(v => [v, meses[v-1]]));
  }

  function grafico(id, registros, a, b, moneda) {
    const contenedor = $(id);
    if (!registros.length) {
      contenedor.innerHTML = '<p class="vacio">Sin EDP conciliables en esta selección.</p>';
      return;
    }
    const maximo = Math.max(...registros.flatMap(r => [Math.abs(r[a]), Math.abs(r[b])]), 1);
    const formato = v => moneda ? pesos(v) : numero(v, 3) + ' t';
    const barra = (v, clase, etiqueta) => '<div class="barra" aria-label="' + escapar(etiqueta + ': ' + formato(v)) + '">' +
      '<div class="barra-pista"><span class="barra-relleno ' + clase + '" style="width:' + Math.abs(v)/maximo*100 + '%"></span></div>' +
      '<span>' + escapar(formato(v)) + '</span></div>';
    contenedor.innerHTML = registros.map(r => '<div class="barra-fila"><div class="barra-etiqueta"><strong>' +
      escapar(r.mes_nombre + ' ' + r.anio) + '</strong>' + escapar(r.unidad + ' · EDP ' + r.edp) +
      '</div><div class="barras">' + barra(r[a], '', 'EDP') + barra(r[b], 'ticket', moneda ? 'Esperado' : 'Tickets') + '</div></div>').join('');
  }

  function renderizar() {
    if (!datos) return;
    visibles = datos.registros.filter(r => filtros.every(k => !$(k).value || String(r[k === 'filtro-estado' ? 'estado' : k]) === $(k).value))
      .sort((a,b) => (a.periodo || '').localeCompare(b.periodo || '') || (a.unidad || '').localeCompare(b.unidad || '') || a.edp-b.edp);
    const validos = visibles.filter(r => r.estado !== 'incompleto');
    const suma = k => validos.length ? validos.reduce((n,r) => n + r[k], 0) : null;
    const cuantos = estado => visibles.filter(r => r.estado === estado).length;
    $('kpi-edp').textContent = numero(visibles.length, 0);
    $('kpi-estados').textContent = cuantos('cuadra') + ' cuadran · ' + cuantos('diferencia') + ' con diferencia';
    $('kpi-ton').textContent = numero(suma('ton_tickets'), 3);
    $('kpi-tickets').textContent = validos.length ? numero(validos.reduce((n,r) => n+r.tickets.length,0),0) + ' filas de tickets incluidas' : 'Sin tickets conciliables';
    $('kpi-monto').textContent = pesos(suma('monto_esperado'));
    $('kpi-diferencia').textContent = pesos(suma('diferencia'));
    $('cobertura').textContent = visibles.length ?
      'Totales de ' + validos.length + ' de ' + visibles.length + ' EDP. ' +
      (cuantos('incompleto') ? cuantos('incompleto') + ' sin conciliar, excluidos de los totales. ' : '') +
      (visibles.some(r => r.avisos.length) ? 'Hay observaciones de tickets en el detalle.' : '') :
      'No hay estados de pago que coincidan con los filtros.';
    grafico('grafico-ton', validos, 'ton_edp', 'ton_tickets', false);
    grafico('grafico-monto', validos, 'monto_edp', 'monto_esperado', true);
    $('cantidad-registros').textContent = visibles.length + ' estados de pago';
    $('exportar').disabled = !visibles.length || cargando;
    $('generar-pdf').disabled = !visibles.length || cargando || generandoPdf;
    $('filas').innerHTML = visibles.length ? visibles.map(r => {
      const [etiqueta, clase] = estados[r.estado], indice = datos.registros.indexOf(r);
      return '<tr><td><strong>' + escapar(r.unidad || 'Unidad no identificada') + '</strong><small>' +
        escapar(r.periodo ? r.mes_nombre + ' ' + r.anio : r.nombre) + '</small></td><td>' + escapar(r.edp ?? '—') +
        '</td><td>' + numero(r.tickets.length,0) + '</td><td>' + numero(r.peso_kg,0) + '</td><td>' + numero(r.ton_tickets,3) +
        '</td><td>' + numero(r.ton_edp,3) + '</td><td>' + numero(r.precio) + '</td><td>' + numero(r.monto_edp) +
        '</td><td>' + numero(r.monto_esperado) + '</td><td>' + numero(r.diferencia) +
        '</td><td><span class="semaforo ' + clase + '">' + etiqueta + '</span>' +
        (r.avisos.length ? '<span class="aviso-celda">Observaciones de tickets</span>' : '') +
        '</td><td><button class="enlace" data-detalle="' + indice + '">Ver detalle</button></td></tr>';
    }).join('') : '<tr><td colspan="12" class="vacio">No hay EDP para esta selección. Revisa los filtros o agrega archivos a Fuentes.</td></tr>';
  }

  function abrirDetalle(indice) {
    const r = datos.registros[indice];
    if (!r) return;
    $('detalle-titulo').textContent = (r.unidad || 'Archivo por revisar') + ' · EDP ' + (r.edp ?? '—') + ' · ' + (r.periodo || '');
    const valores = [['Peso de tickets',numero(r.peso_kg,0)+' kg'],['Toneladas de tickets',numero(r.ton_tickets,3)+' t'],
      ['Toneladas del EDP',numero(r.ton_edp,3)+' t'],['Precio Modificación N.º 1',pesos(r.precio)+'/t'],
      ['Monto EDP',pesos(r.monto_edp)],['Monto esperado',pesos(r.monto_esperado)],
      ['Diferencia de toneladas',numero(r.diferencia_ton,6)+' t'],['Diferencia de monto',pesos(r.diferencia)],
      ['Conciliación',estados[r.estado][0]]];
    const refs = Object.entries(r.referencias).map(([k,v]) => {
      const nombre = {precio:'Precio',ton_edp:'Toneladas EDP',monto_edp:'Monto EDP',peso:'Peso de tickets'}[k];
      return '<p><strong>'+nombre+':</strong> '+escapar(v.hoja)+' · '+escapar(v.celda || v.rango)+
        (v.formula ? ' <code>'+escapar(v.formula)+'</code>' : '')+'</p>';
    }).join('');
    $('detalle-contenido').innerHTML = '<div><p><strong>Archivo:</strong> '+escapar(r.archivo)+'</p>'+
      '<p><strong>Período de pago:</strong> '+escapar(r.periodo_pago || 'No disponible')+'</p></div>'+
      '<dl class="detalle-datos">'+valores.map(([k,v])=>'<div><dt>'+k+'</dt><dd>'+escapar(v)+'</dd></div>').join('')+'</dl>'+
      (r.errores.length || r.avisos.length ? '<div class="observaciones">'+[...r.errores,...r.avisos].map(a=>'<p>'+escapar(a)+'</p>').join('')+'</div>' : '')+
      '<div class="ref">'+refs+'</div><h3>Tickets incluidos ('+r.tickets.length+')</h3>'+
      (r.tickets.length ? '<label>Buscar ticket, fecha, lugar o residuo<input id="buscar-ticket" type="search" placeholder="Escribe para filtrar el detalle"></label>'+
      '<div class="scroll"><table class="tickets"><thead><tr><th>Fila / celda</th><th>Ticket</th><th>Fecha</th><th>Lugar de retiro</th><th>Residuo</th><th>Peso total (kg)</th></tr></thead><tbody id="tickets-filas"></tbody></table></div>'+
      '<p class="nota">El buscador solo filtra esta lista; no cambia los totales del EDP.</p>' : '<p>No se pudieron obtener tickets de este archivo.</p>');
    function tickets() {
      const q = $('buscar-ticket').value.toLocaleLowerCase('es');
      const seleccion = r.tickets.filter(t => [t.ticket,t.fecha,t.retiro,t.residuo].join(' ').toLocaleLowerCase('es').includes(q));
      $('tickets-filas').innerHTML = seleccion.map(t => '<tr><td>'+t.fila+' / '+escapar(t.celda)+'</td><td>'+escapar(t.ticket)+
        '</td><td>'+escapar(t.fecha || 'Sin fecha')+'</td><td>'+escapar(t.retiro)+'</td><td>'+escapar(t.residuo)+
        '</td><td>'+numero(t.peso_kg,0)+'</td></tr>').join('') || '<tr><td colspan="6" class="vacio">Sin coincidencias.</td></tr>';
    }
    if (r.tickets.length) { $('buscar-ticket').addEventListener('input',tickets); tickets(); }
    $('detalle').showModal();
  }

  async function cargar() {
    if (cargando) return;
    cargando = true;
    $('actualizar').disabled = true;
    $('exportar').disabled = true;
    $('generar-pdf').disabled = true;
    $('actualizar').textContent = 'Leyendo fuentes…';
    $('estado').className = '';
    $('estado').textContent = 'Leyendo los Excel y conciliando los tickets…';
    try {
      const respuesta = await fetch('/api/conciliacion', {cache:'no-store'});
      const contenido = await respuesta.json();
      if (!respuesta.ok) throw new Error(contenido.error || 'No se pudieron leer las fuentes.');
      datos = contenido;
      prepararFiltros();
      $('estado').textContent = 'Última lectura: '+new Date(datos.actualizado).toLocaleString('es-CL')+' · '+datos.registros.length+' archivos EDP';
      $('avisos').hidden = !datos.avisos.length;
      $('avisos').innerHTML = datos.avisos.map(v=>'<p>'+escapar(v)+'</p>').join('');
      $('ruta-fuentes').textContent = 'Carpeta consultada: '+datos.fuentes;
      $('archivos-omitidos').textContent = datos.omitidos.length ? 'Informes generales fuera de la conciliación: '+datos.omitidos.join(', ')+'.' : '';
      if ($('detalle').open) $('detalle').close();
      renderizar();
    } catch (error) {
      $('estado').className = 'error';
      $('estado').textContent = (datos ? 'La actualización falló. Se conservan los resultados de la lectura anterior. ' : 'No se pudo cargar el panel. ') +
        (error.message === 'Failed to fetch' ? 'Comprueba que Iniciar_Panel está ejecutándose.' : error.message);
    } finally {
      cargando = false;
      $('actualizar').disabled = false;
      $('actualizar').textContent = 'Actualizar fuentes';
      $('exportar').disabled = !visibles.length;
      $('generar-pdf').disabled = !visibles.length || generandoPdf;
    }
  }


  async function generarPdf() {
    if (!datos || !visibles.length || cargando || generandoPdf) return;
    generandoPdf = true;
    $('generar-pdf').disabled = true;
    $('generar-pdf').textContent = 'Generando PDF…';
    $('pdf-estado').hidden = false;
    $('pdf-estado').className = '';
    $('pdf-estado').textContent = 'Preparando el reporte con los filtros seleccionados…';
    // Se envía la instantánea visible; nunca se releen los Excel al exportar.
    const campos = ['unidad','anio','mes_nombre','periodo','edp','estado','peso_kg','ton_tickets',
      'ton_edp','precio','monto_edp','monto_esperado','diferencia','avisos','errores'];
    const nombres = ['Unidad','Año','Mes','EDP','Conciliación'];
    const seleccion = Object.fromEntries(filtros.map((id,i) => [nombres[i], $(id).selectedOptions[0].textContent]));
    const instantanea = {
      actualizado: new Date(datos.actualizado).toLocaleString('es-CL'),
      filtros: seleccion, avisos: datos.avisos,
      registros: visibles.map(r => ({...Object.fromEntries(campos.map(k=>[k,r[k]])),numero_tickets:r.tickets.length}))
    };
    try {
      const respuesta = await fetch('/api/reporte.pdf', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(instantanea)
      });
      if (!respuesta.ok) {
        const error = await respuesta.json();
        throw new Error(error.error || 'No se pudo generar el PDF.');
      }
      const archivo = await respuesta.blob();
      const url = URL.createObjectURL(archivo);
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = 'reporte-codelco-' + new Date().toISOString().slice(0,10) + '.pdf';
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      setTimeout(()=>URL.revokeObjectURL(url),60000);
      $('pdf-estado').textContent = 'PDF generado con ' + instantanea.registros.length + ' EDP. Revisa las descargas del navegador.';
    } catch (error) {
      $('pdf-estado').className = 'error';
      $('pdf-estado').textContent = 'No se pudo generar el PDF. ' + error.message;
    } finally {
      generandoPdf = false;
      $('generar-pdf').disabled = !visibles.length || cargando;
      $('generar-pdf').textContent = 'Generar reporte PDF';
    }
  }

  function exportar() {
    const campos = [['unidad','Unidad'],['periodo','Período'],['edp','EDP'],['peso_kg','Peso kg'],
      ['ton_tickets','Toneladas tickets'],['ton_edp','Toneladas EDP'],['precio','Precio CLP/t'],
      ['monto_edp','Monto EDP CLP'],['monto_esperado','Esperado CLP'],['diferencia','Diferencia CLP'],
      ['estado','Estado'],['archivo','Archivo'],['errores','Errores'],['avisos','Observaciones']];
    const csv = valor => {
      let texto = Array.isArray(valor) ? valor.join(' / ') : typeof valor === 'number' ? String(valor).replace('.', ',') : String(valor ?? '');
      if (typeof valor !== 'number' && /^[=+\-@\t\r]/.test(texto)) texto = "'" + texto;
      return '"' + texto.replace(/"/g,'""') + '"';
    };
    const lineas = [campos.map(c=>csv(c[1])).join(';'),...visibles.map(r=>campos.map(c=>csv(r[c[0]])).join(';'))];
    const url = URL.createObjectURL(new Blob(['\uFEFF'+lineas.join('\r\n')], {type:'text/csv;charset=utf-8'}));
    const enlace = document.createElement('a');
    enlace.href = url; enlace.download = 'conciliacion-edp.csv'; enlace.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  filtros.forEach(id=>$(id).addEventListener('change',renderizar));
  $('limpiar').addEventListener('click',()=>{ filtros.forEach(id=>$(id).value=''); renderizar(); });
  $('actualizar').addEventListener('click',cargar);
  $('exportar').addEventListener('click',exportar);
  $('generar-pdf').addEventListener('click',generarPdf);
  $('filas').addEventListener('click',event=>{
    const boton = event.target.closest('[data-detalle]');
    if (boton) abrirDetalle(Number(boton.dataset.detalle));
  });
  $('cerrar-detalle').addEventListener('click',()=>$('detalle').close());
  cargar();
})();
