# Zoom e inspector en el kiosco

La ventana Tauri ahora configura `devtools: false`, `zoomHotkeysEnabled: false`, pantalla completa, sin bordes ni controles para redimensionar/maximizar/minimizar. También desactiva el manejo nativo de archivos arrastrados. La desactivación del inspector se aplica aunque el arranque actual use `tauri:dev`.

## Corrección de touch y pinza en Linux

No se cancelan `touchstart`, `touchmove`, `touchend`, `touchcancel` ni los eventos de puntero al detectar varios dedos. Así se conserva la secuencia que WebKitGTK utiliza para generar clics. `touch-action: pan-x pan-y` se aplica también a los descendientes del kiosco: el teclado y otros paneles con scroll propio no pueden reactivar la pinza mediante `manipulation`. El desplazamiento y la opción Texto grande siguen disponibles.

En Linux, `zoomHotkeysEnabled: false` no basta para impedir la magnificación nativa. Al crear la ventana se desactiva solamente la fase de propagación de su `GtkGestureZoom`, sin destruirlo ni alterar los controladores de pulsación y desplazamiento. También se mantiene el zoom de página en 100 %. No se cambian la escala del monitor ni la lupa de Linux.

WebKitGTK no ofrece esta opción como un ajuste público de `Settings`: el adaptador utiliza la clave interna `wk-view-zoom-gesture` de GTK 3, comprobada en WebKitGTK 2.42.5 y 2.50.0, y valida el tipo del objeto antes de modificarlo. Tauri queda limitado a la serie 2.12 para evitar cambios incompatibles de los bindings nativos. Si WebKitGTK cambia esa clave, la aplicación muestra un aviso en la terminal y se debe revisar la integración; no se considera validado el bloqueo nativo en ese caso.

Al iniciar una versión actualizada debe aparecer:

```text
[kiosk] Linux: zoom por pinza desactivado; eventos táctiles habilitados.
```

Si aparece `AVISO: no se encontró GtkGestureZoom`, conservar ese mensaje y la versión de WebKitGTK para diagnóstico. No contiene datos de alumnos.

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

Para esta corrección, desde la carpeta del proyecto en Linux basta con cerrar el proceso anterior y ejecutar:

```bash
git switch KioskoJsEMR
git pull --ff-only origin KioskoJsEMR
bash scripts/start-demo.sh
```

El script conserva la configuración SIPAA existente y recompila la parte nativa. Si el acceso directo ejecuta un `.deb` o AppImage ya empaquetado, ese binario no se actualiza con `git pull`: hay que volver a construirlo con `npm --prefix app run tauri:build` y reinstalar/reemplazar el paquete. Para probar esta corrección puede usarse el script anterior.

Alt+F4 continúa disponible como salida del operador; el botón **Salir** de la interfaz solo cierra la sesión del alumno. La API, los alumnos demo, los adeudos y el proveedor de correo no cambian con esta actualización.

## Límites y comprobación en el equipo físico

Estas medidas controlan la aplicación. JavaScript en una pestaña normal no puede impedir todas las acciones del navegador: sus menús y algunos atajos se procesan fuera de la página. Por eso, para el kiosco instalado se usa la ventana Tauri con el inspector desactivado de forma nativa.

La lupa del escritorio, atajos de XFCE como Alt+Tab, teclas especiales del sistema, acceso a la terminal y notificaciones de otras aplicaciones son configuraciones de Linux. No se modifican desde este repositorio. Si al ampliar crecen también el escritorio o las ventanas externas, hay que revisar la ampliación del escritorio. No se debe confundir bloqueo de interfaz con autorización: los permisos de alumno/administrador continúan comprobándose en la API.

Prueba en la pantalla física: pinza con dos dedos, doble toque, Ctrl+rueda, Ctrl+`+`, F12 y clic derecho. Después comprueba desplazamiento, selección de pagos, correo, QR y Texto grande. Las pruebas automatizadas de navegador validan los eventos y el funcionamiento de la interfaz con detección Tauri simulada; **no sustituyen una prueba de WebKitGTK y del panel táctil real**.

La prueba `touch.spec.js` utiliza toques, contactos simultáneos y gestos de pinza/desplazamiento emulados en Chromium. El workflow `Kiosk Linux touch and zoom` compila con `Cargo.lock` y prueba sobre un WebView GTK real que el reconocedor de escala queda desactivado, los de clic/drag/swipe conservan su fase y el zoom de página vuelve a 100 %. Tampoco sustituye una prueba del panel físico.

En el kiosco: abrir y cerrar el teclado varias veces; tocar teclas rápidamente con ambas manos; levantar todos los dedos y seguir escribiendo; intentar pinza sobre el teclado y sobre una lista; arrastrar la lista con un dedo. No debe cambiar la escala ni quedar una capa del teclado después de Cerrar/Listo.

Referencias: [configuración de Tauri](https://v2.tauri.app/reference/config/#windowconfig) y [control de gestos con touch-action](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/touch-action).

Detalle nativo: [WebKitWebViewBase.cpp de WebKitGTK 2.50.0](https://github.com/WebKit/WebKit/blob/webkitgtk-2.50.0/Source/WebKit/UIProcess/API/gtk/WebKitWebViewBase.cpp) y [comportamiento de gestos GTK documentado en Wry](https://github.com/tauri-apps/wry/issues/544).
