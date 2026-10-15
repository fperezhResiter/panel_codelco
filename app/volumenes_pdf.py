"""PDF de la selección del panel de distribución de volumen."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, LongTable, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
from .pdf import par, numero, NAVY, GRAY, LINE, PALE
from .densidades_pdf import ANCHO
from .volumenes import TRAMOS, clasificar, resumen

NOMBRES = {clave: nombre for clave, nombre, _ in TRAMOS}
COLORES = {clave: colors.HexColor(color) for clave, _, color in TRAMOS}
REGLA = ('Volumen (m³) = peso del ticket (kg) / promedio de densidades inferior y superior (kg/m³). '
         'Tramos sin redondear: menor a 10; desde 10 y menor a 20; desde 20 hasta 30 inclusive; mayor a 30 m³. '
         'Los porcentajes incluyen todos los tickets seleccionados, también los que no tienen volumen calculable.')


def estilo_tabla():
    return TableStyle([('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                       ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
                       ('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                       ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)])


def barras(grupos, volumen=False):
    ancho = ANCHO / 2 - 12
    dibujo = Drawing(ancho, 153)
    dibujo.add(String(4, 138, 'Volumen acumulado por tramo' if volumen else 'Distribución de tickets por tramo',
                      fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    grupos = [g for g in grupos if not volumen or g['volumen_m3'] is not None]
    campo = 'volumen_m3' if volumen else 'cantidad'
    maximo = max(1, *(g[campo] for g in grupos))
    largo = ancho - 230
    for i, g in enumerate(grupos):
        y = 112 - i * 23
        dibujo.add(String(4, y, g['nombre'], fontSize=7, fillColor=GRAY))
        dibujo.add(Rect(130, y, largo, 9, fillColor=PALE, strokeColor=None))
        dibujo.add(Rect(130, y, largo * g[campo] / maximo, 9,
                         fillColor=COLORES[g['id']], strokeColor=None))
        texto = (numero(g[campo]) + ' m³' if volumen else
                 f"{g['cantidad']} / {numero(g['porcentaje'], 1)}%")
        dibujo.add(String(ancho - 3, y, texto, textAnchor='end', fontSize=7, fillColor=NAVY))
    return dibujo


def dispersion(tickets):
    dibujo = Drawing(ANCHO, 156)
    dibujo.add(String(4, 140, 'Volumen calculado por ticket', fontName='Helvetica-Bold', fontSize=10, fillColor=NAVY))
    validos = [t for t in tickets if clasificar(t['volumen_m3']) != 'sin_volumen']
    if not validos:
        dibujo.add(String(4, 95, 'Sin volúmenes calculables en esta selección.', fontSize=9, fillColor=GRAY))
        return dibujo
    maximo = max(36, max(t['volumen_m3'] for t in validos) * 1.03)
    izquierda, largo, abajo, alto = 48, ANCHO - 64, 28, 95
    sy = lambda v: abajo + alto * v / maximo
    for limite in (10, 20, 30):
        dibujo.add(Line(izquierda, sy(limite), izquierda + largo, sy(limite), strokeColor=LINE))
        dibujo.add(String(4, sy(limite) - 2, f'{limite} m³', fontSize=7, fillColor=GRAY))
    dibujo.add(Line(izquierda, abajo, izquierda + largo, abajo, strokeColor=LINE))
    for i, t in enumerate(validos):
        dibujo.add(Circle(izquierda + largo * (i + .5) / len(validos), sy(t['volumen_m3']), 1.7,
                          fillColor=COLORES[clasificar(t['volumen_m3'])], strokeColor=None))
    dibujo.add(String(izquierda, 10, f'{len(validos)} tickets en orden de período y fila. Escala: 0 a {numero(maximo, 1)} m³.',
                      fontSize=7, fillColor=GRAY))
    return dibujo


def crear_pdf_volumenes(datos):
    tickets = datos['tickets']
    if not tickets:
        raise ValueError('No hay tickets en esta selección para generar el PDF.')
    grupos = resumen(tickets)
    salida = BytesIO()
    titulo = 'Distribución de volumen - ' + datos['unidad']
    doc = SimpleDocTemplate(salida, pagesize=landscape(A4), leftMargin=24, rightMargin=24,
                            topMargin=44, bottomMargin=30, title=titulo, author='Resiter Minería')
    filtros = {k: NOMBRES.get(v, v) if k == 'tramo_volumen' else v for k, v in datos.get('filtros', {}).items()}
    historia = [par(titulo, 17, NAVY, True),
                par('Selección: ' + (' / '.join(f'{k}: {v}' for k, v in filtros.items()) or 'Todos los tickets'), 8),
                par(REGLA, 8), par('Maestra: ' + str(datos['maestra'].get('archivo') or 'No disponible'), 8),
                par(f"Tickets: {len(tickets)} / Con volumen calculable: {sum(g['cantidad'] for g in grupos[:-1])} / "
                    f"Volumen total: {numero(sum(g['volumen_m3'] for g in grupos[:-1]))} m³", 10, NAVY, True),
                Spacer(1, 8)]
    filas = [[par(c, 8, colors.white, True) for c in ('Tramo de volumen', 'Tickets', 'Porcentaje', 'Volumen acumulado m³')]]
    filas += [[par(g['nombre'], 8, COLORES[g['id']]), par(g['cantidad'], 8),
               par(numero(g['porcentaje'], 1) + '%', 8), par(numero(g['volumen_m3']), 8)] for g in grupos]
    tabla = Table(filas, colWidths=[ANCHO * .4, ANCHO * .15, ANCHO * .2, ANCHO * .25])
    tabla.setStyle(estilo_tabla())
    graficos = Table([[barras(grupos), barras(grupos, True)]], colWidths=[ANCHO / 2] * 2)
    graficos.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    historia += [tabla, Spacer(1, 8), graficos, dispersion(tickets)]
    for aviso in datos.get('avisos', []):
        historia.append(par(aviso, 7, colors.HexColor('#997000')))
    criterios = sorted({t['criterio_estimacion_residuo'] for t in tickets if t.get('residuo_es_estimado')})
    for criterio in criterios:
        historia.append(par('Estimación de residuo y densidad: ' + criterio, 7, GRAY))
    historia += [PageBreak(), par('Detalle de tickets', 11, NAVY, True), Spacer(1, 5)]
    encabezado = ('Unidad / período / EDP / fila', 'Ticket / fecha', 'Residuo / retiro', 'Peso kg',
                  'Densidad kg/m³', 'Volumen m³', 'Tramo de volumen', 'Origen')
    filas = [[par(c, 7, colors.white, True) for c in encabezado]]
    for t in tickets:
        material = str(t.get('residuo') or 'Sin residuo') + ' / ' + str(t.get('retiro') or '')
        if t.get('residuo_original') != t.get('residuo'):
            material += ' / Original: ' + str(t.get('residuo_original') or '(sin tipo declarado)')
        if t.get('residuo_es_estimado'):
            material += ' / Tipo y densidad estimados'
        origen = f"{t.get('archivo', '')} / {t.get('hoja_ticket', '')}!{t.get('celda', '')}"
        ref = t.get('referencia_maestra')
        if ref:
            origen += f" / AUX: {ref['hoja']}!{ref['celda_inferior']} / {ref['celda_superior']}"
        tramo = clasificar(t['volumen_m3'])
        label = NOMBRES[tramo]
        if tramo == 'sin_volumen':
            label += ' / ' + str(t.get('motivo') or '')
        textos = [f"{t['unidad']} / {t['periodo']} / EDP {t['edp']} / fila {t['fila']}",
                  f"{t['ticket'] if t.get('ticket') is not None else '(sin ID)'} / {t.get('fecha') or '(sin fecha)'}",
                  material, numero(t.get('peso_kg')), numero(t.get('densidad_kg_m3')),
                  numero(t['volumen_m3'], 3), label, origen]
        filas.append([par(v, 7, COLORES[tramo] if i == 6 else NAVY) for i, v in enumerate(textos)])
    detalle = LongTable(filas, colWidths=[95, 80, 130, 60, 60, 60, 110, ANCHO - 595], repeatRows=1)
    detalle.setStyle(estilo_tabla())
    historia += [detalle, Spacer(1, 8), par('La descarga incluye toda la selección filtrada, aunque el panel muestre el detalle por páginas. '
                                           'Se conservan los tickets repetidos y el número 0.', 7)]

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
