use crate::settings::{load_settings, AppSettings};
use serde::Serialize;
use std::{
    fs,
    io::{BufRead, BufReader},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{Manager, Runtime};

const READINESS_TIMEOUT: Duration = Duration::from_secs(30);
const PROCESS_POLL_INTERVAL: Duration = Duration::from_millis(100);
const RECENT_OUTPUT_LIMIT: usize = 50;

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
    pub(crate) desktop_platform: String,
    pub(crate) native_file_actions: bool,
    pub(crate) backend_lifecycle: BackendLifecycleSnapshot,
}

struct BackendRuntime {
    api_base_url: String,
    child: Option<Child>,
    lifecycle: BackendLifecycleSnapshot,
    generation: u64,
}

pub(crate) struct BackendState {
    pub(crate) app_data_dir: PathBuf,
    pub(crate) cache_dir: PathBuf,
    pub(crate) model_dir: PathBuf,
    pub(crate) output_dir: PathBuf,
    pub(crate) media_bin_dir: PathBuf,
    pub(crate) settings_path: PathBuf,
    pub(crate) settings: Mutex<AppSettings>,
    config_path: PathBuf,
    sidecar_path: PathBuf,
    runtime: Arc<Mutex<BackendRuntime>>,
}

impl Drop for BackendState {
    fn drop(&mut self) {
        if let Ok(mut runtime) = self.runtime.lock() {
            if let Some(mut process) = runtime.child.take() {
                stop_child(&mut process);
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

    pub(crate) fn restart(&self) -> BackendLifecycleSnapshot {
        let Ok(mut runtime) = self.runtime.lock() else {
            return self.lifecycle();
        };
        if let Some(mut process) = runtime.child.take() {
            stop_child(&mut process);
        }
        runtime.lifecycle = lifecycle_snapshot("restarting", "Перезапускаем…", None::<String>);
        self.spawn_backend_locked(&mut runtime, READINESS_TIMEOUT);
        runtime.lifecycle.clone()
    }

    fn spawn_backend(&self) {
        if let Ok(mut runtime) = self.runtime.lock() {
            self.spawn_backend_locked(&mut runtime, READINESS_TIMEOUT);
        }
    }

    fn spawn_backend_locked(&self, runtime: &mut BackendRuntime, readiness_timeout: Duration) {
        let port = match reserve_port() {
            Ok(port) => port,
            Err(error) => {
                runtime.lifecycle = lifecycle_snapshot(
                    "error",
                    "Не удалось запустить",
                    Some(format!("Failed to reserve local backend port: {error}")),
                );
                return;
            }
        };
        let api_base_url = format!("http://127.0.0.1:{port}");
        runtime.api_base_url = api_base_url.clone();
        runtime.lifecycle = lifecycle_snapshot("starting", "Запускаем…", None::<String>);

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
        let mut child = match Command::new(&self.sidecar_path)
            .args(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
        {
            Ok(child) => child,
            Err(error) => {
                runtime.lifecycle = lifecycle_snapshot(
                    "error",
                    "Не удалось запустить",
                    Some(format!(
                        "Failed to spawn backend sidecar at {}: {error}",
                        self.sidecar_path.display()
                    )),
                );
                return;
            }
        };

        runtime.generation += 1;
        let generation = runtime.generation;

        if let Some(stdout) = child.stdout.take() {
            let shared_runtime = Arc::clone(&self.runtime);
            thread::spawn(move || {
                for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                    println!("mnema backend: {line}");
                    capture_output(&shared_runtime, generation, line);
                }
            });
        }
        if let Some(stderr) = child.stderr.take() {
            let shared_runtime = Arc::clone(&self.runtime);
            thread::spawn(move || {
                for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                    eprintln!("mnema backend: {line}");
                    capture_output(&shared_runtime, generation, line);
                }
            });
        }

        runtime.child = Some(child);
        runtime.lifecycle.state = "checking".to_string();
        runtime.lifecycle.human_message = "Проверяем…".to_string();
        runtime.lifecycle.last_check_at = Some(now_stamp());
        monitor_child(Arc::clone(&self.runtime), generation, readiness_timeout);
    }
}

fn capture_output(runtime: &Arc<Mutex<BackendRuntime>>, generation: u64, line: String) {
    if let Ok(mut runtime) = runtime.lock() {
        if runtime.generation != generation {
            return;
        }
        runtime.lifecycle.recent_output.push(line);
        let overflow = runtime
            .lifecycle
            .recent_output
            .len()
            .saturating_sub(RECENT_OUTPUT_LIMIT);
        runtime.lifecycle.recent_output.drain(..overflow);
    }
}

fn monitor_child(
    runtime: Arc<Mutex<BackendRuntime>>,
    generation: u64,
    readiness_timeout: Duration,
) {
    thread::spawn(move || {
        let started_at = Instant::now();
        loop {
            thread::sleep(PROCESS_POLL_INTERVAL);
            let Ok(mut runtime) = runtime.lock() else {
                return;
            };
            if runtime.generation != generation {
                return;
            }
            let status = match runtime.child.as_mut() {
                Some(child) => child.try_wait(),
                None => return,
            };
            match status {
                Ok(Some(status)) => {
                    runtime.child = None;
                    let recent_output = std::mem::take(&mut runtime.lifecycle.recent_output);
                    let output = recent_output.last().cloned();
                    runtime.lifecycle = lifecycle_snapshot(
                        "error",
                        "Не удалось запустить",
                        Some(match output {
                            Some(output) => format!("Backend exited with {status}: {output}"),
                            None => format!("Backend exited with {status}"),
                        }),
                    );
                    runtime.lifecycle.recent_output = recent_output;
                    return;
                }
                Err(error) => {
                    runtime.child = None;
                    runtime.lifecycle = lifecycle_snapshot(
                        "error",
                        "Не удалось запустить",
                        Some(format!("Failed to inspect backend process: {error}")),
                    );
                    return;
                }
                Ok(None) => {}
            }
            if runtime.lifecycle.state != "online" && started_at.elapsed() >= readiness_timeout {
                if let Some(mut child) = runtime.child.take() {
                    stop_child(&mut child);
                }
                let recent_output = std::mem::take(&mut runtime.lifecycle.recent_output);
                runtime.lifecycle = lifecycle_snapshot(
                    "error",
                    "Не удалось запустить",
                    Some(format!(
                        "Backend readiness timed out after {} seconds",
                        readiness_timeout.as_secs_f64()
                    )),
                );
                runtime.lifecycle.recent_output = recent_output;
                return;
            }
        }
    });
}

fn stop_child(child: &mut Child) {
    match child.try_wait() {
        Ok(Some(_)) => {}
        _ => {
            let _ = child.kill();
            let _ = child.wait();
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
    let settings = load_settings(&settings_path)?;

    let resource_dir = app
        .path()
        .resource_dir()
        .ok()
        .map(|path| path.join("resources"))
        .filter(|path| path.join("configs/default.yaml").exists())
        .unwrap_or_else(dev_resource_dir);
    let config_path = resource_file(&resource_dir, "configs/default.yaml");
    let bundled_bin_dir = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
        .unwrap_or_else(|| resource_dir.join("bin"));
    let media_bin_dir = if binary_path(&bundled_bin_dir, "ffmpeg").is_some() {
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
        settings: Mutex::new(settings),
        config_path,
        sidecar_path: backend_sidecar_path(),
        runtime: Arc::new(Mutex::new(BackendRuntime {
            api_base_url: String::new(),
            child: None,
            lifecycle: lifecycle_snapshot("starting", "Запускаем…", None::<String>),
            generation: 0,
        })),
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
        .and_then(|path| {
            path.parent()
                .map(|dir| dir.join(executable_name("mnema-backend")))
        })
        .filter(|path| path.exists())
    {
        return path;
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(format!(
        "binaries/mnema-backend-{}{}",
        target_triple(),
        executable_suffix()
    ))
}

pub(crate) fn binary_path(root: &Path, name: &str) -> Option<PathBuf> {
    let path = root.join(executable_name(name));
    path.exists().then_some(path)
}

fn executable_name(name: &str) -> String {
    executable_name_for(name, cfg!(windows))
}

fn executable_name_for(name: &str, windows: bool) -> String {
    format!("{name}{}", if windows { ".exe" } else { "" })
}

#[cfg(windows)]
fn executable_suffix() -> &'static str {
    ".exe"
}

#[cfg(not(windows))]
fn executable_suffix() -> &'static str {
    ""
}

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
fn target_triple() -> &'static str {
    "aarch64-apple-darwin"
}

#[cfg(all(windows, target_arch = "x86_64"))]
fn target_triple() -> &'static str {
    "x86_64-pc-windows-msvc"
}

#[cfg(not(any(
    all(target_os = "macos", target_arch = "aarch64"),
    all(windows, target_arch = "x86_64")
)))]
compile_error!("Mnema desktop supports only macOS arm64 and Windows x64");

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
    use super::{
        binary_path, copy_missing_tree, executable_name_for, lifecycle_snapshot, BackendRuntime,
        BackendState, PROCESS_POLL_INTERVAL,
    };
    use crate::settings::AppSettings;
    use std::{
        fs,
        path::{Path, PathBuf},
        sync::{Arc, Mutex},
        thread,
        time::{Duration, Instant},
    };

    #[test]
    fn executable_names_cover_macos_and_windows() {
        assert_eq!(executable_name_for("mnema-backend", false), "mnema-backend");
        assert_eq!(
            executable_name_for("mnema-backend", true),
            "mnema-backend.exe"
        );

        let root = unique_temp_dir("binary-name");
        fs::create_dir_all(&root).unwrap();
        let expected = root.join(executable_name_for("ffmpeg", cfg!(windows)));
        fs::write(&expected, "binary").unwrap();
        assert_eq!(binary_path(&root, "ffmpeg"), Some(expected));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn migration_copies_missing_data_and_keeps_newer_files() {
        let root = unique_temp_dir("migration");
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

    #[test]
    fn early_exit_reports_status_and_output() {
        let root = unique_temp_dir("early-exit");
        let sidecar = write_sidecar(&root, "echo 'bind failed' >&2\nexit 23");
        let state = test_state(&root, sidecar);

        state.spawn_backend();
        let lifecycle = wait_for_state(&state, "error");

        assert!(lifecycle
            .technical_detail
            .as_deref()
            .unwrap()
            .contains("exit status: 23"));
        assert_eq!(lifecycle.recent_output, ["bind failed"]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn readiness_timeout_kills_and_reaps_child() {
        let root = unique_temp_dir("timeout");
        let sidecar = write_sidecar(&root, "exec sleep 30");
        let state = test_state(&root, sidecar);

        let mut runtime = state.runtime.lock().unwrap();
        state.spawn_backend_locked(&mut runtime, Duration::from_millis(150));
        drop(runtime);
        let lifecycle = wait_for_state(&state, "error");

        assert!(lifecycle
            .technical_detail
            .as_deref()
            .unwrap()
            .contains("readiness timed out"));
        assert!(state.runtime.lock().unwrap().child.is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn concurrent_restarts_leave_one_tracked_child() {
        let root = unique_temp_dir("restart");
        let sidecar = write_sidecar(&root, "exec sleep 30");
        let state = Arc::new(test_state(&root, sidecar));

        let first = {
            let state = Arc::clone(&state);
            thread::spawn(move || state.restart())
        };
        let second = {
            let state = Arc::clone(&state);
            thread::spawn(move || state.restart())
        };
        first.join().unwrap();
        second.join().unwrap();

        let runtime = state.runtime.lock().unwrap();
        assert!(runtime.child.is_some());
        assert_eq!(runtime.generation, 2);
        drop(runtime);
        drop(state);
        fs::remove_dir_all(root).unwrap();
    }

    fn test_state(root: &Path, sidecar_path: PathBuf) -> BackendState {
        BackendState {
            app_data_dir: root.to_path_buf(),
            cache_dir: root.join("cache"),
            model_dir: root.join("models"),
            output_dir: root.join("output"),
            media_bin_dir: root.join("bin"),
            settings_path: root.join("settings.json"),
            settings: Mutex::new(AppSettings {
                default_model_name: "tiny".to_string(),
                autosave_markdown_dir: None,
            }),
            config_path: root.join("config.yaml"),
            sidecar_path,
            runtime: Arc::new(Mutex::new(BackendRuntime {
                api_base_url: String::new(),
                child: None,
                lifecycle: lifecycle_snapshot("starting", "Запускаем…", None::<String>),
                generation: 0,
            })),
        }
    }

    fn write_sidecar(root: &Path, body: &str) -> PathBuf {
        use std::os::unix::fs::PermissionsExt;

        fs::create_dir_all(root).unwrap();
        let path = root.join("sidecar.sh");
        fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o755)).unwrap();
        path
    }

    fn wait_for_state(state: &BackendState, expected: &str) -> super::BackendLifecycleSnapshot {
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            let lifecycle = state.lifecycle();
            if lifecycle.state == expected {
                return lifecycle;
            }
            assert!(
                Instant::now() < deadline,
                "lifecycle remained {}",
                lifecycle.state
            );
            thread::sleep(PROCESS_POLL_INTERVAL);
        }
    }

    fn unique_temp_dir(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "mnema-{label}-{}-{:?}",
            std::process::id(),
            thread::current().id()
        ))
    }
}
