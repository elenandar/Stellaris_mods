from __future__ import annotations

import json
from pathlib import Path

from tools.stellaris_loc_apply_translations import apply_translation_sources
from tools.stellaris_loc_common import load_json
from tools.stellaris_loc_llm_client import extract_json_array_from_response, translate_batch_with_llm
from tools.stellaris_loc_translate_batches import (
    translate_batches_in_directory,
    validate_translation_response,
)
from tools.stellaris_loc_translate_mod import translate_mod_workflow


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_llm_json_extraction_from_plain_json() -> None:
    payload = '[{"id":"a","translation":"Текст"}]'
    data = extract_json_array_from_response(payload)
    assert data == [{"id": "a", "translation": "Текст"}]


def test_llm_json_extraction_from_fenced_markdown() -> None:
    payload = '```json\n[{"id":"a","translation":"Текст"}]\n```'
    data = extract_json_array_from_response(payload)
    assert data == [{"id": "a", "translation": "Текст"}]


def test_invalid_json_triggers_retry() -> None:
    calls = {"count": 0}

    def fake_request(**kwargs):
        del kwargs
        calls["count"] += 1
        if calls["count"] == 1:
            return {"choices": [{"message": {"content": "not json"}}]}
        return {"choices": [{"message": {"content": '[{"id":"a","translation":"Текст"}]'}}]}

    result = translate_batch_with_llm(
        batch_items=[{"id": "a", "text": "Text"}],
        model="dummy-model",
        base_url="https://example.test/v1",
        api_key="dummy-key",
        system_prompt="sys",
        user_prompt="user",
        max_retries=2,
        request_func=fake_request,
    )

    assert calls["count"] == 2
    assert result == [{"id": "a", "translation": "Текст"}]


def test_placeholder_mismatch_is_detected() -> None:
    batch_items = [{"id": "a", "text": "Hello __PROT_0000__"}]
    translations = [{"id": "a", "translation": "Привет"}]
    errors = validate_translation_response("batch_001.json", batch_items, translations)
    assert any("placeholder mismatch" in error for error in errors)


def test_missing_id_is_detected() -> None:
    batch_items = [
        {"id": "a", "text": "One"},
        {"id": "b", "text": "Two"},
    ]
    translations = [{"id": "a", "translation": "Один"}]
    errors = validate_translation_response("batch_001.json", batch_items, translations)
    assert any("missing id 'b'" in error for error in errors)


def test_extra_id_is_detected() -> None:
    batch_items = [{"id": "a", "text": "One"}]
    translations = [
        {"id": "a", "translation": "Один"},
        {"id": "b", "translation": "Два"},
    ]
    errors = validate_translation_response("batch_001.json", batch_items, translations)
    assert any("extra id 'b'" in error for error in errors)


