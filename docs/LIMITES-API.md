# Protección de la API local y de la impresora

La API sigue siendo una demostración local, con estudiantes y cobros ficticios. Estos controles limitan el consumo de papel y de recursos; no agregan autenticación institucional ni una integración bancaria.

## Impresión

Todos los boletos, comprobantes, facturas demo y turnos pasan por el mismo control, tanto con CUPS como con USB directo:

| Control | Límite |
| --- | --- |
| Mismo documento | 3 intentos en 10 minutos, separados al menos 5 segundos |
| Toda la impresora | 20 intentos/minuto, 200/hora y 500/24 horas |
| Cola de la aplicación | 1 trabajo activo y 1 esperando; espera máxima de 2 segundos |
| Boletos nuevos de estacionamiento | 10/minuto |

Son ventanas móviles. Un fallo o timeout del transporte consume un intento: la impresora o CUPS podrían haber recibido el trabajo aunque se pierda la respuesta. Una solicitud rechazada por cuota o cola llena no se envía a la impresora. No se vacía la cola previa de CUPS ni se supervisa la salida física del papel.

Las cuotas se guardan en `PARK_DB`, la SQLite del estacionamiento, y sobreviven al reinicio. Las tablas se crean automáticamente conservando los boletos anteriores. No borres la base para resolver una cuota: espera el tiempo indicado o pide ayuda al encargado. Solo se conservan las últimas 24 horas de intentos de impresión; los folios y sus claves de operación permanecen para recuperar operaciones.

`POST /api/parking/issue` ahora requiere `{"request_id":"identificador-unico-de-16-a-80-caracteres"}`. Admite letras, números, `_` y `-`; el frontend genera un UUID y lo conserva al reintentar una solicitud incierta. Repetir la clave devuelve el mismo boleto con `reused:true` y no imprime nuevamente. La reimpresión es explícita y usa la cuota del mismo folio. Salir del flujo inicia otra operación.

Las reimpresiones de estacionamiento/turno responden `429` al superar cuotas o `503` si la impresora está ocupada, con `retry_after` y `Retry-After`. Pagos, facturas y boletos ya guardados conservan una respuesta exitosa con `printed:false`, `print_error` y, para límites, `retry_after`; nunca se revierte un pago guardado por un fallo de impresión. Reimprimir comprobantes mantiene este contrato. El mensaje se muestra en pantalla.

## Solicitudes HTTP

- Solo escucha en `127.0.0.1` o `localhost`; `MOCK_HOST=0.0.0.0` se rechaza al arrancar.
- Máximo 16 conexiones atendidas y 240 solicitudes válidas por minuto en total. El exceso devuelve `503` o `429`, respectivamente. Las cuotas se comparten entre todos los visitantes del kiosco.
- Plazo absoluto de 10 segundos para recibir línea HTTP, cabeceras y cuerpo. Enviar bytes lentamente no renueva el plazo; al agotarlo se cierra la conexión. Una operación ya recibida puede completar su impresión o SMTP dentro de sus propios timeouts.
- Cuerpo máximo de 8 KB y POST con `application/json`. Rechaza longitudes duplicadas, ambiguas o negativas, `Transfer-Encoding` y cuerpos incompletos.
- `Host` debe ser `127.0.0.1` o `localhost` con el puerto real. No admite destinos HTTP absolutos de proxy.
- Rechaza orígenes web ajenos, `null` y orígenes duplicados antes de ejecutar acciones. CORS devuelve el origen exacto autorizado, nunca `*`.
- Permite Vite en `http://127.0.0.1:1420` y `http://localhost:1420`, y Tauri en `tauri://localhost`, `http://tauri.localhost` y `https://tauri.localhost`. Para otro puerto del frontend, agrega el origen exacto a `API_ALLOWED_ORIGINS` en `api/.env` y reinicia la API. No uses comodines.
- Clientes locales sin `Origin` siguen funcionando, con JSON y las mismas cuotas. Esto no autentica programas que ya ejecutan código en el equipo. Se conservan los permisos de administrador y de cada alumno en sus rutas.
- Máximo 256 sesiones activas para el acceso demo de alumnos. Cerrar sesión libera el token; los vencidos se eliminan al iniciar sesión.

Actualizar **API y frontend juntos** y reiniciar ambos procesos. Las pruebas automatizadas usan bases temporales y transportes simulados: no imprimen papel ni mandan correo real. La comprobación final en el kiosco debe cubrir un boleto, su consulta por QR y una reimpresión después de cinco segundos, además del acceso desde el ejecutable Tauri del equipo.
