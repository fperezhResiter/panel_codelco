"""Reporte de la muestra guardada y de las comprobaciones hechas por el usuario."""
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Rect, String
from .pdf import par, NAVY, GRAY, LINE, PALE, GREEN
from .excel import clave


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
                            ('Muestra', muestra['id']), ('Creada el', muestra['creado']),
                            ('Último cambio', muestra['actualizado']),
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


def fichas_tickets(muestra, ancho):
    historia = []
    for indice, ticket in enumerate(muestra['tickets'], 1):
        historia.extend([PageBreak(), par(f'Ticket {ticket["ticket"] or "sin número"}', 18, NAVY, True),
                         Spacer(1, 6), par(f'{indice} de {len(muestra["tickets"])} | Fila Excel {ticket["fila"]} | '
                         f'{muestra["unidad"]} | {muestra["periodo"]} | EDP {muestra["edp"]}', 9), Spacer(1, 12)])
        estado = 'COMPROBADO MANUALMENTE' if ticket['comprobado'] else 'PENDIENTE DE COMPROBACIÓN'
        historia.extend([par(estado, 11, NAVY, True), Spacer(1, 6)])
        if ticket['comprobado_en']:
            historia.extend([par('Confirmado el: ' + ticket['comprobado_en'], 9), Spacer(1, 8)])
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
        if muestra.get('respaldo_edp'):
            historia.extend([par('Respaldo común del EDP: ' + muestra['respaldo_edp']['nombre'], 9), Spacer(1, 5)])
        if not ticket['documentos'] and not muestra.get('respaldo_edp'):
            historia.append(par('Sin documentos adjuntos.', 9))
        for doc in ticket['documentos']:
            historia.extend([par(f'{doc["nombre"]} ({doc["bytes"]:,} bytes) | Cargado: {doc["creado"]}', 9), Spacer(1, 5)])

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


