"""Registro de consultas JSON; separa el servidor de la lógica del reporte."""
from .base_datos import leer_reporte
from .densidades import leer_densidades


def conciliacion(base_datos, parametros):
    return leer_reporte(base_datos)


API_RUTAS = {'/api/conciliacion': conciliacion, '/api/densidades': leer_densidades}
