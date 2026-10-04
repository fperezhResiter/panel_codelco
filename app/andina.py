"""Lectura del ítem 1.1 de los avances físico y financiero de Andina."""
from .excel import clave, normalizar, fecha, unico


def fila_item(hoja):
    posicion = unico([c for fila in hoja for c in fila if clave(c.value) == 'POSICION'],
                     f"'{hoja.title}': no se identifica una columna Posición única.")
    item = unico([c for fila in hoja.iter_rows(min_row=posicion.row + 1,
                                             min_col=posicion.column, max_col=posicion.column)
                  for c in fila if normalizar(c.value) == '1.1'],
                 f"'{hoja.title}': no se encuentra un único ítem 1.1.")
    return item.row, posicion.row


def columna(hoja, cabecera, nombre):
    return unico([c.column for c in hoja[cabecera] if clave(c.value) == nombre],
                 f"'{hoja.title}': falta una columna única {nombre}.")


def leer_avance_andina(libro):
    fisico = libro.hoja(r'AVANCEFISICO')
    financiero = libro.hoja(r'AVANCEFINANCIERO')
    fila_fisico, cabecera_fisico = fila_item(fisico)
    fila_financiero, cabecera_financiero = fila_item(financiero)
    fuentes = {
        'precio': (fisico, fila_fisico, columna(fisico, cabecera_fisico, 'PRECIO')),
        'ton_edp': (fisico, fila_fisico, columna(fisico, cabecera_fisico, 'TOTALVALORACTUALEP')),
        'monto_edp': (financiero, fila_financiero, columna(financiero, cabecera_financiero, 'TOTALVALORACTUALEP')),
    }
    valores = {k: libro.decimal(*ref) for k, ref in fuentes.items()}
    referencias = {k: libro.referencia(*ref) for k, ref in fuentes.items()}
    periodo = ''
    for fila in fisico.iter_rows(max_row=cabecera_fisico - 1):
        for c in fila:
            if clave(c.value) == 'PERIODO':
                fechas = [fecha(v.value) for v in fila[c.column:] if fecha(v.value)]
                periodo = ' al '.join(fechas)
    return valores, referencias, periodo
