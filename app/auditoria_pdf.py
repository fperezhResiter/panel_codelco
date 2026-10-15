"""Reporte de la muestra guardada y de las comprobaciones hechas por el usuario."""
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.utils import ImageReader
from .pdf import par, NAVY, GRAY, LINE, PALE
from .excel import clave
from .auditoria import orden_revision
from .reportes import ruta_fuente_canonica
from .descargas import MESES


def crear_pdf_auditoria(muestra):
    salida = BytesIO()
    ancho = A4[0] - 80
    documento = SimpleDocTemplate(salida, pagesize=A4, leftMargin=40, rightMargin=40,
                                 topMargin=60, bottomMargin=42,
                                 title='Auditoría de tickets EDP', author='Resiter Minería')
    historia = [par('AUDITORÍA DE TICKETS EDP', 20, NAVY, True), Spacer(1, 10),
                par(f'{muestra["unidad"]} | {muestra["periodo"]} | EDP {muestra["edp"]}', 13, NAVY, True),
                Spacer(1, 12)]
    comprobados = sum(t['comprobado'] for t in muestra['tickets'])
    for etiqueta, valor in [('Excel', muestra['archivo']), ('Hoja', muestra['hoja']),
                            ('Ítem', muestra.get('item') or ('1.1' if clave(muestra['hoja']) == '11' else '2.5.a')),
                            ('Muestra', muestra['id']),
                            ('Selección', ('Manual' if muestra.get('modo') == 'manual' else 'Aleatoria sin repetir filas') +
                             f': {len(muestra["tickets"])} de {muestra["poblacion"]} registros disponibles'),
                            ('Revisión manual', f'{comprobados} comprobados; {len(muestra["tickets"]) - comprobados} pendientes')]:
        historia.extend([par(f'{etiqueta}: {valor}', 10), Spacer(1, 6)])
    historia.extend([Spacer(1, 12), par('La casilla registra la confirmación de la persona que revisó los respaldos. '
                    'El panel no verifica automáticamente la coincidencia entre el ticket y sus documentos.', 10, NAVY),
                    Spacer(1, 10), par('Los documentos se enumeran en este reporte y se descargan desde el panel; '
                    'su contenido no se incorpora al PDF.', 9)])
    for aviso in muestra['avisos']:
        historia.extend([Spacer(1, 8), par(aviso, 9)])
    historia.extend([Spacer(1, 18), par('Huella SHA256 del Excel utilizado:', 8), par(muestra['sha256'], 8)])
    historia.extend(fichas_tickets(muestra, ancho))
    documento.build(historia, onFirstPage=pie_auditoria, onLaterPages=pie_auditoria)
    return salida.getvalue()


def fichas_tickets(muestra, ancho, inicio=0, total=None, encabezado=True):
    historia = []
    for indice, ticket in enumerate(muestra['tickets'], 1):
        if encabezado:
            historia.extend([PageBreak(), par(f'Ticket {ticket["ticket"] or "sin número"}', 18, NAVY, True), Spacer(1, 6)])
        historia.extend([par(f'{inicio + indice} de {total or len(muestra["tickets"])} | Fila Excel {ticket["fila"]} | '
                         f'{muestra["unidad"]} | {muestra["periodo"]} | EDP {muestra["edp"]}', 9), Spacer(1, 12)])
        estado = 'COMPROBADO MANUALMENTE' if ticket['comprobado'] else 'PENDIENTE DE COMPROBACIÓN'
        historia.extend([par(estado, 11, NAVY, True), Spacer(1, 6)])
        filas = [[par('Campo / celda', 9, NAVY, True), par('Información del EDP', 9, NAVY, True)]]
        for campo in ticket['campos']:
            valor = campo['valor'] or '(vacío)'
            if campo.get('unidad') == 't' and campo['valor']:
                valor += ' t'
            if campo['sin_resultado']:
                valor = 'Sin resultado guardado en Excel'
            if campo['formula'] and campo.get('unidad') != 't' and not clave(campo['nombre']).startswith('PESOTOTAL'):
                valor += '\nFórmula: ' + campo['formula']
            filas.append([par(f'{campo["nombre"]} [{campo["celda"]}]', 9), par(valor, 9, NAVY)])
        tabla = Table(filas, colWidths=[ancho * .37, ancho * .63], repeatRows=1, splitInRow=1)
        tabla.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), PALE),
                                  ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 9),
                                  ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                                  ('TOPPADDING', (0, 0), (-1, -1), 8),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
        historia.extend([tabla, Spacer(1, 16), par('Documentos de respaldo', 12, NAVY, True), Spacer(1, 7)])
        respaldo = ticket.get('respaldo_ticket')
        if respaldo:
            historia.extend([par(respaldo['nombre'], 9), Spacer(1, 5)])
        elif muestra.get('respaldo_edp') and not ticket.get('respaldo_autorizado'):
            historia.extend([par('Respaldo común del EDP: ' + muestra['respaldo_edp']['nombre'], 9), Spacer(1, 5)])
        if not respaldo and not ticket['documentos'] and not muestra.get('respaldo_edp'):
            historia.append(par('Sin documentos adjuntos.', 9))
        documentos = [] if respaldo else ticket['documentos']
        if ticket.get('respaldo_autorizado'):
            documentos = [d for d in documentos if d['id'] == ticket['respaldo_autorizado']]
        for doc in documentos:
            historia.extend([par(doc['nombre'], 9), Spacer(1, 5)])

    return historia


