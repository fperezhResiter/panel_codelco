"""Persistencia local del reporte de conciliación en SQLite."""
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from .reportes import crear_reporte

VERSION_ESQUEMA = '1'
EXTENSIONES_EXCEL = {'.xlsx', '.xlsm', '.xls'}


def _json(datos):
    return json.dumps(datos, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _firmas_fuentes(fuentes):
    fuentes = Path(fuentes)
    resultado = {}
    if not fuentes.is_dir():
        return resultado
    for ruta in fuentes.rglob('*'):
        if not ruta.is_file() or ruta.name.startswith('~$') or ruta.suffix.lower() not in EXTENSIONES_EXCEL:
            continue
        try:
            stat = ruta.stat()
            resultado[ruta.relative_to(fuentes).as_posix()] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            resultado[ruta.relative_to(fuentes).as_posix()] = None
    return resultado


def _reutilizables(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        return {}
    try:
        with closing(sqlite3.connect(ruta)) as conexion:
            tabla = conexion.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='firmas_fuentes'"
            ).fetchone()
            if not tabla:
                return {}
            firmas = {archivo: (tamano, modificado) for archivo, tamano, modificado in conexion.execute(
                'SELECT archivo, tamano, modificado FROM firmas_fuentes'
            )}
        reporte = leer_reporte(ruta)
        return {registro['archivo']: (firmas[registro['archivo']], registro)
                for registro in reporte['registros'] if registro['archivo'] in firmas and firmas[registro['archivo']]}
    except (sqlite3.Error, KeyError, ValueError, FileNotFoundError):
        return {}


def actualizar_base_datos(fuentes, destino):
    """Lee las fuentes una vez y reemplaza la base solo si el reporte se generó bien."""
    fuentes = Path(fuentes).resolve()
    destino = Path(destino).resolve()
    destino.parent.mkdir(parents=True, exist_ok=True)
    firmas = _firmas_fuentes(fuentes)
    reporte = crear_reporte(fuentes, reutilizables=_reutilizables(destino), firmas=firmas)
    temporal = None
    try:
        descriptor, nombre = tempfile.mkstemp(prefix=destino.stem + '-', suffix='.sqlite3',
                                               dir=destino.parent)
        os.close(descriptor)
        temporal = Path(nombre)
        with closing(sqlite3.connect(temporal)) as conexion:
            with conexion:
                conexion.execute('PRAGMA journal_mode=DELETE')
                conexion.execute('PRAGMA foreign_keys=ON')
                conexion.executescript('''
                    CREATE TABLE resumen (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        datos TEXT NOT NULL
                    );
                    CREATE TABLE registros (
                        orden INTEGER PRIMARY KEY,
                        archivo TEXT NOT NULL,
                        datos TEXT NOT NULL
                    );
                    CREATE TABLE tickets (
                        registro_orden INTEGER NOT NULL REFERENCES registros(orden) ON DELETE CASCADE,
                        orden INTEGER NOT NULL,
                        datos TEXT NOT NULL,
                        PRIMARY KEY (registro_orden, orden)
                    );
                    CREATE TABLE metadatos (
                        clave TEXT PRIMARY KEY,
                        valor TEXT NOT NULL
                    );
                    CREATE TABLE firmas_fuentes (
                        archivo TEXT PRIMARY KEY,
                        tamano INTEGER NOT NULL,
                        modificado INTEGER NOT NULL
                    );
                ''')
                resumen = {k: v for k, v in reporte.items() if k != 'registros'}
                conexion.execute('INSERT INTO resumen(id, datos) VALUES (1, ?)', (_json(resumen),))
                conexion.execute('INSERT INTO metadatos(clave, valor) VALUES (?, ?)',
                                 ('version_esquema', VERSION_ESQUEMA))
                conexion.executemany(
                    'INSERT INTO firmas_fuentes(archivo, tamano, modificado) VALUES (?, ?, ?)',
                    ((registro['archivo'], *firmas[registro['archivo']])
                     for registro in reporte['registros']
                     if firmas.get(registro['archivo']) is not None)
                )
                for orden, registro in enumerate(reporte['registros']):
                    registro_sin_tickets = {k: v for k, v in registro.items() if k != 'tickets'}
                    conexion.execute('INSERT INTO registros(orden, archivo, datos) VALUES (?, ?, ?)',
                                     (orden, registro.get('archivo', ''), _json(registro_sin_tickets)))
                    conexion.executemany(
                        'INSERT INTO tickets(registro_orden, orden, datos) VALUES (?, ?, ?)',
                        ((orden, i, _json(ticket)) for i, ticket in enumerate(registro.get('tickets', [])))
                    )
        os.replace(temporal, destino)
        temporal = None
    finally:
        if temporal is not None:
            try:
                temporal.unlink()
            except OSError:
                pass
    return reporte


def registrar_firmas_existentes(ruta, fuentes):
    """Migra el reporte actual a lectura incremental sin volver a abrir los Excel."""
    ruta = Path(ruta)
    firmas = _firmas_fuentes(fuentes)
    reporte = leer_reporte(ruta)
    with closing(sqlite3.connect(ruta)) as conexion:
        with conexion:
            conexion.execute('''CREATE TABLE IF NOT EXISTS firmas_fuentes (
                archivo TEXT PRIMARY KEY,
                tamano INTEGER NOT NULL,
                modificado INTEGER NOT NULL
            )''')
            conexion.executemany(
                'INSERT OR REPLACE INTO firmas_fuentes(archivo, tamano, modificado) VALUES (?, ?, ?)',
                ((registro['archivo'], *firmas[registro['archivo']])
                 for registro in reporte['registros']
                 if firmas.get(registro['archivo']) is not None)
            )


def leer_reporte(ruta):
    """Reconstruye el JSON que consume el panel sin abrir ni recorrer Excel."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError('No existe la base de datos local. Ejecuta Actualizar_BD.bat (Windows) o Actualizar_BD_MAC.command (Mac).')
    with closing(sqlite3.connect(ruta)) as conexion:
        with conexion:
            version = conexion.execute(
                'SELECT valor FROM metadatos WHERE clave = ?', ('version_esquema',)
            ).fetchone()
            if not version or version[0] != VERSION_ESQUEMA:
                raise ValueError('La base de datos no es compatible. Ejecuta Actualizar_BD para regenerarla.')
            fila = conexion.execute('SELECT datos FROM resumen WHERE id = 1').fetchone()
            if not fila:
                raise ValueError('La base de datos no contiene un reporte. Ejecuta Actualizar_BD para regenerarla.')
            reporte = json.loads(fila[0])
            registros = []
            for orden, datos in conexion.execute('SELECT orden, datos FROM registros ORDER BY orden'):
                registro = json.loads(datos)
                registro['tickets'] = [json.loads(ticket) for (ticket,) in conexion.execute(
                    'SELECT datos FROM tickets WHERE registro_orden = ? ORDER BY orden', (orden,)
                )]
                registros.append(registro)
            reporte['registros'] = registros
            return reporte
