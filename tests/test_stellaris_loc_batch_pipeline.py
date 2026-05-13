from __future__ import annotations

from pathlib import Path

import pytest

from tools.stellaris_loc_apply_translations import apply_translations
from tools.stellaris_loc_batch_format import build_batch_items
from tools.stellaris_loc_common import (
    build_stable_todo_id,
    count_leading_utf8_boms,
    mask_protected_tokens,
)
from tools.stellaris_loc_extract_todo import build_todo_records
from tools.stellaris_loc_translation_cache import TranslationCache
from tools.stellaris_loc_validate import validate_pair_files


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def _build_todo_record(
    file_rel: Path,
    source: str,
    key: str,
    line: int,
    entry_index: int | None,
    key_occurrence_index: int | None,
) -> dict:
    masked_source, token_map = mask_protected_tokens(source)
    todo_id = build_stable_todo_id(masked_source)

    occurrence = {
        "file": str(file_rel),
        "key": key,
        "line": line,
        "token_map": token_map,
    }
    if entry_index is not None:
        occurrence["entry_index"] = entry_index
    if key_occurrence_index is not None:
        occurrence["key_occurrence_index"] = key_occurrence_index

    record = {
        "id": todo_id,
        "file": str(file_rel),
        "key": key,
        "line": line,
        "source": source,
        "masked_source": masked_source,
        "token_map": token_map,
        "occurrences": [occurrence],
    }
    if entry_index is not None:
        record["entry_index"] = entry_index
    if key_occurrence_index is not None:
        record["key_occurrence_index"] = key_occurrence_index

    return record


def _duplicate_russian_file(russian_root: Path) -> tuple[Path, Path]:
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    file_path = russian_root / file_rel
    _write_text(
        file_path,
        (
            'l_russian:\n'
            'Antares_Prime:0 "Antares Prime"\n'
            'Antares_Prime:0 "P4T-257-a"\n'
        ),
        bom=True,
    )
    return file_rel, file_path


def test_duplicate_key_different_values_apply_correctly(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModDupApply"
    file_rel, file_path = _duplicate_russian_file(russian_root)

    todo_first = _build_todo_record(
        file_rel=file_rel,
        source="Antares Prime",
        key="Antares_Prime",
        line=2,
        entry_index=0,
        key_occurrence_index=0,
    )
    todo_second = _build_todo_record(
        file_rel=file_rel,
        source="P4T-257-a",
        key="Antares_Prime",
        line=3,
        entry_index=1,
        key_occurrence_index=1,
    )

    translations = [
        {"id": todo_first["id"], "translation": "Антарес Прайм"},
        {"id": todo_second["id"], "translation": "P4T-257-a"},
    ]

    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo_first, todo_second],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 2
    assert missing == 0
    assert errors == []

    raw = file_path.read_bytes()
    assert count_leading_utf8_boms(raw) == 1

    text = file_path.read_text(encoding="utf-8-sig")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    assert first_line == "l_russian:"
    assert "\ufeffl_russian:" not in text
    assert 'Antares_Prime:0 "Антарес Прайм"' in text
    assert 'Antares_Prime:0 "P4T-257-a"' in text


def test_duplicate_key_does_not_overwrite_both_occurrences(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModDupFirstOnly"
    file_rel, file_path = _duplicate_russian_file(russian_root)

    todo_first = _build_todo_record(
        file_rel=file_rel,
        source="Antares Prime",
        key="Antares_Prime",
        line=2,
        entry_index=0,
        key_occurrence_index=0,
    )

    translations = [{"id": todo_first["id"], "translation": "Антарес Прайм"}]
    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo_first],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 1
    assert missing == 0
    assert errors == []

    lines = file_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[1] == 'Antares_Prime:0 "Антарес Прайм"'
    assert lines[2] == 'Antares_Prime:0 "P4T-257-a"'


def test_duplicate_key_second_occurrence_can_be_targeted(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModDupSecondOnly"
    file_rel, file_path = _duplicate_russian_file(russian_root)

    todo_second = _build_todo_record(
        file_rel=file_rel,
        source="P4T-257-a",
        key="Antares_Prime",
        line=3,
        entry_index=1,
        key_occurrence_index=1,
    )

    translations = [{"id": todo_second["id"], "translation": "Код P4T-257-a"}]
    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo_second],
        translations=translations,
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 1
    assert missing == 0
    assert errors == []

    lines = file_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[1] == 'Antares_Prime:0 "Antares Prime"'
    assert lines[2] == 'Antares_Prime:0 "Код P4T-257-a"'