def crear_pdf_unidad(reporte):
    """Todos los EDP y revisiones de una unidad, incluidos los EDP sin muestra."""
    salida = BytesIO()
    ancho = A4[0] - 80
    documento = SimpleDocTemplate(salida, pagesize=A4, leftMargin=40, rightMargin=40,
                                 topMargin=60, bottomMargin=42,
                                 title='Auditoría de unidad - ' + reporte['unidad'], author='Resiter Minería')
    registros = reporte['estados_pago']
    categorias = [('completo', 'Chequeo completo', GREEN),
                  ('parcial', 'Chequeo parcial', colors.HexColor('#D49C22')),
                  ('sin_revision', 'Sin revisión', colors.HexColor('#C33D3D'))]
    cantidades = {codigo: sum(e['estado_codigo'] == codigo for e in registros) for codigo, _, _ in categorias}
    colores = {codigo: color for codigo, _, color in categorias}
    historia = [par('AUDITORÍA DE UNIDAD', 20, NAVY, True), Spacer(1, 10),
                par(reporte['unidad'] + ' | ' + reporte.get('alcance', 'Todos los períodos'), 13, NAVY, True), Spacer(1, 10),
                par('Generado: ' + reporte['generado'], 9), Spacer(1, 10),
                par(f'{len(registros)} EDP | {cantidades["completo"]} completos | '
                    f'{cantidades["parcial"]} parciales | {cantidades["sin_revision"]} sin revisión', 11, NAVY, True),
                Spacer(1, 8), par('Verde: chequeo completo de los tickets seleccionados. '
                'Amarillo: chequeo parcial. Rojo: sin tickets confirmados.', 9),
                Spacer(1, 8), par('Cada EDP se cuenta una sola vez por período. El estado y los conteos de tickets '
                'corresponden a su revisión más reciente; las anteriores se conservan en el detalle. '
                'Chequeo completo no significa que toda la '
                'población del EDP haya sido auditada.', 9), Spacer(1, 12)]
    dibujo = Drawing(ancho, 110)
    for indice, (codigo, etiqueta, color) in enumerate(categorias):
        cantidad = cantidades[codigo]
        y = 84 - indice * 30
        dibujo.add(String(0, y + 3, etiqueta, fontName='Helvetica', fontSize=9, fillColor=NAVY))
        dibujo.add(Rect(110, y, ancho - 155, 16, fillColor=PALE, strokeColor=None))
        dibujo.add(Rect(110, y, (ancho - 155) * cantidad / max(1, len(registros)), 16,
                        fillColor=color, strokeColor=None))
        dibujo.add(String(ancho - 8, y + 3, str(cantidad), textAnchor='end', fontName='Helvetica', fontSize=11, fillColor=NAVY))
    historia.extend([dibujo, par('Estados de pago', 13, NAVY, True), Spacer(1, 10)])
    filas = [[par(n, 8, NAVY, True) for n in
              ('Período', 'EDP', 'Revisiones', 'Tickets', 'Chequeados', 'Pendientes', 'Estado de la selección')]]
    for e in registros:
        filas.append([par(v, 8) for v in (e['periodo'], e['edp'], e['revisiones'], e['tickets'],
                                         e['comprobados'], e['pendientes'])] +
                     [par(e['estado'], 8, colores[e['estado_codigo']], True)])
    tabla = Table(filas, colWidths=[60, 30, 58, 40, 67, 62, ancho - 317], repeatRows=1, splitInRow=1)
    tabla.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), PALE),
                              ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                              ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                              ('TOPPADDING', (0, 0), (-1, -1), 8),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    historia.extend([tabla, Spacer(1, 12), par('El detalle conserva los campos de Excel, las fechas de '
                    'confirmación, las observaciones y los nombres de los respaldos. '
                    'Los documentos originales se descargan por separado desde el panel.', 9)])
    for e in registros:
        muestras = [m for m in reporte['muestras'] if m['periodo'] == e['periodo'] and m['edp'] == e['edp']]
        if not muestras:
            bloque = [Spacer(1, 14), par(f'{e["periodo"]} | EDP {e["edp"]}', 11, NAVY, True), Spacer(1, 5)]
            for archivo in e['archivos']:
                bloque.extend([par('Excel: ' + archivo, 9), Spacer(1, 4)])
            bloque.append(par('Sin revisiones guardadas. Este EDP permanece sin chequeo.', 9))
            historia.append(KeepTogether(bloque))
            continue
        historia.extend([PageBreak(), par(f'{e["periodo"]} | EDP {e["edp"]}', 16, NAVY, True), Spacer(1, 10),
                         par(e['estado'], 11, colores[e['estado_codigo']], True), Spacer(1, 8)])
        for archivo in e['archivos']:
            historia.extend([par('Excel: ' + archivo, 9), Spacer(1, 5)])
        for indice, muestra in enumerate(muestras):
            if indice:
                historia.append(PageBreak())
            etiqueta = 'Revisión vigente ' if muestra['id'] == e['muestra_vigente'] else 'Revisión histórica '
            historia.extend([Spacer(1, 12), par(etiqueta + muestra['id'], 11, NAVY, True), Spacer(1, 8)])
            for etiqueta, valor in [('Excel', muestra['archivo']), ('Hoja / ítem', muestra['hoja'] + ' / ' +
                                    (muestra.get('item') or ('1.1' if muestra['unidad'] == 'Andina' else '2.5.a'))),
                                   ('Selección', muestra.get('modo', 'aleatoria')),
                                   ('Tickets seleccionados / población', f'{len(muestra["tickets"])} / {muestra["poblacion"]}'),
                                   ('Creada', muestra['creado']), ('Último cambio', muestra['actualizado']),
                                   ('SHA256 Excel', muestra['sha256'])]:
                historia.extend([par(f'{etiqueta}: {valor}', 9), Spacer(1, 5)])
            for aviso in muestra['avisos']:
                historia.extend([par('Observación: ' + aviso, 9), Spacer(1, 5)])
            historia.extend(fichas_tickets(muestra, ancho))
    documento.build(historia, onFirstPage=pie_auditoria, onLaterPages=pie_auditoria)
    return salida.getvalue()
