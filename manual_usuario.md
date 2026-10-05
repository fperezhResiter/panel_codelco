# Uso del panel Codelco

1. Ejecuta Iniciar_Panel.bat, abre Panel.html y selecciona **Estados de pago y toneladas**.
2. Selecciona unidad, año, mes, EDP o estado. Limpiar filtros vuelve a mostrar todos los registros.
3. Revisa las toneladas, el monto esperado y la diferencia. Los totales y gráficos consideran solo EDP que se pudieron conciliar.
4. Pulsa Ver detalle para consultar período de pago, celdas de origen, fórmulas y tickets. El buscador del detalle no cambia los totales.
5. Cuadra indica que el monto y las toneladas coinciden. Con diferencia requiere revisar el EDP. Sin conciliar indica que faltan datos o existe una ambigüedad.
6. Los avisos de tickets repetidos o con número 0 no eliminan filas de la suma.
7. Para agregar un EDP, crea su carpeta en Fuentes / Unidad / Año-Mes EDP N.º y agrega una sola versión del Excel.
8. Guarda y recalcula los cambios en Excel. Ejecuta `Actualizar_BD.bat` (Windows) o `scripts/mac/Actualizar_BD_MAC.command` (Mac) para cargar los cambios en la base local; luego pulsa **Recargar datos** en el panel.
9. Descargar CSV exporta las filas filtradas, sus resultados y observaciones.

En Andina se revisa el ítem 1.1: se suma Cantidad de la hoja 1.1, que ya está en toneladas, y se compara con Total Valor Actual EP de Avance físico. El monto esperado multiplica esa suma por Precio de Avance físico y se compara con Total Valor Actual EP de Avance financiero. En El Salvador se revisa el ítem 2.5.a: se convierte Peso Total de kg a toneladas (1.000 kg = 1 tonelada) y se usa el precio de Modificación N.º 1. Ambas comparaciones excluyen reajustes.

Si Andina muestra “sin archivos”, incorpora sus Excel. Si el servidor usa un puerto diferente, abre la dirección que muestra la consola. Para detenerlo, pulsa Ctrl+C en esa consola.

La portada también incluye **Auditoría de tickets de EDP** y **Chequeo de densidades**, ambas disponibles. Usa **Volver al inicio** o la navegación superior para cambiar de vista. Si acabas de actualizar el portal con el servidor abierto, reinícialo para cargar las nuevas rutas.

## Generar reporte PDF

Pulsa **Generar reporte PDF**, junto a Recargar datos. Se descarga un archivo PDF con los indicadores, los dos gráficos y todas las filas de la tabla que coinciden con los filtros actuales, además de sus observaciones.

El reporte identifica los filtros sin mostrar la fecha de última lectura de datos. Conserva los colores del panel y utiliza páginas A4 horizontales, con encabezados de tabla repetidos cuando hay varias páginas. La exportación usa la información ya cargada, sin volver a leer los Excel. No incluye el listado individual de tickets del diálogo de detalle.

Los tres paneles incluyen **Descargar compilado por unidad y mes**. Descarga un ZIP con un PDF separado por cada combinación de unidad, mes, año y EDP, con esos datos y el nombre del panel en el archivo. Conciliación y Densidades respetan los filtros actuales. En Auditoría se incluyen todos los EDP de la unidad, año y mes seleccionados, con todas sus revisiones guardadas y también los EDP sin revisión; la selección de un Excel o de una muestra no limita el compilado. Descomprime el ZIP para obtener los PDF individuales.

Si no hay EDP seleccionados o se están cargando los datos, el botón permanece deshabilitado. La primera vez después de actualizar el proyecto, ejecuta Iniciar_Primera_Vez.bat para instalar la dependencia reportlab (en Mac, su iniciador equivalente).

## Chequeo de densidades: El Salvador y Andina

1. Conserva una sola `Reporte de RINP por densidad.xlsx` en Fuentes. Su hoja Aux debe contener Tipo RINP, Dens. Inf y Dens. Sup (kg/m³). Ejecuta Actualizar_BD para guardar la maestra y tickets; abre **Chequeo de densidades**.
2. Selecciona **El Salvador** o **Andina**. El volumen es el peso en kg dividido por el promedio de ambas densidades. El Salvador usa Peso Total en kg y capacidades de **15, 20 o 30 m³**. Andina convierte Cantidad de toneladas a kg (×1.000) y usa **13, 20 o 40 m³**. Verde **Coincide con volumen** indica coincidencia con alguna capacidad usando ±3 m³, incluidos los límites; la banda de 40 m³ abarca de 37 a 43 m³. Fuera de todos los rangos, amarillo **No coincide con volumen menor** indica menos que la capacidad mínima (15 en El Salvador, 13 en Andina) y rojo **No coincide con volumen mayor** indica más. Gris **Sin evaluar** explica un dato faltante o inválido. La coincidencia tiene prioridad: 14 m³ es verde en ambas unidades.
3. Filtra por período del EDP, residuo, resultado o capacidad. El buscador encuentra ticket, lugar de retiro, residuo, archivo o fila. Los indicadores y gráficos siguen la selección.
4. Revisa peso, densidad, volumen, capacidad asignada, delta y celdas de origen en la tabla. Cuando coincide con dos capacidades se elige la más cercana; en un empate, la menor. Los valores se comparan antes de redondear.
5. Pulsa **Generar reporte PDF** para descargar toda la selección con gráficos, detalle y maestra utilizada. **Descargar CSV** también incluye toda la selección, aunque la tabla muestre solo una página.
6. Las variantes de nombre se agrupan bajo el material estándar: por ejemplo, Asimable a RINP, ASimable a RINP y Asimable a RINP (1/2) aparecen como **Asimilable a RINP**. En Andina, **RINP Granel** también usa ese material, cuya densidad promedio en AUX es **475 kg/m³**. **Polvo Roca** usa **Polvo de roca**, con promedio **1.750 kg/m³** en AUX. También se unifican nombres cortos, singulares/plurales, tildes y mayúsculas de los otros materiales. El detalle y los reportes conservan el nombre original; las fracciones no modifican el peso.
7. Los tickets sin tipo usan una estimación basada en los materiales declarados del mismo EDP o de los EDP cercanos de la misma unidad, y su densidad válida en AUX. Si esos EDP discrepan, se usa el material mayoritario de la unidad; sin mayoría suficiente, sigue sin evaluar. Verás **Tipo y densidad estimados** y podrás abrir **Ver estimación** para consultar el criterio. El original vacío se conserva; PDF y CSV incluyen la estimación. En los EDP 39 y 41 de Andina de 2025 se estima Asimilable a RINP, a 475 kg/m³.
8. Para cambiar la maestra o tickets, guarda y recalcula los Excel, ejecuta Actualizar_BD y pulsa Recargar datos. Corregir el tipo en Excel reemplaza la estimación. Los tipos declarados sin correspondencia requieren corregir su origen o la maestra.