def test_extraction_includes_occurrence_identity_for_duplicates(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModExtract"
    russian_root = tmp_path / "output" / "ModExtract"

    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    russian_file = russian_root / "localisation" / "russian" / "mod_l_russian.yml"

    english = (
        'l_english:\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
    )
    russian = (
        'l_russian:\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
    )
    _write_text(english_file, english, bom=False)
    _write_text(russian_file, russian, bom=True)

    records, _ = build_todo_records(fresh_root=fresh_root, russian_root=russian_root)
    assert len(records) == 2

    by_source = {record["source"]: record for record in records}
    first = by_source["Antares Prime"]
    second = by_source["P4T-257-a"]

    assert first["entry_index"] == 0
    assert first["key_occurrence_index"] == 0
    assert first["occurrences"][0]["line"] == 2
    assert first["occurrences"][0]["entry_index"] == 0
    assert first["occurrences"][0]["key_occurrence_index"] == 0

    assert second["entry_index"] == 1
    assert second["key_occurrence_index"] == 1
    assert second["occurrences"][0]["line"] == 3
    assert second["occurrences"][0]["entry_index"] == 1
    assert second["occurrences"][0]["key_occurrence_index"] == 1


def test_apply_rejects_duplicate_key_replacement_without_occurrence_identity(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModLegacyTodo"
    file_rel, file_path = _duplicate_russian_file(russian_root)

    todo_legacy = _build_todo_record(
        file_rel=file_rel,
        source="Antares Prime",
        key="Antares_Prime",
        line=2,
        entry_index=None,
        key_occurrence_index=None,
    )

    # Simulate old TODO rows where occurrence identity was absent.
    todo_legacy.pop("entry_index", None)
    todo_legacy.pop("key_occurrence_index", None)
    todo_legacy["occurrences"][0].pop("entry_index", None)
    todo_legacy["occurrences"][0].pop("key_occurrence_index", None)

    translations = [{"id": todo_legacy["id"], "translation": "Антарес Прайм"}]

    before = file_path.read_bytes()
    files_updated, values_updated, missing, errors = apply_translations(
        todo_records=[todo_legacy],
        translations=translations,
        russian_root=russian_root,
    )
    after = file_path.read_bytes()

    assert files_updated == 0
    assert values_updated == 0
    assert missing == 0
    assert errors
    assert any("occurrence identity is missing" in message for message in errors)
    assert before == after


def test_batch_formatter_includes_file_source_and_occurrence_identity() -> None:
    todo_rows = [
        {
            "id": "id_1",
            "key": "loc_key",
            "file": "localisation/russian/mod_l_russian.yml",
            "source": "Hello $PLANET$",
            "masked_source": "Hello __PROT_0000__",
            "entry_index": 13,
            "key_occurrence_index": 1,
        }
    ]

    items = build_batch_items(todo_rows)

    assert len(items) == 1
    assert items[0]["id"] == "id_1"
    assert items[0]["key"] == "loc_key"
    assert items[0]["file"] == "localisation/russian/mod_l_russian.yml"
    assert items[0]["source"] == "Hello $PLANET$"
    assert items[0]["text"] == "Hello __PROT_0000__"
    assert items[0]["entry_index"] == 13
    assert items[0]["key_occurrence_index"] == 1


def test_batch_formatter_still_skips_completed_cache_entries(tmp_path: Path) -> None:
    todo_rows = [
        {
            "id": "id_1",
            "key": "k1",
            "file": "localisation/russian/mod_l_russian.yml",
            "source": "Text 1",
            "masked_source": "Text 1",
            "entry_index": 0,
            "key_occurrence_index": 0,
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


def test_validator_preserved_duplicate_sequence_is_source_warning_only(tmp_path: Path) -> None:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"

    _write_text(
        english_file,
        (
            'l_english:\n'
            'Antares_Prime:0 "Antares Prime"\n'
            'Antares_Prime:0 "P4T-257-a"\n'
        ),
        bom=False,
    )
    _write_text(
        russian_file,
        (
            'l_russian:\n'
            'Antares_Prime:0 "Антарес Прайм"\n'
            'Antares_Prime:0 "P4T-257-a"\n'
        ),
        bom=True,
    )

    result = validate_pair_files(english_file, russian_file)
    assert result.errors == []
    assert result.source_warnings
    assert result.is_valid


def _make_validation_pair(tmp_path: Path, english_value: str, russian_value: str) -> tuple[Path, Path]:
    english_file = tmp_path / "english_pair.yml"
    russian_file = tmp_path / "russian_pair.yml"
    _write_text(english_file, f'l_english:\nkey:0 "{english_value}"\n', bom=False)
    _write_text(russian_file, f'l_russian:\nkey:0 "{russian_value}"\n', bom=True)
    return english_file, russian_file


def test_validator_flags_extra_dollar_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text $NEW_TOKEN$")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.errors]
    assert any("Extra $...$ token" in message for message in messages)


def test_validator_flags_extra_bracket_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text [Root.GetName]")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.errors]
    assert any("Extra [...] token" in message for message in messages)


def test_validator_flags_extra_icon_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text \u00a3energy\u00a3")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.errors]
    assert any("Extra resource icon token" in message for message in messages)


def test_validator_flags_extra_formatting_token(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Text", "Text \u00a7Ywarn\u00a7!")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.errors]
    assert any("Extra formatting tag token" in message for message in messages)


def test_validator_flags_extra_escape_sequence(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Line1\\nLine2", "Line1\\nLine2\\n")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.errors]
    assert any("Extra escape sequence token" in message for message in messages)


def test_apply_rejects_unknown_translation_ids(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModUnknownID"
    file_rel, _ = _duplicate_russian_file(russian_root)

    todo = _build_todo_record(
        file_rel=file_rel,
        source="Antares Prime",
        key="Antares_Prime",
        line=2,
        entry_index=0,
        key_occurrence_index=0,
    )

    with pytest.raises(ValueError):
        apply_translations(
            todo_records=[todo],
            translations=[{"id": "unknown_id", "translation": "x"}],
            russian_root=russian_root,
        )
