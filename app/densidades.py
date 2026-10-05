"""Maestra de densidades y chequeo de tickets por unidad desde SQLite."""
import json
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from .excel import FuenteExcel, clave, normalizar, numero
from .residuos import clave_material, estandarizar_residuo, identificar_residuo

VOLUMENES = (15, 20, 30)
BANDAS_POR_UNIDAD = {'El Salvador': VOLUMENES, 'Andina': (13, 20, 40)}
TOLERANCIA = Decimal('3')
ESTADOS = {'coincide': 'Coincide con volumen',
           'no_coincide_menor': 'No coincide con volumen menor',
           'no_coincide_mayor': 'No coincide con volumen mayor',
           'sin_evaluar': 'Sin evaluar'}


def regla_unidad(unidad):
    capacidades = ', '.join(map(str, BANDAS_POR_UNIDAD[unidad]))
    umbral = min(BANDAS_POR_UNIDAD[unidad])
    peso = ('Andina: Cantidad (t) × 1.000 = peso en kg. ' if unidad == 'Andina' else
            'El Salvador: Peso Total en kg. ')
    return (peso + 'Volumen (m³) = peso (kg) / promedio de densidades inferior y superior (kg/m³). '
            f'Coincide si está a ±3 m³ de {capacidades} m³, incluidos los límites. '
            'Se asigna la capacidad más cercana; en un empate, la menor. '
            f'Fuera de los rangos: menor a {umbral} m³, amarillo; mayor a {umbral} m³, rojo. Sin evaluar, gris.')


def importar_maestra(fuentes):
    """Lee la tabla de materiales exclusivamente de AUX, sin usar tickets históricos."""
    rutas = sorted(p for p in Path(fuentes).rglob('*') if p.is_file() and
                   not p.name.startswith('~$') and p.suffix.lower() in ('.xlsx', '.xlsm', '.xls') and
                   clave(p.stem) == 'REPORTEDERINPPORDENSIDAD')
    resultado = {'archivo': None, 'materiales': [], 'avisos': [], 'criterio': 'Promedio de ambas densidades'}
    if len(rutas) != 1:
        resultado['avisos'].append('No se encuentra una única maestra Reporte de RINP por densidad.xlsx en Fuentes. '
                                  'Los tickets quedarán sin evaluar hasta corregirlo y actualizar la BD.')
        return resultado
    ruta = rutas[0]
    resultado['archivo'] = ruta.relative_to(fuentes).as_posix()
    libro = None
    try:
        if ruta.suffix.lower() == '.xls':
            raise ValueError('Guarda la maestra de densidades en formato .xlsx.')
        libro = FuenteExcel(ruta)
        hojas_aux = [h for h in libro.valores if normalizar(h.title) == 'AUX']
        if len(hojas_aux) != 1:
            raise ValueError('La maestra debe contener una única hoja AUX con las densidades de los materiales.')
        hoja = hojas_aux[0]
        candidatos = []
        for fila in hoja.iter_rows(max_row=min(60, hoja.max_row)):
            material = [c.column for c in fila if clave(c.value) in
                        ('TIPORINP', 'MATERIAL', 'RESIDUO', 'TIPODERESIDUO')]
            inferior = [c.column for c in fila if clave(c.value) in
                        ('DENSINF', 'DENSINFKGM3', 'DENSIDADINFERIOR', 'DENSIDADINFERIORKGM3')]
            superior = [c.column for c in fila if clave(c.value) in
                        ('DENSSUP', 'DENSSUPKGM3', 'DENSIDADSUPERIOR', 'DENSIDADSUPERIORKGM3')]
            if len(material) == len(inferior) == len(superior) == 1:
                candidatos.append((hoja, fila[0].row, material[0], inferior[0], superior[0]))
        if len(candidatos) != 1:
            raise ValueError('La hoja AUX debe tener una tabla única con Tipo RINP, Dens. Inf y Dens. Sup (kg/m³).')
        hoja, inicio, material_col, inf_col, sup_col = candidatos[0]
        grupos = {}
        for fila in range(inicio + 1, hoja.max_row + 1):
            material = hoja.cell(fila, material_col).value
            if material is None or not str(material).strip():
                continue
            registro = {'material': estandarizar_residuo(material), 'material_original': str(material).strip(),
                        'clave': clave_material(material),
                        'inferior_kg_m3': None, 'superior_kg_m3': None, 'densidad_kg_m3': None,
                        'hoja': hoja.title, 'fila': fila,
                        'celda_inferior': hoja.cell(fila, inf_col).coordinate,
                        'celda_superior': hoja.cell(fila, sup_col).coordinate, 'error': None}
            try:
                inferior = libro.decimal(hoja, fila, inf_col)
                superior = libro.decimal(hoja, fila, sup_col)
                if not 0 < inferior <= superior:
                    raise ValueError('Las densidades deben ser positivas y la inferior no debe superar a la superior.')
                registro.update(inferior_kg_m3=float(inferior), superior_kg_m3=float(superior),
                                densidad_kg_m3=float((inferior + superior) / 2))
            except ValueError as error:
                registro['error'] = str(error)
            grupos.setdefault(registro['clave'], []).append(registro)
        for registros in grupos.values():
            registro = registros[0]
            if len(registros) > 1:
                registro['error'] = 'Material duplicado en la maestra; no se elige una densidad arbitrariamente.'
                registro['densidad_kg_m3'] = None
            resultado['materiales'].append(registro)
            if registro['error']:
                resultado['avisos'].append(f"{registro['material']}: {registro['error']}")
        if not resultado['materiales']:
            raise ValueError('La tabla de densidades está vacía.')
    except Exception as error:
        resultado['materiales'] = []
        resultado['avisos'].append(str(error) if isinstance(error, ValueError) else
                                  f'No se pudo leer la maestra de densidades ({type(error).__name__}).')
    finally:
        if libro:
            libro.cerrar()
    return resultado


