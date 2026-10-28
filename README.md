# DOCKBUY — Kiosco Justo Sierra (DEMO)

Monorepositorio para Debian 13: **Tauri v2 + Vue 3 + Vite** y **API mock Python 3** sin paquetes externos.

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
python3 api/server.py
# Terminal 2
cd /home/dockbuy/repositorio/justo-sierra-kiosco/app
npm install
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

No activar cobros reales hasta disponer de `id_company`, `id_branch`, `user`, `pwd`, `Data 0`, clave AES, URLs QA/producción y callback de MIT. Webpay PLUS exige XML firmado/cifrado según su manual, validación de respuesta y confirmación de pago por servidor. El mock actual **sólo calcula una cotización** y nunca marca adeudos como pagados.

## 5. GitHub

El repositorio facilitado estaba vacío al consultarlo. Para subir el proyecto desde su carpeta:

```bash
git init
git branch -M main
git add .
git commit -m "feat: kiosco Justo Sierra Tauri + API mock"
git remote add origin https://github.com/Dockbuy/dockbuy-kiosco-justo-sierra.git
git push -u origin main
```

Si `origin` ya existe, omite `git remote add origin`. Para autenticación de Git usa SSH o credential manager; no compartas contraseñas ni tokens en la terminal.

## 6. Limitaciones actuales

- Los alumnos, importes y conceptos son **ficticios**, inspirados en la estructura visual mostrada, no están extraídos del sistema real.
- PIN demo común y tokens en RAM; **exclusivamente para pruebas locales**.
- No hay impresora, terminal física bancaria, Webpay real ni captura de pagos.
- Las imágenes de referencia proporcionadas por el usuario están integradas localmente en `app/public/images/`. No se descargan imágenes del sitio en ejecución.
- Google Fonts Inter requiere red; se usa fallback si el kiosco está desconectado. Para producción offline, instalar Inter localmente si se dispone de licencia/distribución adecuada.
- Deben revisarse autorización de uso del logotipo/fotografías y requisitos de privacidad antes del despliegue.

## Actualización: teclado táctil y títulos Roboto Condensed

En Inicio de sesión, toca Matrícula o Contraseña/PIN: se abrirá un teclado numérico propio, incluso cuando Debian no tenga teclado en pantalla. Usa `⌫` para borrar, `LISTO` para ocultarlo y el botón ENTRAR para iniciar sesión. No se instala ni requiere Onboard.

Encabezados, títulos y botones usan la familia Roboto Condensed (Google Fonts; para uso sin red es aconsejable instalar esta familia en el sistema Debian mediante el administrador de paquetes). Los textos normales mantienen Inter.

Para reemplazar la versión previa, primero detén la aplicación (Ctrl+C donde corre start-demo.sh), haz una copia de tu proyecto anterior y descomprime este ZIP desde `/home/dockbuy/repositorio`. Después ejecuta `bash scripts/start-demo.sh`.