## Panel 3: auditoría manual de tickets

1. Abre **Auditoría de tickets de EDP** y elige unidad, año, mes y Excel EDP de la carpeta Fuentes.
2. Elige **3, 4 o 5 tickets** y pulsa **Sortear tickets**, o usa **Cargar lista de tickets**, busca y elige un registro y pulsa **Revisar ticket seleccionado**. Andina lee la hoja **1.1** y muestra **Cantidad en toneladas**; El Salvador lee **RES.NO PELIGROSO(S)** y muestra Peso Total en kg. Los totales y las filas de plantilla vacías de Andina quedan fuera del sorteo.
3. Si la carpeta de ese EDP contiene **1.1 Retiro RINSP.pdf** (o **1.1 Retiro RINP.pdf**) para Andina o **2.5a TICKET INTERNO.pdf** para El Salvador, aparecerá como respaldo común descargable y podrás marcar la casilla sin subir otro archivo. También se admiten nombres con el número del mismo EDP, por ejemplo **2.5a TICKET INTERNO (EDP 47).pdf**. Si falta el PDF, adjunta uno o varios documentos de respaldo (hasta **30 MB por archivo**).
4. Revisa personalmente la documentación y marca **Comprobé manualmente que la información de este ticket coincide con la documentación de respaldo**. El panel no realiza esa comparación. Si agregas o quitas un documento adjunto, debes volver a revisar y marcar la casilla. Al confirmar usando el PDF del EDP se conserva una copia con la revisión.
5. Usa **PDF de esta revisión** o **Descargar CSV** para exportar la muestra con los estados guardados. Los reportes enumeran los respaldos; cada documento se descarga por separado.
6. Al volver a la unidad y período, retoma la muestra desde **Muestras guardadas**. Un nuevo sorteo conserva las muestras anteriores.
7. El gráfico **Estado de chequeo por unidad** muestra todos los períodos de ambas unidades, contando cada EDP una sola vez. **Chequeo completo / verde** significa todos los tickets seleccionados confirmados; **Chequeo parcial / amarillo**, algunos confirmados y otros pendientes; **Sin revisión / rojo**, ninguno confirmado o sin muestra guardada. Chequeo completo se refiere a los tickets seleccionados, no a toda la población. El estado y los conteos de tickets corresponden a la revisión más reciente creada para el EDP. Un nuevo sorteo o selección pasa a definir el estado; editar una revisión histórica no sustituye la vigente. La tabla y el PDF usan ese mismo criterio y conservan todo el historial.
8. Pulsa **Descargar PDF de toda la unidad** para exportar todos los años y meses de la unidad seleccionada. Incluye gráfico, tabla de EDP (también los que no tienen revisión), todas las muestras guardadas y sus fichas de tickets, estados, fechas, campos originales y nombres de los respaldos. Año, mes y Excel seleccionados no limitan este reporte.

Las revisiones se guardan automáticamente en `Datos/Auditoria/Compartido` dentro del proyecto. Todos los equipos deben usar la misma carpeta del panel sincronizada por SharePoint/OneDrive. Reinicia Iniciar_Panel en cada equipo después de esta actualización: al abrirlo, se recuperan también las revisiones de las bases anteriores y sus copias en conflicto, conservando los originales.

Cuando marques o desmarques una casilla, el cambio y su respaldo quedan publicados en la carpeta común. Otro equipo los verá al iniciar el panel o en su actualización automática cada 15 segundos, **después de que OneDrive termine de sincronizar**. El estado **BD conectada** aparece arriba; también puedes pulsar **Actualizar fuentes y chequeos**. Si OneDrive está pausado o sin conexión, el cambio sigue guardado y llegará al otro equipo cuando se reanude. No necesitas ejecutar Actualizar_BD para los chequeos.

Para respaldar las auditorías, copia `Datos/Auditoria` completa, incluida la carpeta `Compartido`. La BD de cada equipo es una caché local que se reconstruye desde esa carpeta. El período de auditoría es el período de pago del EDP, aunque sus tickets tengan fechas de otro mes.
