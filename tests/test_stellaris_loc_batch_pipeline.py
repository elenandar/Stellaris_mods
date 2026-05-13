from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.stellaris_loc_apply_translations import apply_translations
from tools.stellaris_loc_batch_format import build_batch_items, write_batches
from tools.stellaris_loc_common import (
    build_stable_todo_id,
    load_json,
    load_jsonl,
    mask_protected_tokens,
    restore_masked_tokens,
)
from tools.stellaris_loc_extract_todo import build_todo_records
from tools.stellaris_loc_translation_cache import TranslationCache
from tools.stellaris_loc_validate import validate_pair_files


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _make_validation_pair(tmp_path: Path, english_value: str, russian_value: str) -> tuple[Path, Path]:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"
    _write_text(english_file, f'l_english:\nkey:0 "{english_value}"\n', bom=False)
    _write_text(russian_file, f'l_russian:\nkey:0 "{russian_value}"\n', bom=True)
    return english_file, russian_file


def test_mask_restore_dollar_token() -> None:
    source = "Hello $PLANET$"
    masked, token_map = mask_protected_tokens(source)
    assert "$PLANET$" not in masked
    assert restore_masked_tokens(masked, token_map) == source


def test_mask_restore_bracket_token() -> None:
    source = "Name [Root.GetName]"
    masked, token_map = mask_protected_tokens(source)
    assert "[Root.GetName]" not in masked
    assert restore_masked_tokens(masked, token_map) == source


def test_mask_restore_icon_token() -> None:
    source = "\u00a3energy\u00a3 income"
    masked, token_map = mask_protected_tokens(source)
    assert "\u00a3energy\u00a3" not in masked
    assert restore_masked_tokens(masked, token_map) == source


def test_mask_restore_formatting_token() -> None:
    source = "\u00a7YAlert\u00a7!"
    masked, token_map = mask_protected_tokens(source)
    assert "\u00a7Y" not in masked
    assert restore_masked_tokens(masked, token_map) == source


def test_mask_restore_escape_tokens() -> None:
    source = "Line1\\nLine2\\tPath\\\\File\\\"Quote\\\""
    masked, token_map = mask_protected_tokens(source)
    assert "\\n" not in masked
    assert "\\t" not in masked
    assert "\\\\" not in masked
    assert "\\\"" not in masked
    assert restore_masked_tokens(masked, token_map) == source


