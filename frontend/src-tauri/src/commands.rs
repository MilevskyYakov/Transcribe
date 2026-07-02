use crate::{
    backend::{binary_path, AppBootstrap, BackendLifecycleSnapshot, BackendState},
    settings::{save_settings, AppSettings},
};

#[tauri::command]
pub(crate) fn app_bootstrap(state: tauri::State<'_, BackendState>) -> AppBootstrap {
    let ffmpeg_path = binary_path(&state.media_bin_dir, "ffmpeg");
    let ffprobe_path = binary_path(&state.media_bin_dir, "ffprobe");
    let default_model_name = state
        .default_model_name
        .lock()
        .map(|value| value.clone())
        .unwrap_or_else(|_| AppSettings::default().default_model_name);
    AppBootstrap {
        api_base_url: state.api_base_url(),
        app_data_dir: state.app_data_dir.display().to_string(),
        cache_dir: state.cache_dir.display().to_string(),
        output_dir: state.output_dir.display().to_string(),
        ffmpeg_available: ffmpeg_path.is_some(),
        ffprobe_available: ffprobe_path.is_some(),
        ffmpeg_path: ffmpeg_path.map(|path| path.display().to_string()),
        ffprobe_path: ffprobe_path.map(|path| path.display().to_string()),
        default_model_name,
        backend_lifecycle: state.lifecycle(),
    }
}

#[tauri::command]
pub(crate) fn backend_status(state: tauri::State<'_, BackendState>) -> BackendLifecycleSnapshot {
    state.lifecycle()
}

#[tauri::command]
pub(crate) fn mark_backend_online(
    state: tauri::State<'_, BackendState>,
) -> BackendLifecycleSnapshot {
    state.mark_online();
    state.lifecycle()
}

#[tauri::command]
pub(crate) fn mark_backend_offline(
    detail: String,
    state: tauri::State<'_, BackendState>,
) -> BackendLifecycleSnapshot {
    state.mark_offline(detail);
    state.lifecycle()
}

#[tauri::command]
pub(crate) fn restart_backend<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    state: tauri::State<'_, BackendState>,
) -> BackendLifecycleSnapshot {
    state.restart(&app)
}

#[tauri::command]
pub(crate) fn set_default_model(
    model_name: String,
    state: tauri::State<'_, BackendState>,
) -> Result<String, String> {
    let model_name = model_name.trim().to_string();
    if model_name.is_empty() {
        return Err("Model name cannot be empty".to_string());
    }
    save_settings(
        &state.settings_path,
        &AppSettings {
            default_model_name: model_name.clone(),
        },
    )
    .map_err(|error| format!("Failed to save default model: {error}"))?;
    if let Ok(mut current) = state.default_model_name.lock() {
        *current = model_name.clone();
    }
    Ok(model_name)
}
