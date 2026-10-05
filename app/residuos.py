"""Nombres comunes de residuos, conservando siempre el texto de origen."""
import re

from .excel import clave, normalizar


# Equivalencias de escritura y nombres cortos del mismo material. Los
# calificativos que cambian el material (p. ej. contaminado) se conservan.
VARIANTES = {
    'Asimilable a RINP': ('Asimilable a RINP', 'Asimable a RINP', 'Asimilable RINP',
                         'Asimable RINP', 'Asimilables a RINP', 'Asimables a RINP'),
    'Aceite en desuso': ('Aceite en desuso', 'Aceites en desuso', 'Aceite', 'Aceites'),
    'Gomas en desuso': ('Gomas en desuso', 'Goma en desuso', 'Goma', 'Gomas'),
    'Madera': ('Madera', 'Maderas'),
    'Chatarra': ('Chatarra', 'Chatarras'),
    'Cartones': ('Cartones', 'Cartón', 'Carton'),
    'Plástico': ('Plástico', 'Plásticos', 'Plastico', 'Plasticos'),
    'Filtros en desuso': ('Filtros en desuso', 'Filtro en desuso', 'Filtros', 'Filtro'),
    'Bins vacíos': ('Bins vacíos', 'Bin vacío', 'Bins vacios', 'Bin vacio'),
    'Polvo de roca': ('Polvo de roca', 'Polvo roca'),
}
ALIAS_RESIDUOS = {clave(variante): nombre for nombre, variantes in VARIANTES.items() for variante in variantes}
ALIAS_POR_UNIDAD = {'Andina': {'RINPGRANEL': 'Asimilable a RINP', 'RINPAGRANEL': 'Asimilable a RINP'}}


def sin_fraccion(valor):
    texto = normalizar(valor)
    # Admite (1/2), (1 / 2) y la anotación mal cerrada /2/2) encontrada
    # en tickets. Una fracción no divide el peso informado por el ticket.
    return re.sub(r'\s*(?:\(\s*\d+\s*/\s*\d+\s*\)|/\s*\d+\s*/\s*\d+\s*\))\s*$', '', texto).strip()


def estandarizar_residuo(valor, unidad=None):
    texto = sin_fraccion(valor)
    key = clave(texto)
    return ALIAS_POR_UNIDAD.get(unidad, {}).get(key, ALIAS_RESIDUOS.get(key, texto.capitalize()))


def clave_material(valor, unidad=None):
    return clave(estandarizar_residuo(valor, unidad))


def identificar_residuo(ticket, unidad=None):
    original = ticket.get('residuo_original', ticket.get('residuo', ''))
    estimado = ticket.get('residuo_estimado', '') if not str(original or '').strip() else ''
    return {**ticket, 'residuo_original': original,
            'residuo_estandarizado': estandarizar_residuo(estimado or original, unidad),
            'residuo_es_estimado': bool(estimado), 'residuo_estimado': estimado,
            'criterio_estimacion_residuo': ticket.get('criterio_estimacion_residuo', '') if estimado else '',
            'referencias_estimacion_residuo': ticket.get('referencias_estimacion_residuo', []) if estimado else []}
