# Trazabilidad de interacciones, preparada para integrar una API

## Qué existe actualmente en base de datos

La aplicación **sí utiliza SQLite local**. La API Python crea los archivos al trabajar:

| Archivo predeterminado | Contenido |
| --- | --- |
| `api/payments-demo.sqlite3` | Pagos/facturas demo, conceptos pagados, trámites y registros del campus, configuración, incidencias, seguimiento de correo y métricas generales |
| `api/parking-demo.sqlite3` | Boletos, claves de emisión y cuotas de impresión |

Se pueden cambiar mediante `PAYMENTS_DB` y `PARK_DB`. No hay conexión con una base institucional. La interfaz consume la API; no abre las bases directamente.

Ya había métricas generales en `campus_events`: una visita, finalización o salida por servicio y sesión. Esas métricas se conservan y siguen almacenándose. **El nuevo registro detallado de botones no se envía a esa tabla ni a ninguna base**.

## Probar el visor

1. Arranca la API habitual: en Windows, `.\.venv\Scripts\python.exe api/server.py`; en Debian, `.venv/bin/python api/server.py`.
2. Desde la raíz, ejecuta `npm run dev:trace` y abre `http://127.0.0.1:1420`.
3. Inicia sesión, navega, agrega/devuelve conceptos, realiza operaciones demo y sal.
4. Pulsa **TRAZABILIDAD · DESARROLLO** para ver la secuencia, filtrar pantalla/paso, consultar el mapa de toques o revisar JSON.

El visor solo se monta con Vite en modo `trace` y nunca en `/admin`. No aparece con `npm run dev` normal ni en la compilación de producción/Tauri. Es una herramienta para el desarrollador en la misma ventana que se está probando; otro navegador o pestaña no comparte esa memoria. No ofrece descargar, imprimir ni enviar el registro.

La captura comienza cuando el alumno termina de iniciar sesión y cargar sus servicios. Cada login aceptado recibe un UUID de sesión distinto. No se identifica al alumno por nombre o matrícula todavía. Cerrar sesión detiene la captura; las sesiones anteriores permanecen únicamente en RAM para poder revisarlas. Recargar, cerrar la ventana o reiniciar borra el historial. Se mantienen como máximo 10 sesiones y 500 eventos por sesión; el visor avisa si retiró datos por ese límite. Limpiar memoria solo se permite sin una sesión activa.

## Qué se registra

- Inicio y cierre de sesión, con motivo: salida, inactividad, vencimiento o salida de la página.
- Entrada/salida de pantallas y pasos: selección, resumen, procesamiento, comprobante, módulos del campus, etc.
- Botón activado mediante un identificador estable de catálogo; orden, hora UTC, tiempo transcurrido y origen (touch, mouse, teclado, lector o programático).
- Posición normalizada del toque en la ventana, entre 0 y 1. No se inventa una posición para activación con teclado o lectura QR.
- Índice visual de la opción cuando se repite el mismo botón. Ese índice no identifica un concepto, documento o alumno y puede cambiar al filtrar u ordenar.
- Apertura de ayuda, confirmaciones, correo y otras ventanas del flujo.
- Inicio y resultado de operaciones relevantes, duración y código HTTP. `200` con impresión rechazada se distingue de una impresión aceptada. Correo aceptado, pendiente o incierto conserva su estado.

No hay reproducción en video ni capturas del DOM. El mapa es un esquema de posiciones en la ventana, no una captura exacta de cada pantalla ni un mapa agregado de todos los equipos.

## Exclusiones y límites

No se registra matrícula, nombre, PIN, contraseñas, correo, folios, códigos QR, importes, notas, búsquedas, valores de formularios, tokens, cabeceras, cuerpos HTTP ni mensajes libres del servidor. Los campos de texto y teclados virtuales están excluidos, incluyendo sus teclas. Se registra “envió correo” o “escaneó QR”, nunca su contenido.

Los botones declaran `data-trace-action` con valores de `trace-catalog.js`; campos y teclados usan exclusión explícita. Un control nuevo no instrumentado aparece como `control.unmapped`, sin copiar su texto. Una prueba verifica la clasificación de los controles de los componentes actuales. El inspector no registra sus propios botones.

Si una respuesta llega después del cierre, queda asociada a su sesión original con `after_session_end:true`. Nunca se asigna a la persona que inicia sesión después. El orden `sequence` es por sesión; los eventos `operation.start/end` se relacionan por `operation_id`.

