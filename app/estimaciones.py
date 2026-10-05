"""Estimación explícita de tipos faltantes, usando declaraciones de la misma unidad."""
from collections import Counter

from .residuos import clave_material, identificar_residuo, estandarizar_residuo


def estimar_residuos_faltantes(registros, materiales):
    # Nunca reutilizar estimaciones como evidencia para una nueva estimación.
    for registro in registros:
        registro['tickets'] = [identificar_residuo({**t, 'residuo_estimado': ''}, registro['unidad'])
                               for t in registro.get('tickets', [])]
    validos = {m['clave'] for m in materiales if not m.get('error') and m.get('densidad_kg_m3', 0)}

    def mes(registro):
        return int(registro.get('anio') or 0) * 12 + int(registro.get('mes') or 0)

    def predominante(conteos):
        if not conteos:
            return None
        nombre, cantidad = conteos.most_common(1)[0]
        return nombre if cantidad > sum(conteos.values()) / 2 and clave_material(nombre) in validos else None

    evidencias = []
    for registro in registros:
        conteos = Counter(estandarizar_residuo(t['residuo_original'], registro['unidad'])
                          for t in registro['tickets'] if str(t['residuo_original'] or '').strip())
        evidencias.append((registro, conteos, predominante(conteos)))
    for registro, conteos, propio in evidencias:
        faltantes = [t for t in registro['tickets'] if not str(t['residuo_original'] or '').strip()]
        if not faltantes:
            continue
        candidatos = [(r, c, p) for r, c, p in evidencias
                      if r is not registro and r['unidad'] == registro['unidad'] and p]
        candidatos.sort(key=lambda e: (abs(mes(e[0]) - mes(registro)), mes(e[0]), e[0]['archivo']))
        cercanos = candidatos[:2]
        if propio:
            nombre, fuentes, metodo = propio, [(registro, conteos, propio)], 'Material predominante del mismo EDP'
        elif cercanos and len({e[2] for e in cercanos}) == 1:
            nombre, fuentes, metodo = cercanos[0][2], cercanos, 'Material predominante de los EDP más cercanos de la misma unidad'
        else:
            totales = Counter()
            for r, c, _ in evidencias:
                if r['unidad'] == registro['unidad']:
                    totales.update(c)
            nombre = predominante(totales)
            fuentes = [(r, c, p) for r, c, p in evidencias
                       if r['unidad'] == registro['unidad'] and c.get(nombre)]
            metodo = 'Material predominante de los tickets declarados de la misma unidad'
        if not nombre:
            continue
        referencias = [{'archivo': r['archivo'], 'periodo': r.get('periodo'), 'edp': r.get('edp'),
                        'tickets_material': c[nombre], 'tickets_declarados': sum(c.values())}
                       for r, c, _ in fuentes]
        detalle = '; '.join(f"EDP {r['edp']} ({r['periodo']}): {r['tickets_material']}/{r['tickets_declarados']} tickets"
                            for r in referencias)
        criterio = f'{metodo}: {nombre}. {detalle}. El tipo original está vacío; densidad de AUX según material estimado.'
        for ticket in faltantes:
            ticket.update(residuo_estimado=nombre, residuo_es_estimado=True,
                          residuo_estandarizado=nombre, criterio_estimacion_residuo=criterio,
                          referencias_estimacion_residuo=referencias)
