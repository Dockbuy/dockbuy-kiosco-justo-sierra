# DOCKBUY — Kiosco Justo Sierra (DEMO)

Monorepositorio para Debian 13: **Tauri v2 + Vue 3 + Vite** y **API demo Python 3.10+**. ReportLab genera los adjuntos PDF y python-dotenv carga la configuración local del correo.

## Demo de pagos en la rama KioskoJsEMR

**Nuevo: Servicios del campus.** Turnos, constancias, seguimiento de trámites, reinscripción, citas, horario y mapa demo, biblioteca, reposición de credencial, actividades, directorio, encuesta y opciones de accesibilidad. Incluye panel administrativo en `/admin` con gestión de estados, avisos, costos, horarios, cupos, incidencias y reportes. Consulta [cómo iniciar y probar todos los módulos](docs/CAMPUS-DEMO.md).

**Modo kiosco:** la aplicación Tauri desactiva el inspector, bloquea zoom y menús del navegador, y conserva scroll, teclado, QR y Texto grande. Consulta [actualización, mantenimiento y límites del bloqueo](docs/MODO-KIOSCO.md). Las configuraciones del escritorio Linux se gestionan por separado.

Para habilitar administración, ejecuta `python api/setup_admin.py`, elige tu contraseña y reinicia la API. No existe contraseña administrativa predeterminada. Los servicios son demostraciones persistentes; la integración institucional y el proveedor de correo siguen pendientes.

La pantalla separa conceptos pendientes (2/3) y selección (1/3). Los 16 conceptos demo se agregan por fecha de vencimiento y se devuelven desde el último agregado; también se puede cancelar toda la selección. **Continuar** abre un resumen antes de confirmar el pago simulado. El comprobante incluye un QR para abrir **Facturar** en el mismo kiosco.

El portal incluye **Mis comprobantes**, ayuda, teclado de correo y cierre por inactividad (aviso a los 90 segundos; cierre a los 120). Los documentos se imprimen en la impresora del kiosco o se envían por correo: comprobante PDF y factura de prueba PDF/XML. No hay descargas ni impresión desde el navegador.

El menú común conecta pagos, comprobantes, facturación, estacionamiento y perfil, e indica el servicio activo. El logo vuelve al inicio de servicios, **Regresar** vuelve al paso anterior y **Salir** termina la sesión. La selección pendiente se conserva al cambiar de módulo durante la misma sesión; pasar de pago a factura mantiene el acceso a tus servicios.

Los pagos demo persisten en SQLite. No se mueve dinero ni se conecta al SAT. Ver [flujo, impresión y pruebas](docs/PAGOS-DEMO.md).

### Ejecutar la interfaz en Windows

