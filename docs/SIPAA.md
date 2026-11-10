# Consulta institucional de adeudos SIPAA

Implementación basada en las imágenes y el texto del **Manual de integración y uso de APIs Rest Para kiosco de pago**, recibido el 10 de noviembre de 2026, páginas 2, 3, 5 y 7–11. El usuario confirmó que la matrícula y contraseña son las del formulario del kiosco y que `system_code` es **AP**.

## Iniciar desde VS Code en Windows

Abre la carpeta del repositorio y dos terminales PowerShell en su raíz. Después de recibir los cambios de **KioskoJsEMR**, en la primera terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r api/requirements.txt
$env:KIOSCO_DATA_SOURCE="sipaa"
.\.venv\Scripts\python.exe api/server.py
```

Si ya existe `.venv`, omite la primera línea. No necesitas activar el entorno virtual, usar `sudo` ni modificar la política de PowerShell. Si `python` no está disponible pero tienes el lanzador de Windows, usa `py -3 -m venv .venv` para crearlo.

En la segunda terminal:

```powershell
npm run setup
npm run dev
```

Abre **http://127.0.0.1:1420** e ingresa tu matrícula y contraseña reales. No las escribas en comandos, en `.env`, en GitHub ni en el chat. Para inspeccionar la trazabilidad usa `npm run dev:trace` en lugar de `npm run dev`; ambos usan el puerto 1420. Si ya hay una interfaz abierta en otra terminal, detenla con **Ctrl+C** antes de reiniciarla.

En Debian, los comandos de la API son `.venv/bin/python -m pip install -r api/requirements.txt` y `KIOSCO_DATA_SOURCE=sipaa .venv/bin/python api/server.py`; la interfaz conserva los comandos npm existentes.

## Flujo implementado

1. El navegador envía `{matricula,password}` a la API local, `POST /api/auth/login`.
2. La API local envía **HTTPS POST** a `https://sipaa-erp.justo-sierra.net/api/loginApp/direct` con `{username: matricula, password, system_code: "AP"}`. La contraseña se usa tal como se escribió, sin quitar espacios ni cambiar mayúsculas.
3. Se valida el esquema de la imagen de la página 3: `success: true`, `data.token`, `data.token_type: "Bearer"`, `data.expires_at`; el nombre visible procede de `data.user.name`. No se sigue `redirect_url` ni se expone el resto del perfil.
4. La API consulta `POST https://sipaa-erp.justo-sierra.net/api/kardexStudent`, encabezados `Authorization: Bearer <token>`, `Content-Type: application/json`, `Accept: application/json`, cuerpo `{tuition: matricula}`.
5. Solo tras obtener un kardex válido se crea una sesión local. El navegador recibe un token local aleatorio, diferente del institucional. La matrícula se toma de esa sesión en las consultas posteriores; no se acepta cambiar de alumno mediante la URL o el cuerpo de la cotización.
6. La contraseña se limpia del formulario al terminar el intento. El token SIPAA permanece únicamente en la memoria de la API, asociado a esa sesión; no se guarda en SQLite, archivos, localStorage ni trazas. Cerrar sesión elimina la asociación. Un 401/403 de KardexStudent revoca la sesión local y obliga a volver a ingresar; no se retiene la contraseña para renovar automáticamente.

La sesión local dura como máximo 10 minutos y respeta un vencimiento institucional anterior. Se mantiene el cierre por inactividad de la interfaz. El ejemplo de `expires_at` no incluye zona: se interpreta en **America/Mexico_City**, configurable con `SIPAA_TIMEZONE` si el proveedor utiliza otra. `tzdata` permite resolverla también en Windows.

## Adaptación del kardex

| Campo del proveedor | Uso en el kiosco |
| --- | --- |
| `concepts[<idCiclo>]` | Se recorren todos los ciclos, incluidos anteriores. |
| Concepto `type: "contract"`, arreglo `payments` | Una fila por mensualidad; hereda nombre, grupo y ciclo del contrato. |
| Concepto directo dentro del ciclo | Una fila de pago único. El PDF describe la ubicación, pero no trae un ejemplo completo de esa variante. |
| `name`, `group`, `cycle` | `nombre`, `grupo`, `ciclo`. |
| `periodDesc` / `period` | Periodo visible. |
| `date_expiration` | `fechaVencimiento`, validada como fecha ISO. |
| `pending_amount` | `restante`, saldo autoritativo. **No** se recalcula a partir de `total_amount`, beca o descuento. |
| `dayStateDesc` | Estado descriptivo. |
| `id` del pago + contrato + ciclo | Identificador estable con ámbito; evita colisiones entre tablas. |
| `dateConsult` | Fecha de consulta informada por SIPAA. |

