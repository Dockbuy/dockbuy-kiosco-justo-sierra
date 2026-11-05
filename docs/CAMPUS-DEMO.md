# Servicios del campus y administración

Esta versión funciona con datos ficticios persistentes en `api/payments-demo.sqlite3`. No está conectada a los sistemas escolares, biblioteca, banco ni SAT. Los horarios, políticas, ubicaciones y costos de ejemplo **no son información oficial de Justo Sierra**.

## Iniciar después de descargar KioskoJsEMR

Desde la raíz, en la terminal de la API:

```powershell
.\.venv\Scripts\python.exe -m pip install -r api/requirements.txt
.\.venv\Scripts\python.exe api/server.py
```

En otra terminal:

```powershell
npm run setup
npm run dev
```

Abre `http://127.0.0.1:1420`. Usa matrícula `202210` o `202211` y PIN `1234`. Si falta `.venv`, créalo primero con `python -m venv .venv`. Reinicia Python al actualizar: una API anterior no conoce `/campus/*` y mostrará el aviso de actualización. `/api/health` identifica esta versión como `2.0`.

No borres las bases ni sobrescribas `api/.env` para actualizar. Las tablas nuevas se crean automáticamente; se conservan pagos y comprobantes anteriores. Haz una copia de las bases con la API detenida si necesitas un respaldo local. No subas bases ni credenciales a Git.

## Qué puede probar el alumno

| Servicio | Operación y resultado |
| --- | --- |
| Turnos | Elegir área, tomar folio, consultar turnos anteriores, imprimir ticket térmico y cancelar mientras espera. Un turno activo por alumno. El personal llama en orden por área y cierra la atención. Expiran al cambiar el día local. |
| Constancias | Solicitar estudios o calificaciones. Se agrega un concepto de pago con folio. Después de pagarlo, el personal revisa y autoriza. La constancia PDF demo puede enviarse por correo. |
| Mis trámites | Consultar todos los registros propios, sus estados, fechas e historial. Una solicitud pagada o en revisión ya no puede cancelarse desde el alumno. |
| Reinscripción | Lista de tres validaciones: cero adeudos demo, documentación revisada y validación académica. Permite solicitar revisión final cuando las tres están completas. El personal vuelve a comprobarlas antes de autorizar. |
| Citas | Reservar un bloque de una hora, de lunes a viernes, durante las siguientes dos semanas. Horarios configurables por área; una reserva activa por alumno y área. Cancelar libera el horario. |
| Horario y salones | Semana académica ficticia y mapa esquemático accesible del campus. No contiene horarios reales ni geolocalización. |
| Biblioteca | Préstamo inicial ficticio por alumno, renovación única de siete días si no está vencido ni tiene reservas. Catálogo con disponibilidad, reserva, entrega y devolución por el personal. |
| Credencial | Reposición con concepto de pago, revisión, estado Listo e instrucciones de recogida presencial. Sin captura de fotografías en el kiosco. |
| Actividades | Horarios, lugar, cupos e inscripción sin costo demo. Cancelar libera el lugar. El servidor evita sobrecupo entre solicitudes simultáneas. |
| Directorio | Información pública de áreas, horarios, requisitos, ubicación, contacto y avisos. Los llamados muestran solo folios. |
| Encuesta | Calificación del 1 al 5 y motivo, una respuesta por sesión anónima. |

Los costos de trámites se guardan al solicitar y no cambian si después el administrador edita el catálogo. Los cargos se integran en **Servicios y pagos**, respetando el orden de vencimiento ya existente. Cancelar una solicitud pendiente retira su concepto; cancelar y pagar simultáneamente se resuelve en una transacción SQLite. Rechazar una solicitud pagada requiere atención del personal: esta demo no hace reembolsos automáticos.

Los turnos se pueden imprimir por ESC/POS en el kiosco Debian; en Windows se conserva el folio aunque falte la impresora. Las constancias se entregan por correo, sin botones de descarga ni impresión del navegador. Requieren SMTP TLS configurado: ver [CORREO-KIOSCO.md](CORREO-KIOSCO.md). Sin proveedor se muestra la disponibilidad pendiente, nunca un envío ficticiamente exitoso.

## Panel del personal

Configura la contraseña en la computadora donde ejecutas la API:

```powershell
.\.venv\Scripts\python.exe api/setup_admin.py
```

Solicita una contraseña de al menos doce caracteres y confirmación sin mostrarla en pantalla. Guarda un hash PBKDF2 con sal aleatoria en `api/.env`, ignorado por Git. No hay contraseña administrativa predeterminada. Reinicia la API después de configurarla y abre **`http://127.0.0.1:1420/admin`** en el navegador del operador. No se enlaza este panel desde el menú del alumno.

