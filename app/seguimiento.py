"""Seguimiento semanal por patente del maestro y proyección de mantención."""
import math
from datetime import date, datetime, time, timedelta
from .excel import leer_tabla, normalizar, patente_valida, convertir_fecha, TIPO_ADC, TIPO_MANTENCION


def numero(valor):
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        n = float(str(valor).strip().replace(',', '.'))
        return n if math.isfinite(n) and n >= 0 else None
    except (TypeError, ValueError):
        return None


def unidad_control(valor):
    return {'KM': 'KM', 'KMS': 'KM', 'KILOMETROS': 'KM', 'POR KILOMETRAJE': 'KM',
            'HR': 'HR', 'HRS': 'HR', 'HORAS': 'HR', 'POR HOROMETRO': 'HR'}.get(normalizar(valor))


def estado_mantencion(saldo, intervalo):
    if saldo is None or intervalo is None or intervalo <= 0:
        return 'STAND BY', 'neutro'
    if saldo >= intervalo * .1:
        return 'Mantención Vigente', 'verde'
    if saldo >= intervalo * -.1:
        return 'Próxima a vencer', 'amarillo'
    return 'Mantención Vencida', 'rojo'


def calcular_equipo(equipo):
    observadas = [l for l in equipo['lecturas'] if l is not None]
    ultima = observadas[-1] if observadas else None
    unidad = equipo['unidad']
    resultado = {'actual': ultima['valor'] if ultima else None,
                 'fecha_lectura': ultima['fecha_lectura'] if ultima else None,
                 'semana_actual': ultima['semana'] if ultima else None,
                 'proxima': None, 'saldo': None, 'estado': 'STAND BY', 'clase': 'neutro',
                 'motivo': '', 'ritmo_diario': None, 'fecha_proyectada': None,
                 'motivo_proyeccion': '', 'variaciones': []}
    problemas = []
    um, intervalo = equipo['ultima_mantencion'], equipo['intervalo']
    if equipo['conflicto_maestro']:
        problemas.append('Patente repetida con datos distintos en el maestro')
    if not unidad or unidad != equipo['unidad_intervalo']:
        problemas.append('Unidad UM o unidad de intervalo ausente/incompatible')
    if um is None or not equipo['fecha_mantencion']:
        problemas.append('Falta lectura o fecha UM en el maestro')
    if intervalo is None or intervalo <= 0:
        problemas.append('Falta intervalo positivo en el maestro')
    if not ultima or ultima['valor'] is None:
        problemas.append('No hay lectura semanal válida')
    elif ultima['unidad'] != unidad:
        problemas.append('La unidad reportada no coincide con el maestro')
    if ultima and equipo['fecha_mantencion']:
        if equipo['fecha_mantencion'] > ultima['fecha_lectura']:
            problemas.append('La lectura es anterior a la fecha UM')
        if um is not None and ultima['valor'] is not None and ultima['valor'] < um:
            problemas.append('La lectura es menor que KM U HR UM')
    validas = [l for l in observadas if l['valor'] is not None and l['unidad'] == unidad]
    problema_serie = None
    for anterior, actual in zip(validas, validas[1:]):
        dias = (date.fromisoformat(actual['fecha_lectura']) - date.fromisoformat(anterior['fecha_lectura'])).days
        delta = actual['valor'] - anterior['valor']
        if delta < 0:
            problema_serie = 'Hay un retroceso de medidor entre semanas'
        elif dias <= 0:
            problema_serie = 'Las fechas de lectura no avanzan entre semanas'
        resultado['variaciones'].append({'semana': actual['semana'], 'desde_semana': anterior['semana'],
            'dias': dias, 'incremento': delta, 'ritmo': delta / dias if dias > 0 and delta >= 0 else None})
    if any(l['unidad'] != unidad for l in observadas):
        problema_serie = 'Hay unidades distintas o ausentes entre semanas'
    if problema_serie:
        problemas.append(problema_serie)
    if not equipo['conflicto_maestro'] and unidad and unidad == equipo['unidad_intervalo'] and um is not None and intervalo and intervalo > 0:
        resultado['proxima'] = um + intervalo
    if not problemas:
        resultado['saldo'] = resultado['proxima'] - ultima['valor']
        resultado['estado'], resultado['clase'] = estado_mantencion(resultado['saldo'], intervalo)
    resultado['motivo'] = '; '.join(problemas)
    if problemas:
        resultado['motivo_proyeccion'] = 'Resolver los datos marcados STAND BY'
    elif len(validas) < 2:
        resultado['motivo_proyeccion'] = 'Se necesitan al menos dos lecturas semanales'
    else:
        primera, final = validas[0], validas[-1]
        dias = (date.fromisoformat(final['fecha_lectura']) - date.fromisoformat(primera['fecha_lectura'])).days
        ritmo = (final['valor'] - primera['valor']) / dias if dias > 0 else 0
        if ritmo <= 0:
            resultado['motivo_proyeccion'] = 'No hay consumo diario positivo'
        else:
            resultado['ritmo_diario'] = ritmo
            try:
                estimacion = date.fromisoformat(final['fecha_lectura']) + timedelta(days=math.ceil(resultado['saldo'] / ritmo))
                resultado['fecha_proyectada'] = estimacion.isoformat()
            except (OverflowError, ValueError):
                resultado['motivo_proyeccion'] = 'Proyección fuera del rango de fechas'
    return resultado


