# Zoom e inspector en el kiosco

La ventana Tauri ahora configura `devtools: false`, `zoomHotkeysEnabled: false`, pantalla completa, sin bordes ni controles para redimensionar/maximizar/minimizar. También desactiva el manejo nativo de archivos arrastrados. La desactivación del inspector se aplica aunque el arranque actual use `tauri:dev`.

En la interfaz del kiosco se bloquean:

- Ctrl/Cmd con `+`, `-` o `0`, incluyendo teclado numérico, y Ctrl/Cmd con rueda/trackpad.
- Pinza de dos dedos, gestos de escala de WebKit y zoom por doble toque mediante `touch-action` y viewport.
- F12, Ctrl+Shift+I/J/C/K, Cmd+Alt+I/J/C y el menú contextual (clic derecho, pulsación larga o Shift+F10).
- Recarga, impresión del navegador, guardado, ver código fuente, búsqueda, abrir archivo y barra de dirección cuando esos atajos llegan a la página.
- Navegación atrás/adelante por Alt+flecha y apertura de archivos al arrastrarlos sobre la ventana.

Se conservan el scroll con un dedo o rueda normal, clics, teclado táctil, lector QR, escritura de correo, AltGr, copiar/pegar/deshacer y Backspace dentro de campos. **Texto grande**, **Alto contraste** y **Más tiempo** siguen disponibles desde Accesibilidad.

## Activación y mantenimiento

En Tauri se activa automáticamente. En una compilación web de producción se aplica al kiosco público; el panel `/admin` abierto en el navegador del operador conserva sus controles normales. El navegador usado para desarrollo con `npm run dev` sigue permitiendo inspeccionar y depurar. No hay una contraseña, parámetro de URL ni botón público que habilite el inspector nativo.

Para actualizar el kiosco Debian, cierra su ventana con **Alt+F4**, abre la terminal en la carpeta del proyecto y ejecuta:

```bash
git fetch origin
git switch KioskoJsEMR
git pull --ff-only origin KioskoJsEMR
npm run setup
bash scripts/start-demo.sh
```

El comando de arranque vuelve a compilar Tauri con la nueva configuración. Se necesita **cerrar y volver a abrir la aplicación**: recargar únicamente la página no cambia la configuración nativa del inspector. El autoinicio XFCE existente también usa este arranque y toma la configuración al volver a iniciar el kiosco.

Alt+F4 continúa disponible como salida del operador; el botón **Salir** de la interfaz solo cierra la sesión del alumno. La API, los alumnos demo, los adeudos y el proveedor de correo no cambian con esta actualización.

## Límites y comprobación en el equipo físico

Estas medidas controlan la aplicación. JavaScript en una pestaña normal no puede impedir todas las acciones del navegador: sus menús y algunos atajos se procesan fuera de la página. Por eso, para el kiosco instalado se usa la ventana Tauri con el inspector desactivado de forma nativa.

La lupa del escritorio, atajos de XFCE como Alt+Tab, teclas especiales del sistema, acceso a la terminal y notificaciones de otras aplicaciones son configuraciones de Linux. No se modifican desde este repositorio. Si al ampliar crecen también el escritorio o las ventanas externas, hay que revisar la ampliación del escritorio. No se debe confundir bloqueo de interfaz con autorización: los permisos de alumno/administrador continúan comprobándose en la API.

Prueba en la pantalla física: pinza con dos dedos, doble toque, Ctrl+rueda, Ctrl+`+`, F12 y clic derecho. Después comprueba desplazamiento, selección de pagos, correo, QR y Texto grande. Las pruebas automatizadas de navegador validan los eventos y el funcionamiento de la interfaz con detección Tauri simulada; **no sustituyen una prueba de WebKitGTK y del panel táctil real**.

Referencias: [configuración de Tauri](https://v2.tauri.app/reference/config/#windowconfig) y [control de gestos con touch-action](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/touch-action).
