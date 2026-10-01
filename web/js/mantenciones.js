const MT_ESTADOS=['Mantención Vencida','Próxima a vencer','Mantención Vigente','STAND BY'];
const MT_COLORES=['rojo','amarillo','verde','neutro'];
const MT_CLASES=['mt-rojo','mt-amarillo','mt-verde','mt-gris'];
function estadoMt(e)
{
    return MT_ESTADOS.includes(e.calculo.estado)?e.calculo.estado:'STAND BY';
}
function conteoMt(equipos)
{
    const c={estados:[0,0,0,0],total:equipos.length,porcentaje:null};
    for(const e of equipos)
        c.estados[MT_ESTADOS.indexOf(estadoMt(e))]++;
    const base=c.total-c.estados[3];
    c.porcentaje=base?100*(base-c.estados[0])/base:null;
    return c;
}
function agruparMt(equipos)
{
    const mapa=new Map();
    for(const e of equipos){
        if(!mapa.has(e.region))mapa.set(e.region,new Map());
        const c=mapa.get(e.region);
        if(!c.has(e.ceco))c.set(e.ceco,[]);
        c.get(e.ceco).push(e);
    }
    return [...mapa].sort(([a],[b])=>a.localeCompare(b)).map(([region,cecos])=>({
        region,
        conteo:conteoMt([...cecos.values()].flat()),
        cecos:[...cecos].sort(([a],[b])=>a.localeCompare(b)).map(([ceco,equipos])=>({ceco,conteo:conteoMt(equipos)}))
    }));
}
function mesValidoMt(mes)
{
    return typeof mes==='string'&&/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)&&Number(mes.slice(0,4))>=1000;
}
function periodoMesMt(mes){
    if(!mesValidoMt(mes)||mes<'2026-08')throw new Error('Selecciona un mes desde agosto de 2026.');
    const [y,m]=mes.split('-').map(Number);
    return {inicio:mes==='2026-08'?'2026-08-04':mes+'-01',fecha:new Date(Date.UTC(y,m,0)).toISOString().slice(0,10)};
}
function eventosMesMt(equipos,mes,region='')
{
    if(!mesValidoMt(mes))return [];return equipos.filter(e=>e.calculo.fecha_proyectada?.slice(0,7)===mes&&(!region||e.region===region)).sort((a,b)=>a.region.localeCompare(b.region)||a.calculo.fecha_proyectada.localeCompare(b.calculo.fecha_proyectada)||a.patente.localeCompare(b.patente));
}
function celdasCalendarioMt(mes)
{
    if(!mesValidoMt(mes))return [];
    const [y,m]=mes.split('-').map(Number),
          inicio=new Date(Date.UTC(y,m-1,1)),
          dias=new Date(Date.UTC(y,m,0)).getUTCDate();
    const c=Array((inicio.getUTCDay()+6)%7).fill(null);
    for(let d=1;d<=dias;d++)c.push(`${mes}-${String(d).padStart(2,'0')}`);
    while(c.length%7)c.push(null);
    return c;
}
function csvMt(filas)
{
    return '\uFEFF'+filas.map(f=>f.map(v=>{let s=String(v??'');if(typeof v==='string'&&/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}).join(';')).join('\r\n');
}
if(typeof module!=='undefined')module.exports={MT_ESTADOS,estadoMt,conteoMt,agruparMt,eventosMesMt,celdasCalendarioMt,csvMt,periodoMesMt};

if(typeof document!=='undefined')
{
    const mt$=id=>document.getElementById(id);
    const mtEsCalendario=document.body.dataset.panel==='calendario';
    let mtDatos=null,mtIncluidos=[],mtMes=[],mtDia='',mtGrupos=[];
    let mtConsulta=0;
    const mtNumero=n=>Number.isFinite(n)?n.toLocaleString('es-CL',{maximumFractionDigits:1}):'—',mtFecha=s=>s?s.split('-').reverse().join('-'):'—';
    function mtCelda(tr,texto,tipo='td'){const td=document.createElement(tipo);td.textContent=texto;tr.append(td);return td;}
    function mtBadge(td,estado){const b=document.createElement('span');b.className='semaforo '+MT_COLORES[MT_ESTADOS.indexOf(estado)];b.textContent=estado;td.append(b);}
function mtConfiguracion(){if(mtDatos)PortalConfig.registrar(mtDatos.equipos.map(e=>e.region));}
window.addEventListener('portal-config',()=>mtActualizar());
function mtMetricas(tr,conteo){conteo.estados.forEach((v,i)=>{const td=mtCelda(tr,mtNumero(v));td.className=MT_CLASES[i];});mtCelda(tr,mtNumero(conteo.total));mtCelda(tr,conteo.porcentaje===null?'—':mtNumero(conteo.porcentaje)+' %');}
function mtResumen(){
 if(mtEsCalendario)return;
 mtGrupos=agruparMt(mtIncluidos);mt$('mt-detalle').replaceChildren();mt$('mt-totales').replaceChildren();mt$('mt-kpis').replaceChildren();const total=conteoMt(mtIncluidos);
 for(let i=0;i<MT_ESTADOS.length;i++){const k=document.createElement('div');k.className='kpi';const n=document.createElement('b'),t=document.createElement('span');n.textContent=mtNumero(total.estados[i]);t.textContent=MT_ESTADOS[i];k.append(n,t);mt$('mt-kpis').append(k);}
 for(const r of mtGrupos){const tr=document.createElement('tr');tr.className='region';mtCelda(tr,r.region);mtMetricas(tr,r.conteo);mt$('mt-detalle').append(tr);for(const c of r.cecos){const fila=document.createElement('tr');fila.className='mt-ceco';mtCelda(fila,c.ceco);mtMetricas(fila,c.conteo);mt$('mt-detalle').append(fila);}}
 if(!mtGrupos.length){const tr=document.createElement('tr');mtCelda(tr,'No hay patentes para los filtros y las regiones incluidas.').colSpan=7;mt$('mt-detalle').append(tr);}
 const general=document.createElement('tr');mtCelda(general,'Total general');mtMetricas(general,total);mt$('mt-totales').append(general);
 mt$('mt-patentes').replaceChildren();for(const e of mtIncluidos){const tr=document.createElement('tr');[e.patente,e.region,e.ceco].forEach(v=>mtCelda(tr,v));mtBadge(mtCelda(tr,''),estadoMt(e));[e.estado_equipo||'Sin estado reportado',mtFecha(e.fecha_estado_equipo),e.calculo.motivo||'—'].forEach(v=>mtCelda(tr,v));mt$('mt-patentes').append(tr);}
}
function mtActualizar(){if(!mtDatos)return;mtIncluidos=mtDatos.equipos.filter(e=>PortalConfig.incluida(e.region));const regiones=[...new Set(mtIncluidos.map(e=>e.region))].sort();if(mtEsCalendario){const previa=mt$('mt-region-cal').value;mt$('mt-region-cal').replaceChildren(new Option('Todas las regiones incluidas',''));regiones.forEach(r=>mt$('mt-region-cal').add(new Option(r,r)));if(regiones.includes(previa))mt$('mt-region-cal').value=previa;}
 if(!mtEsCalendario){
  const selectorRegion=mt$('mt-region-resumen'),selectorCeco=mt$('mt-ceco-resumen');
  const regionPrevia=selectorRegion.value,cecoPrevio=selectorCeco.value;
  selectorRegion.replaceChildren(new Option('Todas las regiones incluidas',''));
  regiones.forEach(r=>selectorRegion.add(new Option(r,r)));
  selectorRegion.value=regiones.includes(regionPrevia)?regionPrevia:'';
  mtIncluidos=mtIncluidos.filter(e=>!selectorRegion.value||e.region===selectorRegion.value);
  const cecos=[...new Set(mtIncluidos.map(e=>e.ceco))].sort();
  selectorCeco.replaceChildren(new Option('Todos los CeCo',''));
  cecos.forEach(c=>selectorCeco.add(new Option(c,c)));
  selectorCeco.value=cecos.includes(cecoPrevio)?cecoPrevio:'';
  mtIncluidos=mtIncluidos.filter(e=>!selectorCeco.value||e.ceco===selectorCeco.value);
 }
 mt$('mt-alcance').textContent=`${new Set(mtIncluidos.map(e=>e.region)).size} regiones y ${mtIncluidos.length} patentes incluidas. ${mtEsCalendario?'':`Mes de lecturas: ${mtDatos.fecha.slice(0,7)}. `}Lecturas disponibles: ${mtFecha(mtDatos.inicio)} a ${mtFecha(mtDatos.semanas.at(-1).fecha)}. La última mantención y el estado operativo corresponden al estado actual del Excel.`;
 mtResumen();mtDia='';mtCalendario();}
function mtCalendario(){
 if(!mtDatos||!mtEsCalendario)return;const mes=mt$('mt-mes').value,region=mt$('mt-region-cal').value;mtMes=eventosMesMt(mtIncluidos,mes,region);const grid=mt$('mt-cal-grid');grid.replaceChildren();mt$('mt-exportar-informe').disabled=!region||!mesValidoMt(mes);mt$('mt-informe-nota').textContent=region?`La descarga incluye el calendario completo y la tabla de patentes de ${region} para ${mes}.`:'Elige una región para descargar su calendario mensual junto con la tabla de patentes.';
 if(!mesValidoMt(mes)){mt$('mt-cal-nota').textContent='Selecciona un mes válido.';mtMes=[];mtDia='';mtAgenda();mt$('mt-exportar-calendario').disabled=true;return;}
 mt$('mt-exportar-calendario').disabled=false;const candidatos=mtIncluidos.filter(e=>!region||e.region===region),sinFecha=candidatos.filter(e=>!e.calculo.fecha_proyectada).length;
 mt$('mt-cal-nota').textContent=`${mtMes.length} patentes con mantención proyectada en ${mes}. ${sinFecha} patentes de las regiones elegidas no tienen fecha proyectada y quedan fuera del calendario. Cambiar el mes no cambia el período de lecturas utilizado.`;
 for(const dia of ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']){const n=document.createElement('div');n.className='mt-cal-nombre';n.textContent=dia;grid.append(n);}
 const hoy=new Date(),hoyTexto=`${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}-${String(hoy.getDate()).padStart(2,'0')}`;
 for(const fecha of celdasCalendarioMt(mes)){if(!fecha){const vacio=document.createElement('div');vacio.className='mt-cal-vacio';vacio.setAttribute('aria-hidden','true');grid.append(vacio);continue;}const eventos=mtMes.filter(e=>e.calculo.fecha_proyectada===fecha),boton=document.createElement('button');boton.type='button';boton.className='mt-cal-dia'+(eventos.length?' programado':'')+(fecha===hoyTexto?' hoy':'');boton.disabled=!eventos.length;boton.setAttribute('aria-pressed',String(mtDia===fecha));boton.setAttribute('aria-label',`${mtFecha(fecha)}: ${eventos.length} ${eventos.length===1?'mantención preventiva proyectada':'mantenciones preventivas proyectadas'}`);const numero=document.createElement('b');numero.textContent=Number(fecha.slice(-2));boton.append(numero);if(eventos.length){const cuenta=document.createElement('small');cuenta.textContent=`${eventos.length} ${eventos.length===1?'mantención preventiva':'mantenciones preventivas'}`;const ejemplos=document.createElement('small');ejemplos.className='mt-ejemplos';ejemplos.textContent=eventos.slice(0,2).map(e=>e.patente).join(' · ')+(eventos.length>2?'…':'');boton.append(cuenta,ejemplos);boton.onclick=()=>{mtDia=mtDia===fecha?'':fecha;mtCalendario();};}grid.append(boton);}
 mtAgenda();
}
function mtAgenda(){mt$('mt-agenda').replaceChildren();const eventos=mtMes.filter(e=>!mtDia||e.calculo.fecha_proyectada===mtDia);mt$('mt-todo-mes').hidden=!mtDia;mt$('mt-dia-titulo').textContent=mtDia?`Detalle del ${mtFecha(mtDia)} · ${eventos.length} patentes`:`Agenda del mes · ${eventos.length} patentes`;
 let region=null;for(const e of eventos){if(e.region!==region){region=e.region;const r=document.createElement('tr');r.className='region';mtCelda(r,region).colSpan=6;mt$('mt-agenda').append(r);}const tr=document.createElement('tr');[e.patente,e.ceco,e.unidad||'—',mtFecha(e.calculo.fecha_proyectada),mtNumero(e.calculo.proxima)].forEach(v=>mtCelda(tr,v));mtBadge(mtCelda(tr,''),estadoMt(e));mt$('mt-agenda').append(tr);}
 if(!eventos.length){const tr=document.createElement('tr');mtCelda(tr,'No hay mantenciones proyectadas para el mes y las regiones seleccionadas.').colSpan=6;mt$('mt-agenda').append(tr);}}
function descargarMt(filas,nombre){const url=URL.createObjectURL(new Blob([csvMt(filas)],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=nombre;a.click();URL.revokeObjectURL(url);}
if(mtEsCalendario)mt$('mt-exportar-informe').onclick=()=>{const region=mt$('mt-region-cal').value,mes=mt$('mt-mes').value;if(!mtDatos||!region||!mesValidoMt(mes))return;const html=informeCalendarioMt(mtIncluidos,mes,region,mtDatos.inicio,mtDatos.semanas.at(-1).fecha);const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`Calendario_y_Patentes_${region.replace(/[^\p{L}\p{N}_-]/gu,'_')}_${mes}.html`;a.click();URL.revokeObjectURL(url);};
if(!mtEsCalendario)mt$('mt-exportar-resumen').onclick=()=>{if(!mtDatos)return;const filas=[['Tipo','Región','CeCo',...MT_ESTADOS,'Total general','% no vencidas','Fecha referencia']];const agregar=(tipo,region,ceco,c)=>filas.push([tipo,region,ceco,...c.estados,c.total,c.porcentaje,mtDatos.fecha]);for(const r of mtGrupos){agregar('Subtotal región',r.region,'',r.conteo);for(const c of r.cecos)agregar('CeCo',r.region,c.ceco,c.conteo);}agregar('Total general','','',conteoMt(mtIncluidos));descargarMt(filas,`Reporte_Mantencion_${mtDatos.fecha}.csv`);};
if(mtEsCalendario)mt$('mt-exportar-calendario').onclick=()=>{if(!mtDatos)return;const filas=[['Fecha proyectada','Patente','Región','CeCo','Unidad','Próxima mantención','Estado','Fecha de última lectura']];mtMes.forEach(e=>filas.push([e.calculo.fecha_proyectada,e.patente,e.region,e.ceco,e.unidad,e.calculo.proxima,estadoMt(e),e.calculo.fecha_lectura]));descargarMt(filas,`Calendario_Mantenciones_${mt$('mt-mes').value}.csv`);};

if(mtEsCalendario){mt$('mt-mes').onchange=mt$('mt-region-cal').onchange=()=>{mtDia='';mtCalendario();};mt$('mt-todo-mes').onclick=()=>{mtDia='';mtCalendario();};}
if(!mtEsCalendario){mt$('mt-region-resumen').onchange=()=>{mt$('mt-ceco-resumen').value='';mtActualizar();};mt$('mt-ceco-resumen').onchange=mtActualizar;mt$('mt-mes-resumen').onchange=consultarMt;}
function cambiarMesMt(delta){const mes=mt$('mt-mes').value;if(!mesValidoMt(mes))return;const [y,m]=mes.split('-').map(Number),d=new Date(Date.UTC(y,m-1+delta,1));mt$('mt-mes').value=d.toISOString().slice(0,7);mtDia='';mtCalendario();}
if(mtEsCalendario){mt$('mt-mes-anterior').onclick=()=>cambiarMesMt(-1);mt$('mt-mes-siguiente').onclick=()=>cambiarMesMt(1);}
async function consultarMt(event){event?.preventDefault();const consulta=++mtConsulta;mtDatos=null;mtIncluidos=[];mtMes=[];mtDia='';mt$('mt-consultar').disabled=true;for(const id of ['mt-exportar-resumen','mt-exportar-calendario','mt-exportar-informe'])if(mt$(id))mt$(id).disabled=true;for(const id of ['mt-detalle','mt-totales','mt-kpis','mt-patentes','mt-cal-grid','mt-agenda'])mt$(id)?.replaceChildren();for(const id of ['mt-alcance','mt-cal-nota','mt-dia-titulo','mt-informe-nota'])if(mt$(id))mt$(id).textContent='';mtConfiguracion();mt$('mt-mensaje').textContent='Consultando estados de mantención y fechas proyectadas…';
 try{if(location.protocol==='file:')throw new Error('Abre el portal desde http://127.0.0.1:8765.');const periodo=mtEsCalendario?{inicio:mt$('mt-inicio').value,fecha:mt$('mt-fecha').value}:periodoMesMt(mt$('mt-mes-resumen').value);const q=new URLSearchParams(periodo),r=await fetch('/api/mantenciones?'+q,{cache:'no-store'});if(r.status===404)throw new Error('Reinicia Iniciar_Panel.bat para habilitar las nuevas vistas.');const datos=await r.json();if(consulta!==mtConsulta)return;if(!r.ok)throw new Error(datos.error||'No se pudo leer el Excel.');if(datos.version!==2||!datos.incluye_estado_equipo)throw new Error('El servidor usa una versión anterior. Reinicia Iniciar_Panel.bat.');mtDatos=datos;mtConfiguracion();mtActualizar();if(!mtEsCalendario)mt$('mt-exportar-resumen').disabled=false;mt$('mt-mensaje').textContent='Consulta completada. '+datos.advertencias.join(' ');
 }catch(error){if(consulta===mtConsulta)mt$('mt-mensaje').textContent=error.message;}finally{if(consulta===mtConsulta)mt$('mt-consultar').disabled=false;}}
const hoyMt=new Date(),fechaHoyMt=`${hoyMt.getFullYear()}-${String(hoyMt.getMonth()+1).padStart(2,'0')}-${String(hoyMt.getDate()).padStart(2,'0')}`;if(mtEsCalendario){mt$('mt-fecha').value=fechaHoyMt;mt$('mt-mes').value=fechaHoyMt.slice(0,7);}else mt$('mt-mes-resumen').value=fechaHoyMt.slice(0,7);mt$('mt-form').onsubmit=consultarMt;consultarMt();
}

