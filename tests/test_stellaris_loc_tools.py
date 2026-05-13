from __future__ import annotations

from pathlib import Path

from tools.stellaris_loc_common import count_leading_utf8_boms, parse_localisation_file
from tools.stellaris_loc_rebuild_skeleton import rebuild_skeletons
from tools.stellaris_loc_scan import find_english_localisation_files
from tools.stellaris_loc_validate import validate_pair_files, validate_roots


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    path.write_text(text, encoding=encoding)


def _make_pair(
    tmp_path: Path,
    english_body: str,
    russian_body: str,
    russian_bom: bool = True,
) -> tuple[Path, Path]:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"
    _write_text(english_file, english_body, bom=False)
    _write_text(russian_file, russian_body, bom=russian_bom)
    return english_file, russian_file


def _issue_messages(result) -> list[str]:
    return [issue.message for issue in result.issues]


def test_normal_entry_passes(tmp_path: Path) -> None:
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


def test_correct_russian_bom_and_clean_header_passes(tmp_path: Path) -> None:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"

    _write_text(english_file, 'l_english:\nkey:0 "Text"\n', bom=False)
    russian_file.write_bytes(b"\xef\xbb\xbfl_russian:\nkey:0 \"Text\"\n")

    result = validate_pair_files(english_file, russian_file)
    messages = _issue_messages(result)

    assert result.is_valid
    assert not any("Extra BOM marker before localisation header" in message for message in messages)


def test_double_russian_bom_before_header_is_error(tmp_path: Path) -> None:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"

    _write_text(english_file, 'l_english:\nkey:0 "Text"\n', bom=False)
    russian_file.write_bytes(b"\xef\xbb\xbf\xef\xbb\xbfl_russian:\nkey:0 \"Text\"\n")

    result = validate_pair_files(english_file, russian_file)
    messages = _issue_messages(result)

    assert not result.is_valid
    assert any("multiple leading UTF-8 BOM" in message or "Extra BOM marker before localisation header" in message for message in messages)


def test_hidden_ufeef_before_russian_header_after_utf8_sig_is_error(tmp_path: Path) -> None:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"

    _write_text(english_file, 'l_english:\nkey:0 "Text"\n', bom=False)
    russian_file.write_bytes(
        b"\xef\xbb\xbf\n" + "\ufeffl_russian:\nkey:0 \"Text\"\n".encode("utf-8")
    )

    text_after_sig = russian_file.read_text(encoding="utf-8-sig")
    first_nonempty = next((line for line in text_after_sig.splitlines() if line.strip()), "")
    assert first_nonempty == "\ufeffl_russian:"

    result = validate_pair_files(english_file, russian_file)
    messages = _issue_messages(result)

    assert not result.is_valid
    assert any("Extra BOM marker before localisation header" in message for message in messages)


def test_parse_localisation_file_reports_bom_diagnostics(tmp_path: Path) -> None:
    russian_file = tmp_path / "russian.yml"
    russian_file.write_bytes(b"\xef\xbb\xbf\xef\xbb\xbfl_russian:\nkey:0 \"Text\"\n")

    parsed = parse_localisation_file(russian_file, expected_header="l_russian:")

    assert parsed.leading_bom_count == 2
    assert parsed.text_starts_with_hidden_bom is True


def test_english_source_extra_bom_marker_is_source_warning(tmp_path: Path) -> None:
    english_file = tmp_path / "english.yml"
    russian_file = tmp_path / "russian.yml"

    english_file.write_bytes(b"\xef\xbb\xbf\xef\xbb\xbfl_english:\nkey:0 \"Text\"\n")
    _write_text(russian_file, 'l_russian:\nkey:0 "Tekst"\n', bom=True)

    result = validate_pair_files(english_file, russian_file)

    assert result.is_valid
    assert any(
        "Extra BOM marker before localisation header in English source" in item.message
        for item in result.source_warnings
    )


def test_scan_finds_only_english_localisation_yml(tmp_path: Path) -> None:
    with_header = tmp_path / "localisation" / "english" / "a_l_english.yml"
    without_header = tmp_path / "localisation" / "english" / "b_l_english.yml"
    wrong_extension = tmp_path / "localisation" / "english" / "c_l_english.txt"

    _write_text(with_header, 'l_english:\nkey:0 "Text"\n', bom=False)
    _write_text(without_header, 'key:0 "Text"\n', bom=False)
    _write_text(wrong_extension, 'l_english:\nkey:0 "Text"\n', bom=False)

    found = find_english_localisation_files(tmp_path)
    assert found == [with_header]


def test_scan_finds_header_with_hidden_bom_marker(tmp_path: Path) -> None:
    with_hidden_bom = tmp_path / "localisation" / "english" / "hidden_bom_l_english.yml"
    _write_text(with_hidden_bom, '\ufeffl_english:\nkey:0 "Text"\n', bom=False)

    found = find_english_localisation_files(tmp_path)
    assert found == [with_hidden_bom]


