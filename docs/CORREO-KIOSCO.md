# Entrega de documentos por correo

El kiosco ofrece impresión física ESC/POS y envío por correo. La interfaz no descarga PDF/XML, no abre el diálogo de impresión del navegador y no utiliza `mailto:` ni una aplicación de correo instalada.

## Activar cuando se tenga proveedor

1. Instalar `api/requirements.txt` en el entorno virtual descrito en el README.
2. Copiar `api/.env.example` como `api/.env` y completar `SMTP_HOST`, `SMTP_FROM` y los datos de conexión que indique el proveedor. El remitente debe estar autorizado por ese proveedor.
3. Usar `SMTP_SECURITY=starttls` con el puerto indicado (habitualmente 587), o `SMTP_SECURITY=ssl` (habitualmente 465). Se verifica el certificado TLS. No se admite SMTP sin cifrado.
4. Configurar juntos `SMTP_USER` y `SMTP_PASSWORD` si el proveedor requiere autenticación. No poner secretos en el frontend, variables `VITE_`, capturas, Git o chats.
5. Reiniciar la API. La interfaz consulta `GET /api/services` para habilitar el botón. Este endpoint informa si la configuración está completa, no prueba la conectividad o autenticación con el proveedor.

Sin proveedor o con configuración incompleta, el botón queda deshabilitado y aparece un aviso. La demo no simula un éxito de correo. Las variables de entorno del proceso tienen prioridad sobre `api/.env`.

## Recorrido en el kiosco

1. Completar un pago demo, recuperar un pago desde **Mis comprobantes** o generar su factura de prueba.
2. Tocar **Enviar por correo**, escribir dos veces el destinatario y revisar la dirección.
3. Confirmar el envío. El backend recupera los importes y documentos desde SQLite; el navegador no puede modificar el contenido del adjunto.
4. El comprobante adjunta un PDF; la factura adjunta PDF y XML ilustrativo de CFDI 4.0. Todos los documentos dicen **DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL**.
5. Finalizar para limpiar los datos de la pantalla. También se limpia la sesión por inactividad.

Los adjuntos se generan en memoria. El correo completo solo se usa durante la solicitud y se transmite al proveedor SMTP; en la tabla de seguimiento local se guardan una huella del destinatario, una dirección enmascarada, folio, estado e identificador del envío. El proveedor de correo puede conservar el mensaje según su propia política. Los pagos y facturas siguen persistiendo en la base demo para recuperarlos después.

## Estados y reintentos

- `accepted`: SMTP aceptó el mensaje. No confirma llegada a la bandeja, ausencia de rebote ni lectura.
- `sending`: la solicitud ya se está procesando; consultar su estado reutiliza el mismo identificador.
- `failed`: no se pudo conectar/autenticar, o SMTP rechazó el mensaje. No se presenta como enviado.
- `unknown`: se perdió la conexión durante el envío y no puede saberse si fue aceptado. Se indica revisar el correo antes de solicitar otra copia.

`POST /api/billing/email` recibe `code`, `kind` (`payment` o `invoice`), `email` y `request_id`. El QR aleatorio sirve como acceso al documento, igual que en la consulta de facturación; se debe conservar con cuidado. La misma clave recupera el estado sin reenviar, incluso ante solicitudes simultáneas. Una operación que permanece en `sending` más de 120 segundos pasa a `unknown` al consultarla de nuevo.

Si se pierde la respuesta HTTP, **Consultar / reintentar envío** conserva la clave. No se reenvían automáticamente solicitudes fallidas o ambiguas. Para pedir deliberadamente otra copia, cierra el formulario y ábrelo de nuevo después de revisar tu bandeja. Se permiten como máximo tres solicitudes nuevas por comprobante en diez minutos, con 30 segundos entre envíos del mismo tipo. Comprobante y factura pueden solicitarse consecutivamente.

Esta versión usa envío síncrono con límites de tiempo. No hay cola duradera, webhooks de entrega/rebote ni reintentos automáticos en segundo plano. Antes de usar correo real, comprobar autenticación, remitente, TLS y recepción con el proveedor elegido.

## Verificación

Las pruebas Python verifican PDF/XML adjuntos, destinatarios inválidos, configuración ausente, TLS, aceptación/rechazo, pérdida de conexión, límites e idempotencia. Playwright verifica el teclado, confirmación, los avisos y la limpieza por inactividad. Todos los transportes de prueba son mocks: no mandan correos reales.
