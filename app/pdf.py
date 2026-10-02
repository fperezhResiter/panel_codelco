"""PDF descargable de la instantánea filtrada del panel, sin releer las fuentes."""
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from math import isfinite
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.lib.utils import ImageReader

NAVY = colors.HexColor('#073762')
BLUE = colors.HexColor('#0E81C5')
GREEN = colors.HexColor('#2E9E6B')
GRAY = colors.HexColor('#5B6B7C')
LINE = colors.HexColor('#DDE4EC')
PALE = colors.HexColor('#F4F6F9')
ESTADOS = {'cuadra': 'Cuadra', 'diferencia': 'Con diferencia', 'incompleto': 'Sin conciliar'}
CAMPOS_NUMERICOS = ('peso_kg', 'ton_tickets', 'ton_edp', 'precio', 'monto_edp',
                    'monto_esperado', 'diferencia', 'numero_tickets')
ANCHO = landscape(A4)[0] - 60


def validar(datos):
    if not isinstance(datos, dict):
        raise ValueError('El reporte debe ser un objeto JSON.')
    registros = datos.get('registros')
    if not isinstance(registros, list) or not 1 <= len(registros) <= 1000:
        raise ValueError('Selecciona entre 1 y 1.000 EDP para generar el PDF.')
    for r in registros:
        if not isinstance(r, dict) or r.get('estado') not in ESTADOS:
            raise ValueError('Estado de conciliación inválido.')
        for k in CAMPOS_NUMERICOS:
            v = r.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)):
                raise ValueError(f'Valor numérico inválido: {k}.')
        if r['estado'] != 'incompleto' and any(r.get(k) is None for k in CAMPOS_NUMERICOS):
            raise ValueError('Faltan cifras de un EDP conciliado.')
        for k in ('avisos', 'errores'):
            if not isinstance(r.get(k, []), list) or any(not isinstance(x, str) for x in r.get(k, [])):
                raise ValueError('Observaciones inválidas.')
    if not isinstance(datos.get('filtros', {}), dict):
        raise ValueError('Filtros inválidos.')
    if not isinstance(datos.get('avisos', []), list) or any(not isinstance(x, str) for x in datos.get('avisos', [])):
        raise ValueError('Avisos inválidos.')


def numero(v, decimales=2):
    if v is None:
        return '-'
    return f'{v:,.{decimales}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def par(texto, tam=8, color=GRAY, bold=False, align=TA_LEFT):
    estilo = ParagraphStyle('texto', fontName='Helvetica-Bold' if bold else 'Helvetica',
                            fontSize=tam, leading=tam * 1.3, textColor=color, alignment=align)
    return Paragraph(escape(str(texto)), estilo)


