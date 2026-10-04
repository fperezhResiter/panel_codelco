# Uso del panel Codelco

1. Ejecuta Iniciar_Panel.bat, abre Panel.html y selecciona **Estados de pago y toneladas**.
2. Selecciona unidad, año, mes, EDP o estado. Limpiar filtros vuelve a mostrar todos los registros.
3. Revisa las toneladas, el monto esperado y la diferencia. Los totales y gráficos consideran solo EDP que se pudieron conciliar.
4. Pulsa Ver detalle para consultar período de pago, celdas de origen, fórmulas y tickets. El buscador del detalle no cambia los totales.
5. Cuadra indica que el monto y las toneladas coinciden. Con diferencia requiere revisar el EDP. Sin conciliar indica que faltan datos o existe una ambigüedad.
6. Los avisos de tickets repetidos o con número 0 no eliminan filas de la suma.
7. Para agregar un EDP, crea su carpeta en Fuentes / Unidad / Año-Mes EDP N.º y agrega una sola versión del Excel.
8. Guarda y recalcula los cambios en Excel. Ejecuta `Actualizar_BD.bat` (Windows) o `Actualizar_BD_MAC.command` (Mac) para cargar los cambios en la base local; luego pulsa **Recargar datos** en el panel.
9. Descargar CSV exporta las filas filtradas, sus resultados y observaciones.

En Andina se revisa el ítem 1.1: se suma Cantidad de la hoja 1.1, que ya está en toneladas, y se compara con Total Valor Actual EP de Avance físico. El monto esperado multiplica esa suma por Precio de Avance físico y se compara con Total Valor Actual EP de Avance financiero. En El Salvador se revisa el ítem 2.5.a: se convierte Peso Total de kg a toneladas (1.000 kg = 1 tonelada) y se usa el precio de Modificación N.º 1. Ambas comparaciones excluyen reajustes.

Si Andina muestra “sin archivos”, incorpora sus Excel. Si el servidor usa un puerto diferente, abre la dirección que muestra la consola. Para detenerlo, pulsa Ctrl+C en esa consola.

La portada también incluye **Auditoría de tickets de EDP**, disponible, y **Chequeo de densidades**, pendiente de implementación. Usa **Volver al inicio** o la navegación superior para cambiar de vista. Si acabas de actualizar el portal con el servidor abierto, reinícialo para cargar las nuevas rutas.

## Generar reporte PDF

Pulsa **Generar reporte PDF**, junto a Recargar datos. Se descarga un archivo PDF con los indicadores, los dos gráficos y todas las filas de la tabla que coinciden con los filtros actuales, además de sus observaciones.

El reporte identifica los filtros y la última lectura de datos. Conserva los colores del panel y utiliza páginas A4 horizontales, con encabezados de tabla repetidos cuando hay varias páginas. La exportación usa la información ya cargada, sin volver a leer los Excel. No incluye el listado individual de tickets del diálogo de detalle.

Si no hay EDP seleccionados o se están cargando los datos, el botón permanece deshabilitado. La primera vez después de actualizar el proyecto, ejecuta Iniciar_Primera_Vez.bat para instalar la dependencia reportlab (en Mac, su iniciador equivalente).

## Panel 3: auditoría manual de tickets

1. Abre **Auditoría de tickets de EDP** y elige unidad, año, mes y Excel EDP de la carpeta Fuentes.
2. Elige **3, 4 o 5 tickets** y pulsa **Sortear tickets**, o usa **Cargar lista de tickets**, busca y elige un registro y pulsa **Revisar ticket seleccionado**. Andina lee la hoja **1.1** y muestra **Cantidad en toneladas**; El Salvador lee **RES.NO PELIGROSO(S)** y muestra Peso Total en kg. Los totales y las filas de plantilla vacías de Andina quedan fuera del sorteo.
3. Adjunta uno o varios documentos de respaldo (hasta **30 MB por archivo**, tanto para tickets seleccionados como aleatorios). Si la carpeta de ese EDP contiene **1.1 Retiro RINSP.pdf** para Andina o **2.5a TICKET INTERNO.pdf** para El Salvador, aparecerá como respaldo común descargable y podrás marcar la casilla sin subir otro archivo.
4. Revisa personalmente la documentación y marca **Comprobé manualmente que la información de este ticket coincide con la documentación de respaldo**. El panel no realiza esa comparación. Si agregas o quitas un documento adjunto, debes volver a revisar y marcar la casilla. Al confirmar usando el PDF del EDP se conserva una copia con la revisión.
5. Usa **Generar reporte PDF** o **Descargar CSV** para exportar la muestra con los estados guardados. Los reportes enumeran los respaldos; cada documento se descarga por separado.
6. Al volver a la unidad y período, retoma la muestra desde **Muestras guardadas**. Un nuevo sorteo conserva las muestras anteriores.

Las revisiones se guardan automáticamente en `Datos/Auditoria` dentro del proyecto. Para respaldarlas, detén el servidor y copia esa carpeta completa. El período de auditoría es el período de pago del EDP, aunque sus tickets tengan fechas de otro mes.
