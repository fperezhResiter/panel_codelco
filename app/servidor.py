"""Servidor HTTP local del panel de estados de pago y toneladas."""
import argparse
import json
import os
import socket
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit, quote
from .rutas import ARCHIVOS_WEB
from .api import API_RUTAS

BASE = Path(__file__).resolve().parent.parent


class ServidorPanel(ThreadingHTTPServer):
    """Evita que dos instancias atiendan el mismo puerto en Windows."""
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def crear_handler(fuentes, carpeta_auditoria=None):
    from .auditoria import Auditoria, crear_csv, MAX_SOLICITUD
    auditoria = Auditoria(fuentes, carpeta_auditoria or BASE / 'Datos' / 'Auditoria')

    class Handler(BaseHTTPRequestHandler):
        def responder(self, status, contenido, tipo, descarga=None):
            self.send_response(status)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(contenido)))
            self.send_header('Cache-Control', 'no-store')
            if descarga:
                self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{quote(descarga, safe='')}")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(contenido)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path.startswith('/api/auditoria'):
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
                    datos = API_RUTAS[url.path](fuentes, parse_qs(url.query))
                    self.responder(200, json.dumps(datos, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')
                except Exception as error:
                    self.log_error('Error de lectura: %s', error)
                    mensaje = 'No se pudieron leer las fuentes. Revisa su disponibilidad local y los permisos de la carpeta.'
                    self.responder(500, json.dumps({'error': mensaje}).encode(), 'application/json; charset=utf-8')
            else:
                self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')

        def do_POST(self):
            if urlsplit(self.path).path.startswith('/api/auditoria/'):
                self.auditoria_post(urlsplit(self.path).path)
                return
            if urlsplit(self.path).path != '/api/reporte.pdf':
                self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
                return
            try:
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('Se requiere contenido JSON.')
                longitud = int(self.headers.get('Content-Length', '0'))
                if not 0 < longitud <= 2_000_000:
                    raise ValueError('El reporte supera el tamaño permitido o está vacío.')
                contenido = json.loads(self.rfile.read(longitud))
                from .pdf import crear_pdf
                documento = crear_pdf(contenido)
                self.responder(200, documento, 'application/pdf', 'reporte-codelco.pdf')
            except (ValueError, UnicodeDecodeError) as error:
                self.responder(400, json.dumps({'error': str(error)}).encode(), 'application/json; charset=utf-8')
            except ImportError:
                mensaje = 'Falta la dependencia PDF. Ejecuta Iniciar_Primera_Vez.bat (o su equivalente Mac) y vuelve a iniciar el panel.'
                self.responder(503, json.dumps({'error': mensaje}).encode(), 'application/json; charset=utf-8')
            except Exception as error:
                self.log_error('Error generando PDF: %s', error)
                self.responder(500, json.dumps({'error': 'No se pudo generar el PDF de esta selección.'}).encode(), 'application/json; charset=utf-8')

        def json_respuesta(self, datos, status=200):
            self.responder(status, json.dumps(datos, ensure_ascii=False, allow_nan=False).encode(), 'application/json; charset=utf-8')

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
                    self.json_respuesta(auditoria.obtener(identificador))
                elif url.path == '/api/auditoria/tickets':
                    self.json_respuesta(auditoria.listar_tickets(identificador))
                elif url.path == '/api/auditoria/respaldo-edp':
                    nombre, contenido = auditoria.documento_edp(identificador)
                    self.responder(200, contenido, 'application/pdf', nombre)
                elif url.path == '/api/auditoria/documento':
                    nombre, contenido = auditoria.documento(identificador)
                    self.responder(200, contenido, 'application/octet-stream', nombre)
                elif url.path in ('/api/auditoria/reporte.pdf', '/api/auditoria/reporte.csv'):
                    muestra = auditoria.obtener(identificador)
                    nombre = f'auditoria-{muestra["unidad"]}-{muestra["periodo"]}-EDP{muestra["edp"]}-{muestra["id"][:8]}'
                    if url.path.endswith('.pdf'):
                        from .auditoria_pdf import crear_pdf_auditoria
                        self.responder(200, crear_pdf_auditoria(muestra), 'application/pdf', nombre + '.pdf')
                    else:
                        self.responder(200, crear_csv(muestra), 'text/csv; charset=utf-8', nombre + '.csv')
                else:
                    self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
            except Exception as error:
                self.auditoria_error(error)

        def auditoria_post(self, ruta):
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
                datos = json.loads(self.rfile.read(longitud))
                if not isinstance(datos, dict):
                    raise ValueError('La solicitud debe ser un objeto JSON.')
                if ruta == '/api/auditoria/seleccionar':
                    resultado = auditoria.seleccionar(datos)
                elif ruta == '/api/auditoria/sortear':
                    resultado = auditoria.sortear(datos)
                elif ruta.rsplit('/', 1)[-1] in ('adjuntar', 'comprobar', 'quitar'):
                    resultado = auditoria.modificar(datos, ruta.rsplit('/', 1)[-1])
                else:
                    self.responder(404, b'No encontrado', 'text/plain; charset=utf-8')
                    return
                self.json_respuesta(resultado)
            except Exception as error:
                self.auditoria_error(error)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fuentes', type=Path, default=Path(os.environ.get('CARPETA_FUENTES', BASE / 'Fuentes')),
                        help='Carpeta con unidades, períodos y archivos EDP.')
    parser.add_argument('--puerto', type=int, default=8765)
    parser.add_argument('--auditorias', type=Path, default=BASE / 'Datos' / 'Auditoria',
                        help='Carpeta persistente de muestras y respaldos de auditoría.')
    args = parser.parse_args()
    try:
        servidor = ServidorPanel(('127.0.0.1', args.puerto), crear_handler(args.fuentes.resolve(), args.auditorias.resolve()))
    except OSError as error:
        print(f'No se pudo iniciar el panel en el puerto {args.puerto}: {error}', flush=True)
        print('Detén la otra instancia o utiliza --puerto 8766.', flush=True)
        raise SystemExit(1)
    print(f'Panel disponible en http://127.0.0.1:{servidor.server_address[1]} | Ctrl+C para detener', flush=True)
    print(f'Fuentes: {args.fuentes.resolve()}', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == '__main__':
    main()