Esta analítica del cliente sirve para UX y diagnóstico. No es prueba de que hubo un cobro, una autorización o un cambio administrativo: esas evidencias deben generarse y verificarse en el servidor correspondiente.

## Contrato propuesto para la futura API (todavía desconectado)

Ruta propuesta: `POST /api/interaction-events/batch`. No se implementó ni se llama a ese endpoint. La ruta definitiva, autenticación y asociación al alumno se adaptarán al contrato que entregue la institución.

```json
{
  "schema_version": 1,
  "batch_id": "e44943a5-5d74-4ec1-b100-138582f339c8",
  "events": [{
    "schema_version": 1,
    "event_id": "1ecb2f96-bc71-4fe5-a6cd-88603357263f",
    "session_id": "b06fbb1c-2610-4bc0-9147-048c18bd4701",
    "sequence": 4,
    "occurred_at": "2026-11-06T18:30:00.000Z",
    "elapsed_ms": 1250,
    "type": "interaction",
    "screen": "charges",
    "step": "select",
    "overlay": "",
    "action": "payment.add",
    "input": "touch",
    "position": {"x": 0.46, "y": 0.62},
    "item_index": 0
  }]
}
```

Tipos: `session.start`, `session.end`, `screen.enter`, `screen.leave`, `overlay.change`, `interaction`, `operation.start`, `operation.end`. Además de los campos comunes del ejemplo:

| Tipo | Campos adicionales |
| --- | --- |
| `session.end` | `reason`: `logout`, `inactivity`, `expired`, `page_exit` o `replaced` |
| `overlay.change` | `previous_overlay` |
| `interaction` | `action`, `input`; opcionales `position`, `item_index` |
| `operation.start` | `operation`, `operation_id` |
| `operation.end` | Los anteriores más `outcome`, `http_status`, `duration_ms`, `after_session_end` |

Respuesta requerida para confirmar recepción:

```json
{"accepted_event_ids":["1ecb2f96-bc71-4fe5-a6cd-88603357263f"]}
```

Requisitos del receptor:

1. Autenticar el kiosco/gateway y resolver del lado servidor la vinculación entre sesión de trazabilidad y alumno autorizado. **Esa vinculación sigue pendiente**. No confiar en una matrícula, rol o identificador de equipo enviado libremente por el navegador. Los lotes pueden contener sesiones cerradas o varias sesiones: no atribuir todo al alumno que esté conectado al momento de enviarlos.
2. Validar versión, tipos, catálogo y tamaños, guardar hora de recepción y tratar la hora del cliente como informativa. Admitir eventos fuera de orden y respuestas posteriores al cierre.
3. Deduplicar por `event_id`. Una repetición de un evento ya guardado debe volver a confirmarse; no insertarse dos veces. Confirmar solo IDs efectivamente aceptados.
4. Definir retención y acceso al historial del personal. No mezclar esta telemetría con el registro financiero o de autorizaciones.
5. Usar HTTPS si hay comunicación fuera del equipo, con credenciales gestionadas por el backend. No agregar claves permanentes a variables `VITE_`.

## Punto de integración en código

`interaction-trace.js` expone `interactionTrace.setTransport(adapter)` y `flush()`. No existe adaptador de red activado, temporizador de envío ni proveedor externo configurado. El adaptador recibirá `(batch, {signal})` y deberá devolver la confirmación anterior. Se invocará desde el módulo de integración cuando se conozca la API, fuera del recorrido público del kiosco.

`flush()` envía como máximo 10 eventos por lote; llamadas concurrentes comparten el envío. Un error, timeout (5 segundos) o respuesta inválida deja los eventos pendientes y conserva el mismo `batch_id` al reintentar. Una confirmación parcial conserva los eventos no aceptados. El transporte debe respetar `AbortSignal`. No se garantiza entrega tras recargar o cerrar: no hay cola persistente ni reintento automático todavía. No se bloquea el pago por una falla de analítica.

## Verificación

`npm test` cubre orden, separación de sesiones, privacidad, límites de memoria, lotes, errores/timeout, confirmación parcial y controles instrumentados. Para el navegador se usa `TEST_TRACE_MODE=1` con `npm run test:e2e`; los servicios, impresora y SMTP de esa suite son simulados. El build normal excluye el visor de desarrollo.
