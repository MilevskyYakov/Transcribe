"""YAML-backed application configuration models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Dict, TypeAlias, TypeGuard, cast

import yaml

from transcribe_doc.app.exceptions import ConfigurationError


@dataclass(frozen=True)
class AppSection:
    temp_dir: str = "./tmp"
    output_dir: str = "./output"
    keep_temp: bool = True
    save_artifacts: bool = True


@dataclass(frozen=True)
class RuntimeSection:
    device: str = "mps"
    max_parallel_jobs: int = 1


@dataclass(frozen=True)
class MediaSection:
    sample_rate: int = 16000
    mono: bool = True
    normalize_audio: bool = True


@dataclass(frozen=True)
class AsrSection:
    backend: str = "whisper"
    model_name: str = "large-v3"
    language: str = "ru"
    allow_mixed_vocabulary: bool = True


@dataclass(frozen=True)
class AlignmentSection:
    enabled: bool = True
    word_timestamps: bool = True


@dataclass(frozen=True)
class DiarizationSection:
    enabled: bool = True
    num_speakers: str = "auto"
    allow_expected_speaker_mapping: bool = True


@dataclass(frozen=True)
class PostprocessSection:
    mode: str = "almost_verbatim"
    remove_fillers: bool = False
    aggressive_cleanup: bool = False
    merge_adjacent_same_speaker: bool = True


@dataclass(frozen=True)
class SummarySection:
    enabled: bool = True
    mode: str = "extractive_or_local_llm"


@dataclass(frozen=True)
class ExportSection:
    txt: bool = True
    md: bool = True
    docx: bool = True
    pdf: bool = True
    srt: bool = True
    json: bool = True


@dataclass(frozen=True)
class WatchFolderSection:
    enabled: bool = False
    stability_seconds: int = 10
    move_processed: bool = True
    move_failed: bool = True


@dataclass(frozen=True)
class AppConfig:
    app: AppSection = AppSection()
    runtime: RuntimeSection = RuntimeSection()
    media: MediaSection = MediaSection()
    asr: AsrSection = AsrSection()
    alignment: AlignmentSection = AlignmentSection()
    diarization: DiarizationSection = DiarizationSection()
    postprocess: PostprocessSection = PostprocessSection()
    summary: SummarySection = SummarySection()
    export: ExportSection = ExportSection()
    watch_folder: WatchFolderSection = WatchFolderSection()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the config into a JSON/YAML-friendly mapping."""
        return asdict(self)


def config_for_app_data_dir(config: AppConfig, app_data_dir: Path | str) -> AppConfig:
    """Return a config whose mutable runtime data lives below the app data directory."""
    root = Path(app_data_dir).expanduser()
    app_section = replace(
        config.app,
        output_dir=str(root / "output"),
        temp_dir=str(root / "tmp"),
    )
    return replace(config, app=app_section)


ConfigDataclass: TypeAlias = (
    AppSection
    | RuntimeSection
    | MediaSection
    | AsrSection
    | AlignmentSection
    | DiarizationSection
    | PostprocessSection
    | SummarySection
    | ExportSection
    | WatchFolderSection
    | AppConfig
)


def load_config(path: Path | str) -> AppConfig:
    """Load and validate a YAML configuration file."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw_data = yaml.safe_load(handle) or {}

    if not isinstance(raw_data, dict):
        raise ConfigurationError("Top-level config must be a mapping.")

    return cast(AppConfig, _merge_dataclass(AppConfig(), raw_data))


def _merge_dataclass(instance: ConfigDataclass, overrides: Dict[str, Any]) -> ConfigDataclass:
    merged: Dict[str, Any] = {}
    for field_info in fields(instance):
        current_value = getattr(instance, field_info.name)
        override_value = overrides.get(field_info.name, current_value)

        if _is_config_dataclass_instance(current_value):
            if override_value is current_value:
                merged[field_info.name] = current_value
            elif not isinstance(override_value, dict):
                raise ConfigurationError(f"Section '{field_info.name}' must be a mapping.")
            else:
                merged[field_info.name] = _merge_dataclass(current_value, override_value)
        else:
            merged[field_info.name] = override_value

    return cast(ConfigDataclass, type(instance)(**merged))


def _is_config_dataclass_instance(value: Any) -> TypeGuard[ConfigDataclass]:
    return is_dataclass(value) and not isinstance(value, type)
