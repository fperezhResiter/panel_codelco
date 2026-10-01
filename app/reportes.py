"""Reportabilidad exclusiva de formularios semanales ADC."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from .excel import leer_tabla, normalizar, patente_valida, convertir_fecha, TIPO_ADC

def crear_reporte(excel, maestro, fecha):
    primera_semana = date(2026, 8, 4)
    fecha = fecha + timedelta(days=1-fecha.weekday())
    if fecha < primera_semana:
        raise ValueError('La primera semana del reporte es el martes 4 de agosto de 2026.')
    # Martes de la semana calendario (lunes a domingo).
    semana = (fecha - primera_semana).days // 7 + 1
    fecha = primera_semana + timedelta(weeks=semana - 1)
    inicio, fin = fecha - timedelta(days=1), fecha + timedelta(days=3)
    semanas = []
    for retroceso in range(semana - 1, -1, -1):
        referencia = fecha - timedelta(weeks=retroceso)
        semanas.append({'numero': semana-retroceso, 'fecha': referencia.isoformat(),
                        'inicio': (referencia-timedelta(days=1)).isoformat(),
                        'fin': (referencia+timedelta(days=3)).isoformat()})
    historico = [defaultdict(set) for _ in semanas]
    mapa = defaultdict(set)
    advertencias = []
    activos, _, _ = leer_tabla(maestro, ['NOMBRE CeCo ACTUAL', 'REGION ACTUAL', 'PATENTE'], nombre_hoja='BD ACTIVOS MOVILES')
    for ceco, region, patente in activos:
        ceco, region = normalizar(ceco), normalizar(region)
        if ceco and region.startswith('REGION '):
            mapa[ceco].add(region)

    def region_ceco(ceco):
        regiones = mapa.get(ceco, set())
        return next(iter(regiones)) if len(regiones) == 1 else 'SIN REGIÓN'


    base = defaultdict(set)
    reportadas = defaultdict(set)
    invalidas_maestro = 0
    for ceco, region, patente in activos:
        patente = patente_valida(patente)
        if patente is None:
            invalidas_maestro += 1
            continue
        ceco = normalizar(ceco) or 'SIN CECO'
        base[ceco].add(patente)

    filas, epoch, hoja = leer_tabla(excel, ['Hora de finalización', 'CeCo (Centro de costo)', 'REGION', 'PATENTE', 'Reportabilidad a realizar'], nombre_hoja='Sheet1')
    invalidas = sin_patente = filas_periodo = 0
    fechas = []
    for hora, ceco, region, patente, tipo in filas:
        if normalizar(tipo) != normalizar(TIPO_ADC):
            continue
        dia = convertir_fecha(hora, epoch)
        if dia is None:
            invalidas += 1
            continue
        fechas.append(dia)
        p = patente_valida(patente)
        if p:
            for s, reportes_semana in zip(semanas, historico):
                if s['inicio'] <= dia.isoformat() <= s['fin']:
                    reportes_semana[normalizar(ceco) or 'SIN CECO'].add(p)
        if not inicio <= dia <= fin:
            continue
        filas_periodo += 1
        patente = patente_valida(patente)
        if patente is None:
            sin_patente += 1
            continue
        ceco = normalizar(ceco) or 'SIN CECO'
        reportadas[ceco].add(patente)
    grupos = defaultdict(list)
    for ceco in sorted(set(base) | set().union(*(set(h) for h in historico))):
        cantidad, esperado = len(reportadas[ceco]), len(base[ceco])
        fuera = len(reportadas[ceco] - base[ceco])
        grupos[region_ceco(ceco)].append({'ceco': ceco, 'reportadas': cantidad, 'total': esperado,
            'porcentaje': cantidad / esperado * 100 if esperado else None, 'fuera_maestro': fuera,
            'historico': [len(h[ceco]) for h in historico[-4:]],
            'historico_completo': [len(h[ceco]) for h in historico]})
    regiones_resultado = []
    for region, detalle in sorted(grupos.items()):
        cantidad, esperado = sum(c['reportadas'] for c in detalle), sum(c['total'] for c in detalle)
        regiones_resultado.append({'region': region, 'cecos': detalle, 'reportadas': cantidad, 'total': esperado,
            'porcentaje': cantidad / esperado * 100 if esperado else None})
    cantidad = sum(r['reportadas'] for r in regiones_resultado)
    esperado = sum(r['total'] for r in regiones_resultado)
    fuera = sum(c['fuera_maestro'] for r in regiones_resultado for c in r['cecos'])
    if invalidas:
        advertencias.append(f'{invalidas} filas del archivo tienen fecha vacía o inválida y no se cuentan.')
    if sin_patente:
        advertencias.append(f'{sin_patente} filas del período sin patente válida (incluye REVISAR) fueron excluidas.')
    if invalidas_maestro:
        advertencias.append(f'{invalidas_maestro} filas del maestro sin patente válida fueron excluidas del total.')
    if fuera:
        advertencias.append(f'{fuera} patentes reportadas por CeCo no figuran en el maestro de ese CeCo. Se incluyen en Reportadas; el porcentaje puede superar 100%.')
    if 'SIN REGIÓN' in grupos:
        advertencias.append('Los CeCo sin región única en el maestro se muestran en SIN REGIÓN; sus patentes se incluyen en los totales.')
    if any(len(regiones) > 1 for regiones in mapa.values()):
        advertencias.append('Hay CeCo con varias regiones en el maestro; se agrupan en SIN REGIÓN para evitar duplicar el conteo.')
    return {'version_reporte': 2, 'semanas': semanas[-4:], 'semanas_completas': semanas, 'semana': semana, 'fecha': fecha.isoformat(), 'inicio': inicio.isoformat(), 'fin': fin.isoformat(),
            'reportadas': cantidad, 'total': esperado, 'porcentaje': cantidad / esperado * 100 if esperado else None,
            'regiones': regiones_resultado, 'advertencias': advertencias,
            'filas_fuente': len(filas), 'filas_periodo': filas_periodo, 'fuera_maestro': fuera,
            'fuente': excel.name, 'hoja': hoja, 'actualizado': datetime.now().isoformat(timespec='seconds'),
            'min_fecha': min(fechas).isoformat() if fechas else None, 'max_fecha': max(fechas).isoformat() if fechas else None}