def evaluar_ticket(ticket, material, unidad='El Salvador'):
    ticket = identificar_residuo(ticket, unidad)
    ticket['residuo'] = ticket['residuo_estandarizado']
    capacidades = BANDAS_POR_UNIDAD[unidad]
    resultado = {**ticket, 'unidad': unidad, 'estado': 'sin_evaluar', 'motivo': '', 'volumen_m3': None,
                 'volumen_tipo': None, 'volumen_cercano': None, 'diferencia_m3': None,
                 'capacidades_compatibles': [], 'densidad_kg_m3': None,
                 'inferior_kg_m3': None, 'superior_kg_m3': None, 'referencia_maestra': None}
    if material is None:
        resultado['motivo'] = ('El residuo no tiene correspondencia en la maestra.' if ticket['residuo'] else
                               'El ticket no declara tipo de residuo o producto; requiere revisión caso a caso.')
        return resultado
    resultado.update({k: material[k] for k in ('densidad_kg_m3', 'inferior_kg_m3', 'superior_kg_m3')})
    resultado['referencia_maestra'] = {k: material[k] for k in
                                     ('material', 'hoja', 'fila', 'celda_inferior', 'celda_superior')}
    if material['error']:
        resultado['motivo'] = material['error']
        return resultado
    try:
        peso = numero(ticket.get('peso_kg'))
        densidad = (numero(material['inferior_kg_m3']) + numero(material['superior_kg_m3'])) / 2
        if peso < 0 or densidad <= 0:
            raise ValueError('Peso negativo o densidad no positiva.')
        volumen = peso / densidad
    except ValueError as error:
        resultado['motivo'] = 'No se puede calcular el volumen: ' + str(error)
        return resultado
    cercano = min(capacidades, key=lambda v: (abs(volumen - v), v))
    compatibles = [v for v in capacidades if abs(volumen - v) <= TOLERANCIA]
    estado = ('coincide' if compatibles else
              'no_coincide_menor' if volumen < min(capacidades) else 'no_coincide_mayor')
    resultado.update(volumen_m3=float(volumen), volumen_cercano=cercano,
                     diferencia_m3=float(volumen - cercano), capacidades_compatibles=compatibles,
                     volumen_tipo=cercano if compatibles else None,
                     estado=estado)
    resultado['motivo'] = (f'Coincide con {cercano} m³ (±3 m³).' if compatibles else
                           ESTADOS[estado] + ': fuera de los rangos de ' +
                           ', '.join(map(str, capacidades)) + ' m³ (±3 m³).')
    return resultado


