use crate::settings::load_settings;
use serde::Serialize;
use std::{
    fs,
    net::TcpListener,
    path::{Path, PathBuf},
    sync::Mutex,
};
use tauri::{Manager, Runtime};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

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
}

pub(crate) struct BackendState {
    pub(crate) api_base_url: String,
    pub(crate) app_data_dir: PathBuf,
    pub(crate) cache_dir: PathBuf,
    pub(crate) output_dir: PathBuf,
    pub(crate) media_bin_dir: PathBuf,
    pub(crate) settings_path: PathBuf,
    pub(crate) default_model_name: Mutex<String>,
    child: Mutex<Option<CommandChild>>,
}

impl BackendState {
    pub(crate) fn stop(&self) {
        if let Ok(mut child) = self.child.lock() {
            if let Some(process) = child.take() {
                let _ = process.kill();
            }
        }
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
    let port = reserve_port()?;
    let api_base_url = format!("http://127.0.0.1:{port}");

    let args = vec![
        "--config".to_string(),
        config_path.display().to_string(),
        "serve".to_string(),
        "--host".to_string(),
        "127.0.0.1".to_string(),
        "--port".to_string(),
        port.to_string(),
        "--app-data-dir".to_string(),
        app_data_dir.display().to_string(),
        "--media-bin-dir".to_string(),
        media_bin_dir.display().to_string(),
    ];

    eprintln!("Starting Transcribe Doc backend on {api_base_url}");
    let sidecar = app.shell().sidecar("transcribe-doc-backend")?.args(args);
    let (mut rx, child) = sidecar.spawn()?;
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("transcribe-doc backend: {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("transcribe-doc backend: {}", String::from_utf8_lossy(&line));
                }
                _ => {}
            }
        }
    });

    Ok(BackendState {
        api_base_url,
        app_data_dir,
        cache_dir,
        output_dir,
        media_bin_dir,
        settings_path,
        default_model_name: Mutex::new(settings.default_model_name),
        child: Mutex::new(Some(child)),
    })
}

pub(crate) fn binary_path(root: &Path, name: &str) -> Option<PathBuf> {
    let path = root.join(name);
    path.exists().then_some(path)
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