El panel permite:

- Llamar/cerrar turnos, revisar/autorizar/entregar trámites, completar/cancelar citas y gestionar reservas e inscripciones.
- Añadir una nota visible en el historial del alumno al cambiar el estado.
- Validar documentación y situación académica; registrar devoluciones de libros.
- Cambiar avisos, disponibilidad, directorio, ventanas de citas, costos/plazos/requisitos de trámites y cupos/horarios de actividades. Los cupos no pueden reducirse por debajo de las inscripciones existentes.
- Revisar fallas de impresión y envíos SMTP fallidos, ambiguos o en curso. Marcar un incidente revisado no reimprime ni reenvía el documento.
- Consultar uso por servicio, distribución horaria UTC y encuestas. Los eventos contienen sesión aleatoria, módulo, tipo y fecha; no matrícula ni correo. Son indicadores de la demo, no auditoría financiera.

La API comprueba el rol administrativo en cada operación. Un token de alumno no sirve para administración y un token administrativo no sirve como alumno. El acceso administrativo expira a los 30 minutos y cierra la pantalla tras cinco minutos sin actividad. Cinco intentos de ingreso por minuto y dirección. Los tokens solo viven en memoria y se revocan al cerrar sesión. **Este control sigue siendo para desarrollo local; no expongas el servidor demo a Internet.** Para un despliegue institucional se necesita identidad del personal, roles nominativos, HTTPS y auditoría institucional.

## Navegación, privacidad y accesibilidad

Campus reúne once servicios con categorías, búsqueda y teclado táctil. El logo y Mis servicios regresan al inicio; Regresar vuelve al paso anterior; Salir limpia la pantalla. Las solicitudes confirmadas permanecen en la cuenta demo y se recuperan al ingresar otra vez. Las selecciones de pagos se conservan solo durante la sesión.

Accesibilidad permite texto grande, contraste alto y ampliar la espera por inactividad de dos a cinco minutos; se restablece al salir. Los modales y estados tienen etiquetas para teclado/lectores. La interfaz contempla computadora y tableta, objetivos táctiles, estados vacíos, errores y actualización manual. Las pantallas del campus consultan cambios cada quince segundos; esto no renueva la sesión.

## Contrato local añadido

| Método y ruta | Acceso | Uso |
| --- | --- | --- |
| GET `/api/campus/public` | Público | Directorio, avisos, catálogo de trámites y folios llamados. |
| GET `/api/campus/state` | Alumno | Registros propios, disponibilidad, préstamos, calendario y checklist. |
| POST `/api/campus/action` | Alumno | `action`: procedure, appointment, turn, book, activity, cancel o renew. |
| POST `/api/campus/print-turn` | Alumno | `folio`: ticket térmico de turno propio activo. |
| POST `/api/campus/email` | Alumno | `code`, `email`, `request_id`: constancia propia autorizada. |
| POST `/api/campus/event` | Público | `session`, `module`, `event`: open, complete, abandon, api_offline. |
| POST `/api/campus/survey` | Público | `session`, `score`, `topic`: facilidad, rapidez o atencion. |
| POST `/api/admin/login` | Contraseña del operador | Token administrativo temporal. |
| GET `/api/admin/state` | Administrador | Registros, configuración, incidencias y métricas. |
| POST `/api/admin/action` | Administrador | transition, return_book, validate, resolve o config. |

Las creaciones requieren `item` e identificador `request_id` (UUID). Repetir el mismo identificador devuelve el registro original; cambiar la selección con ese identificador se rechaza. Citas añaden `detail` con horario local ISO `YYYY-MM-DDTHH:mm`. Cancelar usa `folio`; renovar usa el `id` del préstamo. El backend comprueba propiedad, cupos, horarios, duplicados y transiciones. El cliente no determina costos ni autoriza documentos.

Las métricas cuentan una visita/finalización/salida por servicio y sesión, no cada clic. Una salida sin finalizar puede corresponder a una consulta informativa: no equivale a un pago fallido. Los cortes de API solo se reportan al recuperarse la conexión; no se promete monitoreo cuando el kiosco está apagado. El panel lista los 300 registros más recientes; el historial restante sigue en SQLite.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
npm test
npm run build
$env:TEST_BROWSER_PATH='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:TEST_PYTHON=(Resolve-Path '.\.venv\Scripts\python.exe').Path
npm run test:e2e
```

Las pruebas usan bases temporales, impresora simulada y SMTP simulado. Cubren propiedad y roles, concurrencia, idempotencia, cargos/cancelación, renovación, cupos, estados, constancias PDF, navegación, privacidad, configuración y correo. No cobran, no imprimen físicamente ni envían correos reales.
