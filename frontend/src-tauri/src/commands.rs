use crate::{
    backend::{binary_path, AppBootstrap, BackendLifecycleSnapshot, BackendState},
    settings::{save_settings, AppSettings},
};
use std::{
    path::{Path, PathBuf},
    process::Command,
};

#[tauri::command]
pub(crate) fn app_bootstrap(state: tauri::State<'_, BackendState>) -> AppBootstrap {
    let ffmpeg_path = binary_path(&state.media_bin_dir, "ffmpeg");
    let ffprobe_path = binary_path(&state.media_bin_dir, "ffprobe");
    let settings = state
        .settings
        .lock()
        .map(|value| value.clone())
        .unwrap_or_default();
    AppBootstrap {
        api_base_url: state.api_base_url(),
        app_data_dir: state.app_data_dir.display().to_string(),
        cache_dir: state.cache_dir.display().to_string(),
        model_dir: state.model_dir.display().to_string(),
        output_dir: state.output_dir.display().to_string(),
        ffmpeg_available: ffmpeg_path.is_some(),
        ffprobe_available: ffprobe_path.is_some(),
        ffmpeg_path: ffmpeg_path.map(|path| path.display().to_string()),
        ffprobe_path: ffprobe_path.map(|path| path.display().to_string()),
        default_model_name: settings.default_model_name,
        autosave_markdown_dir: settings.autosave_markdown_dir,
        backend_lifecycle: state.lifecycle(),
    }
}

#[tauri::command]
pub(crate) fn backend_status(state: tauri::State<'_, BackendState>) -> BackendLifecycleSnapshot {
    state.lifecycle()
}

#[tauri::command]
pub(crate) fn is_regular_file_path(path: String) -> bool {
    Path::new(&path).is_file()
}

#[tauri::command]
pub(crate) fn open_saved_markdown(path: String) -> Result<(), String> {
    run_macos_open(&existing_file(&path)?, false)
}

#[tauri::command]
pub(crate) fn reveal_saved_markdown(path: String) -> Result<(), String> {
    run_macos_open(&existing_file(&path)?, true)
}

fn existing_file(path: &str) -> Result<PathBuf, String> {
    let path = Path::new(path);
    if !path.is_file() {
        return Err("Markdown file does not exist".to_string());
    }
    path.canonicalize()
        .map_err(|error| format!("Failed to resolve Markdown path: {error}"))
}

#[cfg(target_os = "macos")]
fn run_macos_open(path: &Path, reveal: bool) -> Result<(), String> {
    let mut command = Command::new("/usr/bin/open");
    if reveal {
        command.arg("-R");
    }
    let status = command
        .arg(path)
        .status()
        .map_err(|error| format!("Failed to launch macOS open command: {error}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("macOS open command failed with status {status}"))
    }
}

#[cfg(not(target_os = "macos"))]
fn run_macos_open(_path: &Path, _reveal: bool) -> Result<(), String> {
    Err("Opening saved Markdown is supported only on macOS".to_string())
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
pub(crate) fn restart_backend(state: tauri::State<'_, BackendState>) -> BackendLifecycleSnapshot {
    state.restart()
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
    update_settings(&state.settings, &state.settings_path, |settings| {
        settings.default_model_name = model_name.clone();
    })
    .map_err(|error| format!("Failed to save default model: {error}"))?;
    Ok(model_name)
}

#[tauri::command]
pub(crate) fn set_autosave_markdown_dir(
    dir: Option<String>,
    state: tauri::State<'_, BackendState>,
) -> Result<Option<String>, String> {
    let normalized = dir.and_then(|value| {
        let trimmed = value.trim().to_string();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed)
        }
    });
    update_settings(&state.settings, &state.settings_path, |settings| {
        settings.autosave_markdown_dir = normalized.clone();
    })
    .map_err(|error| format!("Failed to save autosave folder: {error}"))?;
    Ok(normalized)
}

fn update_settings(
    settings: &std::sync::Mutex<AppSettings>,
    settings_path: &Path,
    update: impl FnOnce(&mut AppSettings),
) -> Result<(), Box<dyn std::error::Error>> {
    let mut current = settings.lock().map_err(|_| "settings lock poisoned")?;
    let mut changed = current.clone();
    update(&mut changed);
    save_settings(settings_path, &changed)?;
    *current = changed;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{existing_file, update_settings};
    use crate::settings::{load_settings, AppSettings};
    use std::{
        fs,
        sync::{Arc, Mutex},
        thread,
    };

    #[test]
    fn existing_file_accepts_files_and_rejects_missing_paths() {
        let path = std::env::temp_dir().join(format!("mnema-markdown-{}.md", std::process::id()));
        fs::write(&path, "# Mnema").unwrap();

        assert_eq!(
            existing_file(path.to_str().unwrap()).unwrap(),
            path.canonicalize().unwrap()
        );
        fs::remove_file(&path).unwrap();
        assert_eq!(
            existing_file(path.to_str().unwrap()).unwrap_err(),
            "Markdown file does not exist"
        );
    }

    #[test]
    fn concurrent_setting_updates_preserve_both_values() {
        let root = std::env::temp_dir().join(format!(
            "mnema-command-settings-{}-{:?}",
            std::process::id(),
            thread::current().id()
        ));
        let path = Arc::new(root.join("settings.json"));
        let settings = Arc::new(Mutex::new(AppSettings::default()));

        let model_update = {
            let path = Arc::clone(&path);
            let settings = Arc::clone(&settings);
            thread::spawn(move || {
                update_settings(&settings, &path, |value| {
                    value.default_model_name = "tiny".to_string();
                })
                .unwrap();
            })
        };
        let folder_update = {
            let path = Arc::clone(&path);
            let settings = Arc::clone(&settings);
            thread::spawn(move || {
                update_settings(&settings, &path, |value| {
                    value.autosave_markdown_dir = Some("/tmp/transcripts".to_string());
                })
                .unwrap();
            })
        };
        model_update.join().unwrap();
        folder_update.join().unwrap();

        assert_eq!(
            load_settings(&path).unwrap(),
            AppSettings {
                default_model_name: "tiny".to_string(),
                autosave_markdown_dir: Some("/tmp/transcripts".to_string()),
            }
        );
        fs::remove_dir_all(root).unwrap();
    }
}
