"""Resumen mensual de la programación registrada en PROGRAMA."""
from collections import defaultdict
from datetime import date
from .excel import leer_tabla, convertir_fecha, normalizar, patente_valida

CAMPOS = ('realizadas', 'regularizadas', 'no_realizadas', 'na', 'sin_clasificar')


def resumir(equipos):
    resultado = {campo: sum(e['estado'] == campo for e in equipos) for campo in CAMPOS}
    resultado['total'] = len(equipos)
    aplicables = resultado['total'] - resultado['na']
    resultado['porcentaje'] = (resultado['realizadas'] * 100 / aplicables
                               if aplicables else None)
    return resultado


def crear_programa(excel, mes):
    try:
        periodo = date.fromisoformat(mes + '-01')
    except (ValueError, TypeError):
        raise ValueError('Seleccione un mes válido (AAAA-MM).') from None
    filas, epoch, hoja = leer_tabla(excel, ['REGION ACTUAL', 'NOMBRE CeCo ACTUAL', 'PATENTE',
        'FECHA PROYECTADA', 'ESTADO'], nombre_hoja='PROGRAMA')
    estados = {'REALIZADA': 'realizadas', 'REALIZADO': 'realizadas',
               'REGULARIZADA': 'regularizadas', 'REGULARIZADO': 'regularizadas',
               'NO REALIZADA': 'no_realizadas', 'NO REALIZADO': 'no_realizadas',
               'N/A': 'na', 'NA': 'na', 'NO APLICA': 'na'}
    unicos = {}
    invalidas = sin_patente = duplicados = conflictos = 0
    for region, ceco, patente, proyectada, estado in filas:
        dia = convertir_fecha(proyectada, epoch)
        if dia is None:
            invalidas += 1
            continue
        del_mes = (dia.year, dia.month) == (periodo.year, periodo.month)
        patente = patente_valida(patente)
        if not patente:
            sin_patente += int(del_mes)
            continue
        region, ceco = normalizar(region) or 'SIN REGIÓN', normalizar(ceco) or 'SIN CECO'
        clave = (dia.strftime('%Y-%m'), region, ceco, patente)
        categoria = estados.get(normalizar(estado), 'sin_clasificar')
        if clave in unicos:
            duplicados += int(del_mes)
            if unicos[clave]['estado'] != categoria:
                conflictos += int(del_mes)
                unicos[clave]['estado'] = 'sin_clasificar'
            continue
        unicos[clave] = {'region': region, 'ceco': ceco, 'patente': patente, 'estado': categoria}
    por_mes = defaultdict(list)
    for clave, equipo in unicos.items():
        por_mes[clave[0]].append(equipo)
    historico = []
    for m, equipos in sorted(por_mes.items()):
        regiones_mes = defaultdict(lambda: defaultdict(list))
        for equipo in equipos:
            regiones_mes[equipo['region']][equipo['ceco']].append(equipo)
        detalle = []
        for region, centros in sorted(regiones_mes.items()):
            detalle.append(dict(region=region,
                cecos=[dict(ceco=c, **resumir(es)) for c, es in sorted(centros.items())],
                **resumir([e for es in centros.values() for e in es])))
        historico.append(dict(mes=m, regiones=detalle, **resumir(equipos)))
    seleccionados = por_mes.get(mes, [])
    grupos = defaultdict(lambda: defaultdict(list))
    for equipo in seleccionados:
        grupos[equipo['region']][equipo['ceco']].append(equipo)
    regiones = []
    for region, centros in sorted(grupos.items()):
        cecos = [dict(ceco=ceco, **resumir(equipos)) for ceco, equipos in sorted(centros.items())]
        regiones.append(dict(region=region, cecos=cecos,
                             **resumir([e for equipos in centros.values() for e in equipos])))
    avisos = []
    for cantidad, mensaje in [(invalidas, 'filas con fecha proyectada vacía o inválida excluidas'),
                              (sin_patente, 'filas del mes sin patente válida excluidas'),
                              (duplicados, 'filas repetidas por región, CeCo y patente contadas una sola vez'),
                              (conflictos, 'duplicados con estados distintos marcados Sin clasificar')]:
        if cantidad:
            avisos.append(f'{cantidad} {mensaje}.')
    if any(e['estado'] == 'sin_clasificar' for e in seleccionados):
        avisos.append('Hay patentes con estado vacío, desconocido o contradictorio: se incluyen en programadas y en el denominador de cumplimiento, pero no en la torta de estados.')
    return dict(mes=mes, regiones=regiones, historico=historico, advertencias=avisos, fuente=excel.name, hoja=hoja,
                **resumir(seleccionados))
