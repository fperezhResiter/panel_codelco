"""Registro explícito de recursos publicados; no expone los Excel."""
ARCHIVOS_WEB = {
    '/Panel_Configuraciones.html': ('web/pages/Panel_Configuraciones.html', 'text/html; charset=utf-8'),
    '/js/configuracion.js': ('web/js/configuracion.js', 'text/javascript; charset=utf-8'),
    '/js/configuraciones_panel.js': ('web/js/configuraciones_panel.js', 'text/javascript; charset=utf-8'),
    '/Panel_Programa_Mantencion.html': ('web/pages/Panel_Programa_Mantencion.html', 'text/html; charset=utf-8'),
    '/js/programa.js': ('web/js/programa.js', 'text/javascript; charset=utf-8'),
    '/': ('Panel.html', 'text/html; charset=utf-8'),
    '/Panel.html': ('Panel.html', 'text/html; charset=utf-8'),
    '/Panel_Reportabilidad.html': ('web/pages/Panel_Reportabilidad.html', 'text/html; charset=utf-8'),
    '/Panel_repostabilidad.html': ('web/pages/Panel_Reportabilidad.html', 'text/html; charset=utf-8'),
    '/Panel_Seguimiento_KM_HR.html': ('web/pages/Panel_Seguimiento_KM_HR.html', 'text/html; charset=utf-8'),
    '/panel.css': ('web/css/panel.css', 'text/css; charset=utf-8'),
    '/reportabilidad.js': ('web/js/reportabilidad.js', 'text/javascript; charset=utf-8'),
    '/seguimiento_km_hr.js': ('web/js/seguimiento_km_hr.js', 'text/javascript; charset=utf-8'),
    '/Panel_Mantenciones.html': ('web/pages/Panel_Mantenciones.html', 'text/html; charset=utf-8'),
    '/Panel_Resumen_Mantencion.html': ('web/pages/Panel_Resumen_Mantencion.html', 'text/html; charset=utf-8'),
    '/Panel_Calendario_Mantencion.html': ('web/pages/Panel_Calendario_Mantencion.html', 'text/html; charset=utf-8'),
    '/calendario_descarga.js': ('web/js/calendario_descarga.js', 'text/javascript; charset=utf-8'),
    '/mantenciones.js': ('web/js/mantenciones.js', 'text/javascript; charset=utf-8'),
    '/mantenciones.css': ('web/css/mantenciones.css', 'text/css; charset=utf-8'),
    '/css/panel.css': ('web/css/panel.css', 'text/css; charset=utf-8'),
    '/css/mantenciones.css': ('web/css/mantenciones.css', 'text/css; charset=utf-8'),
    '/js/reportabilidad.js': ('web/js/reportabilidad.js', 'text/javascript; charset=utf-8'),
    '/js/seguimiento_km_hr.js': ('web/js/seguimiento_km_hr.js', 'text/javascript; charset=utf-8'),
    '/js/mantenciones.js': ('web/js/mantenciones.js', 'text/javascript; charset=utf-8'),
    '/js/calendario_descarga.js': ('web/js/calendario_descarga.js', 'text/javascript; charset=utf-8'),
}

# Rutas reales usadas por los enlaces relativos; conserva los accesos anteriores.
ARCHIVOS_WEB['/js/abrir_portal.js'] = ('web/js/abrir_portal.js', 'text/javascript; charset=utf-8')
for archivo, tipo in list(ARCHIVOS_WEB.values()):
    ARCHIVOS_WEB['/' + archivo] = (archivo, tipo)


