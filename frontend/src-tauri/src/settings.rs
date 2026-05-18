use serde::{Deserialize, Serialize};
use std::{fs, path::Path};

#[derive(Deserialize, Serialize)]
pub(crate) struct AppSettings {
    pub(crate) default_model_name: String,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            default_model_name: "large-v3".to_string(),
        }
    }
}

pub(crate) fn load_settings(path: &Path) -> AppSettings {
    fs::read_to_string(path)
        .ok()
        .and_then(|content| serde_json::from_str::<AppSettings>(&content).ok())
        .unwrap_or_default()
}

pub(crate) fn save_settings(
    path: &Path,
    settings: &AppSettings,
) -> Result<(), Box<dyn std::error::Error>> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let content = serde_json::to_string_pretty(settings)?;
    fs::write(path, content)?;
    Ok(())
}
