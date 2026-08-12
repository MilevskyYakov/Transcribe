from pathlib import Path

from mnema.app.config import AppConfig, config_for_app_data_dir, load_config


def test_load_config_reads_default_yaml() -> None:
    config_path = Path("configs/default.yaml")

    config = load_config(config_path)

    assert isinstance(config, AppConfig)
    assert config.app.output_dir == "./output"
    assert config.runtime.device == "mps"
    assert config.asr.model_name == "large-v3"
    assert config.export.json is True
    assert config.watch_folder.stability_seconds == 10


def test_config_for_app_data_dir_keeps_runtime_data_under_app_support(tmp_path: Path) -> None:
    config = config_for_app_data_dir(AppConfig(), tmp_path / "Mnema")

    assert config.app.output_dir == str(tmp_path / "Mnema" / "output")
    assert config.app.temp_dir == str(tmp_path / "Mnema" / "tmp")