def test_rebuild_skeleton_creates_russian_file_with_bom(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModA"
    out_root = tmp_path / "output" / "ModA"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    _write_text(english_file, 'l_english:\n# comment\nkey:0 "Text"\n', bom=False)

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=out_root, dry_run=False)

    russian_file = out_root / "localisation" / "russian" / "mod_l_russian.yml"
    assert russian_file.exists()
    raw = russian_file.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert count_leading_utf8_boms(raw) == 1
    russian_text = russian_file.read_text(encoding="utf-8-sig")
    first_line = russian_text.splitlines()[0] if russian_text.splitlines() else ""
    assert first_line == "l_russian:"
    assert "\ufeffl_russian:" not in russian_text
    assert 'key:0 "Text"' in russian_text
    assert summary.files_created == 1


def test_rebuild_skeleton_handles_hidden_bom_header_and_validator_accepts(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModBom"
    out_root = tmp_path / "output" / "ModBom"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    _write_text(english_file, '\ufeffl_english:\nkey:0 "Text"\n', bom=False)

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=out_root, dry_run=False)

    russian_file = out_root / "localisation" / "russian" / "mod_l_russian.yml"
    assert russian_file.exists()
    assert summary.files_created == 1

    raw_ru = russian_file.read_bytes()
    assert raw_ru.startswith(b"\xef\xbb\xbf")
    assert count_leading_utf8_boms(raw_ru) == 1

    ru_text = russian_file.read_text(encoding="utf-8-sig")
    first_line = ru_text.splitlines()[0] if ru_text.splitlines() else ""
    assert first_line == "l_russian:"
    assert "l_english:" not in ru_text
    assert "\ufeffl_russian:" not in ru_text

    result = validate_pair_files(english_file, russian_file)
    assert result.is_valid


def test_rebuild_skeleton_dry_run_does_not_write(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModB"
    out_root = tmp_path / "output" / "ModB"
    english_file = fresh_root / "localisation" / "english" / "mod_l_english.yml"
    _write_text(english_file, 'l_english:\nkey:0 "Text"\n', bom=False)

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=out_root, dry_run=True)

    russian_file = out_root / "localisation" / "russian" / "mod_l_russian.yml"
    assert not russian_file.exists()
    assert summary.dry_run_actions == 1


def test_duplicate_keys_preserved_sequence_are_source_warnings_only(tmp_path: Path) -> None:
    english = (
        'l_english:\n'
        'Ancient_Antares:0 "Ancient Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    russian = (
        'l_russian:\n'
        'Ancient_Antares:0 "Drevnii Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    en, ru = _make_pair(tmp_path, english, russian)

    result = validate_pair_files(en, ru)
    assert result.is_valid
    assert result.errors == []
    assert result.source_warnings
    assert any("Duplicate key in English source" in item.message for item in result.source_warnings)


def test_duplicate_key_only_in_russian_is_error(tmp_path: Path) -> None:
    english = (
        'l_english:\n'
        'Ancient_Antares:0 "Ancient Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    russian = (
        'l_russian:\n'
        'Ancient_Antares:0 "Drevnii Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    en, ru = _make_pair(tmp_path, english, russian)

    result = validate_pair_files(en, ru)
    assert not result.is_valid
    assert result.errors
    assert any(
        "Duplicate key appears only in Russian output" in item.message
        or "Duplicate key count increased in Russian output" in item.message
        for item in result.errors
    )


def test_duplicate_in_english_but_russian_breaks_full_sequence_is_error(tmp_path: Path) -> None:
    english = (
        'l_english:\n'
        'Ancient_Antares:0 "Ancient Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'Antares_Prime:0 "P4T-257-a"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    russian = (
        'l_russian:\n'
        'Ancient_Antares:0 "Drevnii Antares"\n'
        'Antares_Prime:0 "Antares Prime"\n'
        'PXT_947:0 "PXT-947"\n'
    )
    en, ru = _make_pair(tmp_path, english, russian)

    result = validate_pair_files(en, ru)
    assert not result.is_valid
    assert result.errors
    assert any(
        "did not preserve full duplicate key sequence" in item.message
        or "Missing key occurrence" in item.message
        for item in result.errors
    )


def test_recursive_validation_not_blocked_by_source_duplicate_warnings(tmp_path: Path) -> None:
    fresh_root = tmp_path / "fresh_mods" / "ModDup"
    russian_root = tmp_path / "output" / "ModDup"

    english_file = fresh_root / "localisation" / "english" / "dup_l_english.yml"
    russian_file = russian_root / "localisation" / "russian" / "dup_l_russian.yml"

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

    results = validate_roots(fresh_root=fresh_root, russian_root=russian_root)
    assert len(results) == 1
    result = results[0]
    assert result.errors == []
    assert result.source_warnings
    assert result.is_valid
