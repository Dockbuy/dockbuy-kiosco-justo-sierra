# Pagos, tickets y facturación de prueba

Rama de trabajo: `KioskoJsEMR`.

## Navegación

El encabezado y menú son comunes a todos los servicios. El menú señala la sección activa y muestra cuántos conceptos hay seleccionados. El logo abre **Mis servicios** cuando hay sesión, o la bienvenida en servicios públicos. **Regresar** respeta el paso actual (por ejemplo, del resumen a la selección o del documento al historial). **Salir** y **Finalizar y salir** limpian la sesión y el borrador. La ayuda se puede cerrar con su botón o Escape.

Cambiar de módulo conserva la selección de conceptos durante esa sesión; al regresar se valida contra los pendientes del servidor. Abrir **Facturar** desde un pago o desde el historial conserva la sesión. Desde el modo público se puede escanear un QR sin iniciar sesión. La navegación entre servicios se deshabilita durante el registro del pago, pero **Salir** permanece disponible; si un pago ya se guardó, se puede recuperar desde el historial.

## Flujo

1. Ingresar con matrícula `202210` o `202211` y PIN `1234`.
2. Abrir **Servicios y pagos**. Hay 16 conceptos demo: reinscripción, seguro, colegiaturas de septiembre a enero, laboratorio, biblioteca, transporte, deportes, credencial, idiomas, arte y música. Se ordenan por vencimiento ascendente; en un empate, por ID. Se conservan los IDs anteriores para no volver a cobrar conceptos ya pagados en la base demo.
3. Solo se puede agregar el primer concepto pendiente. Desaparece de la lista izquierda y pasa al panel derecho, que ocupa un tercio del área en escritorio.
4. **Devolver** solo está habilitado en el último concepto agregado. **Cancelar toda la selección** devuelve todos y no registra un pago.
5. **Continuar** abre el resumen de conceptos e importe. Puedes modificar la selección o pulsar **Confirmar pago demo**. Entonces se registra el pago simulado y se genera el comprobante con QR. No hay tarjeta, pasarela ni movimiento de dinero.
6. El pago y sus conceptos quedan guardados en SQLite. Los conceptos pagados en la demo dejan de aparecer como pendientes para esa matrícula.
7. El QR contiene un folio aleatorio `JS-PAY-` seguido de 32 caracteres hexadecimales. El lector USB del mismo kiosco debe enviar el contenido seguido de Enter. Se puede escanear desde Inicio, el comprobante o la pantalla Facturar. No es una URL para celular.
8. **Facturar** muestra el comprobante y permite generar e imprimir una factura de prueba. Escanear nuevamente devuelve la misma factura. También hay entrada manual mediante teclado táctil.
9. **Enviar por correo** solicita y confirma el destinatario con teclado táctil. Envía el comprobante PDF o la factura PDF/XML mediante SMTP, únicamente cuando esté configurado. Ver [correo del kiosco](CORREO-KIOSCO.md).
10. **Mis comprobantes** recupera los últimos 30 pagos de la matrícula. **Finalizar y salir** limpia la pantalla; también se cierra tras 120 segundos de inactividad, con aviso previo a los 90 segundos.

## Documentos de prueba

La factura contiene emisor/receptor ficticios, RFC genérico y un folio que empieza con `DEMO-`. La pantalla y el ticket dicen **DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL**.

El XML adjunto por correo solo ilustra elementos de CFDI 4.0. **No cumple un proceso de emisión fiscal**: no lleva certificado, sello, UUID de timbrado ni TimbreFiscalDigital, y no se envía a un PAC o al SAT. No debe presentarse como factura válida. No se solicitan datos fiscales personales; el usuario solo introduce un correo si desea recibir los documentos.

## Impresión

Los tickets de estacionamiento, pago y factura comparten el transporte ESC/POS de 80 mm:

- Debian/CUPS: `PARK_PRINTER=NOMBRE_COLA` (o cola predeterminada).
- Debian/USB: `PARK_DEVICE=/dev/usb/lp0`, con permisos del usuario sobre el dispositivo.
- Windows: la demo conserva y muestra el documento aunque no exista CUPS/USB Linux. Puede probarse el correo configurado. No hay acciones de descarga ni impresión del navegador; la impresión física requiere el kiosco compatible.

El cobro y la factura se guardan antes de imprimir. Un fallo no elimina el folio. **Reimprimir en kiosco** reenvía el mismo documento. La aceptación de un trabajo no confirma que haya salido papel; revisar físicamente la impresora. Los trabajos se serializan y los envíos USB/CUPS tienen tiempo límite.

## Persistencia y reintentos

Se usa `api/payments-demo.sqlite3` (ignorado por Git). Puede cambiarse con `PAYMENTS_DB`. La base de estacionamiento sigue separada en `PARK_DB`.

Cada pago lleva una clave de idempotencia generada por la interfaz. Los reintentos con la misma clave recuperan el mismo pago, sin imprimir automáticamente otra copia. La base impide pagar dos veces el mismo concepto de una matrícula, incluso con solicitudes simultáneas. Hay una sola factura por pago. El orden también se valida en el servidor.

Los pagos demo persisten al reiniciar la API. Para una demostración con datos nuevos, detener la API y arrancarla con **otra ruta** en `PAYMENTS_DB`; no es necesario borrar la base anterior.

## Pruebas

Desde la raíz:

```bash
.venv/bin/python -m pip install -r api/requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

En Windows reemplaza `.venv/bin/python` por `.\.venv\Scripts\python.exe`. Desde `app/`:

```bash
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

`TEST_PYTHON` debe apuntar al ejecutable absoluto del entorno virtual si no está activado. Opcionalmente `TEST_BROWSER_PATH` permite usar un Chrome instalado. E2E inicia servidores exclusivos en `127.0.0.1:1421` y `127.0.0.1:8878`, usa bases temporales y sustituye impresión y SMTP por mocks. Los adjuntos se generan en memoria, pero no se envían correos ni papel. El servidor `tests/e2e_server.py` es solo para pruebas y nunca debe usarse como API del kiosco.
