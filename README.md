# Panel Codelco

Portal local de Reporte Codelco con tres vistas: **Estados de pago y toneladas**, **Chequeo de densidades** y **Auditoría de tickets de EDP**. La primera concilia el ítem **1.1, retiro de residuos industriales no peligrosos**, para Andina y el ítem **2.5.a, servicio CMRIS**, para El Salvador. La tercera permite sortear tickets y registrar una revisión documental manual. Chequeo de densidades está pendiente de implementación.

## Inicio

1. La primera vez, ejecuta `Iniciar_Primera_Vez.bat` (Python 3.10 o superior).
2. Ejecuta `Actualizar_BD.bat` para crear la base inicial con los Excel de `Fuentes`.
3. Ejecuta `Iniciar_Panel.bat`.
4. Abre `Panel.html` o http://127.0.0.1:8765.
5. Selecciona **Estados de pago y toneladas** para abrir la conciliación. Usa **Volver al inicio** o la navegación superior para cambiar de vista.
6. Conserva la ventana del servidor abierta. Si el servidor ya estaba abierto al actualizar el portal, reinícialo para cargar las nuevas rutas.

En Mac, utiliza `Actualizar_BD_MAC.command` y los iniciadores `.command` equivalentes.

## Fuentes

Coloca una única versión del Excel de cada EDP en:

```text
Fuentes/
  Codelco El Salvador/
    2026 -05 EDP 47/
      EDP 47 MAYO 2026.xlsx
  Codelco Andina/
    2026 -05 EDP 12/
      EDP 12.xlsx
```

Se admiten .xlsx y .xlsm. Los temporales de Excel (~$) se omiten. Los informes ubicados directamente en Fuentes, como Reporte de RINP por densidad.xlsx, se enumeran como informes generales y no se concilian.

El lector identifica encabezados y celdas combinadas, en lugar de fijar letras de columnas. Para Andina:
- Ítem exacto 1.1 en la columna Posición.
- Hoja Avance físico: Precio (CLP/t) y Total Valor Actual EP (toneladas).
- Hoja Avance financiero: Total Valor Actual EP (monto CLP).
- Hoja 1.1: Ticket y Cantidad o Cantidad (Ton), ya expresada en toneladas.

Para El Salvador:
- Hoja DETALLE DE IMPUTACIONES, con sufijo opcional de número EP/EDP.
- Ítem exacto 2.5.a.
- Precio dentro del bloque MODIFICACIÓN N.º 1.
- EP/EDP actual del bloque AVANCE FÍSICO (toneladas).
- EP/EDP actual del bloque AVANCE FINANCIERO (monto).
- Hoja RES.NO PELIGROSO o RES.NO PELIGROSOS, columnas N.º TICKET y Peso Total (kg).

Usa la tabla Excel para delimitar los tickets; si no hay tabla, exige una fila TOTAL que marque el final. En los formatos antiguos de Andina también reconoce la fórmula SUM de cierre sin etiqueta. Se suman todas las filas de tickets, incluso las ocultas, con fecha escrita como texto o ticket 0. En Andina se excluyen filas de plantilla sin ticket, fecha ni cantidad, aunque tengan precio precargado. No se suman totales ni resúmenes inferiores y no se eliminan números repetidos. Las observaciones quedan visibles en el detalle.

## Cálculo

- Andina: toneladas de tickets = suma de Cantidad de hoja 1.1, sin dividir por 1.000.
- Andina: monto esperado = Precio de Avance físico, ítem 1.1 × toneladas de tickets.
- El Salvador: toneladas de tickets = suma de Peso Total (kg) / 1.000.
- El Salvador: monto esperado = precio Modificación N.º 1 × toneladas de tickets.
- Diferencia = monto EDP actual − monto esperado.
- También se compara tonelaje del EDP con tonelaje de tickets.
- Importes comparados a dos decimales (redondeo HALF_UP); tolerancia técnica de toneladas: 0,000001 t.
- No se aplican reajustes, IVA ni acumulados. Moneda de los EDP verificados: CLP.

