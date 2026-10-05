"""Reporte de densidades calculado desde la BD y con la selección de la vista."""
from collections import Counter
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, LongTable
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line

from .pdf import par, numero, NAVY, BLUE, GREEN, GRAY, LINE, PALE
from .densidades import ESTADOS

RED = colors.HexColor('#a12424')
AMBER = colors.HexColor('#997000')
COLORES = {'coincide': GREEN, 'no_coincide_menor': AMBER,
           'no_coincide_mayor': RED, 'sin_evaluar': GRAY}
ANCHO = landscape(A4)[0] - 48


def titulo_seccion(texto):
    titulo = par(texto, 11, NAVY, True)
    titulo.keepWithNext = True
    espacio = Spacer(1, 5)
    espacio.keepWithNext = True
    return [titulo, espacio]


def grafico_estados(tickets):
    dibujo = Drawing(ANCHO / 2 - 12, 142)
    dibujo.add(String(5, 126, 'Resultados del chequeo', fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    conteos = Counter(t['estado'] for t in tickets)
    mayor = max(conteos.values(), default=1)
    for i, estado in enumerate(ESTADOS):
        y = 98 - i * 30
        dibujo.add(String(5, y + 2, ESTADOS[estado], fontSize=8, fillColor=GRAY))
        dibujo.add(Rect(151, y, 170 * conteos[estado] / mayor, 12,
                       fillColor=COLORES[estado], strokeColor=None))
        dibujo.add(String(335, y + 2, str(conteos[estado]), fontSize=8, fillColor=NAVY))
    return dibujo


def grafico_volumenes(tickets, capacidades):
    dibujo = Drawing(ANCHO / 2 - 12, 142)
    dibujo.add(String(5, 126, 'Capacidad asignada a tickets verdes', fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    conteos = Counter(t['volumen_tipo'] for t in tickets if t['estado'] == 'coincide')
    mayor = max(conteos.values(), default=1)
    for i, capacidad in enumerate(capacidades):
        y = 98 - i * 30
        dibujo.add(String(5, y + 2, f'{capacidad} m³ (±3 m³)', fontSize=8, fillColor=GRAY))
        dibujo.add(Rect(151, y, 170 * conteos[capacidad] / mayor, 12, fillColor=BLUE, strokeColor=None))
        dibujo.add(String(335, y + 2, str(conteos[capacidad]), fontSize=8, fillColor=NAVY))
    return dibujo


def grafico_comparacion(tickets, capacidades):
    validos = [t for t in tickets if t['volumen_m3'] is not None]
    dibujo = Drawing(ANCHO, 155)
    dibujo.add(String(5, 138, 'Volumen calculado por ticket y ventanas permitidas', fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    if not validos:
        dibujo.add(String(5, 95, 'Sin volúmenes calculables en esta selección.', fontSize=9, fillColor=GRAY))
        return dibujo
    maximo = max(max(capacidades) + 6, max(t['volumen_m3'] for t in validos) * 1.03)
    izquierda, ancho, abajo, alto = 48, ANCHO - 64, 30, 90
    sy = lambda v: abajo + alto * v / maximo
    for capacidad in capacidades:
        dibujo.add(Rect(izquierda, sy(capacidad - 3), ancho, alto * 6 / maximo,
                       fillColor=colors.HexColor('#e4f4ec'), strokeColor=None))
        dibujo.add(Line(izquierda, sy(capacidad), izquierda + ancho, sy(capacidad), strokeColor=GREEN, strokeWidth=.5))
        dibujo.add(String(4, sy(capacidad) - 2, f'{capacidad} m³', fontSize=7, fillColor=GRAY))
    dibujo.add(Line(izquierda, abajo, izquierda + ancho, abajo, strokeColor=LINE))
    for i, ticket in enumerate(validos):
        dibujo.add(Circle(izquierda + ancho * (i + .5) / len(validos), sy(ticket['volumen_m3']), 1.7,
                          fillColor=COLORES[ticket['estado']], strokeColor=None))
    dibujo.add(String(izquierda, 12, f'{len(validos)} tickets en orden de período y fila. Escala: 0 a {numero(maximo, 1)} m³.',
                      fontSize=7, fillColor=GRAY))
    return dibujo


def crear_pdf_densidades(datos):
    tickets = datos['tickets']
    if not tickets:
        raise ValueError('No hay tickets en esta selección para generar el PDF.')
    salida = BytesIO()
    titulo = 'Chequeo de densidades - ' + datos['unidad']
    doc = SimpleDocTemplate(salida, pagesize=landscape(A4), leftMargin=24, rightMargin=24,
                            topMargin=48, bottomMargin=30, title=titulo, author='Resiter Minería')
    historia = [par(titulo, 17, NAVY, True),
                par('Selección: ' + (' / '.join(f'{k}: {v}' for k, v in datos.get('filtros', {}).items()) or 'Todos los tickets'), 8),
                par(datos['regla'], 8),
                par('Maestra: ' + str(datos['maestra'].get('archivo') or 'No disponible') + ' / Densidad utilizada: promedio de ambas densidades.', 8),
                Spacer(1, 8)]
    conteos = Counter(t['estado'] for t in tickets)
    kpis = Table([[par(f'{titulo}: {valor}', 10, NAVY, True) for titulo, valor in
                   [('Tickets', len(tickets)), ('Coinciden', conteos['coincide']),
                    ('Volumen menor', conteos['no_coincide_menor']), ('Volumen mayor', conteos['no_coincide_mayor']),
                    ('Sin evaluar', conteos['sin_evaluar'])]]], colWidths=[ANCHO / 5] * 5)
    kpis.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                             ('TOPPADDING', (0, 0), (-1, -1), 10)]))
    historia += [kpis, Spacer(1, 8), Table([[grafico_estados(tickets), grafico_volumenes(tickets, datos['volumenes'])]],
                                        colWidths=[ANCHO / 2] * 2), grafico_comparacion(tickets, datos['volumenes']), Spacer(1, 8)]
    for aviso in datos['avisos']:
        historia.append(par(aviso, 7, AMBER))
    criterios = sorted({t['criterio_estimacion_residuo'] for t in tickets if t.get('residuo_es_estimado')})
    for criterio in criterios:
        historia.append(par('Estimación de residuo y densidad: ' + criterio, 7, GRAY))
    historia += [Spacer(1, 8), *titulo_seccion('Detalle de tickets')]
    encabezado = ['Unidad / período / EDP / fila', 'Ticket / fecha', 'Residuo / producto', 'Peso kg', 'Dens. media kg/m³',
                  'Volumen m³', 'Capacidad m³', 'Delta m³', 'Resultado / motivo']
    filas = [[par(c, 7, colors.white, True) for c in encabezado]]
    for t in tickets:
        textos = [f"{t['unidad']} / {t['periodo']} / EDP {t['edp']} / fila {t['fila']}",
                  f"{t['ticket'] or '(sin ID)'} / {t['fecha'] or '(sin fecha)'}", t['residuo'],
                  numero(t['peso_kg']), numero(t['densidad_kg_m3']), numero(t['volumen_m3'], 3),
                  numero(t['volumen_tipo'], 0), numero(t['diferencia_m3'], 3), t['motivo']]
        fila = [par(v, 7, COLORES[t['estado']] if i == 8 else NAVY) for i, v in enumerate(textos)]
        if t.get('residuo_original') != t['residuo']:
            fila[2] = [fila[2], par('Original: ' + str(t.get('residuo_original') or '(vacío)'), 6, GRAY)]
        if t.get('residuo_es_estimado'):
            fila[2].append(par('Tipo estimado', 6, AMBER, True))
            fila[4] = [fila[4], par('Según material estimado', 6, GRAY)]
        filas.append(fila)
    tabla = LongTable(filas, colWidths=[95, 85, 100, 65, 65, 65, 55, 55, ANCHO - 585], repeatRows=1)
    tabla.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                              ('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                              ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)]))
    historia += [tabla, Spacer(1, 7), par('Delta = volumen calculado menos capacidad más cercana. '
                                        'Los tickets sin evaluar no se incluyen en los gráficos de volumen. '
                                        'Se conservan filas repetidas y tickets 0.', 7)]
    historia += [Spacer(1, 9), *titulo_seccion('Maestra de densidades utilizada (kg/m³)')]
    filas = [[par(c, 8, colors.white, True) for c in ('Material', 'Inferior', 'Superior', 'Promedio', 'Origen / observación')]]
    for m in datos['maestra']['materiales']:
        filas.append([par(v, 8) for v in (m['material'], numero(m['inferior_kg_m3']), numero(m['superior_kg_m3']),
                                          numero(m['densidad_kg_m3']), f"{m['hoja']}!{m['celda_inferior']} / {m['celda_superior']} " + (m['error'] or ''))])
    tabla_maestra = Table(filas, colWidths=[190, 85, 85, 85, ANCHO - 445], repeatRows=1)
    tabla_maestra.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), NAVY),
                                      ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), .4, LINE)]))
    historia += [Spacer(1, 5), tabla_maestra]
    def pagina(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(NAVY)
        canvas.drawString(24, landscape(A4)[1] - 25, 'Resiter Minería / Reporte Codelco')
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(GRAY)
        canvas.drawString(24, 15, titulo)
        canvas.drawRightString(landscape(A4)[0] - 24, 15, f'Página {documento.page}')
        canvas.restoreState()
    doc.build(historia, onFirstPage=pagina, onLaterPages=pagina)
    return salida.getvalue()
