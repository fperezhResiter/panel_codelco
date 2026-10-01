"""Registro de consultas JSON; cada función recibe rutas de Excel y parámetros URL."""
from datetime import date
from .reportes import crear_reporte
from .seguimiento_hoja import crear_seguimiento
from .programa import crear_programa


def fecha_consulta(parametros):
    return date.fromisoformat(parametros.get('fecha', [date.today().isoformat()])[0])


def reporte(excel, maestro, parametros):
    return crear_reporte(excel, maestro, fecha_consulta(parametros))


def seguimiento(excel, maestro, parametros):
    inicio = date.fromisoformat(parametros.get('inicio', ['2026-08-04'])[0])
    return crear_seguimiento(excel, maestro, fecha_consulta(parametros), inicio)


def mantenciones(excel, maestro, parametros):
    inicio = date.fromisoformat(parametros.get('inicio', ['2026-08-04'])[0])
    return crear_seguimiento(excel, maestro, fecha_consulta(parametros), inicio, incluir_estado=True)


def programa(excel, maestro, parametros):
    return crear_programa(excel, parametros.get('mes', [date.today().strftime('%Y-%m')])[0])


API_RUTAS = {'/api/reporte': reporte, '/api/seguimiento-km-hr': seguimiento, '/api/mantenciones': mantenciones,
             '/api/programa-mantencion': programa}
