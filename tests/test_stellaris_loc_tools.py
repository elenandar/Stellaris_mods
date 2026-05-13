from __future__ import annotations

from pathlib import Path

from tools.stellaris_loc_rebuild_skeleton import rebuild_skeletons
from tools.stellaris_loc_scan import find_english_localisation_files
from tools.stellaris_loc_validate import validate_pair_files


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    path.write_text(text, encoding=encoding)


def _make_pair(tmp_path: Path, english_body: str, russian_body: str, russian_bom: bool = True) -> tuple[Path, Path]:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"
    _write_text(english_file, english_body, bom=False)
    _write_text(russian_file, russian_body, bom=russian_bom)
    return english_file, russian_file


def _issue_messages(result) -> list[str]:
    return [issue.message for issue in result.issues]


def test_normal_entry_passes(tmp_path: Path) -> None:
    # key:0 "Text"
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:0 "Tekst"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_indented_entry_passes(tmp_path: Path) -> None:
    english = 'l_english:\n    key:0 "Text"\n'
    russian = 'l_russian:\n    key:0 "Tekst"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_dollar_token_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Hello $PLANET$"\n'
    russian = 'l_russian:\nkey:0 "Privet $PLANET$"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_scripted_localisation_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "[Root.GetName] arrived"\n'
    russian = 'l_russian:\nkey:0 "[Root.GetName] arrived"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_resource_icon_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "\u00a3energy\u00a3"\n'
    russian = 'l_russian:\nkey:0 "\u00a3energy\u00a3"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_formatting_tags_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "\u00a7YWarning\u00a7!"\n'
    russian = 'l_russian:\nkey:0 "\u00a7YWarning\u00a7!"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_newline_escape_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Line1\\nLine2"\n'
    russian = 'l_russian:\nkey:0 "Stroka1\\nStroka2"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_escaped_quote_preserved(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "He said \\\"Hi\\\""\n'
    russian = 'l_russian:\nkey:0 "On skazal \\\"Privet\\\""\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    assert result.is_valid


def test_unescaped_internal_quote_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:0 "Bad "quote" text"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("Unescaped internal quote" in message for message in messages)


def test_unicode_quotes_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:0 "\u00abText\u00bb"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("Unicode quote" in message for message in messages)


def test_multiline_value_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:0 "Line1\nLine2"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("multiline value" in message.lower() for message in messages)


def test_key_mismatch_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey_one:0 "Text"\n'
    russian = 'l_russian:\nkey_two:0 "Text"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("Missing key" in message for message in messages)


def test_order_mismatch_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey_a:0 "A"\nkey_b:0 "B"\n'
    russian = 'l_russian:\nkey_b:0 "B"\nkey_a:0 "A"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("Key order mismatch" in message for message in messages)


def test_marker_mismatch_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:1 "Text"\n'
    en, ru = _make_pair(tmp_path, english, russian)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("Numeric marker mismatch" in message for message in messages)


def test_missing_bom_detected(tmp_path: Path) -> None:
    english = 'l_english:\nkey:0 "Text"\n'
    russian = 'l_russian:\nkey:0 "Text"\n'
    en, ru = _make_pair(tmp_path, english, russian, russian_bom=False)
    result = validate_pair_files(en, ru)
    messages = _issue_messages(result)
    assert any("UTF-8 with BOM" in message for message in messages)


def test_scan_finds_only_english_localisation_yml(tmp_path: Path) -> None:
    with_header = tmp_path / "localisation" / "english" / "a_l_english.yml"
    without_header = tmp_path / "localisation" / "english" / "b_l_english.yml"
    wrong_extension = tmp_path / "localisation" / "english" / "c_l_english.txt"

    _write_text(with_header, "l_english:\nkey:0 \"Text\"\n", bom=False)
    _write_text(without_header, "key:0 \"Text\"\n", bom=False)
    _write_text(wrong_extension, "l_english:\nkey:0 \"Text\"\n", bom=False)

    found = find_english_localisation_files(tmp_path)
    assert found == [with_header]


def test_rebuild_skeleton_creates_russian_file_with_bom(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModA"
    out_root = tmp_path / "output" / "ModA"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    _write_text(english_file, 'l_english:\n# comment\nkey:0 "Text"\n', bom=False)

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=out_root, dry_run=False)

    russian_file = out_root / "localisation" / "russian" / "mod_l_russian.yml"
    assert russian_file.exists()
    assert russian_file.read_bytes().startswith(b"\xef\xbb\xbf")
    russian_text = russian_file.read_text(encoding="utf-8-sig")
    assert "l_russian:" in russian_text
    assert 'key:0 "Text"' in russian_text
    assert summary.files_created == 1


def test_rebuild_skeleton_dry_run_does_not_write(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModB"
    out_root = tmp_path / "output" / "ModB"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    _write_text(english_file, 'l_english:\nkey:0 "Text"\n', bom=False)

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=out_root, dry_run=True)

    russian_file = out_root / "localisation" / "russian" / "mod_l_russian.yml"
    assert not russian_file.exists()
    assert summary.dry_run_actions == 1
