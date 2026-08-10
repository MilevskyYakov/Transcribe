from pathlib import Path

from transcribe_doc.storage.final_markdown import (
    inspect_saved_final_markdown,
    safe_filename_stem,
    save_final_markdown,
    sync_saved_markdown_metadata,
    title_derived_markdown_filename,
)


def test_safe_markdown_filename_preserves_title_words() -> None:
    assert safe_filename_stem('Созвон: клиент / CRM?') == 'Созвон клиент CRM'
    assert title_derived_markdown_filename({'metadata': {'display_title': 'Встреча.md'}}) == 'Встреча.md'


def test_save_final_markdown_writes_renames_and_detects_missing(tmp_path: Path) -> None:
    output_root = tmp_path / 'output'
    job_dir = output_root / 'job-1'
    job_dir.mkdir(parents=True)
    (job_dir / 'segments.json').write_text(
        '[{"segment_id":"s1","start_seconds":0,"end_seconds":1,"text_raw":"Привет",'
        '"text_clean":"Привет","speaker_label":"SPEAKER_00",'
        '"mapping":{"machine_label":"SPEAKER_00","display_label":"Яков","confidence":1.0}}]',
        encoding='utf-8',
    )
    job = {
        'job_id': 'job-1',
        'source_paths': [],
        'metadata': {'display_title': 'Первое название'},
    }
    autosave_dir = tmp_path / 'saved'
    autosave_dir.mkdir()

    status = save_final_markdown(job, output_root, autosave_dir)
    sync_saved_markdown_metadata(job, status)

    first_path = autosave_dir / 'Первое название.md'
    assert first_path.exists()
    assert status.message == 'Сохранено: Первое название.md'
    first_content = first_path.read_text(encoding='utf-8')
    assert first_content.startswith('# Первое название\n\n## Транскрипция')
    assert '[00:00:00–00:00:01] Яков: Привет' in first_content
    assert 'SPEAKER_00' not in first_content

    job['metadata']['display_title'] = 'Новое название'
    status = save_final_markdown(job, output_root, autosave_dir)
    sync_saved_markdown_metadata(job, status)

    renamed_path = autosave_dir / 'Новое название.md'
    assert not first_path.exists()
    assert renamed_path.exists()
    assert job['metadata']['saved_markdown_path'] == str(renamed_path)

    renamed_path.unlink()
    missing = inspect_saved_final_markdown(job)
    assert missing.missing is True
    assert missing.message == 'Файл транскрипции не найден'


def test_save_final_markdown_rejects_unsafe_destination(tmp_path: Path) -> None:
    output_root = tmp_path / 'output'
    job_dir = output_root / 'job-1'
    job_dir.mkdir(parents=True)
    (job_dir / 'segments.json').write_text(
        '[{"segment_id":"1","start_seconds":0,"end_seconds":1,"text_raw":"ok","text_clean":"ok"}]',
        encoding='utf-8',
    )
    job = {'job_id': 'job-1', 'metadata': {'display_title': 'Result'}}

    try:
        save_final_markdown(job, output_root, 'relative/path')
    except ValueError as error:
        assert str(error) == 'Папка сохранения должна иметь абсолютный путь'
    else:
        raise AssertionError('relative destination must be rejected')
