mod backend;
mod commands;
mod settings;

use backend::{start_backend, BackendState};
use tauri::{Manager, WindowEvent};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let state = start_backend(app.handle())?;
            app.manage(state);
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                if let Some(state) = window.app_handle().try_state::<BackendState>() {
                    state.stop();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::app_bootstrap,
            commands::set_default_model
        ])
        .run(tauri::generate_context!())
        .expect("error while running Transcribe Doc");
}
