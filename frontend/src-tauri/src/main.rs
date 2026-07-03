mod backend;
mod commands;
mod settings;

use backend::{start_backend, BackendState};
use tauri::{Manager, WindowEvent};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(desktop)]
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;
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
            commands::backend_status,
            commands::mark_backend_offline,
            commands::mark_backend_online,
            commands::restart_backend,
            commands::set_autosave_markdown_dir,
            commands::set_default_model
        ])
        .run(tauri::generate_context!())
        .expect("error while running Transcribe Doc");
}
