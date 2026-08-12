use crate::settings::load_settings;
use serde::Serialize;
use std::{
    fs,
    io::{BufRead, BufReader},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{Manager, Runtime};

#[derive(Clone, Serialize)]
pub(crate) struct BackendLifecycleSnapshot {
    pub(crate) state: String,
    pub(crate) human_message: String,
    pub(crate) technical_detail: Option<String>,
    pub(crate) last_check_at: Option<String>,
    pub(crate) recent_output: Vec<String>,
}

#[derive(Serialize)]
pub(crate) struct AppBootstrap {
    pub(crate) api_base_url: String,
    pub(crate) app_data_dir: String,
    pub(crate) cache_dir: String,
    pub(crate) model_dir: String,
    pub(crate) output_dir: String,
    pub(crate) ffmpeg_available: bool,
    pub(crate) ffprobe_available: bool,
    pub(crate) ffmpeg_path: Option<String>,
    pub(crate) ffprobe_path: Option<String>,
    pub(crate) default_model_name: String,
    pub(crate) autosave_markdown_dir: Option<String>,
    pub(crate) backend_lifecycle: BackendLifecycleSnapshot,
}

struct BackendRuntime {
    api_base_url: String,
    child: Option<Child>,
    lifecycle: BackendLifecycleSnapshot,
}

pub(crate) struct BackendState {
    pub(crate) app_data_dir: PathBuf,
    pub(crate) cache_dir: PathBuf,
    pub(crate) model_dir: PathBuf,
    pub(crate) output_dir: PathBuf,
    pub(crate) media_bin_dir: PathBuf,
    pub(crate) settings_path: PathBuf,
    pub(crate) default_model_name: Mutex<String>,
    pub(crate) autosave_markdown_dir: Mutex<Option<String>>,
    config_path: PathBuf,
    runtime: Mutex<BackendRuntime>,
}

impl Drop for BackendState {
    fn drop(&mut self) {
        if let Ok(mut runtime) = self.runtime.lock() {
            if let Some(mut process) = runtime.child.take() {
                let _ = process.kill();
            }
        }
    }
}

impl BackendState {
    pub(crate) fn api_base_url(&self) -> String {
        self.runtime
            .lock()
            .map(|runtime| runtime.api_base_url.clone())
            .unwrap_or_default()
    }

    pub(crate) fn lifecycle(&self) -> BackendLifecycleSnapshot {
        self.runtime
            .lock()
            .map(|runtime| runtime.lifecycle.clone())
            .unwrap_or_else(|_| {
                lifecycle_snapshot(
                    "error",
                    "Не удалось запустить",
                    Some("backend runtime lock poisoned"),
                )
            })
    }

    pub(crate) fn mark_online(&self) {
        if let Ok(mut runtime) = self.runtime.lock() {
            runtime.lifecycle.state = "online".to_string();
            runtime.lifecycle.human_message = "Готово".to_string();
            runtime.lifecycle.technical_detail = None;
            runtime.lifecycle.last_check_at = Some(now_stamp());
        }
    }

    pub(crate) fn mark_offline(&self, detail: String) {
        if let Ok(mut runtime) = self.runtime.lock() {
            if runtime.lifecycle.state == "error" || runtime.lifecycle.state == "starting" {
                runtime.lifecycle.last_check_at = Some(now_stamp());
                return;
            }
            runtime.lifecycle.state = "offline".to_string();
            runtime.lifecycle.human_message = "Проверяем…".to_string();
            runtime.lifecycle.technical_detail = Some(detail);
            runtime.lifecycle.last_check_at = Some(now_stamp());
        }
    }

    pub(crate) fn stop(&self) {
        if let Ok(mut runtime) = self.runtime.lock() {
            if let Some(mut process) = runtime.child.take() {
                let _ = process.kill();
            }
        }
    }

    pub(crate) fn restart<R: Runtime>(
        &self,
        _app: &tauri::AppHandle<R>,
    ) -> BackendLifecycleSnapshot {
        self.stop();
        self.set_lifecycle("restarting", "Перезапускаем…", None);
        self.spawn_backend();
        self.lifecycle()
    }

    fn set_lifecycle(&self, state: &str, human_message: &str, detail: Option<String>) {
        if let Ok(mut runtime) = self.runtime.lock() {
            runtime.lifecycle.state = state.to_string();
            runtime.lifecycle.human_message = human_message.to_string();
            runtime.lifecycle.technical_detail = detail;
            runtime.lifecycle.last_check_at = Some(now_stamp());
        }
    }

    fn spawn_backend(&self) {
        let port = match reserve_port() {
            Ok(port) => port,
            Err(error) => {
                self.set_lifecycle(
                    "error",
                    "Не удалось запустить",
                    Some(format!("Failed to reserve local backend port: {error}")),
                );
                return;
            }
        };
        let api_base_url = format!("http://127.0.0.1:{port}");
        if let Ok(mut runtime) = self.runtime.lock() {
            runtime.api_base_url = api_base_url.clone();
            runtime.lifecycle = lifecycle_snapshot("starting", "Запускаем…", None::<String>);
        }

        let args = vec![
            "--config".to_string(),
            self.config_path.display().to_string(),
            "serve".to_string(),
            "--host".to_string(),
            "127.0.0.1".to_string(),
            "--port".to_string(),
            port.to_string(),
            "--app-data-dir".to_string(),
            self.app_data_dir.display().to_string(),
            "--media-bin-dir".to_string(),
            self.media_bin_dir.display().to_string(),
        ];

        eprintln!("Starting Mnema backend on {api_base_url}");
        let sidecar_path = backend_sidecar_path();
        let mut child = match Command::new(&sidecar_path)
            .args(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(error) => {
                self.set_lifecycle(
                    "error",
                    "Не удалось запустить",
                    Some(format!(
                        "Failed to spawn backend sidecar at {}: {error}",
                        sidecar_path.display()
                    )),
                );
                return;
            }
        };

        if let Some(stdout) = child.stdout.take() {
            thread::spawn(move || {
                for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                    println!("mnema backend: {line}");
                }
            });
        }
        if let Some(stderr) = child.stderr.take() {
            thread::spawn(move || {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    eprintln!("mnema backend: {line}");
                }
            });
        }

        if let Ok(mut runtime) = self.runtime.lock() {
            runtime.child = Some(child);
            runtime.lifecycle.state = "checking".to_string();
            runtime.lifecycle.human_message = "Проверяем…".to_string();
            runtime.lifecycle.last_check_at = Some(now_stamp());
        }
    }
}

