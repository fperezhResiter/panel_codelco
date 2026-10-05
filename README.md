# Panel Codelco

Portal local de Reporte Codelco con tres vistas: **Estados de pago y toneladas**, **Chequeo de densidades** y **Auditoría de tickets de EDP**. La primera concilia el ítem **1.1, retiro de residuos industriales no peligrosos**, para Andina y el ítem **2.5.a, servicio CMRIS**, para El Salvador. La segunda chequea el volumen de los tickets de ambas unidades con su densidad promedio. La tercera permite sortear tickets y registrar una revisión documental manual.

## Inicio

1. La primera vez, ejecuta `Iniciar_Primera_Vez.bat` (Python 3.10 o superior).
2. Ejecuta `Actualizar_BD.bat` para crear la base inicial con los Excel de `Fuentes`.
3. Ejecuta `Iniciar_Panel.bat`.
4. Abre `Panel.html` o http://127.0.0.1:8765.
5. Selecciona **Estados de pago y toneladas** para abrir la conciliación. Usa **Volver al inicio** o la navegación superior para cambiar de vista.
6. Conserva la ventana del servidor abierta. Si el servidor ya estaba abierto al actualizar el portal, reinícialo para cargar las nuevas rutas.

En Mac, utiliza `scripts/mac/Actualizar_BD_MAC.command` y los iniciadores `.command` equivalentes de `scripts/mac/`.

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

Se admiten .xlsx y .xlsm. Los temporales de Excel (~$) se omiten. Los informes ubicados directamente en Fuentes no se concilian como EDP. **Reporte de RINP por densidad.xlsx** se importa además como maestra para el chequeo de densidades.

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
- Si falta la columna N.º TICKET, se admite ID MINIMIZA como identificador. Si están ambas, se usa N.º TICKET. Los identificadores vacíos siguen dejando el EDP sin conciliar; la alternativa también se admite en auditoría y se informa como observación.

Usa la tabla Excel para delimitar los tickets; si no hay tabla, exige una fila TOTAL que marque el final. En los formatos antiguos de Andina también reconoce la fórmula SUM de cierre sin etiqueta. Se suman todas las filas de tickets, incluso las ocultas, con fecha escrita como texto o ticket 0. En Andina se excluyen filas de plantilla sin ticket, fecha ni cantidad, aunque tengan precio precargado. No se suman totales ni resúmenes inferiores y no se eliminan números repetidos. Las observaciones quedan visibles en el detalle.

## Exportar los PDF de una unidad a ZIP

Ejecuta el script independiente desde la carpeta principal:

```powershell
python scripts/exportar_pdfs.py
```

Ingresa **1 / Andina** o **2 / El Salvador**. Recorre todas las subcarpetas de la unidad seleccionada en `Fuentes` e incluye todos sus PDF, conservando las carpetas de cada EDP. El ZIP se guarda en la carpeta principal, al mismo nivel que `scripts`, con la unidad y la fecha/hora en el nombre. Los originales se conservan y cada ejecución genera un ZIP nuevo. No requiere iniciar el panel ni instalar dependencias adicionales.

También puedes indicar la unidad directamente con `python scripts/exportar_pdfs.py --unidad salvador` (o `andina`). Para otras ubicaciones, admite `--fuentes "C:\ruta\Fuentes"` y `--salida "C:\ruta\destino"`. Si no hay PDF o falla la lectura de un archivo o carpeta, informa el error y no entrega un ZIP parcial.

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

El panel de estados de pago carga el reporte desde `Datos/conciliacion.sqlite3`; abrir o recargar la página no vuelve a procesar los Excel. Cuando agregues un EDP o cambies uno existente, recalcula y guarda el Excel, ejecuta `Actualizar_BD.bat` en Windows o `scripts/mac/Actualizar_BD_MAC.command` en Mac, y luego pulsa **Recargar datos**. El actualizador detecta archivos nuevos, modificados y eliminados, reutiliza los EDP sin cambios y reemplaza la base solo al terminar correctamente. La base guarda registros, tickets y los datos de resumen necesarios para la página. También puedes ejecutarlo desde terminal con `python -B -m app.actualizar_BD --fuentes "C:\ruta\Fuentes" --bd "C:\ruta\conciliacion.sqlite3"`.