Los archivos originales nunca se escriben. Se consultan los resultados guardados por Excel; si falta el resultado de una fórmula, ese EDP queda sin conciliar. Recalcula y guarda en Excel antes de actualizar el panel. Fechas de tickets que cruzan meses se conservan dentro del período de pago del EDP.

## Base de datos local

El panel de estados de pago carga el reporte desde `Datos/conciliacion.sqlite3`; abrir o recargar la página no vuelve a procesar los Excel. Cuando agregues un EDP o cambies uno existente, recalcula y guarda el Excel, ejecuta `Actualizar_BD.bat` en Windows o `Actualizar_BD_MAC.command` en Mac, y luego pulsa **Recargar datos**. El actualizador detecta archivos nuevos, modificados y eliminados, reutiliza los EDP sin cambios y reemplaza la base solo al terminar correctamente. La base guarda registros, tickets y los datos de resumen necesarios para la página. También puedes ejecutarlo desde terminal con `python actualizar_BD.py --fuentes "C:\ruta\Fuentes" --bd "C:\ruta\conciliacion.sqlite3"`.

Errores de lectura, encabezados ambiguos, pesos faltantes, tablas vacías y versiones duplicadas quedan como **Sin conciliar** y se excluyen de los totales. No se convierten en ceros. Un resultado **Cuadra** puede contener observaciones de tickets.

## Estructura conservada

- `Panel.html`: portada con las tres tarjetas de acceso e identidad Resiter.
- `web/pages/Panel_Conciliacion.html`: vista de estados de pago y toneladas.
- `web/pages/Panel_Auditoria_EDP.html` y `web/js/auditoria.js`: auditoría documental manual.
- `app/auditoria.py` y `app/auditoria_pdf.py`: lectura, muestreo, persistencia y exportaciones de auditoría.
- `web/pages/Panel_Densidades.html`: próxima vista.
- `web/css/panel.css`: estilos compartidos.
- `web/js/conciliacion.js`: filtros, gráficos, detalle y exportación.
- `app/excel.py`: lectura y normalización.
- `app/reportes.py`: cálculo y validaciones.
- `app/base_datos.py` y `actualizar_BD.py`: generación y lectura de la base SQLite.
- `app/api.py`: registro de consultas JSON.
- `app/rutas.py`: registro de archivos web.
- `app/servidor.py`: servidor HTTP local.
- `reportabilidad.py`: punto de entrada compatible.

Se retiraron los módulos de mantenimiento, kilometraje, programas y configuración que no utiliza este panel.

## Configuración y pruebas

```powershell
python reportabilidad.py --fuentes "C:\ruta\Fuentes" --puerto 8765
python -B -m unittest discover -s tests -v
```

La variable de entorno CARPETA_FUENTES también permite elegir una carpeta. El valor predeterminado es Fuentes junto a Panel.html. No se requiere .env.

La prueba opcional de integración usa PRUEBA_FUENTES y verifica los cuatro EDP de El Salvador (47–50) existentes al implementar el panel. Las regresiones de Andina cubren las hojas de avance, Cantidad en toneladas, formatos con y sin tabla, filas de plantilla, totales sin etiqueta e invalidación de resultados guardados con la regla antigua.

## PDF de la vista filtrada

El botón **Generar reporte PDF** descarga una instantánea de los EDP visibles, con indicadores, gráficos vectoriales, tabla paginada y observaciones. Usa reportlab; instala las dependencias actualizadas con el iniciador de primera vez o python -m pip install -r requirements.txt.

app/pdf.py presenta el reporte sin releer fuentes ni recalcular la conciliación. POST /api/reporte.pdf recibe la selección actual en JSON y devuelve application/pdf. Los listados de tickets no se envían al generador.

## Panel 3: auditoría de tickets de EDP

