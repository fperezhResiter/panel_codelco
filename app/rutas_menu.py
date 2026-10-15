"""Recursos públicos del menú universal, mediante una lista de archivos concreta."""
from pathlib import Path
from urllib.parse import quote


def registrar_menu(rutas, base):
    raiz = Path(base).resolve().parents[1]
    tipos = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
             '.js': 'text/javascript; charset=utf-8', '.png': 'image/png',
             '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.ico': 'image/x-icon'}
    archivos = [raiz / 'Panel Universal.html', raiz / 'Panel Administradores Resiter/Panel Administradores.html',
                raiz / 'Panel Costos Resiter/panel_costos/Panel Costos Resiter.html']
    archivos.extend((raiz / 'Panel Costos Resiter/panel_costos/web/pages').glob('*.html'))
    carpetas = [raiz / 'portal', raiz / 'Panel Costos Resiter/panel_costos/app',
                raiz / 'Panel Costos Resiter/panel_costos/app/vendor']
    for area in ('Panel Mantenimiento/panel_mantenimiento', 'Panel Reporte Codelco/panel_codelco'):
        carpeta = raiz / area
        archivos.append(carpeta / 'Panel.html')
        archivos.extend(p for p in (carpeta / 'web/pages').glob('*.html')
                        if p.stem not in ('Login', 'Perfil', 'Panel_Configuraciones'))
        carpetas.extend(carpeta / 'web' / p for p in ('css', 'js', 'img', 'vendor', 'datos', 'publicado'))
    for carpeta in carpetas:
        if carpeta.exists():
            archivos.extend(p for p in carpeta.iterdir() if p.is_file() and p.suffix in tipos)
    for archivo in archivos:
        if archivo.is_file() and archivo.suffix in tipos:
            url = '/principal/' + quote(archivo.relative_to(raiz).as_posix(), safe='/')
            rutas[url] = (str(archivo), tipos[archivo.suffix])
    for extension, carpeta in (('css', 'css'), ('js', 'js')):
        rutas[f'/web/{carpeta}/controles-comunes.{extension}'] = (
            f'web/{carpeta}/controles-comunes.{extension}', tipos['.' + extension])
        rutas[f'/{carpeta}/controles-comunes.{extension}'] = rutas[f'/web/{carpeta}/controles-comunes.{extension}']
