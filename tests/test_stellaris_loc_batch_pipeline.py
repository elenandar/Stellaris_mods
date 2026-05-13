from __future__ import annotations

from pathlib import Path

import pytest

from tools.stellaris_loc_apply_translations import apply_translations
from tools.stellaris_loc_batch_format import build_batch_items
from tools.stellaris_loc_common import build_stable_todo_id, mask_protected_tokens
from tools.stellaris_loc_translation_cache import TranslationCache
from tools.stellaris_loc_validate import validate_pair_files


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def _create_russian_file(russian_root: Path, file_rel: Path, value: str = "Alpha") -> Path:
    file_path = russian_root / file_rel
    _write_text(file_path, f'l_russian:\nkey_a:0 "{value}"\n', bom=True)
    return file_path


def _build_todo_record(file_rel: Path, source: str, key: str = "key_a", token_map: dict[str, str] | None = None) -> dict:
    masked_source, auto_token_map = mask_protected_tokens(source)
    token_map = auto_token_map if token_map is None else token_map
    todo_id = build_stable_todo_id(masked_source)

    return {
        "id": todo_id,
        "file": str(file_rel),
        "key": key,
        "line": 2,
        "source": source,
        "masked_source": masked_source,
        "token_map": token_map,
        "occurrences": [
            {
                "file": str(file_rel),
                "key": key,
                "line": 2,
                "token_map": token_map,
            }
        ],
    }


def _make_validation_pair(tmp_path: Path, english_value: str, russian_value: str) -> tuple[Path, Path]:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"
    _write_text(english_file, f'l_english:\nkey:0 "{english_value}"\n', bom=False)
    _write_text(russian_file, f'l_russian:\nkey:0 "{russian_value}"\n', bom=True)
    return english_file, russian_file


def test_apply_rejects_missing_required_placeholder(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModMissing"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    russian_file = _create_russian_file(russian_root, file_rel, value="Hello $PLANET$")

    todo = _build_todo_record(file_rel=file_rel, source="Hello $PLANET$")
    translations = [{"id": todo["id"], "translation": "Privet planeta"}]

    original = russian_file.read_text(encoding="utf-8-sig")
    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert "missing" in errors[0]
    assert russian_file.read_text(encoding="utf-8-sig") == original


def test_apply_rejects_placeholder_count_mismatch(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModCount"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    _create_russian_file(russian_root, file_rel, value="Hello $PLANET$")

    todo = _build_todo_record(file_rel=file_rel, source="Hello $PLANET$")
    translations = [{"id": todo["id"], "translation": "__PROT_0000__ __PROT_0000__"}]

    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert "count mismatch" in errors[0]


def test_apply_rejects_unknown_placeholder(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModUnknown"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    _create_russian_file(russian_root, file_rel, value="Hello $PLANET$")

    todo = _build_todo_record(file_rel=file_rel, source="Hello $PLANET$")
    translations = [{"id": todo["id"], "translation": "__PROT_0000__ __PROT_9999__"}]

    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert "unknown placeholder" in errors[0]


def test_apply_rejects_unresolved_placeholder_after_restore(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModUnresolved"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    _create_russian_file(russian_root, file_rel, value="Hello token")

    # Intentionally corrupted token_map for regression-hardening test.
    token_map = {"__PROT_0000__": "__PROT_9999__"}
    todo = _build_todo_record(file_rel=file_rel, source="__PROT_0000__", token_map=token_map)
    translations = [{"id": todo["id"], "translation": "__PROT_0000__"}]

    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert "unresolved placeholders remain after restore" in errors[0]


def test_failed_placeholder_validation_does_not_modify_file(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModSafe"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    russian_file = _create_russian_file(russian_root, file_rel, value="Hello $PLANET$")

    todo = _build_todo_record(file_rel=file_rel, source="Hello $PLANET$")
    translations = [{"id": todo["id"], "translation": "Broken"}]

    before_bytes = russian_file.read_bytes()
    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo],
        translations=translations,
        russian_root=russian_root,
    )
    after_bytes = russian_file.read_bytes()

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert before_bytes == after_bytes


def test_apply_preserves_keys_order_and_bom(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModOrder"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    russian_file = russian_root / file_rel

    original = (
        'l_russian:\n'
        '# keep comment\n'
        'key_a:0 "Alpha"\n'
        'key_b:0 "Bravo" # trailing\n'
    )
    _write_text(russian_file, original, bom=True)

    todo_a = _build_todo_record(file_rel=file_rel, source="Alpha", key="key_a")
    todo_b = _build_todo_record(file_rel=file_rel, source="Bravo", key="key_b")

    translations = [
        {"id": todo_a["id"], "translation": "Alfa"},
        {"id": todo_b["id"], "translation": "Brava"},
    ]

    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo_a, todo_b],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 2
    assert missing == 0
    assert errors == []

    raw = russian_file.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    text = russian_file.read_text(encoding="utf-8-sig")
    assert "# keep comment" in text
    assert 'key_a:0 "Alfa"' in text
    assert 'key_b:0 "Brava" # trailing' in text
    assert text.index("key_a:0") < text.index("key_b:0")


def test_apply_rejects_unknown_translation_ids(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModUnknownID"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    _create_russian_file(russian_root, file_rel, value="Alpha")

    todo = _build_todo_record(file_rel=file_rel, source="Alpha")
    bad_translations = [{"id": "unknown_id", "translation": "Alfa"}]

    with pytest.raises(ValueError):
        apply_translations(
            todo_records=[todo],
            translations=bad_translations,
            russian_root=russian_root,
        )


def test_batch_formatter_includes_file_and_source() -> None:
    todo_rows = [
        {
            "id": "id_1",
            "key": "loc_key",
            "file": "localisation/russian/mod_l_russian.yml",
            "source": "Hello $PLANET$",
            "masked_source": "Hello __PROT_0000__",
        }
    ]

    items = build_batch_items(todo_rows)

    assert len(items) == 1
    assert items[0]["id"] == "id_1"
    assert items[0]["key"] == "loc_key"
    assert items[0]["file"] == "localisation/russian/mod_l_russian.yml"
    assert items[0]["source"] == "Hello $PLANET$"
    assert items[0]["text"] == "Hello __PROT_0000__"


def test_batch_formatter_still_skips_completed_cache_entries(tmp_path: Path) -> None:
    todo_rows = [
        {
            "id": "id_1",
            "key": "k1",
            "file": "localisation/russian/mod_l_russian.yml",
            "source": "Text 1",
            "masked_source": "Text 1",
        }
    ]

    cache = TranslationCache(tmp_path / "cache" / "translations.sqlite3")
    cache.init_db()
    cache.save_translation(
        source_text="Text 1",
        masked_source="Text 1",
        translated_masked_text="Tekst 1",
        restored_translation="Tekst 1",
        model_name="test-model",
        glossary_version="v1",
        status="translated",
        error_message=None,
    )

    items = build_batch_items(todo_rows, cache=cache, skip_cached_complete=True)
    assert items == []


def test_validator_flags_extra_dollar_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text $NEW_TOKEN$")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.issues]
    assert any("Extra $...$ token" in message for message in messages)


def test_validator_flags_extra_bracket_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text [Root.GetName]")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.issues]
    assert any("Extra [...] token" in message for message in messages)


def test_validator_flags_extra_icon_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text \u00a3energy\u00a3")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.issues]
    assert any("Extra resource icon token" in message for message in messages)


def test_validator_flags_extra_formatting_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text \u00a7Ywarn\u00a7!")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.issues]
    assert any("Extra formatting tag token" in message for message in messages)
