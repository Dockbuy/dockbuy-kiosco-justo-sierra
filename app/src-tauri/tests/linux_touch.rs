// El harness predeterminado de Rust crea hilos incluso con test-threads=1.
// Este ejecutable comprueba el mismo adaptador en el hilo principal de GTK.
#[cfg(target_os = "linux")]
#[path = "../src/linux_touch.rs"]
mod linux_touch;

fn main() {
    #[cfg(target_os = "linux")]
    {
        linux_touch::tests::native_zoom_is_disabled_without_disabling_clicks_or_scrolling();
        println!("Linux touch: native zoom, click and scroll controller checks passed");
    }
    #[cfg(not(target_os = "linux"))]
    println!("Linux touch: requiere Linux y una pantalla GTK");
}