pub(crate) fn start_backend<R: Runtime>(
    app: &tauri::AppHandle<R>,
) -> Result<BackendState, Box<dyn std::error::Error>> {
    let app_data_dir = app.path().app_data_dir()?;
    migrate_legacy_app_data(&app_data_dir)?;
    let output_dir = app_data_dir.join("output");
    let cache_dir = app_data_dir.join("cache");
    let model_dir = app_data_dir.join("models");
    let settings_path = app_data_dir.join("settings.json");
    fs::create_dir_all(&output_dir)?;
    fs::create_dir_all(app_data_dir.join("tmp"))?;
    fs::create_dir_all(&cache_dir)?;
    fs::create_dir_all(&model_dir)?;
    let settings = load_settings(&settings_path);

    let resource_dir = bundled_resource_dir_from_exe().unwrap_or_else(dev_resource_dir);
    let config_path = resource_file(&resource_dir, "configs/default.yaml");
    let bundled_bin_dir = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| resource_dir.join("bin"));
    let media_bin_dir = if bundled_bin_dir.join("ffmpeg").exists() {
        bundled_bin_dir
    } else {
        resource_dir.join("bin")
    };

    let state = BackendState {
        app_data_dir,
        cache_dir,
        model_dir,
        output_dir,
        media_bin_dir,
        settings_path,
        default_model_name: Mutex::new(settings.default_model_name),
        autosave_markdown_dir: Mutex::new(settings.autosave_markdown_dir),
        config_path,
        runtime: Mutex::new(BackendRuntime {
            api_base_url: String::new(),
            child: None,
            lifecycle: lifecycle_snapshot("starting", "Запускаем…", None::<String>),
        }),
    };
    state.spawn_backend();
    Ok(state)
}

