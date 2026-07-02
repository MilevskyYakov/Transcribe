use crate::settings::load_settings;
use serde::Serialize;
use std::{
    collections::VecDeque,
    fs,
    net::TcpListener,
    path::{Path, PathBuf},
    sync::Mutex,
    time::{SystemTime, UNIX_EPOCH},
};
use tauri::{Manager, Runtime};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

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
    pub(crate) output_dir: String,
    pub(crate) ffmpeg_available: bool,
    pub(crate) ffprobe_available: bool,
    pub(crate) ffmpeg_path: Option<String>,
    pub(crate) ffprobe_path: Option<String>,
    pub(crate) default_model_name: String,
    pub(crate) backend_lifecycle: BackendLifecycleSnapshot,
}

struct BackendRuntime {
    api_base_url: String,
    child: Option<CommandChild>,
    lifecycle: BackendLifecycleSnapshot,
}

pub(crate) struct BackendState {
    pub(crate) app_data_dir: PathBuf,
    pub(crate) cache_dir: PathBuf,
    pub(crate) output_dir: PathBuf,
    pub(crate) media_bin_dir: PathBuf,
    pub(crate) settings_path: PathBuf,
    pub(crate) default_model_name: Mutex<String>,
    config_path: PathBuf,
    runtime: Mutex<BackendRuntime>,
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
            if let Some(process) = runtime.child.take() {
                let _ = process.kill();
            }
        }
    }

    pub(crate) fn restart<R: Runtime>(
        &self,
        app: &tauri::AppHandle<R>,
    ) -> BackendLifecycleSnapshot {
        self.stop();
        self.set_lifecycle("restarting", "Перезапускаем…", None);
        self.spawn_backend(app);
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

    fn push_output(&self, line: String) {
        if let Ok(mut runtime) = self.runtime.lock() {
            let mut recent: VecDeque<String> = runtime.lifecycle.recent_output.drain(..).collect();
            recent.push_back(line.trim().to_string());
            while recent.len() > 20 {
                recent.pop_front();
            }
            runtime.lifecycle.recent_output = recent.into_iter().collect();
        }
    }

    fn spawn_backend<R: Runtime>(&self, app: &tauri::AppHandle<R>) {
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

        eprintln!("Starting Transcribe Doc backend on {api_base_url}");
        let sidecar = match app.shell().sidecar("transcribe-doc-backend") {
            Ok(command) => command.args(args),
            Err(error) => {
                self.set_lifecycle(
                    "error",
                    "Не удалось запустить",
                    Some(format!("Failed to prepare backend sidecar: {error}")),
                );
                return;
            }
        };
        let (mut rx, child) = match sidecar.spawn() {
            Ok(result) => result,
            Err(error) => {
                self.set_lifecycle(
                    "error",
                    "Не удалось запустить",
                    Some(format!("Failed to spawn backend sidecar: {error}")),
                );
                return;
            }
        };

        if let Ok(mut runtime) = self.runtime.lock() {
            runtime.child = Some(child);
            runtime.lifecycle.state = "checking".to_string();
            runtime.lifecycle.human_message = "Проверяем…".to_string();
            runtime.lifecycle.last_check_at = Some(now_stamp());
        }

        let app_handle = app.clone();
        tauri::async_runtime::spawn(async move {
            while let Some(event) = rx.recv().await {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let text = String::from_utf8_lossy(&line).to_string();
                            println!("transcribe-doc backend: {}", text);
                            state.push_output(format!("stdout: {text}"));
                        }
                        CommandEvent::Stderr(line) => {
                            let text = String::from_utf8_lossy(&line).to_string();
                            eprintln!("transcribe-doc backend: {}", text);
                            state.push_output(format!("stderr: {text}"));
                        }
                        CommandEvent::Terminated(payload) => {
                            let detail = format!("Backend process terminated: {payload:?}");
                            state.push_output(detail.clone());
                            state.set_lifecycle("error", "Не удалось запустить", Some(detail));
                        }
                        _ => {}
                    }
                }
            }
        });
    }
}

pub(crate) fn start_backend<R: Runtime>(
    app: &tauri::AppHandle<R>,
) -> Result<BackendState, Box<dyn std::error::Error>> {
    let app_data_dir = app.path().app_data_dir()?;
    let output_dir = app_data_dir.join("output");
    let cache_dir = app_data_dir.join("cache");
    let settings_path = app_data_dir.join("settings.json");
    fs::create_dir_all(&output_dir)?;
    fs::create_dir_all(app_data_dir.join("tmp"))?;
    fs::create_dir_all(&cache_dir)?;
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
        output_dir,
        media_bin_dir,
        settings_path,
        default_model_name: Mutex::new(settings.default_model_name),
        config_path,
        runtime: Mutex::new(BackendRuntime {
            api_base_url: String::new(),
            child: None,
            lifecycle: lifecycle_snapshot("starting", "Запускаем…", None::<String>),
        }),
    };
    state.spawn_backend(app);
    Ok(state)
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
