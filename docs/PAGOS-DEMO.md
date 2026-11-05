# Pagos, tickets y facturación de prueba

Rama de trabajo: `KioskoJsEMR`.

## Flujo

1. Ingresar con matrícula `202210` o `202211` y PIN `1234`.
2. Abrir **Servicios y pagos**. Los conceptos se ordenan por vencimiento ascendente; en un empate, por ID. En los datos actuales el orden es `45, 36, 55, 56`.
3. Solo se puede agregar el primer concepto pendiente. Desaparece de la lista izquierda y pasa al panel derecho, que ocupa un tercio del área en escritorio.
4. **Devolver** solo está habilitado en el último concepto agregado. **Cancelar toda la selección** devuelve todos y no registra un pago.
5. **Continuar** registra un pago simulado, muestra el estado de procesamiento y genera un comprobante con QR. No hay tarjeta, pasarela ni movimiento de dinero.
6. El pago y sus conceptos quedan guardados en SQLite. Los conceptos pagados en la demo dejan de aparecer como pendientes para esa matrícula.
7. El QR contiene un folio aleatorio `JS-PAY-` seguido de 32 caracteres hexadecimales. El lector USB del mismo kiosco debe enviar el contenido seguido de Enter. Se puede escanear desde Inicio, el comprobante o la pantalla Facturar. No es una URL para celular.
8. **Facturar** muestra el comprobante y permite generar e imprimir una factura de prueba. Escanear nuevamente devuelve la misma factura. También hay entrada manual mediante teclado táctil.

## Documentos de prueba

La factura contiene emisor/receptor ficticios, RFC genérico y un folio que empieza con `DEMO-`. La pantalla y el ticket dicen **DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL**.

El XML descargable solo ilustra elementos de CFDI 4.0. **No cumple un proceso de emisión fiscal**: no lleva certificado, sello, UUID de timbrado ni TimbreFiscalDigital, y no se envía a un PAC o al SAT. No debe presentarse como factura válida. No se solicitan datos personales reales.

## Impresión

Los tickets de estacionamiento, pago y factura comparten el transporte ESC/POS de 80 mm:

- Debian/CUPS: `PARK_PRINTER=NOMBRE_COLA` (o cola predeterminada).
- Debian/USB: `PARK_DEVICE=/dev/usb/lp0`, con permisos del usuario sobre el dispositivo.
- Windows: la demo conserva y muestra el documento aunque no exista CUPS/USB Linux. **Imprimir / guardar PDF** abre la impresión del navegador; puede elegirse una impresora de Windows o guardar PDF.

El cobro y la factura se guardan antes de imprimir. Un fallo no elimina el folio. **Reimprimir en kiosco** reenvía el mismo documento. La aceptación de un trabajo no confirma que haya salido papel; revisar físicamente la impresora. Los trabajos se serializan y los envíos USB/CUPS tienen tiempo límite.

## Persistencia y reintentos

Se usa `api/payments-demo.sqlite3` (ignorado por Git). Puede cambiarse con `PAYMENTS_DB`. La base de estacionamiento sigue separada en `PARK_DB`.

Cada pago lleva una clave de idempotencia generada por la interfaz. Los reintentos con la misma clave recuperan el mismo pago, sin imprimir automáticamente otra copia. La base impide pagar dos veces el mismo concepto de una matrícula, incluso con solicitudes simultáneas. Hay una sola factura por pago. El orden también se valida en el servidor.

Los pagos demo persisten al reiniciar la API. Para una demostración con datos nuevos, detener la API y arrancarla con **otra ruta** en `PAYMENTS_DB`; no es necesario borrar la base anterior.

## Pruebas

Desde la raíz:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

En Debian usar `python3` si no existe `python`. Desde `app/`:

```bash
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Opcionalmente `TEST_BROWSER_PATH` permite usar un Chrome instalado para las pruebas. E2E inicia servidores exclusivos en `127.0.0.1:1421` y `127.0.0.1:8878`, usa bases temporales y sustituye la impresión por un mock. No afecta los datos del kiosco ni envía papel. El servidor `tests/e2e_server.py` es solo para pruebas y nunca debe usarse como API del kiosco.
