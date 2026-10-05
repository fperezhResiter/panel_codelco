"""Nombres de PDF basados en los datos que contiene cada reporte."""
import re
import unicodedata

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def componente(valor):
    texto = unicodedata.normalize('NFKD', str(valor)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')[:60]


def nombre_pdf(panel, registros, unidad=None, revision=None):
    unidades = {str(r['unidad']) for r in registros if r.get('unidad')}
    if unidad:
        unidades.add(unidad)
    unidad_nombre = next(iter(unidades)) if len(unidades) == 1 else (
        'varias-unidades' if unidades else 'unidad-sin-identificar')
    periodos = set()
    for registro in registros:
        periodo = registro.get('periodo')
        if not periodo and registro.get('anio') and registro.get('mes'):
            periodo = f"{registro['anio']}-{int(registro['mes']):02d}"
        if periodo:
            periodos.add(str(periodo))
    if len(periodos) == 1:
        periodo = next(iter(periodos))
        coincidencia = re.fullmatch(r'(\d{4})-(0[1-9]|1[0-2])', periodo)
        mes_nombre = (f'{MESES[int(coincidencia[2]) - 1]}-{coincidencia[1]}'
                      if coincidencia else periodo)
    elif periodos:
        mes_nombre = f'varios-meses-{min(periodos)}-a-{max(periodos)}'
    else:
        mes_nombre = 'mes-sin-identificar'
    edps = sorted({str(r['edp']) for r in registros if r.get('edp') is not None},
                  key=lambda valor: (len(valor), valor))
    edp_nombre = ('edp-' + '-'.join(edps) if 0 < len(edps) <= 3 else
                  'varios-edp' if edps else 'edp-sin-identificar')
    partes = [unidad_nombre, mes_nombre, edp_nombre, 'panel-' + panel]
    if revision:
        partes.append(str(revision)[:8])
    return '-'.join(componente(parte) for parte in partes) + '.pdf'