def crear_seguimiento(excel, maestro, corte, inicio=date(2026, 8, 4), incluir_estado=False):
    if corte < inicio:
        raise ValueError('La última semana debe ser igual o posterior al inicio de la semana 1.')
    cantidad = (corte - inicio).days // 7 + 1
    if cantidad > 104:
        raise ValueError('Selecciona un período de hasta 104 semanas.')
    semanas = []
    for i in range(cantidad):
        referencia = inicio + timedelta(days=7 * i)
        semanas.append({'numero': i + 1, 'fecha': referencia.isoformat(),
                       'desde': (referencia - timedelta(days=3)).isoformat(),
                       'hasta': (referencia + timedelta(days=1)).isoformat()})
    activos, epoch_maestro, _ = leer_tabla(maestro, ['PATENTE', 'NOMBRE CeCo ACTUAL', 'REGION ACTUAL',
        'KM U HR UM', 'UN UM', 'FECHA UM', 'INTERVALO', 'UN IN'])
    equipos = {}
    for patente, ceco, region, um, un_um, fecha_um, intervalo, un_in in activos:
        p = patente_valida(patente)
        if not p:
            continue
        fecha_um = convertir_fecha(fecha_um, epoch_maestro)
        datos = {'patente': p, 'ceco': normalizar(ceco) or 'SIN CECO', 'region': normalizar(region) or 'SIN REGIÓN',
                 'ultima_mantencion': numero(um), 'unidad': unidad_control(un_um),
                 'fecha_mantencion': fecha_um.isoformat() if fecha_um else None,
                 'intervalo': numero(intervalo), 'unidad_intervalo': unidad_control(un_in)}
        if p in equipos:
            if any(equipos[p][k] != v for k, v in datos.items()):
                equipos[p]['conflicto_maestro'] = True
            continue
        equipos[p] = {**datos, 'conflicto_maestro': False, 'lecturas': [None] * cantidad,
                      'origen_mantencion': 'Maestro', 'certificado_mantencion': '',
                      'fila_mantencion': None, 'fecha_envio_mantencion': None}
    columnas = ['Hora de finalización', 'PATENTE', 'Unidad de Control del equipo',
        'Fecha de lectura de Km y hrs', 'Kilometraje actual (km)', 'Horómetro actual (hrs)',
        'Reportabilidad a realizar', 'REGION', 'PATENTES TARAPACA', 'PATENTES COPIAPO', 'PATENTES BHP',
        'FECHA DE MANTENCION', 'KM U HRS DE MANTENCION', 'CERTIFICADO DE MANTENCION']
    if incluir_estado:
        columnas.append('Status actual del equipo')
    filas, epoch, hoja = leer_tabla(excel, columnas)
    elegidas, fuera = {}, set()
    mantenciones = {}
    limite_mtto = max(corte, date.fromisoformat(semanas[-1]['hasta']))
    mtto_invalidas = 0
    invalidas = 0
    for indice, (final, patente, control, fecha_lectura, km, hr, tipo, region_form,
                 pat_tarapaca, pat_copiapo, pat_bhp, fecha_mtto, valor_mtto, certificado, *estado_equipo) in enumerate(filas):
        tipo = normalizar(tipo)
        if tipo not in (normalizar(TIPO_ADC), normalizar(TIPO_MANTENCION)):
            continue
        enviado = convertir_fecha(final, epoch)
        if not enviado:
            invalidas += 1
            continue
        p = patente_valida(patente)
        if tipo == normalizar(TIPO_MANTENCION):
            if enviado > limite_mtto:
                continue
            candidatas = {p for v in (pat_tarapaca, pat_copiapo, pat_bhp) if (p := patente_valida(v))}
            # La patente específica del formulario prevalece sobre la columna calculada PATENTE.
            if not candidatas and (p := patente_valida(patente)):
                candidatas.add(p)
            dia_mtto, valor = convertir_fecha(fecha_mtto, epoch), numero(valor_mtto)
            if len(candidatas) != 1 or dia_mtto is None or valor is None or dia_mtto > enviado:
                mtto_invalidas += 1
                continue
            p = next(iter(candidatas))
            if p not in equipos:
                fuera.add(p)
                continue
            hora = final.time().replace(tzinfo=None) if isinstance(final, datetime) else time.min
            clave = (dia_mtto, enviado, hora, indice)
            if p not in mantenciones or clave > mantenciones[p]['clave']:
                mantenciones[p] = {'clave': clave, 'valor': valor, 'fecha': dia_mtto.isoformat(),
                                    'envio': enviado.isoformat(), 'fila': indice + 2,
                                    'certificado': str(certificado).strip() if certificado else ''}
            continue
        if not p or not semanas[0]['desde'] <= enviado.isoformat() <= semanas[-1]['hasta']:
            continue
        if p not in equipos:
            fuera.add(p)
            continue
        for i, semana in enumerate(semanas):
            if not semana['desde'] <= enviado.isoformat() <= semana['hasta']:
                continue
            hora = final.time().replace(tzinfo=None) if isinstance(final, datetime) else time.min
            clave = (enviado, hora, indice)
            if clave <= elegidas.get((p, i), (date.min, time.min, -1)):
                break
            elegidas[p, i] = clave
            declarada = unidad_control(control)
            unidad = declarada or equipos[p]['unidad']
            fecha_valor = convertir_fecha(fecha_lectura, epoch)
            equipos[p]['lecturas'][i] = {'semana': i + 1, 'valor': numero(km if unidad == 'KM' else hr) if unidad else None,
                'unidad': unidad, 'unidad_desde_maestro': declarada is None,
                'fecha_envio': enviado.isoformat(), 'fecha_lectura': (fecha_valor or enviado).isoformat(),
                'fecha_desde_envio': fecha_valor is None, 'fila_excel': indice + 2,
                'estado_equipo': normalizar(estado_equipo[0]) if estado_equipo else ''}
            break
    actualizadas = sin_certificado = 0
    for e in equipos.values():
        mtto = mantenciones.get(e['patente'])
        if mtto and (not e['fecha_mantencion'] or mtto['fecha'] >= e['fecha_mantencion']):
            e.update(ultima_mantencion=mtto['valor'], fecha_mantencion=mtto['fecha'],
                     origen_mantencion='PruebaForm · Jefe de Mantenimiento',
                     certificado_mantencion=mtto['certificado'], fila_mantencion=mtto['fila'],
                     fecha_envio_mantencion=mtto['envio'])
            actualizadas += 1
            sin_certificado += not bool(mtto['certificado'])
        e['calculo'] = calcular_equipo(e)
        ultima = next((l for l in reversed(e['lecturas']) if l is not None), None)
        e['estado_equipo'] = ultima['estado_equipo'] if ultima else ''
        e['fecha_estado_equipo'] = ultima['fecha_envio'] if ultima else None
    avisos = []
    if actualizadas:
        avisos.append(f'{actualizadas} patentes con última mantención actualizada desde el formulario del Jefe de Mantenimiento.')
    if mtto_invalidas:
        avisos.append(f'{mtto_invalidas} actualizaciones de mantención omitidas por patente ambigua, fecha inválida/futura o lectura inválida.')
    if sin_certificado:
        avisos.append(f'{sin_certificado} actualizaciones aplicadas no incluyen certificado; revisar respaldo.')
    if invalidas:
        avisos.append(f'{invalidas} filas sin fecha de finalización válida fueron omitidas.')
    if fuera:
        avisos.append(f'{len(fuera)} identificadores reportados no pertenecen al maestro y no se incluyen.')
    conflictos = sum(e['conflicto_maestro'] for e in equipos.values())
    if conflictos:
        avisos.append(f'{conflictos} patentes repetidas con datos distintos en el maestro: STAND BY.')
    return {'version': 2, 'fecha': corte.isoformat(), 'inicio': inicio.isoformat(), 'semanas': semanas,
            'equipos': sorted(equipos.values(), key=lambda e: (e['region'], e['ceco'], e['patente'])),
            'advertencias': avisos, 'fuente': excel.name, 'maestro': maestro.name, 'hoja': hoja,
            'incluye_estado_equipo': incluir_estado, 'actualizaciones_mantencion': actualizadas,
            'limite_mantenciones': limite_mtto.isoformat()}
