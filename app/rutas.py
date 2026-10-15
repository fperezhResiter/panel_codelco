"""Registro explícito de recursos publicados; no expone los Excel."""
ARCHIVOS_WEB = {
    '/perfil': ('web/pages/Perfil.html', 'text/html; charset=utf-8'),
    '/web/pages/Perfil.html': ('web/pages/Perfil.html', 'text/html; charset=utf-8'),
    '/web/js/perfil.js': ('web/js/perfil.js', 'text/javascript; charset=utf-8'),
    '/web/js/paneles.js': ('web/js/paneles.js', 'text/javascript; charset=utf-8'),
    '/configuraciones': ('web/pages/Panel_Configuraciones.html', 'text/html; charset=utf-8'),
    '/web/pages/Panel_Configuraciones.html': ('web/pages/Panel_Configuraciones.html', 'text/html; charset=utf-8'),
    '/web/js/configuraciones.js': ('web/js/configuraciones.js', 'text/javascript; charset=utf-8'),
    '/login': ('web/pages/Login.html', 'text/html; charset=utf-8'),
    '/web/js/login.js': ('web/js/login.js', 'text/javascript; charset=utf-8'),
    '/web/js/sesion.js': ('web/js/sesion.js', 'text/javascript; charset=utf-8'),
    '/web/pages/Panel_Volumenes.html': ('web/pages/Panel_Volumenes.html', 'text/html; charset=utf-8'),
    '/web/js/tramos_volumen.js': ('web/js/tramos_volumen.js', 'text/javascript; charset=utf-8'),
    '/': ('Panel.html', 'text/html; charset=utf-8'),
    '/Panel.html': ('Panel.html', 'text/html; charset=utf-8'),
    '/logo_sin_fondo_resiter.png': ('web/img/logo_sin_fondo_resiter.png', 'image/png'),
    '/logo_sin_fondo_codelco.png': ('web/img/logo_sin_fondo_codelco.png', 'image/png'),
    '/web/pages/Panel_Conciliacion.html': ('web/pages/Panel_Conciliacion.html', 'text/html; charset=utf-8'),
    '/web/pages/Panel_Densidades.html': ('web/pages/Panel_Densidades.html', 'text/html; charset=utf-8'),
    '/web/pages/Panel_Auditoria_EDP.html': ('web/pages/Panel_Auditoria_EDP.html', 'text/html; charset=utf-8'),
    '/web/img/logo_sin_fondo_resiter.png': ('web/img/logo_sin_fondo_resiter.png', 'image/png'),
    '/web/img/logo_sin_fondo_codelco.png': ('web/img/logo_sin_fondo_codelco.png', 'image/png'),
    '/web/css/panel.css': ('web/css/panel.css', 'text/css; charset=utf-8'),
    '/web/js/conciliacion.js': ('web/js/conciliacion.js', 'text/javascript; charset=utf-8'),
    '/web/js/densidades.js': ('web/js/densidades.js', 'text/javascript; charset=utf-8'),
    '/web/js/auditoria.js': ('web/js/auditoria.js', 'text/javascript; charset=utf-8'),
    '/web/js/abrir_portal.js': ('web/js/abrir_portal.js', 'text/javascript; charset=utf-8'),
}

# Menú y publicaciones de consulta; nunca publica motores, BD ni fuentes.
from pathlib import Path
from .rutas_menu import registrar_menu
registrar_menu(ARCHIVOS_WEB, Path(__file__).resolve().parent.parent)