def pie_auditoria(canvas, doc):
    root = Path(__file__).resolve().parent.parent
    resiter = ImageReader(str(root / 'web' / 'img' / 'logo_sin_fondo_resiter.png'))
    codelco = ImageReader(str(root / 'web' / 'img' / 'logo_sin_fondo_codelco.png'))
    canvas.drawImage(resiter, 43, A4[1] - 52, width=39, height=32,
                     preserveAspectRatio=True, anchor='c', mask='auto')
    canvas.drawImage(codelco, A4[0] - 111, A4[1] - 52, width=68, height=32,
                     preserveAspectRatio=True, anchor='c', mask='auto')
    canvas.setStrokeColor(LINE)
    canvas.line(40, 32, A4[0] - 40, 32)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(40, 20, 'Auditoría manual EDP')
    canvas.drawRightString(A4[0] - 40, 20, f'Página {doc.page}')


def tickets_completados(muestras):
    """Una ficha por fila y versión de Excel; se usa su última revisión confirmada."""
    revisados = {}
    for muestra in sorted(muestras, key=orden_revision):
        for ticket in muestra['tickets']:
            if ticket['comprobado']:
                llave = (muestra['unidad'], muestra['periodo'], str(muestra['edp']),
                         ruta_fuente_canonica(muestra['archivo']), muestra['sha256'], muestra['hoja'], ticket['fila'])
                revisados[llave] = (muestra, ticket)
    return [revisados[llave] for llave in sorted(revisados)]


def seleccionar_edp(reporte, filtros):
    if not all(filtros.get(k) for k in ('anio', 'mes', 'edp')):
        raise ValueError('Selecciona unidad, año, mes y EDP para generar el PDF.')
    registros = [r for r in reporte['estados_pago'] if all(
        str(r.get(k)) == str(filtros[k]) for k in ('anio', 'mes', 'edp'))]
    if len(registros) != 1:
        raise ValueError('No se encuentra un único EDP para la selección.')
    registro = registros[0]
    muestras = [m for m in reporte['muestras'] if m['unidad'] == registro['unidad']
                and m['periodo'] == registro['periodo'] and str(m['edp']) == str(registro['edp'])]
    return {**reporte, 'estados_pago': registros, 'muestras': muestras}


