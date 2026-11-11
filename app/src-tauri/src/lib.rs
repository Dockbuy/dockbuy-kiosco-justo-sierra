#[cfg(target_os = "linux")]
mod linux_touch;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(target_os = "linux")]
            {
                use tauri::Manager;
                let window = app.get_webview_window("main").ok_or("Falta la ventana principal")?;
                window.with_webview(|webview| {
                    linux_touch::configure(&webview.inner());
                })?;
            }
            #[cfg(not(target_os = "linux"))]
            let _ = app;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Error iniciando el kiosco Justo Sierra");
}
