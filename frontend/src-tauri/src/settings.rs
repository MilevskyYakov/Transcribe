use serde::{Deserialize, Serialize};
use std::{
    fs::{self, File},
    io::{self, Write},
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub(crate) struct AppSettings {
    pub(crate) default_model_name: String,
    #[serde(default)]
    pub(crate) autosave_markdown_dir: Option<String>,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            default_model_name: "large-v3".to_string(),
            autosave_markdown_dir: None,
        }
    }
}

pub(crate) fn load_settings(path: &Path) -> Result<AppSettings, Box<dyn std::error::Error>> {
    let content = match fs::read_to_string(path) {
        Ok(content) => content,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(AppSettings::default()),
        Err(error) => return Err(error.into()),
    };
    serde_json::from_str(&content).map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("Failed to parse settings JSON: {error}"),
        )
        .into()
    })
}

pub(crate) fn save_settings(
    path: &Path,
    settings: &AppSettings,
) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let content = serde_json::to_string_pretty(settings)?;
    let temporary_path = temporary_path(path);
    let mut file = File::create(&temporary_path)?;
    file.write_all(content.as_bytes())?;
    file.sync_all()?;
    fs::rename(&temporary_path, path)?;
    if let Some(parent) = path.parent() {
        File::open(parent)?.sync_all()?;
    }
    Ok(())
}

fn temporary_path(path: &Path) -> PathBuf {
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("settings.json");
    path.with_file_name(format!(".{file_name}.tmp"))
}

#[cfg(test)]
mod tests {
    use super::{load_settings, save_settings, temporary_path, AppSettings};
    use std::fs;

    #[test]
    fn missing_settings_use_defaults_and_corrupt_settings_return_error() {
        let root = unique_temp_dir("load");
        let path = root.join("settings.json");

        assert_eq!(load_settings(&path).unwrap(), AppSettings::default());
        fs::create_dir_all(&root).unwrap();
        fs::write(&path, "{not json").unwrap();
        assert!(load_settings(&path)
            .unwrap_err()
            .to_string()
            .contains("Failed to parse settings JSON"));
        assert_eq!(fs::read_to_string(&path).unwrap(), "{not json");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_atomic_write_keeps_last_valid_settings() {
        let root = unique_temp_dir("save");
        let path = root.join("settings.json");
        let original = AppSettings::default();
        save_settings(&path, &original).unwrap();
        fs::create_dir(temporary_path(&path)).unwrap();

        let changed = AppSettings {
            default_model_name: "tiny".to_string(),
            autosave_markdown_dir: Some("/tmp/transcripts".to_string()),
        };
        assert!(save_settings(&path, &changed).is_err());
        assert_eq!(load_settings(&path).unwrap(), original);
        fs::remove_dir_all(root).unwrap();
    }

    fn unique_temp_dir(label: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "mnema-settings-{label}-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ))
    }
}
