# Estacionamiento demo · Dockbuy / Justo Sierra

Este parche incorpora emisión de tickets sin login, cotización demo y envío de tickets ESC/POS mediante CUPS. No registra pagos ni abre barrera. Usa SQLite en `api/parking-demo.sqlite3` y folios aleatorios (el QR solo contiene un folio, no datos personales).

## Dispositivos
- Impresora CASHINO KP-347 de 80 mm compatible con ESC/POS y QR nativo. El envío usa CUPS con `lp -o raw` (cola que acepte datos ESC/POS); verifica compatibilidad de la cola configurada y opciones de corte antes de operar.
- Lector QR USB en modo HID/teclado, configurado para **enviar Enter después de cada lectura**. También admite introducir folio con el teclado táctil. La cámara NO se usa en esta versión.

## Requisitos en Debian 13
```
command -v lp || sudo apt install -y cups-client
lpstat -p -d
lpoptions -d NOMBRE_COLA
```
Si no deseas cambiar la impresora por defecto, inicia la API con la variable `PARK_PRINTER=NOMBRE_COLA`, por ejemplo:
```
PARK_PRINTER=NOMBRE_COLA bash scripts/start-demo.sh
```
La impresora seleccionada debe aceptar trabajos RAW ESC/POS. `lpstat` puede mostrar la cola aunque el hardware no esté conectado: comprueba el ticket físico.

## Flujo
1. Inicio → ESTACIONAMIENTO → GENERAR TICKET: crea folio en base local y envía a imprimir el ticket con QR, fecha y tarifa DEMO. Si falla impresión, se puede reimprimir el mismo folio.
2. ESTACIONAMIENTO → CONSULTAR Y PAGAR: acerca el QR al lector USB, o pulsa el campo para escribir con el teclado en pantalla. Se calcula $20 por bloque iniciado de 8 horas, mínimo $20.
3. Se muestra **TOTAL A PAGAR**; ningún botón ejecuta un pago real.

## Endpoints públicos, solo localhost
- `POST /api/parking/issue` con `{}`
- `POST /api/parking/reprint` con `{"code":"JS-PARK-..."}`
- `POST /api/parking/quote` con `{"code":"JS-PARK-..."}`
- `GET /api/parking/printer`

**ATENCIÓN**: Solo demostración. La API corre en 127.0.0.1. Para producción deben agregarse control de acceso, antirreimpresión, registro de salidas, conciliación, reglas de cortesía/extravío, auditoría, pasarela de pago real, controles de abuso y reglas de estacionamiento institucionales.


### Impresión USB directa (cuando CUPS alimenta papel en blanco)

Validar primero `ls -l /dev/usb/lp0` y una impresión directa ESC/POS.
La aplicación se ejecuta como usuario normal y no debe usar sudo.
Para conceder acceso permanente: `sudo usermod -aG lp dockbuy` y **reiniciar sesión** (o el equipo).
Iniciar: `PARK_DEVICE=/dev/usb/lp0 bash scripts/start-demo.sh`.
Si no se define PARK_DEVICE, usa CUPS (`PARK_PRINTER` opcional).