Errores de lectura, encabezados ambiguos, pesos faltantes, tablas vacías y versiones duplicadas quedan como **Sin conciliar** y se excluyen de los totales. No se convierten en ceros. Un resultado **Cuadra** puede contener observaciones de tickets.

## Estructura de carpetas

La carpeta principal contiene solo los tres iniciadores de Windows, `Panel.html`, `manual_usuario.md` y `README.md`. Los archivos auxiliares se organizan así:

- `app/`: código Python, incluidos los puntos de entrada del servidor y del actualizador.
- `config/`: dependencias (`requirements.txt`) y configuración auxiliar.
- `scripts/mac/`: los tres iniciadores de macOS; se pueden abrir desde esa carpeta.
- `web/`: páginas, estilos, JavaScript y logos en `web/img/`.
- `Fuentes/`: archivos originales de los EDP y maestra de densidades.
- `Datos/`: base de datos y revisiones de auditoría.
- `tests/`: pruebas del panel.
- `tmp/`: archivos temporales de trabajo.

- `Panel.html`: portada con las tres tarjetas de acceso e identidad Resiter.
- `web/pages/Panel_Conciliacion.html`: vista de estados de pago y toneladas.
- `web/pages/Panel_Auditoria_EDP.html` y `web/js/auditoria.js`: auditoría documental manual.
- `app/auditoria.py` y `app/auditoria_pdf.py`: lectura, muestreo, persistencia y exportaciones de auditoría.
- `app/auditoria_compartida.py`: BD local y sincronización de comprobaciones por la carpeta compartida de SharePoint/OneDrive.
- `web/pages/Panel_Densidades.html` y `web/js/densidades.js`: chequeo de volumen por ticket de El Salvador y Andina.
- `app/densidades.py` y `app/densidades_pdf.py`: importación de la maestra, consulta desde BD, cálculo y reporte PDF.
- `web/css/panel.css`: estilos compartidos.
- `web/js/conciliacion.js`: filtros, gráficos, detalle y exportación.
- `app/excel.py`: lectura y normalización.
- `app/reportes.py`: cálculo y validaciones.
- `app/base_datos.py` y `app/actualizar_BD.py`: generación y lectura de la base SQLite.
- `app/api.py`: registro de consultas JSON.
- `app/rutas.py`: registro de archivos web.
- `app/servidor.py`: servidor HTTP local.
- `app/reportabilidad.py`: punto de entrada compatible.

Se retiraron los módulos de mantenimiento, kilometraje, programas y configuración que no utiliza este panel.

## Configuración y pruebas

```powershell
python -B -m app.reportabilidad --fuentes "C:\ruta\Fuentes" --puerto 8765
python -B -m unittest discover -s tests -v
```

La variable de entorno CARPETA_FUENTES también permite elegir una carpeta. El valor predeterminado es Fuentes junto a Panel.html. No se requiere .env.

La prueba opcional de integración usa PRUEBA_FUENTES y verifica los cuatro EDP de El Salvador (47–50) existentes al implementar el panel. Las regresiones de Andina cubren las hojas de avance, Cantidad en toneladas, formatos con y sin tabla, filas de plantilla, totales sin etiqueta e invalidación de resultados guardados con la regla antigua.

## PDF de la vista filtrada

El botón **Generar reporte PDF** descarga una instantánea de los EDP visibles, con indicadores, gráficos vectoriales, tabla paginada y observaciones. Usa reportlab; instala las dependencias actualizadas con el iniciador de primera vez o python -m pip install -r config/requirements.txt.

app/pdf.py presenta el reporte sin releer fuentes ni recalcular la conciliación. POST /api/reporte.pdf recibe la selección actual en JSON y devuelve application/pdf. Los listados de tickets no se envían al generador.

## Chequeo de densidades de El Salvador y Andina

