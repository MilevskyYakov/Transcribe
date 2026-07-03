mod backend;
mod commands;
mod settings;

use backend::start_backend;
use tauri::Manager;

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