fn migrate_legacy_app_data(app_data_dir: &Path) -> std::io::Result<()> {
    let Some(parent) = app_data_dir.parent() else {
        return Ok(());
    };
    copy_missing_tree(&parent.join("local.transcribe-doc"), app_data_dir)
}

fn copy_missing_tree(source: &Path, destination: &Path) -> std::io::Result<()> {
    if !source.is_dir() {
        return Ok(());
    }
    fs::create_dir_all(destination)?;
    for entry in fs::read_dir(source)? {
        let entry = entry?;
        let source_path = entry.path();
        let destination_path = destination.join(entry.file_name());
        if source_path.is_dir() {
            copy_missing_tree(&source_path, &destination_path)?;
        } else if !destination_path.exists() {
            let temporary_path = destination_path.with_extension("mnema-migration");
            let _ = fs::remove_file(&temporary_path);
            fs::copy(source_path, &temporary_path)?;
            fs::rename(temporary_path, destination_path)?;
        }
    }
    Ok(())
}

fn backend_sidecar_path() -> PathBuf {
    if let Some(path) = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|dir| dir.join("mnema-backend")))
        .filter(|path| path.exists())
    {
        return path;
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("binaries/mnema-backend-aarch64-apple-darwin")
}

pub(crate) fn binary_path(root: &Path, name: &str) -> Option<PathBuf> {
    let path = root.join(name);
    path.exists().then_some(path)
}

fn lifecycle_snapshot(
    state: &str,
    human_message: &str,
    technical_detail: Option<impl Into<String>>,
) -> BackendLifecycleSnapshot {
    BackendLifecycleSnapshot {
        state: state.to_string(),
        human_message: human_message.to_string(),
        technical_detail: technical_detail.map(Into::into),
        last_check_at: Some(now_stamp()),
        recent_output: Vec::new(),
    }
}

fn now_stamp() -> String {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => format!("{}", duration.as_secs()),
        Err(_) => "0".to_string(),
    }
}

fn reserve_port() -> Result<u16, std::io::Error> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

fn dev_resource_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("resources")
}

fn bundled_resource_dir_from_exe() -> Option<PathBuf> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
    let resource_dir = exe_dir.join("../Resources/resources");
    resource_dir
        .join("configs/default.yaml")
        .exists()
        .then_some(resource_dir)
}

fn resource_file(resource_dir: &Path, relative: &str) -> PathBuf {
    let path = resource_dir.join(relative);
    if path.exists() {
        return path;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../")
        .join(relative)
}

#[cfg(test)]
mod tests {
    use super::copy_missing_tree;
    use std::{fs, path::PathBuf};

    #[test]
    fn migration_copies_missing_data_and_keeps_newer_files() {
        let root = unique_temp_dir();
        let old = root.join("local.transcribe-doc");
        let new = root.join("local.mnema");
        fs::create_dir_all(old.join("models")).unwrap();
        fs::create_dir_all(&new).unwrap();
        fs::write(old.join("settings.json"), "old settings").unwrap();
        fs::write(old.join("models/model.bin"), "model").unwrap();
        fs::write(new.join("settings.json"), "new settings").unwrap();

        copy_missing_tree(&old, &new).unwrap();
        copy_missing_tree(&old, &new).unwrap();

        assert_eq!(
            fs::read_to_string(new.join("settings.json")).unwrap(),
            "new settings"
        );
        assert_eq!(
            fs::read_to_string(new.join("models/model.bin")).unwrap(),
            "model"
        );
        assert!(old.join("models/model.bin").exists());
        fs::remove_dir_all(root).unwrap();
    }

    fn unique_temp_dir() -> PathBuf {
        std::env::temp_dir().join(format!("mnema-migration-{}", std::process::id()))
    }
}