Para el pago único se admiten los campos anteriores o sus equivalentes normalizados `nombre`, `grupo`, `ciclo`, `periodo`, `fechaVencimiento`, `restante`. Esta variante requiere verificar una respuesta real. Una estructura desconocida, moneda diferente de MXN, matrícula distinta, ID duplicado, fecha o importe inválido produce un error visible: nunca se sustituye por adeudos demo ni por saldo cero.

Los conceptos con saldo cero se excluyen. `{concepts:{}}` o `{concepts:[]}` con éxito es una consulta válida sin adeudos. Se ordena por vencimiento y luego ID numérico del concepto, con desempate estable por ámbito. La interfaz conserva ese orden incluso con IDs compuestos.

El carrito mantiene la distribución 2/3 y 1/3. Solo se puede agregar el siguiente adeudo, devolver el último o cancelar la selección completa. **Actualizar saldos** consulta de nuevo; una consulta fallida bloquea el uso del listado anterior hasta reintentar correctamente.

**Continuar** llama a `POST /api/payments/quote`; el servidor vuelve a consultar SIPAA, verifica que los IDs sigan siendo el prefijo permitido y muestra los importes nuevos. Si desapareció un concepto o cambió su orden, responde 409 y actualiza la lista. Los totales de la API usan aritmética decimal.

## Alcance y límites

Este manual solo entrega **autenticación y consulta**. No incluye registro/liquidación de pagos, pasarela bancaria, reversos, historial de comprobantes, facturación ni notificaciones. En modo SIPAA se deshabilitan esos módulos y todas las rutas de demostración, incluso si se llaman directamente. No se guarda ni se imprime un pago simulado sobre adeudos institucionales. Los servicios del campus tampoco se presentan como datos reales.

Las consultas y selecciones no escriben adeudos en SQLite. Los archivos SQLite existentes siguen siendo de la demostración y no se usan para descontar saldos SIPAA. La trazabilidad detallada continúa en memoria y excluye contraseña, matrícula, nombres, tokens, importes y cuerpos HTTP.

La API local permanece ligada a `127.0.0.1:8787`, con sus controles previos de Origin, Host, JSON, tamaño y concurrencia. La salida institucional valida TLS, no sigue redirecciones, limita la respuesta a 2 MiB y dispone de plazo de 4 segundos por operación de red, dos consultas concurrentes y 30 solicitudes por minuto. Los errores enviados al navegador no contienen el cuerpo de error del proveedor.

`GET /api/health` confirma que la **API local** funciona y muestra `modo: "SIPAA"`; no demuestra por sí solo que SIPAA haya aceptado credenciales. La validación completa requiere un inicio de sesión autorizado contra la institución.

## Configuración y diagnóstico

SIPAA es el modo predeterminado. Configuración opcional en `api/.env`, ignorado por Git:

```dotenv
KIOSCO_DATA_SOURCE=sipaa
SIPAA_BASE_URL=https://sipaa-erp.justo-sierra.net/api
SIPAA_TIMEZONE=America/Mexico_City
```

`AP` es fijo en el gateway, no viene del navegador. No hay `SIPAA_USERNAME` ni `SIPAA_PASSWORD` de servicio. Las variables de proceso tienen prioridad sobre `.env`. No sobrescribas un archivo que ya contenga configuración de correo o administración.

Diagnóstico opcional desde la raíz (solicita contraseña sin mostrarla; no cobra ni persiste datos):

```powershell
.\.venv\Scripts\python.exe api/check_sipaa.py
```

Para volver a probar los módulos ficticios, detén la API, ejecuta `$env:KIOSCO_DATA_SOURCE="demo"` y vuelve a iniciarla. Solo entonces funcionan `202210` / `202211`, PIN `1234`. Recarga el navegador al cambiar de modo.

Las pruebas automatizadas usan respuestas ficticias con la estructura de las imágenes del PDF. No prueban cuentas reales ni realizan pagos. Antes de habilitar cobro se necesitan su contrato de API y pruebas de confirmación, idempotencia y conciliación con el proveedor.