Andina usa la hoja **1.1**, con **Cantidad en toneladas**. El Salvador usa **RES.NO PELIGROSO(S)** y Peso Total en kg. Se usa el mismo límite de tickets que en la conciliación: no entran totales ni resúmenes posteriores; en Andina se omiten las filas de plantilla sin ticket, fecha ni cantidad. Las filas ocultas, tickets repetidos y registros con datos faltantes se conservan para revisión manual.

Ambas unidades permiten sortear 3, 4 o 5 tickets sin repetir filas, seleccionar uno manualmente y retomar las muestras guardadas. El PDF común de Andina es **1.1 Retiro RINSP.pdf** (también se admite **1.1 Retiro RINP.pdf**); en El Salvador es **2.5a TICKET INTERNO.pdf**. Debe estar en la carpeta del EDP correspondiente. Los campos originales y la unidad de la cantidad se conservan en las tarjetas y exportaciones.

Selecciona unidad, año, mes y un Excel de Fuentes. Se retiró la carga de otros Excel desde el panel; las revisiones anteriores se conservan.

**Sortear tickets** toma 3, 4 o 5 filas distintas de la hoja del servicio de cada unidad. También puedes pulsar **Cargar lista de tickets**, buscar por número, fila o fecha y **Revisar ticket seleccionado** para revisar un único registro. Cada revisión conserva todos los valores y celdas de origen; la cantidad y el peso total muestran sus valores sin la fórmula de Excel. No necesita la hoja de imputaciones. El período corresponde al EDP, aunque una fecha de ticket esté en otro mes. Si faltan registros suficientes para el tamaño elegido, se informa y no se crea una muestra parcial. Si el Excel cambia después de listar los tickets, se debe cargar de nuevo la lista antes de seleccionar.

Cada ticket, seleccionado o aleatorio, admite varios respaldos (PDF, imágenes, Word, Excel, CSV o texto, máximo **30 MB por archivo**). Se descargan desde su tarjeta. Tras adjuntar al menos un respaldo se habilita **Comprobé manualmente…**. También se habilita sin adjuntos si se encuentra el PDF común del servicio correspondiente directamente en la carpeta del Excel del EDP dentro de Fuentes (se toleran diferencias de mayúsculas, espacios y puntuación). El panel ofrece descargar ese PDF común y nunca usa el de otro período. Cuando se confirma una revisión usando el PDF común, guarda una copia por muestra para conservar el respaldo aunque se mueva el original. El sistema no analiza ni compara los documentos y nunca marca automáticamente la casilla. Agregar o quitar un respaldo adjunto restablece esa casilla a pendiente.

Las muestras, copias de Excel cargados, respaldos y estados se guardan en `Datos/Auditoria/auditoria.sqlite3`. El historial conserva las muestras anteriores; los cambios posteriores al Excel no modifican una muestra ya sorteada. Los Excel originales nunca se escriben. Para respaldar o trasladar el trabajo, detén el servidor y copia la carpeta `Datos/Auditoria`. Puedes configurar otra carpeta con `--auditorias`. Es almacenamiento local sin usuarios ni firmas de auditor; no uses simultáneamente una misma base SQLite desde varios equipos mediante una carpeta sincronizada.

**Generar reporte PDF** produce un resumen y fichas de los tickets, con su estado manual y listado de respaldos. **Descargar CSV** incluye las mismas filas, todos sus campos, período, fuente y estado. Ambos exportan la muestra guardada; los documentos se descargan por separado y no se incrustan en el reporte.

Rutas GET bajo `/api/auditoria`: catálogo, `/tickets?id=fuente`, `/muestra?id=…`, `/documento?id=…`, `/respaldo-edp?id=muestra`, `/reporte.pdf?id=…`, `/reporte.csv?id=…`; POST JSON `/seleccionar`, `/sortear`, `/adjuntar`, `/comprobar`, `/quitar`. `/importar` ya no está publicado. Los adjuntos se transportan como base64; el límite de solicitud incluye el tamaño codificado de un archivo de 30 MB. Las exportaciones distinguen selección manual/aleatoria e identifican el respaldo común del EDP.