def leer_densidades(ruta, parametros=None):
    from .base_datos import leer_reporte
    parametros = parametros or {}
    unidad = parametros.get('unidad', 'El Salvador')
    unidad = unidad[0] if isinstance(unidad, list) and unidad else unidad
    if unidad not in BANDAS_POR_UNIDAD:
        raise ValueError('Selecciona la unidad Andina o El Salvador.')
    reporte = leer_reporte(ruta)
    with closing(sqlite3.connect(ruta)) as conexion:
        if not conexion.execute("SELECT 1 FROM sqlite_master WHERE name='maestra_densidades'").fetchone():
            raise ValueError('La BD aún no contiene la maestra de densidades. Ejecuta Actualizar_BD y recarga el panel.')
        materiales = [json.loads(f[0]) for f in conexion.execute('SELECT datos FROM maestra_densidades ORDER BY clave')]
        meta = conexion.execute("SELECT valor FROM metadatos WHERE clave='densidades'").fetchone()
        maestra = json.loads(meta[0]) if meta else {'avisos': []}
    indice = {}
    for material in materiales:
        material['material'] = estandarizar_residuo(material['material'])
        key = clave_material(material['material'])
        if key in indice:
            indice[key] = {**indice[key], 'densidad_kg_m3': None,
                           'error': 'Material duplicado en la maestra después de estandarizar sus nombres.'}
        else:
            indice[key] = material
    tickets, avisos_edp = [], []
    for registro in reporte['registros']:
        if registro['unidad'] != unidad:
            continue
        if registro['errores']:
            avisos_edp.append({**{k: registro[k] for k in ('anio', 'mes', 'edp')},
                              'mensaje': f"EDP {registro['edp']} / {registro['periodo']}: " + ' '.join(registro['errores'])})
        for ticket in registro['tickets']:
            ticket = identificar_residuo(ticket, unidad)
            fila = evaluar_ticket(ticket, indice.get(clave_material(ticket['residuo_estandarizado'], unidad)), unidad)
            fila.update({k: registro[k] for k in ('archivo', 'periodo', 'anio', 'mes', 'edp')})
            fila['hoja_ticket'] = registro.get('referencias', {}).get('peso', {}).get('hoja', '')
            tickets.append(fila)
    tickets.sort(key=lambda t: (t['periodo'] or '', t['edp'] or 0, t['archivo'], t['fila']))
    datos = {'actualizado': reporte['actualizado'], 'maestra': {**maestra, 'materiales': materiales},
             'tickets': tickets, 'avisos_edp': avisos_edp, 'regla': regla_unidad(unidad), 'unidad': unidad,
             'unidades': list(BANDAS_POR_UNIDAD), 'umbral_m3': min(BANDAS_POR_UNIDAD[unidad]),
             'volumenes': list(BANDAS_POR_UNIDAD[unidad]), 'tolerancia_m3': float(TOLERANCIA)}
    return filtrar_reporte(datos, parametros or {})


def filtrar_reporte(datos, parametros):
    filtros = {k: str(v[0] if isinstance(v, list) and v else v).strip() for k, v in parametros.items()
               if k in ('unidad', 'anio', 'mes', 'edp', 'residuo', 'estado', 'volumen_tipo', 'buscar') and v}
    def coincide(t):
        for campo, valor in filtros.items():
            if campo == 'buscar':
                if normalizar(valor) not in normalizar(' '.join(str(t.get(k) or '') for k in
                                                              ('ticket', 'retiro', 'residuo', 'residuo_original', 'archivo', 'fila'))):
                    return False
            elif campo == 'residuo':
                if clave_material(t.get(campo), datos['unidad']) != clave_material(valor, datos['unidad']):
                    return False
            elif str(t.get(campo)) != valor:
                return False
        return True
    avisos = list(datos['maestra']['avisos'])
    avisos.extend(a['mensaje'] for a in datos['avisos_edp'] if all(
        str(a[k]) == filtros[k] for k in ('anio', 'mes', 'edp') if filtros.get(k)))
    if not datos['tickets']:
        avisos.append(f"No hay tickets de {datos['unidad']} guardados en la BD.")
    seleccionados = [t for t in datos['tickets'] if coincide(t)]
    pendientes = {}
    for ticket in seleccionados:
        if ticket['referencia_maestra'] is None:
            nombre = ticket['residuo'] or '(sin tipo declarado)'
            pendientes[nombre] = pendientes.get(nombre, 0) + 1
    avisos.extend(f"{datos['unidad']}: {nombre}, {cantidad} tickets sin correspondencia en AUX; revisar caso a caso."
                  for nombre, cantidad in pendientes.items())
    estimados = sum(t.get('residuo_es_estimado', False) for t in seleccionados)
    if estimados:
        avisos.append(f'{datos["unidad"]}: {estimados} tickets con tipo de residuo estimado. '
                      'La densidad de AUX corresponde al material estimado; el original y el criterio se conservan en el detalle y reportes.')
    return {**datos, 'avisos': avisos, 'filtros': filtros, 'tickets': seleccionados}