def test_identical_strings_deduplicated_in_todo_and_cache(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModSame"
    russian_root = tmp_path / "output" / "ModSame"

    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    russian_file = russian_root / "localisation" / "russian" / "mod_l_russian.yml"

    body = 'l_english:\nkey_a:0 "Same text"\nkey_b:0 "Same text"\n'
    _write_text(english_file, body, bom=False)
    _write_text(
        russian_file,
        body.replace("l_english:", "l_russian:"),
        bom=True,
    )

    cache = TranslationCache(tmp_path / "cache" / "translations.sqlite3")
    cache.init_db()

    records, summary = build_todo_records(fresh_root=fresh_root, russian_root=russian_root, cache=cache)
    assert summary.unique_units == 1
    assert len(records) == 1
    assert len(records[0]["occurrences"]) == 2

    cache.upsert_source(source_text="Same text", masked_source="Same text", status="pending")
    cache.upsert_source(source_text="Same text", masked_source="Same text", status="pending")
    assert cache.count_records() == 1


def test_technical_only_values_are_skipped_in_todo(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModTech"
    russian_root = tmp_path / "output" / "ModTech"

    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    russian_file = russian_root / "localisation" / "russian" / "mod_l_russian.yml"

    english = (
        'l_english:\n'
        'a_key:0 "$OTHER_KEY$"\n'
        'b_key:0 "+15%"\n'
        'c_key:0 "Translate this"\n'
    )
    russian = english.replace("l_english:", "l_russian:")
    _write_text(english_file, english, bom=False)
    _write_text(russian_file, russian, bom=True)

    records, summary = build_todo_records(fresh_root=fresh_root, russian_root=russian_root)
    assert summary.technical_only_skipped >= 2
    assert len(records) == 1
    assert records[0]["key"] == "c_key"


def test_extract_todo_masks_source_and_keeps_token_map(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModMask"
    russian_root = tmp_path / "output" / "ModMask"

    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    russian_file = russian_root / "localisation" / "russian" / "mod_l_russian.yml"

    english = 'l_english:\nname_key:0 "Hello $PLANET$"\n'
    russian = english.replace("l_english:", "l_russian:")
    _write_text(english_file, english, bom=False)
    _write_text(russian_file, russian, bom=True)

    records, _ = build_todo_records(fresh_root=fresh_root, russian_root=russian_root)
    assert len(records) == 1
    record = records[0]
    assert record["source"] == "Hello $PLANET$"
    assert "__PROT_0000__" in record["masked_source"]
    assert record["token_map"]["__PROT_0000__"] == "$PLANET$"


def test_batch_formatter_writes_expected_batches(tmp_path: Path) -> None:
    todo_rows = [
        {"id": "id_1", "key": "k1", "masked_source": "Text 1"},
        {"id": "id_2", "key": "k2", "masked_source": "Text 2"},
        {"id": "id_3", "key": "k3", "masked_source": "Text 3"},
    ]
    items = build_batch_items(todo_rows)
    out_dir = tmp_path / "batches"
    paths = write_batches(items=items, batch_size=2, out_dir=out_dir, dry_run=False)

    assert len(paths) == 2
    batch_one = load_json(paths[0])
    batch_two = load_json(paths[1])

    assert len(batch_one) == 2
    assert len(batch_two) == 1
    assert batch_one[0] == {"id": "id_1", "key": "k1", "text": "Text 1"}


def test_batch_formatter_skips_completed_cache_entries(tmp_path: Path) -> None:
    todo_rows = [
        {"id": "id_1", "key": "k1", "masked_source": "Text 1"},
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


def test_apply_preserves_keys_order_and_bom(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModApply"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    russian_file = russian_root / file_rel

    original = (
        'l_russian:\n'
        '# keep comment\n'
        'key_a:0 "Alpha"\n'
        'key_b:0 "Bravo" # trailing\n'
    )
    _write_text(russian_file, original, bom=True)

    masked_a, token_map_a = mask_protected_tokens("Alpha")
    masked_b, token_map_b = mask_protected_tokens("Bravo")
    id_a = build_stable_todo_id(masked_a)
    id_b = build_stable_todo_id(masked_b)

    todo_rows = [
        {
            "id": id_a,
            "file": str(file_rel),
            "key": "key_a",
            "line": 3,
            "source": "Alpha",
            "masked_source": masked_a,
            "token_map": token_map_a,
            "occurrences": [{"file": str(file_rel), "key": "key_a", "line": 3, "token_map": token_map_a}],
        },
        {
            "id": id_b,
            "file": str(file_rel),
            "key": "key_b",
            "line": 4,
            "source": "Bravo",
            "masked_source": masked_b,
            "token_map": token_map_b,
            "occurrences": [{"file": str(file_rel), "key": "key_b", "line": 4, "token_map": token_map_b}],
        },
    ]
    translations = [
        {"id": id_a, "translation": "Alfa"},
        {"id": id_b, "translation": "Brava"},
    ]

    todo_path = tmp_path / "todo.jsonl"
    translations_path = tmp_path / "translations.json"
    _write_jsonl(todo_path, todo_rows)
    _write_json(translations_path, translations)

    files_updated, values_updated, missing = apply_translations(
        todo_records=load_jsonl(todo_path),
        translations=load_json(translations_path),
        russian_root=russian_root,
    )

    assert files_updated == 1
    assert values_updated == 2
    assert missing == 0

    raw = russian_file.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")

    text = russian_file.read_text(encoding="utf-8-sig")
    assert "# keep comment" in text
    assert 'key_a:0 "Alfa"' in text
    assert 'key_b:0 "Brava" # trailing' in text
    assert text.index("key_a:0") < text.index("key_b:0")


def test_apply_rejects_unknown_translation_ids(tmp_path: Path) -> None:
    russian_root = tmp_path / "output" / "ModApplyUnknown"
    file_rel = Path("localisation/russian/mod_l_russian.yml")
    russian_file = russian_root / file_rel
    _write_text(russian_file, 'l_russian:\nkey_a:0 "Alpha"\n', bom=True)

    masked, token_map = mask_protected_tokens("Alpha")
    todo_id = build_stable_todo_id(masked)

    todo_rows = [
        {
            "id": todo_id,
            "file": str(file_rel),
            "key": "key_a",
            "line": 2,
            "source": "Alpha",
            "masked_source": masked,
            "token_map": token_map,
            "occurrences": [{"file": str(file_rel), "key": "key_a", "line": 2, "token_map": token_map}],
        }
    ]
    bad_translations = [{"id": "unknown_id", "translation": "Alfa"}]

    with pytest.raises(ValueError):
        apply_translations(
            todo_records=todo_rows,
            translations=bad_translations,
            russian_root=russian_root,
        )


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


def test_validator_flags_extra_escape_sequence(tmp_path: Path) -> None:
    en, ru = _make_validation_pair(tmp_path, "Line1\\nLine2", "Line1\\nLine2\\n")
    result = validate_pair_files(en, ru)
    messages = [issue.message for issue in result.issues]
    assert any("Extra escape sequence token" in message for message in messages)
