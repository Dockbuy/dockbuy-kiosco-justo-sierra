use gtk::{glib, prelude::*};
use webkit2gtk::{WebView, WebViewExt};

// WebKitGTK 4.1 / GTK 3 guarda un GtkGestureZoom propio en este qdata.
// No es una API pública: comprobar presencia y tipo, y avisar si cambia.
// Fuente: WebKitWebViewBase.cpp (webkitgtk-2.42.5 y webkitgtk-2.50.0).
const ZOOM_GESTURE: &[u8] = b"wk-view-zoom-gesture\0";

fn gesture_object(view: &WebView, key: &[u8]) -> Option<glib::Object> {
    // SAFETY: solo se pasan las claves constantes de WebKitGTK que contienen
    // GObjects. Se ejecuta en el hilo GTK con el WebView vivo. from_glib_none
    // toma una referencia propia; no libera ni sustituye el qdata de WebKit.
    unsafe {
        let pointer = glib::gobject_ffi::g_object_get_data(
            view.as_ptr().cast(),
            key.as_ptr().cast(),
        );
        if pointer.is_null() {
            None
        } else {
            Some(glib::translate::from_glib_none(
                pointer.cast::<glib::gobject_ffi::GObject>(),
            ))
        }
    }
}

pub(crate) fn configure(view: &WebView) -> bool {
    // El zoom de página y la magnificación por pinza son mecanismos distintos.
    view.set_zoom_level(1.0);
    view.connect_zoom_level_notify(|view| {
        if view.zoom_level() != 1.0 {
            view.set_zoom_level(1.0);
        }
    });

    let zoom = gesture_object(view, ZOOM_GESTURE)
        .and_then(|object| object.downcast::<gtk::GestureZoom>().ok());
    let Some(zoom) = zoom else {
        eprintln!("[kiosk] AVISO: no se encontró GtkGestureZoom; verificar el bloqueo de pinza en este WebKitGTK.");
        return false;
    };

    // Deshabilitar únicamente el reconocedor de escala. No consumir eventos
    // táctiles, destruir controladores ni modificar los de clic/drag/swipe.
    zoom.set_propagation_phase(gtk::PropagationPhase::None);
    eprintln!("[kiosk] Linux: zoom por pinza desactivado; eventos táctiles habilitados.");
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_zoom_is_disabled_without_disabling_clicks_or_scrolling() {
        gtk::init().expect("La prueba necesita una pantalla GTK (usar xvfb-run en CI)");
        let view = WebView::new();
        let controllers = [
            b"wk-view-multi-press-gesture\0".as_slice(),
            b"wk-view-drag-gesture\0".as_slice(),
            b"wk-view-swipe-gesture\0".as_slice(),
        ].map(|key| {
            let object = gesture_object(&view, key).expect("Falta un controlador táctil de WebKitGTK");
            let controller = object.downcast::<gtk::EventController>().unwrap();
            let phase = controller.propagation_phase();
            assert_ne!(phase, gtk::PropagationPhase::None);
            (controller, phase)
        });

        assert!(configure(&view));
        let zoom = gesture_object(&view, ZOOM_GESTURE).unwrap()
            .downcast::<gtk::GestureZoom>().unwrap();
        assert_eq!(zoom.propagation_phase(), gtk::PropagationPhase::None);
        for (controller, phase) in controllers {
            assert_eq!(controller.propagation_phase(), phase);
        }
        for scale in [1.25, 0.75, 2.0, 1.0] {
            view.set_zoom_level(scale);
            assert_eq!(view.zoom_level(), 1.0);
        }
    }
}