**Actualizar_BD** importa la hoja **Aux** de `Fuentes/Reporte de RINP por densidad.xlsx` en la tabla `maestra_densidades` de la misma BD SQLite. Se conserva cada material, densidad inferior, superior, promedio y celdas de origen. El promedio es la densidad utilizada, en kg/m³. No se importan los tickets históricos de ese Excel: se usan los tickets de los EDP de El Salvador y Andina guardados en la BD. Las consultas del panel y del PDF nunca abren Excel. La maestra se vuelve a importar al actualizar la BD, aunque los EDP no hayan cambiado.

Volumen = Peso Total (kg) / densidad promedio (kg/m³). Coincide en verde si está dentro de **12–18**, **17–23** o **27–33 m³**, incluidos los límites. Se informa la capacidad correspondiente: **15, 20 o 30 m³**. Si coincide con dos ventanas, se asigna la capacidad más cercana y se muestran ambas compatibilidades; en un empate se asigna la menor. Se evalúa sin redondear y se prioriza siempre la coincidencia: 14 m³ es verde. Fuera de todas las ventanas, un volumen **menor a 15 m³** queda amarillo **No coincide con volumen menor**; uno **mayor a 15 m³** queda rojo **No coincide con volumen mayor**. Pesos faltantes o negativos, materiales ausentes, densidades no positivas, fórmulas sin resultado y materiales duplicados quedan gris **Sin evaluar**, con el motivo. Un peso cero válido calcula 0 m³ y queda amarillo. Estos cuatro estados se usan en filtros, indicadores, gráficos, PDF y CSV. La clasificación se calcula al consultar los tickets y la maestra guardados en BD; este cambio de estados no requiere volver a importar Excel.

Andina usa **Cantidad (toneladas) × 1.000 / densidad promedio** de sus tickets de la hoja **1.1**, con Tipo de Producto o Residuo. Sus capacidades son **13, 20 y 40 m³**, con ventanas inclusivas de **10–16, 17–23 y 37–43 m³**. Fuera de todas las ventanas, menos de 13 m³ queda amarillo y más de 13 m³ queda rojo; por ejemplo, 16,5 m³ queda rojo. Los datos faltantes quedan gris. La unidad seleccionada determina las bandas, indicadores, filtros, gráficos y exportaciones.

Los residuos se estandarizan antes de buscar su densidad. Se unifican tildes, espacios, mayúsculas, fracciones finales como `(1/2)` y variantes conocidas: «Asimable a RINP» → «Asimilable a RINP», «Aceite» → «Aceite en desuso», «Goma» → «Gomas en desuso», singulares/plurales de madera, chatarra, cartones, plástico y filtros. Solo en Andina, **RINP Granel** corresponde a **Asimilable a RINP**, según la equivalencia confirmada: AUX tiene 350 y 600 kg/m³, cuyo promedio es **475 kg/m³**. **Polvo Roca** corresponde a **Polvo de roca**, con 1.500 y 2.000 kg/m³ en AUX, promedio **1.750 kg/m³**. `app/residuos.py` mantiene las equivalencias. Los calificativos que cambian el material, como «Madera contaminada», se conservan. Los tipos declarados sin equivalencia en AUX siguen sin evaluar. La BD conserva `residuo_original` y `residuo_estandarizado`; el panel de densidades, sus filtros, gráficos, PDF y CSV usan el nombre estándar y permiten consultar el original. Las fracciones no modifican el peso ni eliminan filas. Los tickets 0, filas ocultas y tickets repetidos se conservan. Se leen tickets aunque falte la imputación financiera del EDP, y se muestran sus advertencias.

Al actualizar la BD, `app/estimaciones.py` estima únicamente los tipos vacíos, según lo autorizado. Usa el material mayoritario entre los tickets declarados del mismo EDP; si no existe, busca acuerdo entre los materiales mayoritarios de los dos EDP más cercanos en meses de la misma unidad. Si no concuerdan, usa la mayoría de los tickets declarados de esa unidad. Solo se elige un material con densidad válida en AUX y mayoría superior al 50%; sin evidencia suficiente, el ticket sigue sin evaluar. Las estimaciones anteriores nunca cuentan como evidencia, los pesos no intervienen en la elección y no se busca una densidad que fuerce la coincidencia de volumen. En los EDP 39 y 41 de Andina de 2025, los 316 tipos vacíos usan **Asimilable a RINP / 475 kg/m³**, respaldados por los EDP cercanos que declaran RINP Granel. Se guardan el tipo original vacío, `residuo_estimado`, `residuo_es_estimado`, `criterio_estimacion_residuo` y las referencias de los EDP utilizados. El panel, PDF y CSV distinguen estas estimaciones de los tipos declarados. Una corrección posterior del tipo en Excel reemplaza la estimación al actualizar la BD.