def metodologia_auditoria(completados):
    historia = [Spacer(1, 18), par('Metodología de auditoría documental', 13, NAVY, True), Spacer(1, 10)]
    pasos = [
        ('1. Selección del estado de pago (EDP)',
         'Se identifica el EDP de la unidad, mes y año indicados en este informe. '
         'La población para el sorteo corresponde a todos los registros de tickets de la hoja '
         'del servicio auditado en el Excel de ese EDP.'),
        ('2. Selección aleatoria de la muestra',
         'En cada revisión por sorteo se eligen al azar 3, 4 o 5 tickets de esa población, '
         'según el tamaño de muestra seleccionado. El sorteo se realiza sin repetir filas '
         'dentro de una misma muestra. Los tickets elegidos directamente se registran '
         'como selección manual y siguen el mismo procedimiento de revisión documental.'),
        ('3. Comparación manual con el ticket físico',
         'La persona revisora compara la información registrada en Excel para cada ticket '
         'seleccionado con la fotografía o digitalización del ticket físico contenida en '
         'el documento de respaldo. Coteja el número de ticket, la fecha, el residuo o material, '
         'la cantidad o el peso y los demás campos disponibles. La revisión es manual; '
         'el panel conserva los datos y la confirmación registrada por la persona revisora.'),
        ('4. Registro del resultado y del respaldo',
         'Tras comprobar la coincidencia entre la información del ticket y su respaldo, '
         'la persona revisora marca la casilla de comprobación manual. Las fichas de este '
         'informe presentan el detalle de cada ticket completado y el nombre del documento '
         'de respaldo utilizado. Las nuevas comprobaciones requieren el respaldo individual '
         'NumeroTicket_EDPNumeroEDP o NumeroTicket EDP NumeroEDP, con o sin guion y con cualquier extensión, en la carpeta del EDP en Fuentes. Las autorizaciones '
         'anteriores conservan su respaldo histórico. Los archivos se entregan junto '
         'al reporte dentro de un ZIP y pueden descargarse desde el panel.'),
    ]
    for titulo, descripcion in pasos:
        historia.extend([par(titulo, 10, NAVY, True), Spacer(1, 4), par(descripcion, 10), Spacer(1, 10)])
    revisiones = {m['id']: m for m, _ in completados}
    manuales = sum(m.get('modo') == 'manual' for m in revisiones.values())
    aleatorias = len(revisiones) - manuales
    historia.extend([par(f'Revisiones incluidas: {aleatorias} por sorteo aleatorio y '
                         f'{manuales} por selección manual de tickets.', 9, NAVY), Spacer(1, 8),
                     par('Alcance: esta auditoría documenta la comprobación de los tickets revisados. '
                         'Sus resultados se refieren a esa selección y no acreditan la revisión '
                         'de todos los tickets del EDP. Los respaldos se identifican por nombre; '
                         'su contenido no se incorpora a este PDF.', 9)])
    return historia


def crear_pdf_unidad(reporte, *, invariante=False):
    """PDF de un EDP con todos sus tickets confirmados y sus respaldos."""
    registros = reporte['estados_pago']
    if len(registros) != 1:
        raise ValueError('El PDF debe corresponder a una unidad, mes, año y EDP.')
    registro = registros[0]
    muestras = [m for m in reporte['muestras'] if m['unidad'] == registro['unidad']
                and m['periodo'] == registro['periodo'] and str(m['edp']) == str(registro['edp'])]
    completados = tickets_completados(muestras)
    if not completados:
        raise ValueError('El EDP seleccionado no tiene tickets completados para generar el PDF.')
    salida = BytesIO()
    ancho = A4[0] - 80
    documento = SimpleDocTemplate(salida, pagesize=A4, leftMargin=40, rightMargin=40,
                                 topMargin=60, bottomMargin=42,
                                 title='Auditoría de tickets EDP', author='Resiter Minería',
                                 invariant=1 if invariante else None)
    mes = MESES[int(registro['mes']) - 1].capitalize()
    historia = [par('AUDITORÍA DE TICKETS EDP', 20, NAVY, True), Spacer(1, 10),
                par(f'{registro["unidad"]} | {mes} {registro["anio"]} | EDP {registro["edp"]}',
                    13, NAVY, True), Spacer(1, 12),
                par(f'Tickets revisados: {len(completados)}', 13, NAVY, True), Spacer(1, 10),
                par('Se incluyen todos los tickets completados de las revisiones guardadas de este EDP. '
                    'Cada fila de una misma versión del Excel se cuenta una sola vez. '
                    'Los números de ticket repetidos en filas distintas se conservan.', 9)]
    historia.extend(metodologia_auditoria(completados))
    for indice, (muestra, ticket) in enumerate(completados):
        ficha = {**muestra, 'tickets': [ticket]}
        historia.extend([PageBreak(),
                         par(f'Ticket {ticket["ticket"] or "sin número"}', 18, NAVY, True),
                         Spacer(1, 8)])
        for etiqueta, valor in [('Excel', muestra['archivo']), ('Hoja / ítem', muestra['hoja'] + ' / ' +
                                (muestra.get('item') or ('1.1' if muestra['unidad'] == 'Andina' else '2.5.a')))]:
            historia.extend([par(f'{etiqueta}: {valor}', 9), Spacer(1, 5)])
        for aviso in muestra['avisos']:
            historia.extend([par('Observación: ' + aviso, 9), Spacer(1, 5)])
        historia.extend(fichas_tickets(ficha, ancho, inicio=indice, total=len(completados), encabezado=False))
    documento.build(historia, onFirstPage=pie_auditoria, onLaterPages=pie_auditoria)
    return salida.getvalue()
