"""Un PDF por unidad, período y EDP, reunidos en una descarga ZIP."""
from collections import defaultdict
from io import BytesIO
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from .descargas import nombre_pdf, MESES


def agrupar(registros):
    grupos = defaultdict(list)
    for registro in registros:
        periodo = registro.get('periodo') or ''
        if registro.get('anio') and registro.get('mes'):
            periodo = f"{registro['anio']}-{int(registro['mes']):02d}"
        grupos[(registro.get('unidad') or '', periodo, str(registro.get('edp')))].append(registro)
    return [grupos[clave] for clave in sorted(grupos)]


def crear_zip(reportes, *, estable=False):
    salida = BytesIO()
    with ZipFile(salida, 'w', compression=ZIP_DEFLATED) as archivo:
        for nombre, contenido in reportes:
            if nombre in archivo.namelist():
                raise ValueError('Dos reportes tienen el mismo nombre. Revisa los períodos de los EDP.')
            if estable:
                entrada = ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
                entrada.compress_type = ZIP_DEFLATED
                archivo.writestr(entrada, contenido)
            else:
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


def compilar_volumenes(datos):
    from .densidades import filtrar_reporte
    from .volumenes_pdf import crear_pdf_volumenes

    def reportes():
        for grupo in agrupar(datos['tickets']):
            filtros = {**datos.get('filtros', {}), **{k: grupo[0][k] for k in ('unidad', 'anio', 'mes', 'edp')}}
            reporte = filtrar_reporte({**datos, 'tickets': grupo}, filtros)
            reporte['filtros'] = filtros
            yield nombre_pdf('distribucion-volumen', grupo, unidad=datos['unidad']), crear_pdf_volumenes(reporte)
    return crear_zip(reportes())


def filtrar_edp_auditoria(reporte, filtros):
    filtros = {k: str(v) for k, v in filtros.items() if v and k in ('unidad', 'anio', 'trimestre', 'mes', 'edp', 'estado')}
    if filtros.get('trimestre') and filtros['trimestre'] not in ('1', '2', '3', '4'):
        raise ValueError('El trimestre debe ser 1, 2, 3 o 4.')
    def coincide(registro):
        for k, valor in filtros.items():
            actual = ((int(registro['mes']) - 1) // 3 + 1 if k == 'trimestre' else
                      registro.get('estado_codigo') if k == 'estado' else registro.get(k))
            if str(actual) != valor:
                return False
        return True
    return [r for r in reporte['estados_pago'] if coincide(r)]


def compilar_auditoria(reporte, filtros, por_periodo=False, auditoria=None):
    from .auditoria_pdf import crear_pdf_unidad, tickets_completados
    registros = filtrar_edp_auditoria(reporte, filtros)

    def reportes():
        emitidos = False
        for grupo in agrupar(registros):
            registro = grupo[0]
            muestras = [m for m in reporte['muestras']
                        if m['unidad'] == registro['unidad'] and m['periodo'] == registro['periodo']
                        and str(m['edp']) == str(registro['edp'])]
            if not tickets_completados(muestras):
                continue
            detalle = seleccion(registro)
            parcial = {**reporte, 'estados_pago': grupo, 'muestras': muestras,
                       'alcance': detalle['Mes'] + ' ' + detalle['Año'] + ' | ' + detalle['EDP']}
            emitidos = True
            nombre = nombre_pdf('auditoria-edp', grupo, unidad=reporte['unidad'])
            if por_periodo:
                nombre = f'{registro["anio"]}/{int(registro["mes"]):02d}-{detalle["Mes"].lower()}/{nombre}'
            yield nombre, crear_pdf_unidad(parcial)
            if auditoria is not None:
                carpeta = nombre.removesuffix('.pdf')
                for respaldo, contenido in auditoria.archivos_respaldo(parcial):
                    yield f'{carpeta}/{respaldo}', contenido
        if not emitidos:
            raise ValueError('No hay tickets completados en la selección para generar el compilado.')
    return crear_zip(reportes())