En GitHub Desktop selecciona **KioskoJsEMR**, pulsa **Fetch origin** y después **Pull origin** si hay cambios. Desde la raíz del repositorio, instala las dependencias de Python (primera ejecución o cuando cambien):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r api/requirements.txt
.\.venv\Scripts\python.exe api/server.py
```

En otra terminal, desde la raíz:

```powershell
npm run setup
npm run dev
```

Abrir http://127.0.0.1:1420. Matrícula `202210` o `202211`, PIN `1234`. `npm run dev` ya funciona desde la raíz; la API sigue en la primera terminal. Al actualizar el backend, reiniciar Python. La impresión ESC/POS requiere el kiosco Debian; en Windows puedes probar el flujo y el correo configurado.

El envío permanece deshabilitado hasta configurar SMTP. Copia `api/.env.example` a `api/.env`, completa los datos del proveedor cuando exista y reinicia la API. Nunca subas ese archivo ni uses variables `VITE_` para credenciales. Consulta [configuración y estados de correo](docs/CORREO-KIOSCO.md).

## 1. Instalación en el kiosco

```bash
cd /home/dockbuy/repositorio
# Extrae aquí el ZIP (crea justo-sierra-kiosco/) o clona el repositorio GitHub vacío y copia estos archivos.
cd justo-sierra-kiosco
node -v && npm -v && cargo -V && python3 --version
bash scripts/install-debian13.sh
bash scripts/start-demo.sh
```

Si falta Rust: instalar según https://rustup.rs/ (sin ejecutar scripts de fuentes no confiables); cerrar/reabrir terminal después.

Alternativa en dos terminales:

```bash
# Terminal 1
cd /home/dockbuy/repositorio/justo-sierra-kiosco
.venv/bin/python api/server.py
# Terminal 2
cd /home/dockbuy/repositorio/justo-sierra-kiosco/app
npm ci
npm run tauri:dev
```

**Credenciales demo:** matrícula `202210` o `202211`, PIN `1234`. Ninguno corresponde a un alumno real.

## 2. Comprobar API

```bash
curl -s http://127.0.0.1:8787/api/health
curl -s -X POST http://127.0.0.1:8787/api/auth/login -H 'Content-Type: application/json' -d '{"matricula":"202210","pin":"1234"}'
```

Endpoints: `GET /api/health`, `POST /api/auth/login`, `GET /api/me`, `GET /api/charges`, `POST /api/payments/quote`, `POST /api/auth/logout`.

Para consultar cargos o generar cotización, pasar `Authorization: Bearer <access_token>`.

## 3. Compilación Debian

```bash
cd /home/dockbuy/repositorio/justo-sierra-kiosco/app
npm run tauri:build
# Archivos en src-tauri/target/release/bundle/deb/ y /appimage/
```

La compilación empaqueta el **frontend**. El servicio API Python debe ejecutarse por separado antes de abrir el programa. En producción puede convertirse en un servicio systemd ligado a localhost o reemplazarse con el gateway real.

## 4. Integración real pendiente

No se recibió contrato de API de alumnos ni evidencia sobre su autenticación. El Bearer token es **una suposición simulada**; no asegura que el endpoint real lo acepte. Si usa OAuth2/Keycloak, API key, Basic, mTLS, cookies u otra modalidad, adaptar `app/src/api.js` o —preferentemente— un gateway backend que maneje credenciales con seguridad.

No exponer secretos, tokens permanentes ni claves MIT en variables `VITE_`: terminan en el bundle del frontend. Validar TLS, certificado, rutas, esquema JSON, paginación, identificadores, roles y vigencia de las sesiones en las instalaciones.

No activar cobros reales hasta disponer del contrato y credenciales del proveedor, validación de respuestas y confirmación por servidor. El mock actual **registra pagos ficticios exclusivamente en la base demo**; no modifica adeudos de la universidad ni se comunica con MIT.

## 5. GitHub

El desarrollo de esta demo está en **KioskoJsEMR**. Para recibir las actualizaciones, selecciona esa rama en GitHub Desktop y usa Fetch/Pull origin. No es necesario crear de nuevo el repositorio ni cambiar `main`.

## 6. Limitaciones actuales

- Los alumnos, importes y conceptos son **ficticios**, inspirados en la estructura visual mostrada, no están extraídos del sistema real.
- PIN demo común y tokens en RAM; **exclusivamente para pruebas locales**.
- Hay impresión ESC/POS de tickets y facturas de prueba; falta validar físicamente los nuevos formatos en la impresora. No hay terminal bancaria ni Webpay real.
- El correo necesita un proveedor SMTP configurado. La aceptación SMTP no garantiza la llegada a la bandeja; la demo no tiene webhooks de entrega ni rebotes.
- Las imágenes de referencia proporcionadas por el usuario están integradas localmente en `app/public/images/`. No se descargan imágenes del sitio en ejecución.
- Google Fonts Inter requiere red; se usa fallback si el kiosco está desconectado. Para producción offline, instalar Inter localmente si se dispone de licencia/distribución adecuada.
- Deben revisarse autorización de uso del logotipo/fotografías y requisitos de privacidad antes del despliegue.

## Actualización: teclado táctil y títulos Roboto Condensed

En Inicio de sesión, toca Matrícula o Contraseña/PIN: se abrirá un teclado numérico propio, incluso cuando Debian no tenga teclado en pantalla. Usa `⌫` para borrar, `LISTO` para ocultarlo y el botón ENTRAR para iniciar sesión. No se instala ni requiere Onboard.

Encabezados, títulos y botones usan la familia Roboto Condensed (Google Fonts; para uso sin red es aconsejable instalar esta familia en el sistema Debian mediante el administrador de paquetes). Los textos normales mantienen Inter.

Para actualizar, detén la aplicación, descarga los cambios de `KioskoJsEMR` y actualiza las dependencias antes de iniciar de nuevo. Los archivos `.env` y las bases SQLite locales no forman parte del repositorio.

## Límites de impresión y protección local

La API limita reimpresiones, conserva los folios al reintentar y rechaza conexiones u orígenes web no permitidos. Consulta [límites y configuración](docs/LIMITES-API.md). Después de actualizar, reinicia API y frontend juntos.

## Trazabilidad de botones y navegación

Después del login se registra en memoria el recorrido por sesión: botones, pantallas, pasos, toques y resultados. Para inspeccionarlo, inicia la API y ejecuta `npm run dev:trace`; abre el botón **TRAZABILIDAD · DESARROLLO**. No guarda estos eventos detallados en una base ni los envía a una API. El contrato y el adaptador quedan listos para la integración posterior. Consulta [uso, datos excluidos y contrato](docs/TRAZABILIDAD.md).

La aplicación ya utiliza **SQLite local** para sus operaciones demo y métricas generales anteriores. No hay conexión con la base institucional. El visor detallado es temporal: recargar borra su memoria y no aparece en la compilación de producción.