def grafico(registros, campo, comparado, titulo, dinero=False):
    ancho = (ANCHO - 18) / 2
    alto = 34 + len(registros) * 26
    dibujo = Drawing(ancho, alto)
    dibujo.add(String(10, alto-16, titulo, fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    for x, color, texto in ((10,BLUE,'EDP'),(65,GREEN,'Esperado' if dinero else 'Tickets')):
        dibujo.add(Rect(x,alto-31,7,7,fillColor=color,strokeColor=None))
        dibujo.add(String(x+11,alto-30,texto,fontName='Helvetica',fontSize=7,fillColor=GRAY))
    maximo = max([abs(r[k]) for r in registros for k in (campo,comparado)] + [1])
    inicio, largo = 112, ancho - 112 - 97
    for i,r in enumerate(registros):
        y = alto - 46 - i * 26
        etiqueta = f"{r.get('mes_nombre') or r.get('periodo') or '-'} {r.get('anio') or ''}"
        dibujo.add(String(10,y,etiqueta[:30],fontName='Helvetica-Bold',fontSize=7.5,fillColor=NAVY))
        dibujo.add(String(10,y-10,f"{r.get('unidad') or '-'} / EDP {r.get('edp') or '-'}"[:34],fontName='Helvetica',fontSize=6.5,fillColor=GRAY))
        for j,k in enumerate((campo,comparado)):
            base = y - j * 10
            dibujo.add(Rect(inicio,base, largo,6,fillColor=PALE,strokeColor=None))
            dibujo.add(Rect(inicio,base,largo*abs(r[k])/maximo,6,fillColor=BLUE if j==0 else GREEN,strokeColor=None))
            etiqueta = ('$ ' if dinero else '') + numero(r[k],2 if dinero else 3) + ('' if dinero else ' t')
            dibujo.add(String(ancho-8,base,etiqueta,textAnchor='end',fontName='Helvetica',fontSize=7,fillColor=NAVY))
    return dibujo


def crear_pdf(datos):
    validar(datos)
    registros = datos['registros']
    validos = [r for r in registros if r['estado'] != 'incompleto']
    suma = lambda k: sum((Decimal(str(r[k])) for r in validos), Decimal(0)) if validos else None
    salida = BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=landscape(A4), leftMargin=24, rightMargin=24,
                            topMargin=65, bottomMargin=30, title='Estados de pago y toneladas',
                            author='Resiter Minería')
    historia = [par('Estados de pago y toneladas',18,NAVY,True),
                par('Ítem 2.5.a - Recolección y disposición final de residuos - CMRIS',8),
                Spacer(1,7)]
    filtros = datos.get('filtros',{})
    seleccion = ' / '.join(f'{k}: {v}' for k,v in filtros.items()) or 'Todos los EDP'
    historia += [par(seleccion,8,NAVY), par('Última lectura: '+str(datos.get('actualizado','No disponible')),7),
                 par('Precio Modificación N.º 1 × (Peso Total de tickets ÷ 1.000) = Monto esperado del EDP',8,NAVY),
                 Spacer(1,5)]
    cuadros = [
        ('EDP revisados',str(len(registros)),f"{sum(r['estado']=='cuadra' for r in registros)} cuadran / {sum(r['estado']=='diferencia' for r in registros)} con diferencia"),
        ('Toneladas según tickets',numero(suma('ton_tickets'),3),f"{sum(r['numero_tickets'] for r in validos)} filas de tickets"),
        ('Monto esperado (CLP)','$ '+numero(suma('monto_esperado')),'Precio por tonelada × toneladas'),
        ('Diferencia neta (CLP)','$ '+numero(suma('diferencia')),'EDP menos monto esperado')]
    kpis = Table([[[par(a,7),Spacer(1,4),par(b,14,NAVY,True),Spacer(1,4),par(c,7)] for a,b,c in cuadros]],
                 colWidths=[ANCHO/4]*4)
    kpis.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),
                             ('BOX',(0,0),(-1,-1),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),10),
                             ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    historia += [kpis,Spacer(1,6),par(f'Totales de {len(validos)} de {len(registros)} EDP. Los EDP sin conciliar se excluyen de los totales.',7)]
    for aviso in datos.get('avisos',[]):
        historia.append(par(aviso,7,colors.HexColor('#795000')))
    historia.append(Spacer(1,7))
    if validos:
        for i in range(0,len(validos),8):
            grupo = validos[i:i+8]
            graficos = Table([[grafico(grupo,'ton_edp','ton_tickets','Toneladas por EDP'),
                               grafico(grupo,'monto_edp','monto_esperado','Monto por EDP (CLP)',True)]],
                             colWidths=[ANCHO/2]*2)
            graficos.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.5,LINE),
                                         ('LINEBEFORE',(1,0),(1,0),.5,LINE),('LEFTPADDING',(0,0),(-1,-1),4),
                                         ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
            historia += [graficos,Spacer(1,6)]
    else:
        historia += [par('Sin EDP conciliables para los gráficos.',9),Spacer(1,6)]
    encabezado = ['Unidad / período','EDP','Tickets','Peso total kg','Tickets t','EDP t',
                  'Precio Mod. 1 CLP/t','Monto EDP CLP','Esperado CLP','Diferencia CLP','Estado']
    filas = [[par(c,7,colors.white,True) for c in encabezado]]
    for r in registros:
        fila = [par(f"{r.get('unidad') or '-'} / {r.get('periodo') or '-'}",7,NAVY),
                par(r.get('edp') or '-',7,NAVY),par(numero(r.get('numero_tickets'),0),7,NAVY,align=TA_RIGHT)]
        for k,decimales in (('peso_kg',0),('ton_tickets',3),('ton_edp',3),('precio',2),
                           ('monto_edp',2),('monto_esperado',2),('diferencia',2)):
            fila.append(par(numero(r.get(k),decimales),7,NAVY,align=TA_RIGHT))
        texto = ESTADOS[r['estado']] + (' *' if r.get('avisos') else '')
        fila.append(par(texto,7, GREEN if r['estado']=='cuadra' else colors.HexColor('#a12424')))
        filas.append(fila)
    pesos = [96,29,36,57,56,56,65,85,85,70,65]
    tabla = Table(filas, colWidths=[x*ANCHO/sum(pesos) for x in pesos],repeatRows=1,hAlign='LEFT')
    tabla.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                              ('LINEBELOW',(0,0),(-1,-1),.4,LINE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
                              ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                              ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    historia += [KeepTogether([par('Detalle de conciliación',11,NAVY,True),Spacer(1,5)]),tabla,Spacer(1,6),
                 par('Diferencia positiva: el EDP supera el monto esperado. Importes comparados a 2 decimales; tolerancia: 0,000001 t. Sin acumulados ni reajustes.',7)]
    observaciones = [(r, r.get('errores',[])+r.get('avisos',[])) for r in registros]
    if any(obs for _,obs in observaciones):
        historia += [Spacer(1,8),par('* Observaciones de los EDP seleccionados',9,NAVY,True)]
        notas = {}
        for r,obs in observaciones:
            for nota in obs:
                notas.setdefault(nota, []).append(f"{r.get('unidad') or '-'} EDP {r.get('edp') or '-'}")
        for nota, edps in notas.items():
            historia.append(par(', '.join(edps) + ': ' + nota,7))
    def pagina(canvas, documento):
        ancho,alto = landscape(A4)
        canvas.saveState()
        canvas.setFillColor(colors.white); canvas.rect(0,alto-48,ancho,48,fill=1,stroke=0)
        root = Path(__file__).resolve().parent.parent
        resiter = ImageReader(str(root / 'logo_sin_fondo_resiter.png'))
        codelco = ImageReader(str(root / 'logo_sin_fondo_codelco.png'))
        canvas.drawImage(resiter,23,alto-40,width=42,height=32,preserveAspectRatio=True,anchor='c',mask='auto')
        canvas.drawImage(codelco,ancho-105,alto-40,width=82,height=32,preserveAspectRatio=True,anchor='c',mask='auto')
        canvas.setFillColor(NAVY); canvas.setFont('Helvetica',9); canvas.drawRightString(ancho-116,alto-28,'Reporte Codelco')
        canvas.setFillColor(GRAY); canvas.setFont('Helvetica',7)
        canvas.drawString(24,16,'Estados de pago y toneladas')
        canvas.drawRightString(ancho-24,16,f'Página {documento.page}')
        canvas.restoreState()
    doc.build(historia,onFirstPage=pagina,onLaterPages=pagina)
    return salida.getvalue()
