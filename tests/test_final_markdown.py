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
        '[{"segment_id":"s1","start_seconds":0,"end_seconds":1,"text_raw":"Привет","text_clean":"Привет","speaker_label":"Яков"}]',
        encoding='utf-8',
    )
    job = {
        'job_id': 'job-1',
        'source_paths': [],
        'metadata': {'display_title': 'Первое название'},
    }
    autosave_dir = tmp_path / 'saved'

    status = save_final_markdown(job, output_root, autosave_dir)
    sync_saved_markdown_metadata(job, status)

    first_path = autosave_dir / 'Первое название.md'
    assert first_path.exists()
    assert status.message == 'Сохранено: Первое название.md'
    assert '**Яков**' in first_path.read_text(encoding='utf-8')

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
