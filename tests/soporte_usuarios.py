"""Sesión administrativa para pruebas existentes de reportes; autenticación en test_usuarios."""
from app.servidor import crear_handler
from app.usuarios import Usuarios


def crear_handler_administrador(*args, **kwargs):
    handler = crear_handler(*args, **kwargs)
    sesion = {'usuario': Usuarios.publico({'nombre': 'prueba', 'rol': 'administrador'}), 'preview': None}
    handler.sesion_actual = lambda self: sesion
    return handler
