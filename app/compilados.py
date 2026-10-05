"""Un PDF por unidad, período y EDP, reunidos en una descarga ZIP."""
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from .descargas import nombre_pdf, MESES


def agrupar(registros):
    grupos = defaultdict(list)
    for registro in registros:
        periodo = registro.get('periodo') or ''
        if registro.get('anio') and registro.get('mes'):
            periodo = f"{registro['anio']}-{int(registro['mes']):02d}"
        grupos[(registro.get('unidad') or '', periodo, str(registro.get('edp')))].append(registro)
    return [grupos[clave] for clave in sorted(grupos)]


def crear_zip(reportes):
    salida = BytesIO()
    with ZipFile(salida, 'w', compression=ZIP_DEFLATED) as archivo:
        for nombre, contenido in reportes:
            if nombre in archivo.namelist():
                raise ValueError('Dos reportes tienen el mismo nombre. Revisa los períodos de los EDP.')
            archivo.writestr(nombre, contenido)
        if not archivo.namelist():
            raise ValueError('No hay EDP en esta selección para generar el compilado.')
    return salida.getvalue()


def seleccion(registro):
    periodo = str(registro.get('periodo') or '')
    anio = registro.get('anio') or (periodo[:4] if periodo else '')
    mes = registro.get('mes') or (periodo[5:7] if len(periodo) == 7 else '')
    mes_nombre = MESES[int(mes) - 1].capitalize() if str(mes).isdigit() and 1 <= int(mes) <= 12 else 'Sin identificar'
    return {'Unidad': registro.get('unidad') or 'Sin identificar', 'Año': str(anio),
            'Mes': mes_nombre, 'EDP': 'EDP ' + str(registro.get('edp', 'Sin identificar'))}


def compilar_conciliacion(datos):
    from .pdf import crear_pdf, validar
    validar(datos)
    return crear_zip((nombre_pdf('conciliacion', grupo), crear_pdf({
        **datos, 'registros': grupo, 'filtros': {**datos.get('filtros', {}), **seleccion(grupo[0])}
    })) for grupo in agrupar(datos['registros']))


def compilar_densidades(datos):
    from .densidades import filtrar_reporte
    from .densidades_pdf import crear_pdf_densidades

    def reportes():
        for grupo in agrupar(datos['tickets']):
            registro = grupo[0]
            filtros = {**datos.get('filtros', {}), **{k: registro[k] for k in ('unidad', 'anio', 'mes', 'edp')}}
            reporte = filtrar_reporte({**datos, 'tickets': grupo}, filtros)
            yield nombre_pdf('densidades', grupo, unidad=datos['unidad']), crear_pdf_densidades(reporte)
    return crear_zip(reportes())


def compilar_auditoria(reporte, filtros):
    from .auditoria_pdf import crear_pdf_unidad
    registros = [r for r in reporte['estados_pago'] if all(
        str(r.get(k)) == str(v) for k, v in filtros.items() if v and k in ('anio', 'mes', 'edp'))]

    def reportes():
        for grupo in agrupar(registros):
            registro = grupo[0]
            muestras = [m for m in reporte['muestras']
                        if m['periodo'] == registro['periodo'] and m['edp'] == registro['edp']]
            detalle = seleccion(registro)
            parcial = {**reporte, 'estados_pago': grupo, 'muestras': muestras,
                       'alcance': detalle['Mes'] + ' ' + detalle['Año'] + ' | ' + detalle['EDP']}
            yield nombre_pdf('auditoria-edp', grupo, unidad=reporte['unidad']), crear_pdf_unidad(parcial)
    return crear_zip(reportes())
