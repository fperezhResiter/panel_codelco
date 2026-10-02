"""Reporte de la muestra guardada y de las comprobaciones hechas por el usuario."""
from io import BytesIO
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.utils import ImageReader
from .pdf import par, NAVY, GRAY, LINE, PALE
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
            if campo['sin_resultado']:
                valor = 'Sin resultado guardado en Excel'
            if campo['formula'] and not clave(campo['nombre']).startswith('PESOTOTAL'):
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

    def pie(canvas, doc):
        root = Path(__file__).resolve().parent.parent
        resiter = ImageReader(str(root / 'logo_sin_fondo_resiter.png'))
        codelco = ImageReader(str(root / 'logo_sin_fondo_codelco.png'))
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
    documento.build(historia, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