def test_translate_batches_writes_batch_001_ru_json(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    translations_dir = tmp_path / "translations"
    batch_file = batches_dir / "batch_001.json"
    _write_json(
        batch_file,
        [
            {
                "id": "a",
                "key": "hello_key",
                "file": "localisation/russian/mod_l_russian.yml",
                "source": "Hello world",
                "text": "Hello world",
                "entry_index": 0,
                "key_occurrence_index": 0,
            }
        ],
    )

    def fake_translator(*, batch_items, **kwargs):
        del kwargs
        return [{"id": batch_items[0]["id"], "translation": "Привет, мир"}]

    summary = translate_batches_in_directory(
        batches_dir=batches_dir,
        translations_dir=translations_dir,
        provider="openai-compatible",
        base_url="https://example.test/v1",
        api_key="dummy-key",
        model="dummy-model",
        glossary_version="v1",
        temperature=0.2,
        timeout=30,
        max_retries=2,
        translator=fake_translator,
    )

    out_file = translations_dir / "batch_001_ru.json"
    assert out_file.exists()
    assert summary.batches_translated == 1
    assert load_json(out_file) == [{"id": "a", "translation": "Привет, мир"}]


def test_existing_translated_file_is_skipped_unless_force(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    translations_dir = tmp_path / "translations"
    batch_file = batches_dir / "batch_001.json"
    out_file = translations_dir / "batch_001_ru.json"
    payload = [
        {
            "id": "a",
            "key": "hello_key",
            "file": "localisation/russian/mod_l_russian.yml",
            "source": "Hello world",
            "text": "Hello world",
            "entry_index": 0,
            "key_occurrence_index": 0,
        }
    ]
    _write_json(batch_file, payload)
    _write_json(out_file, [{"id": "a", "translation": "Привет, мир"}])

    calls = {"count": 0}

    def fake_translator(*, batch_items, **kwargs):
        del batch_items, kwargs
        calls["count"] += 1
        return [{"id": "a", "translation": "Привет, мир"}]

    summary = translate_batches_in_directory(
        batches_dir=batches_dir,
        translations_dir=translations_dir,
        provider="openai-compatible",
        base_url="https://example.test/v1",
        api_key="dummy-key",
        model="dummy-model",
        glossary_version="v1",
        temperature=0.2,
        timeout=30,
        max_retries=2,
        translator=fake_translator,
        force=False,
    )
    assert summary.batches_skipped == 1
    assert calls["count"] == 0

    summary_force = translate_batches_in_directory(
        batches_dir=batches_dir,
        translations_dir=translations_dir,
        provider="openai-compatible",
        base_url="https://example.test/v1",
        api_key="dummy-key",
        model="dummy-model",
        glossary_version="v1",
        temperature=0.2,
        timeout=30,
        max_retries=2,
        translator=fake_translator,
        force=True,
    )
    assert summary_force.batches_translated == 1
    assert calls["count"] == 1


def test_translate_mod_orchestration_works_with_fake_translator(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "mod_1"
    russian_root = tmp_path / "output" / "mod_1"
    work_dir = tmp_path / "work" / "mod_1"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"

    _write_text(
        english_file,
        'l_english:\nhello_key:0 "Hello world"\n',
        bom=False,
    )

    def fake_translator(*, batch_items, **kwargs):
        del kwargs
        return [{"id": item["id"], "translation": "Привет, мир"} for item in batch_items]

    report = translate_mod_workflow(
        fresh_root=fresh_root,
        russian_root=russian_root,
        work_dir=work_dir,
        cache_db=None,
        provider="openai-compatible",
        base_url="https://example.test/v1",
        api_key="dummy-key",
        model="dummy-model",
        batch_size=20,
        glossary_version="v1",
        temperature=0.2,
        timeout=30,
        max_retries=2,
        translator=fake_translator,
    )

    assert report["status"] == "ok"
    assert (work_dir / "report.json").exists()
    russian_text = (russian_root / "localisation" / "russian" / "mod_l_russian.yml").read_text(
        encoding="utf-8-sig"
    )
    assert 'hello_key:0 "Привет, мир"' in russian_text


def test_apply_translations_dir_applies_multiple_translation_files(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "mod"
    file_path = russian_root / "localisation" / "russian" / "mod_l_russian.yml"
    _write_text(
        file_path,
        (
            'l_russian:\n'
            'hello_key:0 "Hello"\n'
            'bye_key:0 "Bye"\n'
        ),
        bom=True,
    )

    todo_records = [
        {
            "id": "id_1",
            "file": "localisation/russian/mod_l_russian.yml",
            "key": "hello_key",
            "line": 2,
            "entry_index": 0,
            "key_occurrence_index": 0,
            "source": "Hello",
            "masked_source": "Hello",
            "token_map": {},
            "occurrences": [
                {
                    "file": "localisation/russian/mod_l_russian.yml",
                    "key": "hello_key",
                    "line": 2,
                    "entry_index": 0,
                    "key_occurrence_index": 0,
                    "token_map": {},
                }
            ],
        },
        {
            "id": "id_2",
            "file": "localisation/russian/mod_l_russian.yml",
            "key": "bye_key",
            "line": 3,
            "entry_index": 1,
            "key_occurrence_index": 0,
            "source": "Bye",
            "masked_source": "Bye",
            "token_map": {},
            "occurrences": [
                {
                    "file": "localisation/russian/mod_l_russian.yml",
                    "key": "bye_key",
                    "line": 3,
                    "entry_index": 1,
                    "key_occurrence_index": 0,
                    "token_map": {},
                }
            ],
        },
    ]

    translations_dir = tmp_path / "translations"
    _write_json(translations_dir / "batch_001_ru.json", [{"id": "id_1", "translation": "Привет"}])
    _write_json(translations_dir / "batch_002_ru.json", [{"id": "id_2", "translation": "Пока"}])

    files_updated, values_updated, missing, errors = apply_translation_sources(
        todo_records=todo_records,
        translations_path=None,
        translations_dir=translations_dir,
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 2
    assert missing == 0
    assert errors == []

    text = file_path.read_text(encoding="utf-8-sig")
    assert 'hello_key:0 "Привет"' in text
    assert 'bye_key:0 "Пока"' in text