La vista incluye selector de unidad (El Salvador por defecto), filtros por año, mes, EDP, residuo, resultado y capacidad, buscador, indicadores, gráficos de resultados/capacidades y volumen por ticket con ventanas permitidas. La tabla muestra 100 filas por página; el **PDF** y el **CSV** incluyen toda la selección. El PDF incorpora unidad, filtros, indicadores, tres gráficos, tabla paginada, observaciones y maestra utilizada. Rutas: `GET /api/densidades`, `GET /api/densidades/reporte.pdf`, con los mismos parámetros de filtro; `unidad=Andina` selecciona Andina.

## Panel 3: auditoría de tickets de EDP

Andina usa la hoja **1.1**, con **Cantidad en toneladas**. El Salvador usa **RES.NO PELIGROSO(S)** y Peso Total en kg. Se usa el mismo límite de tickets que en la conciliación: no entran totales ni resúmenes posteriores; en Andina se omiten las filas de plantilla sin ticket, fecha ni cantidad. Las filas ocultas, tickets repetidos y registros con datos faltantes se conservan para revisión manual.

Ambas unidades permiten sortear 3, 4 o 5 tickets sin repetir filas, seleccionar uno manualmente y retomar las muestras guardadas. El PDF común de Andina es **1.1 Retiro RINSP.pdf** (también se admite **1.1 Retiro RINP.pdf**); en El Salvador es **2.5a TICKET INTERNO.pdf**. Debe estar en la carpeta del EDP correspondiente. Los campos originales y la unidad de la cantidad se conservan en las tarjetas y exportaciones.

Selecciona unidad, año, mes y un Excel de Fuentes. Se retiró la carga de otros Excel desde el panel; las revisiones anteriores se conservan.

**Sortear tickets** toma 3, 4 o 5 filas distintas de la hoja del servicio de cada unidad. También puedes pulsar **Cargar lista de tickets**, buscar por número, fila o fecha y **Revisar ticket seleccionado** para revisar un único registro. Cada revisión conserva todos los valores y celdas de origen; la cantidad y el peso total muestran sus valores sin la fórmula de Excel. No necesita la hoja de imputaciones. El período corresponde al EDP, aunque una fecha de ticket esté en otro mes. Si faltan registros suficientes para el tamaño elegido, se informa y no se crea una muestra parcial. Si el Excel cambia después de listar los tickets, se debe cargar de nuevo la lista antes de seleccionar.

Cada ticket, seleccionado o aleatorio, admite varios respaldos (PDF, imágenes, Word, Excel, CSV o texto, máximo **30 MB por archivo**). Se descargan desde su tarjeta. Tras adjuntar al menos un respaldo se habilita **Comprobé manualmente…**. También se habilita sin adjuntos si se encuentra el PDF común del servicio correspondiente directamente en la carpeta del Excel del EDP dentro de Fuentes (se toleran diferencias de mayúsculas, espacios y puntuación). El panel ofrece descargar ese PDF común y nunca usa el de otro período. Cuando se confirma una revisión usando el PDF común, guarda una copia por muestra para conservar el respaldo aunque se mueva el original. El sistema no analiza ni compara los documentos y nunca marca automáticamente la casilla. Agregar o quitar un respaldo adjunto restablece esa casilla a pendiente.

**Iniciar_Panel** usa por defecto la BD de auditoría compartida mediante la misma carpeta del proyecto en SharePoint/OneDrive. Cada creación, comprobación o cambio de respaldo publica un archivo de cambio independiente en `Datos/Auditoria/Compartido/eventos`; los respaldos se conservan una vez por contenido en `Compartido/archivos`. Cada equipo incorpora los cambios en su propia caché SQLite, fuera de OneDrive, bajo la carpeta temporal `panel-codelco-auditoria`. Esa caché se puede reconstruir desde los archivos compartidos; ningún equipo sobrescribe la base de otro. Se admite trabajar en filas distintas simultáneamente. Para dos cambios sobre la misma fila, prevalece el cambio con mayor versión (fecha UTC e identificador, incorporando la última versión conocida); desmarcar también se comparte.

