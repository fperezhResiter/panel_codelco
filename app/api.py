"""Registro de consultas JSON; separa el servidor de la lógica del reporte."""
from .reportes import crear_reporte


def conciliacion(fuentes, parametros):
    return crear_reporte(fuentes)


API_RUTAS = {'/api/conciliacion': conciliacion}
