/* Reportes A4 locales: Helvetica, colores, tablas y gráficos vectoriales del panel. */
(() => {
  'use strict';
  const NAVY = '#073762', BLUE = '#0E81C5', GREEN = '#2E9E6B', GRAY = '#5B6B7C', PALE = '#F4F6F9', LINE = '#DDE4EC';
  const estados = {coincide:['Transacción es Consistente con las tolvas en Faena',GREEN],no_coincide_menor:['Transacción No óptima con las tolvas en Faena','#997000'],no_coincide_mayor:['Transacción No es Consistente con las tolvas en Faena','#a12424'],sin_evaluar:['Sin evaluar',GRAY]};
  const tramos = [['menor_10','Menor a 10 m³',BLUE],['10_20','10 a menos de 20 m³',GREEN],['20_30','20 a 30 m³','#997000'],['mayor_30','Mayor a 30 m³','#a12424'],['sin_volumen','Sin volumen calculable',GRAY]];
  const tramo = t => t.volumen_m3 == null || !Number.isFinite(t.volumen_m3) || t.volumen_m3 < 0 ? 'sin_volumen' : t.volumen_m3 < 10 ? 'menor_10' : t.volumen_m3 < 20 ? '10_20' : t.volumen_m3 <= 30 ? '20_30' : 'mayor_30';
  const numero = (v, dec = 2) => v == null ? '-' : new Intl.NumberFormat('es-CL',{minimumFractionDigits:dec, maximumFractionDigits:dec}).format(v);
  const texto = v => String(v ?? '').replace(/[\u2010-\u2015]/g,'-').replace(/\u2192/g,'->').replace(/\u2264/g,'<=').replace(/\u2265/g,'>=').replace(/\u2212/g,'-');
  const color = c => PDFLib.rgb(...c.match(/[\da-f]{2}/gi).map(n => parseInt(n,16)/255));

  async function documento(titulo, logos = false, top = 48) {
    const pdf = await PDFLib.PDFDocument.create();
    pdf.setTitle(titulo); pdf.setAuthor('Resiter Minería');
    const regular = await pdf.embedFont(PDFLib.StandardFonts.Helvetica), bold = await pdf.embedFont(PDFLib.StandardFonts.HelveticaBold);
    const imagenes = logos ? await Promise.all(['logo_sin_fondo_resiter.png','logo_sin_fondo_codelco.png'].map(n => pdf.embedPng(window.PanelPublicado.imagenes[n]))) : [];
    const W = 841.8898, H = 595.2756, margen = 24, ancho = W-margen*2;
    let pagina, y, indice = 0;
    // WinAnsi permite tildes, ñ, m³ y símbolos usados por los reportes actuales.
    const limpiar = v => [...texto(v)].map(c => {if(c === '\n') return c; try {regular.encodeText(c); return c;} catch {return '?';}}).join('');
    const t = (s,x,arriba,size=8,c=GRAY,b=false) => pagina.drawText(limpiar(s),{x,y:H-arriba-size,font:b?bold:regular,size,color:color(c)});
    const rect = (x,arriba,w,h,c) => pagina.drawRectangle({x,y:H-arriba-h,width:w,height:h,color:color(c)});
    const linea = (x,a,x2,b,c=LINE) => pagina.drawLine({start:{x,y:H-a},end:{x:x2,y:H-b},color:color(c),thickness:.4});
    const nueva = () => {
      pagina = pdf.addPage([W,H]); indice++; y=top;
      if (logos) {
        for (const [i,img] of imagenes.entries()) {const caja=i ? [82,32] : [42,32];const escala=Math.min(caja[0]/img.width,caja[1]/img.height);pagina.drawImage(img,{x:i?W-105:23,y:H-40,width:img.width*escala,height:img.height*escala});}
        t('Reporte Codelco',W-190,19,9,NAVY);
      } else t('Resiter Minería / Reporte Codelco',24,16,9,NAVY,true);
      t(titulo,24,H-22,7); t('Página '+indice,W-70,H-22,7);
    };
    nueva();
    const espacio = h => {if(y+h>H-32)nueva();};
    const envolver = (s,w,size=8,b=false) => {
      const font=b?bold:regular, filas=[];
      for(const parrafo of limpiar(s).split('\n')) {
        let fila='';
        for (const palabra of parrafo.split(/\s+/)) {
          if(!palabra)continue;
          if (font.widthOfTextAtSize((fila?fila+' ':'')+palabra,size) <= w) {fila+=(fila?' ':'')+palabra;continue;}
          if(fila){filas.push(fila);fila='';}
          let fragmento='';
          for(const c of palabra){if(font.widthOfTextAtSize(fragmento+c,size)>w&&fragmento){filas.push(fragmento);fragmento='';} fragmento+=c;}
          fila=fragmento;
        }
        filas.push(fila);
      }
      return filas;
    };
    const par = (s,size=8,c=GRAY,b=false) => {
      const filas=envolver(s,ancho,size,b);
      for(const fila of filas){espacio(size*1.3);t(fila,margen,y,size,c,b);y+=size*1.3;}
      y+=4;
    };
    const seccion = s => {espacio(100);par(s,11,NAVY,true);};
    const tabla = (cabeceras,filas,pesos,colores=null,size=7) => {
      const total=pesos.reduce((s,v)=>s+v,0), anchuras=pesos.map(v=>ancho*v/total);
      const preparar = fila => fila.map((c,i)=>envolver(c,anchuras[i]-10,size));
      const cab = preparar(cabeceras), altoCab=Math.max(...cab.map(c=>c.length))*size*1.3+10;
      const dibujar=(fila,alto,fondo,esCab,offset=0,cantidad=Infinity,indiceFila=0)=>{
        rect(margen,y,ancho,alto,fondo);let x=margen;
        fila.forEach((lineas,i)=>{lineas.slice(offset,offset+cantidad).forEach((s,j)=>t(s,x+5,y+5+j*size*1.3,size,esCab?'#FFFFFF':colores?.(indiceFila,i)||NAVY,esCab));x+=anchuras[i];});
        linea(margen,y+alto,W-margen,y+alto);y+=alto;
      };
      espacio(altoCab+24);dibujar(cab,altoCab,NAVY,true);
      filas.forEach((fila,i)=>{
        const lineas=preparar(fila), cuenta=Math.max(1,...lineas.map(c=>c.length));
        const alto=cuenta*size*1.3+10;
        if(y+alto>H-32&&alto<H-32-top-altoCab){nueva();dibujar(cab,altoCab,NAVY,true);}
        let offset=0;
        while(offset<cuenta){
          let capacidad=Math.floor((H-32-y-10)/(size*1.3));
          if(capacidad<1){nueva();dibujar(cab,altoCab,NAVY,true);capacidad=Math.floor((H-32-y-10)/(size*1.3));}
          const cantidad=Math.min(capacidad,cuenta-offset);
          dibujar(lineas,cantidad*size*1.3+10,i%2?PALE:'#FFFFFF',false,offset,cantidad,i);offset+=cantidad;
        }
      });y+=7;
    };
    const kpis = lista => {
      const w=ancho/lista.length, alto=68;
      espacio(alto);rect(margen,y,ancho,alto,PALE);
      lista.forEach(([a,b,c],i)=>{let yy=y+7;for(const s of envolver(a,w-20,7)){t(s,margen+i*w+10,yy,7);yy+=9;}t(b,margen+i*w+10,yy+4,14,NAVY,true);for(const [j,s] of envolver(c||'',w-20,7).entries())t(s,margen+i*w+10,yy+26+j*9,7);});y+=alto+8;
    };
    const barras=(titulo,lista,x,w,arriba,h=140,apiladas=false)=>{
      t(titulo,x,arriba,10,NAVY,true);
      const max=Math.max(1,...lista.map(r=>Math.abs(r[1]))), paso=(h-24)/Math.max(1,lista.length);
      lista.forEach(([nombre,n,c,etiqueta],i)=>{
        const base=arriba+24+i*paso;
        if(apiladas){
          t(nombre,x,base,7);rect(x,base+14,w-60,8,PALE);rect(x,base+14,(w-60)*Math.abs(n)/max,8,c);t(etiqueta??String(n),x+w-45,base+12,7,NAVY);
        }else{
          t(nombre,x,base,7);rect(x+130,base+1,Math.max(10,w-230),8,PALE);rect(x+130,base+1,Math.max(10,w-230)*Math.abs(n)/max,8,c);
          t(etiqueta??String(n),x+w-90,base,7,NAVY);
        }
      });
    };
    const dispersion=(tickets,capacidades,distribucion=false)=>{
      espacio(156);t(distribucion?'Volumen calculado por ticket':'Volumen calculado por ticket y ventanas permitidas',margen,y,10,NAVY,true);
      const validos=tickets.filter(t=>t.volumen_m3!=null&&Number.isFinite(t.volumen_m3)&&t.volumen_m3>=0);
      if(!validos.length){t('Sin volúmenes calculables en esta selección.',margen,y+42,9);y+=156;return;}
      const max=Math.max(distribucion?36:Math.max(...capacidades)+6,...validos.map(t=>t.volumen_m3*1.03));
      const base=y+128, sy=v=>base-90*v/max,x=margen+48,w=ancho-64;
      for(const v of distribucion?[10,20,30]:capacidades){if(!distribucion)rect(x,sy(v+3),w,90*6/max,'#E4F4EC');linea(x,sy(v),x+w,sy(v),distribucion?LINE:GREEN);t(v+' m³',margen+4,sy(v)-5,7);}
      linea(x,base,x+w,base);
      validos.forEach((ticket,i)=>pagina.drawCircle({x:x+w*(i+.5)/validos.length,y:H-sy(ticket.volumen_m3),size:1.7,color:color(distribucion?tramos.find(g=>g[0]===tramo(ticket))[2]:estados[ticket.estado][1])}));
      t(`${validos.length} tickets en orden de período y fila. Escala: 0 a ${numero(max,1)} m³.`,x,y+140,7);y+=160;
    };
    return {pdf,par,seccion,tabla,kpis,nueva,espacio,barras,dispersion,t,rect,linea,ancho,margen,get y(){return y;},set y(v){y=v;},guardar:()=>pdf.save()};
  }

  async function conciliacion(datos) {
    const registros=datos.registros, validos=registros.filter(r=>r.estado!=='incompleto');
    if(!registros.length)throw new Error('Selecciona al menos un EDP.');
    const d=await documento('Estados de pago y toneladas',true,65);
    d.par('Estados de pago y toneladas',18,NAVY,true);
    d.par('Andina: ítem 1.1 - Retiro de residuos industriales no peligrosos. El Salvador: ítem 2.5.a - CMRIS.');
    d.par(Object.entries(datos.filtros||{}).map(([k,v])=>k+': '+v).join(' / ')||'Todos los EDP',8,NAVY);
    d.par('Monto esperado = precio por tonelada × toneladas de tickets.',8,NAVY);
    d.par('Andina: Cantidad (t) de hoja 1.1 y Precio de Avance físico. El Salvador: Peso Total (kg) ÷ 1.000 y Precio Modificación N.º 1.',7);
    const suma=k=>validos.length?validos.reduce((s,r)=>s+(r[k]||0),0):null;
    d.kpis([['EDP revisados',String(registros.length),`${registros.filter(r=>r.estado==='cuadra').length} cuadran / ${registros.filter(r=>r.estado==='diferencia').length} con diferencia`],['Toneladas según tickets',numero(suma('ton_tickets'),3),`${suma('numero_tickets')||0} filas de tickets`],['Monto esperado (CLP)','$ '+numero(suma('monto_esperado')),'Precio por tonelada × toneladas'],['Diferencia neta (CLP)','$ '+numero(suma('diferencia')),'EDP menos monto esperado']]);
    d.par(`Totales de ${validos.length} de ${registros.length} EDP. Los EDP sin conciliar se excluyen de los totales.`,7);
    for(const aviso of datos.avisos||[])d.par(aviso,7,'#795000');
    for(let i=0;i<validos.length;i+=8){
      const grupo=validos.slice(i,i+8),h=55+grupo.length*26;d.espacio(h);
      for(const [j,a,b,titulo,dinero] of [[0,'ton_edp','ton_tickets','Toneladas por EDP',false],[1,'monto_edp','monto_esperado','Monto por EDP (CLP)',true]]){
        const x=d.margen+j*d.ancho/2,w=d.ancho/2-10,arriba=d.y,max=Math.max(1,...grupo.flatMap(r=>[Math.abs(r[a]),Math.abs(r[b])]));
        d.t(titulo,x+10,arriba,10,NAVY,true);
        d.t(dinero?'EDP: monto declarado en el estado de pago.':'EDP: toneladas declaradas en el estado de pago.',x+10,arriba+17,7,BLUE);
        d.t(dinero?'Esperado: precio por tonelada × toneladas de tickets.':'Tickets: suma de toneladas de los tickets incluidos.',x+10,arriba+29,7,GREEN);
        grupo.forEach((r,k)=>{const yy=arriba+49+k*26;d.t(`${r.mes_nombre||r.periodo||'-'} ${r.anio||''}`,x+10,yy,7,NAVY,true);d.t(`${r.unidad} / EDP ${r.edp}`,x+10,yy+10,6.5);for(const [z,campo]of[a,b].entries()){const largo=w-209;d.rect(x+112,yy+z*10,largo,6,PALE);d.rect(x+112,yy+z*10,largo*Math.abs(r[campo])/max,6,z?GREEN:BLUE);d.t((dinero?'$ ':'')+numero(r[campo],dinero?2:3)+(dinero?'':' t'),x+w-93,yy+z*10-1,7,NAVY);}});
      }d.y+=h+6;
    }
    if(!validos.length)d.par('Sin EDP conciliables para los gráficos.',9);
    d.seccion('Detalle de conciliación');
    const nombres={cuadra:'Cuadra',diferencia:'Con diferencia',incompleto:'Sin conciliar'};
    d.tabla(['Unidad / período / ítem','EDP','Tickets','Peso total kg','Tickets t','EDP t','Precio CLP/t','Monto EDP CLP','Esperado CLP','Diferencia CLP','Estado'],registros.map(r=>[`${r.unidad||'-'} / ${r.periodo||'-'} / ${r.item||(r.unidad==='Andina'?'1.1':'2.5.a')}`,r.edp??'-',numero(r.numero_tickets,0),...['peso_kg','ton_tickets','ton_edp','precio','monto_edp','monto_esperado','diferencia'].map(k=>numero(r[k],k==='peso_kg'?0:['ton_tickets','ton_edp'].includes(k)?3:2)),nombres[r.estado]+(r.avisos?.length?' *':'')]),[96,29,36,57,56,56,65,85,85,70,65],(i,c)=>c===10?(registros[i].estado==='cuadra'?GREEN:'#a12424'):NAVY);
    d.par('Diferencia positiva: el EDP supera el monto esperado. Importes comparados a 2 decimales; tolerancia: 0,000001 t. Sin acumulados ni reajustes.',7);
    const notas=new Map();for(const r of registros)for(const nota of [...r.errores||[],...r.avisos||[]]){const lista=notas.get(nota)||[];lista.push(`${r.unidad||'-'} EDP ${r.edp??'-'}`);notas.set(nota,lista);}
    if(notas.size){d.seccion('* Observaciones de los EDP seleccionados');for(const [nota,edps]of notas)d.par(edps.join(', ')+': '+nota,7);}
    return d.guardar();
  }

  async function densidades(datos,distribucion=false) {
    const tickets=datos.tickets;if(!tickets.length)throw new Error('No hay tickets en esta selección para generar el PDF.');
    const titulo=(distribucion?'Distribución de volumen - ':'Chequeo de densidades - ')+datos.unidad;
    const d=await documento(titulo,false,distribucion?44:48);
    d.par(titulo,17,NAVY,true);
    d.par('Selección: '+(Object.entries(datos.filtros||{}).map(([k,v])=>k+': '+(k==='tramo_volumen'?tramos.find(t=>t[0]===v)?.[1]||v:v)).join(' / ')||'Todos los tickets'));
    d.par(distribucion?'Volumen (m³) = peso del ticket (kg) / promedio de densidades inferior y superior (kg/m³). Tramos sin redondear: menor a 10; desde 10 y menor a 20; desde 20 hasta 30 inclusive; mayor a 30 m³. Los porcentajes incluyen todos los tickets seleccionados, también los que no tienen volumen calculable.':datos.regla);
    d.par('Maestra: '+(datos.maestra.archivo||'No disponible')+(distribucion?'':' / Densidad utilizada: promedio de ambas densidades.'));
    if(distribucion){
      const grupos=tramos.map(([id,nombre,c])=>{const lista=tickets.filter(t=>tramo(t)===id);return{id,nombre,c,cantidad:lista.length,porcentaje:lista.length/tickets.length*100,volumen:id==='sin_volumen'?null:lista.reduce((s,t)=>s+t.volumen_m3,0)};});
      d.par(`Tickets: ${tickets.length} / Con volumen calculable: ${grupos.slice(0,4).reduce((s,g)=>s+g.cantidad,0)} / Volumen total: ${numero(grupos.reduce((s,g)=>s+(g.volumen||0),0))} m³`,10,NAVY,true);
      d.tabla(['Tramo de volumen','Tickets','Porcentaje','Volumen acumulado m³'],grupos.map(g=>[g.nombre,g.cantidad,numero(g.porcentaje,1)+'%',numero(g.volumen)]),[40,15,20,25],(i,c)=>c===0?grupos[i].c:NAVY,8);
      d.espacio(153);d.barras('Distribución de tickets por tramo',grupos.map(g=>[g.nombre,g.cantidad,g.c,`${g.cantidad} / ${numero(g.porcentaje,1)}%`]),24,d.ancho/2-12,d.y,153);d.barras('Volumen acumulado por tramo',grupos.slice(0,4).map(g=>[g.nombre,g.volumen,g.c,numero(g.volumen)+' m³']),24+d.ancho/2,d.ancho/2-12,d.y,153);d.y+=157;
    } else {
      const conteo=k=>tickets.filter(t=>t.estado===k).length;
      d.kpis([['Tickets',String(tickets.length),''],...Object.entries(estados).map(([k,[s]])=>[s,String(conteo(k)),''])]);
      d.espacio(142);d.barras('Resultados del chequeo',Object.entries(estados).map(([k,[s,c]])=>[s,conteo(k),c]),24,d.ancho/2-12,d.y,142,true);d.barras('Capacidad asignada a tickets verdes',datos.volumenes.map(v=>[v+' m³ (±3 m³)',tickets.filter(t=>t.volumen_tipo===v&&t.estado==='coincide').length,BLUE]),24+d.ancho/2,d.ancho/2-12,d.y);d.y+=146;
    }
    d.dispersion(tickets,datos.volumenes,distribucion);
    for(const aviso of datos.avisos||[])d.par(aviso,7,'#997000');
    for(const criterio of [...new Set(tickets.filter(t=>t.residuo_es_estimado).map(t=>t.criterio_estimacion_residuo))].sort())d.par('Estimación de residuo y densidad: '+criterio,7);
    if(distribucion)d.nueva();d.seccion('Detalle de tickets');
    if(distribucion){
      d.tabla(['Unidad / período / EDP / fila','Ticket / fecha','Residuo / retiro','Peso kg','Densidad kg/m³','Volumen m³','Tramo de volumen','Origen'],tickets.map(t=>{let material=(t.residuo||'Sin residuo')+' / '+(t.retiro||'');if(t.residuo_original!==t.residuo)material+=' / Original: '+(t.residuo_original||'(sin tipo declarado)');if(t.residuo_es_estimado)material+=' / Tipo y densidad estimados';const ref=t.referencia_maestra;const origen=`${t.archivo||''} / ${t.hoja_ticket||''}!${t.celda||''}`+(ref?` / AUX: ${ref.hoja}!${ref.celda_inferior} / ${ref.celda_superior}`:'');return[`${t.unidad} / ${t.periodo} / EDP ${t.edp} / fila ${t.fila}`,`${t.ticket??'(sin ID)'} / ${t.fecha||'(sin fecha)'}`,material,numero(t.peso_kg),numero(t.densidad_kg_m3),numero(t.volumen_m3,3),tramos.find(g=>g[0]===tramo(t))[1]+(tramo(t)==='sin_volumen'?' / '+(t.motivo||''):''),origen];}),[95,80,130,60,60,60,110,d.ancho-595],(i,c)=>c===6?tramos.find(g=>g[0]===tramo(tickets[i]))[2]:NAVY);
      d.par('La descarga incluye toda la selección filtrada, aunque el panel muestre el detalle por páginas. Se conservan los tickets repetidos y el número 0.',7);
    } else {
      d.tabla(['Unidad / período / EDP / fila','Ticket / fecha','Residuo / producto','Peso kg','Dens. media kg/m³','Volumen m³','Capacidad m³','Delta m³','Resultado / motivo','Comentario'],tickets.map(t=>[`${t.unidad} / ${t.periodo} / EDP ${t.edp} / fila ${t.fila}`,`${t.ticket||'(sin ID)'} / ${t.fecha||'(sin fecha)'}`,t.residuo+(t.residuo_original!==t.residuo?'\nOriginal: '+(t.residuo_original||'(vacío)'):'')+(t.residuo_es_estimado?'\nTipo estimado':''),numero(t.peso_kg),numero(t.densidad_kg_m3)+(t.residuo_es_estimado?'\nSegún material estimado':''),numero(t.volumen_m3,3),numero(t.volumen_tipo,0),numero(t.diferencia_m3,3),estados[t.estado][0]+'. '+t.motivo,(t.comentario||'Sin comentario')+(t.comentario_autor?'\n'+t.comentario_autor+' / '+t.comentario_actualizado:'')]),[80,65,80,45,50,50,45,45,120,d.ancho-580],(i,c)=>c===8?estados[tickets[i].estado][1]:NAVY);
      d.par('Delta = volumen calculado menos capacidad más cercana. Los tickets sin evaluar no se incluyen en los gráficos de volumen. Se conservan filas repetidas y tickets 0.',7);
      d.seccion('Maestra de densidades utilizada (kg/m³)');d.tabla(['Material','Inferior','Superior','Promedio','Origen / observación'],datos.maestra.materiales.map(m=>[m.material,numero(m.inferior_kg_m3),numero(m.superior_kg_m3),numero(m.densidad_kg_m3),`${m.hoja}!${m.celda_inferior} / ${m.celda_superior} ${m.error||''}`]),[190,85,85,85,d.ancho-445],null,8);
    }
    return d.guardar();
  }
  window.PanelPDF = {conciliacion,densidades};
})();