Al iniciar, se recuperan las muestras y respaldos de `auditoria.sqlite3` y de las copias en conflicto `auditoria*.sqlite3`, conservando sus confirmaciones y sin modificar esos originales. Los cambios posteriores al Excel no alteran una muestra guardada. Para respaldar o trasladar el trabajo, copia la carpeta completa `Datos/Auditoria`, incluidos los archivos `Compartido`. Los Excel originales nunca se escriben. Puedes elegir otra carpeta común con `--auditorias` o `CARPETA_AUDITORIAS`; cada equipo debe apuntar a su copia sincronizada de la misma carpeta. `--auditoria-local` mantiene el modo SQLite anterior para pruebas o uso individual.

El panel muestra **BD conectada**, consulta cambios cada 15 segundos y al regresar a la pestaña, y ofrece **Actualizar fuentes y chequeos**. Otro equipo verá los checks y sus documentos cuando OneDrive termine de sincronizar la carpeta. Si llega un cambio antes que su respaldo, queda pendiente y se reintenta; no se aplica parcialmente. No se requiere ejecutar Actualizar_BD para compartir auditorías. Es almacenamiento sin usuarios ni firmas de auditor.

**PDF de esta revisión** produce un resumen y fichas de los tickets, con su estado manual y listado de respaldos. **Descargar CSV** incluye las mismas filas, todos sus campos, período, fuente y estado. Ambos exportan la muestra guardada; los documentos se descargan por separado y no se incrustan en el reporte.

Se admiten también PDF con sufijo del mismo EDP, por ejemplo **2.5a TICKET INTERNO (EDP 47).pdf**, conservando la restricción de carpeta y servicio. Un sufijo de otro EDP no habilita el check.

El gráfico **Estado de chequeo por unidad** usa todos los períodos y cuenta una vez cada combinación unidad/período/EDP, aunque tenga varios Excel o muestras. **Chequeo completo / verde** indica todos los tickets seleccionados comprobados; **Chequeo parcial / amarillo**, algunos comprobados y otros pendientes; **Sin revisión / rojo**, ninguna confirmación, incluidos los EDP sin muestra. Chequeo completo se refiere a la selección, no certifica toda la población. El estado y los conteos corresponden a la revisión más reciente creada para el EDP, independientemente del orden de sincronización. Un nuevo sorteo o selección pasa a definir el estado; editar una revisión histórica no sustituye la vigente. La tabla y el resumen del PDF usan el mismo criterio y conservan todas las revisiones en el historial y el detalle. El gráfico se actualiza al guardar, modificar adjuntos o recibir cambios compartidos.

**Descargar PDF de toda la unidad** exporta todos sus períodos, gráfico de cobertura, tabla de EDP (incluidos los que aún no tienen revisión), todas las revisiones guardadas y fichas completas de sus tickets. Conserva campos originales, fechas, huella de Excel, observaciones y nombres de respaldos, sin incrustar los documentos. Año, mes y Excel no limitan esta exportación. **PDF de esta revisión** conserva la exportación individual.

Rutas GET bajo `/api/auditoria`: catálogo (incluye `estados_pago`), `/tickets?id=fuente`, `/muestra?id=…`, `/documento?id=…`, `/respaldo-edp?id=muestra`, `/reporte.pdf?id=…`, `/reporte.csv?id=…`, `/unidad.pdf?unidad=Andina` (o `El%20Salvador`); POST JSON `/seleccionar`, `/sortear`, `/adjuntar`, `/comprobar`, `/quitar`. `/importar` ya no está publicado. Los adjuntos se transportan como base64; el límite de solicitud incluye el tamaño codificado de un archivo de 30 MB. Las exportaciones distinguen selección manual/aleatoria e identifican el respaldo común del EDP.
