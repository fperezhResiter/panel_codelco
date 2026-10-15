"""Servidor HTTP local del panel de estados de pago y toneladas."""
import argparse
import json
import mimetypes
import os
import socket
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit, quote
from .rutas import ARCHIVOS_WEB
from .api import API_RUTAS
from .descargas import nombre_pdf

BASE = Path(__file__).resolve().parent.parent


class ServidorPanel(ThreadingHTTPServer):
    """Evita que dos instancias atiendan el mismo puerto en Windows."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def crear_handler(fuentes, carpeta_auditoria=None, base_datos=None, compartir_auditoria=False, usuarios=None):
    from .usuarios import Usuarios, DURACION_SESION
    usuarios = usuarios or Usuarios(BASE / 'Datos' / 'usuarios.sqlite3')
    from .auditoria import Auditoria, crear_csv, MAX_SOLICITUD
    if compartir_auditoria:
        from .auditoria_compartida import AuditoriaCompartida
        auditoria = AuditoriaCompartida(fuentes, carpeta_auditoria or BASE / 'Datos' / 'Auditoria')
    else:
        auditoria = Auditoria(fuentes, carpeta_auditoria or BASE / 'Datos' / 'Auditoria')
    base_datos = Path(base_datos or BASE / 'Datos' / 'conciliacion.sqlite3')

    class Handler(BaseHTTPRequestHandler):
        def responder(self, status, contenido, tipo, descarga=None):
            # Consumir cuerpos rechazados evita resets TCP en Windows al cerrar.
            if status >= 400 and getattr(self, 'command', '') == 'POST' and not getattr(self, 'cuerpo_leido', False):
                try:
                    longitud = int(self.headers.get('Content-Length', '0'))
                    if 0 < longitud <= MAX_SOLICITUD:
                        self.leer_cuerpo(longitud)
                except ValueError:
                    pass
            self.send_response(status)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(contenido)))
            self.send_header('Cache-Control', 'no-store')
            if getattr(self, 'cookie_respuesta', None):
                self.send_header('Set-Cookie', self.cookie_respuesta)
            if descarga:
                self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{quote(descarga, safe='')}")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(contenido)

        def leer_cuerpo(self, longitud):
            self.cuerpo_leido = True
            return self.rfile.read(longitud)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/sesion':
                sesion = self.sesion_actual()
                self.json_respuesta({'configurado': usuarios.configurado(), 'usuario': sesion['usuario'] if sesion else None})
                return
            publico = url.path in ('/login', '/web/js/login.js', '/web/css/panel.css', '/web/js/abrir_portal.js',
                                  '/web/css/controles-comunes.css', '/web/js/controles-comunes.js',
                                  '/web/img/logo_sin_fondo_resiter.png', '/web/img/logo_sin_fondo_codelco.png',
                                  '/logo_sin_fondo_resiter.png', '/logo_sin_fondo_codelco.png')
            permiso = 'configurar' if url.path in ('/configuraciones', '/web/pages/Panel_Configuraciones.html', '/web/js/configuraciones.js') or url.path.startswith('/api/configuraciones') else 'consultar'
            if not publico and not self.autorizar(permiso, pagina=url.path.endswith('.html') or url.path in ('/', '/perfil')):
                return
            if url.path == '/api/configuraciones/usuarios':
                self.json_respuesta({'usuarios': usuarios.listar()})
            elif url.path in ('/api/volumenes/reporte.pdf', '/api/volumenes/compilado.zip'):
                try:
                    from .volumenes import leer_volumenes
                    from .volumenes_pdf import crear_pdf_volumenes
                    from .compilados import compilar_volumenes
                    reporte = leer_volumenes(base_datos, parse_qs(url.query))
                    nombre = nombre_pdf('distribucion-volumen', reporte['tickets'], unidad=reporte['unidad'])
                    if url.path.endswith('.zip'):
                        self.responder(200, compilar_volumenes(reporte), 'application/zip',
                                       'compilado-' + nombre.removesuffix('.pdf') + '.zip')
                    else:
                        self.responder(200, crear_pdf_volumenes(reporte), 'application/pdf', nombre)
                except FileNotFoundError as error:
                    self.json_respuesta({'error': str(error)}, 503)
                except Exception as error:
                    self.auditoria_error(error)
            elif url.path in ('/api/densidades/reporte.pdf', '/api/densidades/compilado.zip'):
                try:
                    from .densidades import leer_densidades
                    from .densidades_pdf import crear_pdf_densidades
                    reporte = leer_densidades(base_datos, parse_qs(url.query))
                    nombre = nombre_pdf('densidades', reporte['tickets'], unidad=reporte['unidad'])
                    if url.path.endswith('.zip'):
                        from .compilados import compilar_densidades
                        self.responder(200, compilar_densidades(reporte), 'application/zip',
                                       'compilado-' + nombre.removesuffix('.pdf') + '.zip')
                    else:
                        self.responder(200, crear_pdf_densidades(reporte), 'application/pdf', nombre)
                except FileNotFoundError as error:
                    self.json_respuesta({'error': str(error)}, 503)
                except Exception as error:
                    self.auditoria_error(error)
            elif url.path.startswith('/api/auditoria'):
                self.auditoria_get(url)
            elif url.path in ARCHIVOS_WEB:
                nombre, tipo = ARCHIVOS_WEB[url.path]
                try:
                    contenido = (BASE / nombre).read_bytes()
                except OSError:
                    self.responder(404, b'Archivo del panel no disponible.', 'text/plain; charset=utf-8')
                    return
                self.responder(200, contenido, tipo)
            elif url.path in API_RUTAS:
                try:
                    datos = API_RUTAS[url.path](base_datos, parse_qs(url.query))
                    self.responder(200, json.dumps(datos, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')
                except Exception as error:
                    self.log_error('Error de lectura: %s', error)
                    if isinstance(error, (FileNotFoundError, ValueError)):
                        mensaje = str(error)
                        estado = 503
                    else:
                        mensaje = 'No se pudo leer la base de datos local. Revisa que Datos/conciliacion.sqlite3 esté disponible.'
                        estado = 500
                    self.responder(estado, json.dumps({'error': mensaje}, ensure_ascii=False).encode(), 'application/json; charset=utf-8')
            else:
                self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')

        def do_POST(self):
            ruta = urlsplit(self.path).path
            if ruta.startswith('/api/sesion/'):
                self.sesion_post(ruta)
                return
            if ruta in ('/api/configuraciones/usuarios', '/api/configuraciones/usuarios/editar'):
                if self.autorizar('configurar'):
                    self.sesion_post(ruta)
                return
            # Todo POST nuevo queda reservado al administrador, salvo estas operaciones.
            permiso = {'/api/reporte.pdf': 'descargar', '/api/conciliacion/compilado.zip': 'descargar',
                       '/api/auditoria/sortear': 'revisar', '/api/auditoria/seleccionar': 'revisar',
                       '/api/auditoria/adjuntar': 'revisar',
                       '/api/auditoria/eliminar': 'revisar',
                       '/api/auditoria/comprobar': 'comprobar', '/api/densidades/comentario': 'revisar'}.get(ruta, 'modificar')
            if not self.autorizar(permiso):
                return
            if ruta == '/api/densidades/comentario':
                self.densidades_comentario()
                return
            if urlsplit(self.path).path.startswith('/api/auditoria/'):
                self.auditoria_post(urlsplit(self.path).path)
                return
            if urlsplit(self.path).path not in ('/api/reporte.pdf', '/api/conciliacion/compilado.zip'):
                self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
                return
            try:
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('Se requiere contenido JSON.')
                longitud = int(self.headers.get('Content-Length', '0'))
                if not 0 < longitud <= 2_000_000:
                    raise ValueError('El reporte supera el tamaño permitido o está vacío.')
                contenido = json.loads(self.leer_cuerpo(longitud))
                from .pdf import crear_pdf
                if urlsplit(self.path).path.endswith('.zip'):
                    from .compilados import compilar_conciliacion
                    documento = compilar_conciliacion(contenido)
                    nombre = 'compilado-' + nombre_pdf('conciliacion', contenido['registros']).removesuffix('.pdf') + '.zip'
                    self.responder(200, documento, 'application/zip', nombre)
                else:
                    documento = crear_pdf(contenido)
                    self.responder(200, documento, 'application/pdf', nombre_pdf('conciliacion', contenido['registros']))
            except (ValueError, UnicodeDecodeError) as error:
                self.responder(400, json.dumps({'error': str(error)}).encode(), 'application/json; charset=utf-8')
            except ImportError:
                mensaje = 'Falta la dependencia PDF. Ejecuta Iniciar_Primera_Vez.bat (o su equivalente Mac) y vuelve a iniciar el panel.'
                self.responder(503, json.dumps({'error': mensaje}).encode(), 'application/json; charset=utf-8')
            except Exception as error:
                self.log_error('Error generando PDF: %s', error)
                self.responder(500, json.dumps({'error': 'No se pudo generar el PDF de esta selección.'}).encode(), 'application/json; charset=utf-8')

        def densidades_comentario(self):
            try:
                origen = self.headers.get('Origin')
                if origen and origen != 'http://' + self.headers.get('Host', ''):
                    raise ValueError('La operación debe realizarse desde el panel local.')
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('Se requiere contenido JSON.')
                longitud = int(self.headers.get('Content-Length', '0'))
                if not 0 < longitud <= 20000:
                    raise ValueError('Solicitud inválida.')
                datos = json.loads(self.leer_cuerpo(longitud))
                if not isinstance(datos, dict):
                    raise ValueError('Solicitud inválida.')
                from .densidades import guardar_comentario
                self.json_respuesta(guardar_comentario(base_datos, datos, self.sesion_actual()['usuario']))
            except PermissionError as error:
                self.json_respuesta({'error': str(error)}, 403)
            except (ValueError, UnicodeDecodeError) as error:
                self.json_respuesta({'error': str(error)}, 400)
            except Exception as error:
                self.auditoria_error(error)

        def json_respuesta(self, datos, status=200):
            self.responder(status, json.dumps(datos, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')

        def token_actual(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                return cookie['panel_sesion'].value if 'panel_sesion' in cookie else ''
            except Exception:
                return ''

        def sesion_actual(self):
            return usuarios.sesion(self.token_actual())

        def autorizar(self, permiso, pagina=False):
            sesion = self.sesion_actual()
            if not sesion:
                if pagina:
                    self.send_response(302)
                    self.send_header('Location', '/login')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                else:
                    self.json_respuesta({'error': 'Inicia sesión para acceder al panel.'}, 401)
                return False
            if permiso not in sesion['usuario']['permisos']:
                self.json_respuesta({'error': 'Tu usuario no tiene permiso para realizar esta operación.'}, 403)
                return False
            return True

        def sesion_post(self, ruta):
            try:
                origen = self.headers.get('Origin')
                if origen and origen != 'http://' + self.headers.get('Host', ''):
                    raise ValueError('La operación debe realizarse desde el panel local.')
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('Se requiere contenido JSON.')
                longitud = int(self.headers.get('Content-Length', '0'))
                if not 0 < longitud <= 4096:
                    raise ValueError('Solicitud inválida.')
                datos = json.loads(self.leer_cuerpo(longitud))
                if not isinstance(datos, dict):
                    raise ValueError('Solicitud inválida.')
                if ruta == '/api/sesion/configurar':
                    usuarios.inicializar(datos)
                    self.json_respuesta({'ok': True})
                elif ruta == '/api/sesion/ingresar':
                    token = usuarios.ingresar(datos.get('usuario'), datos.get('password'))
                    self.cookie_respuesta = f'panel_sesion={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={DURACION_SESION}'
                    self.json_respuesta({'usuario': usuarios.sesion(token)['usuario']})
                elif ruta == '/api/sesion/salir':
                    usuarios.salir(self.token_actual())
                    self.cookie_respuesta = 'panel_sesion=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
                    self.json_respuesta({'ok': True})
                elif ruta == '/api/sesion/password':
                    if not self.sesion_actual():
                        self.json_respuesta({'error': 'Inicia sesión para cambiar tu contraseña.'}, 401)
                        return
                    usuarios.cambiar_password(self.token_actual(), datos.get('actual'), datos.get('nueva'))
                    self.cookie_respuesta = 'panel_sesion=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
                    self.json_respuesta({'ok': True})
                elif ruta == '/api/sesion/vista':
                    if not self.sesion_actual():
                        self.json_respuesta({'error': 'Inicia sesión para acceder al panel.'}, 401)
                        return
                    self.json_respuesta({'usuario': usuarios.cambiar_vista(self.token_actual(), datos.get('general'))})
                elif ruta == '/api/configuraciones/usuarios':
                    self.json_respuesta({'usuario': usuarios.agregar(datos)}, 201)
                elif ruta == '/api/configuraciones/usuarios/editar':
                    usuario = usuarios.editar(datos)
                    self.json_respuesta({'usuario': usuario, 'sesion_cerrada': self.sesion_actual() is None})
                else:
                    self.json_respuesta({'error': 'Ruta no disponible.'}, 404)
            except (ValueError, UnicodeDecodeError) as error:
                self.json_respuesta({'error': str(error)}, 400)
            except PermissionError as error:
                self.json_respuesta({'error': str(error)}, 403)

        def obtener_muestra(self, identificador):
            preview = (self.sesion_actual() or {}).get('preview')
            return preview if preview and preview['id'] == identificador else auditoria.obtener(identificador)

        def auditoria_error(self, error):
            if isinstance(error, ValueError):
                self.json_respuesta({'error': str(error)}, 400)
            elif isinstance(error, ImportError):
                self.json_respuesta({'error': 'Falta la dependencia PDF. Ejecuta el iniciador de primera vez y reinicia el panel.'}, 503)
            else:
                self.log_error('Error de auditoría: %s', error)
                self.json_respuesta({'error': 'No se pudo completar la operación. Revisa que el archivo esté disponible y que la carpeta Datos permita guardar.'}, 500)

        def auditoria_get(self, url):
            try:
                identificador = parse_qs(url.query).get('id', [''])[0]
                if url.path == '/api/auditoria':
                    self.json_respuesta(auditoria.catalogo())
                elif url.path == '/api/auditoria/muestra':
                    self.json_respuesta(self.obtener_muestra(identificador))
                elif url.path == '/api/auditoria/tickets':
                    if not self.autorizar('revisar'):
                        return
                    self.json_respuesta(auditoria.listar_tickets(identificador))
                elif url.path == '/api/auditoria/respaldo-edp':
                    muestra = self.obtener_muestra(identificador)
                    with auditoria.conexion() as db:
                        nombre, contenido = auditoria.leer_respaldo_edp(muestra, db)
                    self.responder(200, contenido, mimetypes.guess_type(nombre)[0] or 'application/octet-stream', nombre)
                elif url.path == '/api/auditoria/documento':
                    nombre, contenido = auditoria.documento(identificador)
                    self.responder(200, contenido, 'application/octet-stream', nombre)
                elif url.path == '/api/auditoria/respaldo-ticket':
                    fila = int(parse_qs(url.query).get('fila', ['0'])[0])
                    nombre, contenido = auditoria.documento_ticket(identificador, fila)
                    self.responder(200, contenido, mimetypes.guess_type(nombre)[0] or 'application/octet-stream', nombre)
                elif url.path in ('/api/auditoria/unidad.pdf', '/api/auditoria/unidad.zip', '/api/auditoria/compilado.zip'):
                    unidad = parse_qs(url.query).get('unidad', [''])[0]
                    from .auditoria_pdf import crear_pdf_unidad, seleccionar_edp
                    reporte = auditoria.reporte_unidad(unidad)
                    filtros = {k: v[0] for k, v in parse_qs(url.query).items() if k in ('anio', 'trimestre', 'mes', 'edp', 'estado')}
                    if url.path.endswith('.zip'):
                        from .compilados import compilar_auditoria, filtrar_edp_auditoria
                        por_periodo = url.path == '/api/auditoria/compilado.zip'
                        if url.path == '/api/auditoria/unidad.zip':
                            reporte = seleccionar_edp(reporte, filtros)
                        registros = filtrar_edp_auditoria(reporte, filtros)
                        nombre = 'compilado-' + nombre_pdf('auditoria-edp', registros, unidad=unidad).removesuffix('.pdf') + '.zip'
                        self.responder(200, compilar_auditoria(reporte, filtros, por_periodo=por_periodo, auditoria=auditoria), 'application/zip', nombre)
                    else:
                        reporte = seleccionar_edp(reporte, filtros)
                        self.responder(200, crear_pdf_unidad(reporte), 'application/pdf',
                                       nombre_pdf('auditoria-edp', reporte['estados_pago'], unidad=unidad))
                elif url.path in ('/api/auditoria/reporte.pdf', '/api/auditoria/reporte.zip', '/api/auditoria/reporte.csv'):
                    muestra = self.obtener_muestra(identificador)
                    nombre = f'auditoria-{muestra["unidad"]}-{muestra["periodo"]}-EDP{muestra["edp"]}-{muestra["id"][:8]}'
                    if url.path.endswith('.zip'):
                        from .compilados import compilar_auditoria
                        reporte = auditoria.reporte_unidad(muestra['unidad'])
                        filtros = {k: muestra[k] for k in ('anio', 'mes', 'edp')}
                        nombre = nombre_pdf('auditoria-edp', [muestra], unidad=muestra['unidad']).removesuffix('.pdf') + '.zip'
                        self.responder(200, compilar_auditoria(reporte, filtros, auditoria=auditoria), 'application/zip', nombre)
                    elif url.path.endswith('.pdf'):
                        from .auditoria_pdf import crear_pdf_unidad, seleccionar_edp
                        reporte = seleccionar_edp(auditoria.reporte_unidad(muestra['unidad']), muestra)
                        self.responder(200, crear_pdf_unidad(reporte), 'application/pdf',
                                       nombre_pdf('auditoria-edp', reporte['estados_pago'], unidad=muestra['unidad']))
                    else:
                        self.responder(200, crear_csv(muestra), 'text/csv; charset=utf-8', nombre + '.csv')
                else:
                    self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
            except Exception as error:
                self.auditoria_error(error)

        def auditoria_post(self, ruta):
            permiso = 'revisar' if ruta in ('/api/auditoria/seleccionar', '/api/auditoria/sortear', '/api/auditoria/adjuntar', '/api/auditoria/eliminar') else 'comprobar' if ruta == '/api/auditoria/comprobar' else 'modificar'
            if not self.autorizar(permiso):
                return
            try:
                # El panel local recibe JSON del mismo origen, nunca formularios de otros sitios.
                origen = self.headers.get('Origin')
                if origen and origen != 'http://' + self.headers.get('Host', ''):
                    raise ValueError('La operación debe realizarse desde el panel local.')
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('Se requiere contenido JSON.')
                longitud = int(self.headers.get('Content-Length', '0'))
                if not 0 < longitud <= MAX_SOLICITUD:
                    raise ValueError('La solicitud está vacía o supera el tamaño permitido (30 MB por archivo).')
                datos = json.loads(self.leer_cuerpo(longitud))
                if not isinstance(datos, dict):
                    raise ValueError('La solicitud debe ser un objeto JSON.')
                if ruta == '/api/auditoria/seleccionar':
                    resultado = auditoria.seleccionar(datos, guardar='revisar' in self.sesion_actual()['usuario']['permisos'])
                elif ruta == '/api/auditoria/sortear':
                    resultado = auditoria.sortear(datos, guardar='revisar' in self.sesion_actual()['usuario']['permisos'])
                elif ruta == '/api/auditoria/eliminar':
                    resultado = auditoria.eliminar(datos)
                elif ruta.rsplit('/', 1)[-1] in ('adjuntar', 'comprobar', 'quitar'):
                    resultado = auditoria.modificar(datos, ruta.rsplit('/', 1)[-1])
                else:
                    self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
                    return
                if resultado.get('preview'):
                    self.sesion_actual()['preview'] = resultado
                self.json_respuesta(resultado)
            except Exception as error:
                self.auditoria_error(error)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fuentes', type=Path, default=Path(os.environ.get('CARPETA_FUENTES', BASE / 'Fuentes')),
                        help='Carpeta Fuentes organizada por unidad, año y EDP mensual.')
    parser.add_argument('--puerto', type=int, default=8765)
    parser.add_argument('--sin-abrir', action='store_true', help='Iniciar sin abrir el navegador automáticamente.')
    parser.add_argument('--auditorias', type=Path, default=Path(os.environ.get('CARPETA_AUDITORIAS', BASE / 'Datos' / 'Auditoria')),
                        help='Carpeta persistente de muestras y respaldos de auditoría.')
    parser.add_argument('--auditoria-local', action='store_true',
                        help='Usar SQLite local sin compartir cambios entre equipos.')
    parser.add_argument('--bd', type=Path, default=BASE / 'Datos' / 'conciliacion.sqlite3',
                        help='Base SQLite del panel de estados de pago y toneladas.')
    args = parser.parse_args()
    try:
        servidor = ServidorPanel(('127.0.0.1', args.puerto), crear_handler(
            args.fuentes.resolve(), args.auditorias.resolve(), args.bd.resolve(),
            compartir_auditoria=not args.auditoria_local))
    except OSError as error:
        print(f'No se pudo iniciar el panel en el puerto {args.puerto}: {error}', flush=True)
        print('Detén la otra instancia o utiliza --puerto 8766.', flush=True)
        raise SystemExit(1)
    print(f'Panel disponible en http://127.0.0.1:{servidor.server_address[1]} | Ctrl+C para detener', flush=True)
    print(f'Fuentes: {args.fuentes.resolve()}', flush=True)
    print(f'Base de datos: {args.bd.resolve()}', flush=True)
    print(f'Auditoría: {args.auditorias.resolve()} | ' +
          ('BD local' if args.auditoria_local else 'Cambios compartidos por SharePoint/OneDrive'), flush=True)
    if not args.sin_abrir:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{servidor.server_address[1]}/Panel.html')
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == '__main__':
    main()
