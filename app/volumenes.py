"""Distribución del volumen calculado por densidades, con los mismos filtros."""
from math import isfinite
from .densidades import leer_densidades, filtrar_reporte

TRAMOS = (
    ('menor_10', 'Menor a 10 m³', '#0E81C5'),
    ('10_20', '10 a menos de 20 m³', '#2E9E6B'),
    ('20_30', '20 a 30 m³', '#997000'),
    ('mayor_30', 'Mayor a 30 m³', '#a12424'),
    ('sin_volumen', 'Sin volumen calculable', '#5B6B7C'),
)


def clasificar(volumen):
    if isinstance(volumen, bool) or not isinstance(volumen, (int, float)) or not isfinite(volumen) or volumen < 0:
        return 'sin_volumen'
    return ('menor_10' if volumen < 10 else '10_20' if volumen < 20 else
            '20_30' if volumen <= 30 else 'mayor_30')


def resumen(tickets):
    grupos = []
    for clave, nombre, color in TRAMOS:
        seleccion = [t for t in tickets if clasificar(t.get('volumen_m3')) == clave]
        grupos.append({'id': clave, 'nombre': nombre, 'color': color, 'cantidad': len(seleccion),
                       'porcentaje': len(seleccion) / len(tickets) * 100 if tickets else 0,
                       'volumen_m3': None if clave == 'sin_volumen' else
                       sum(t['volumen_m3'] for t in seleccion)})
    return grupos


def leer_volumenes(ruta, parametros=None):
    parametros = parametros or {}
    tramo = parametros.get('tramo_volumen', '')
    tramo = str(tramo[0] if isinstance(tramo, list) and tramo else tramo).strip()
    if tramo and tramo not in {t[0] for t in TRAMOS}:
        raise ValueError('Tramo de volumen inválido.')
    datos = leer_densidades(ruta, parametros)
    if tramo:
        datos = filtrar_reporte({**datos, 'tickets': [t for t in datos['tickets']
                                                    if clasificar(t['volumen_m3']) == tramo]}, parametros)
        datos['filtros']['tramo_volumen'] = tramo
    return datos
