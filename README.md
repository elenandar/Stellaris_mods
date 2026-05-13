# Stellaris Localisation Safety Tools

This repository contains safe tooling for Stellaris `.yml` localisation workflows.

Important:
- Fresh English localisation files are the only source of truth.
- Old translations and translation memory are not used.
- The pipeline prepares and applies translations safely, but does not call any LLM API directly.

## Workspace layout

```text
StellarisTranslationWorkspace/
  fresh_mods/
  output/
  tools/
  tests/
  glossary_ru.md
  glossary_candidates.md
  translation_rules.md
  known_issues.md
```

## Mandatory reading before translation

Before any translation run, the agent must read:
- [glossary_ru.md](glossary_ru.md)
- [translation_rules.md](translation_rules.md)
- [known_issues.md](known_issues.md)

Quality policy:
- Every newly discovered validator error must become a regression test.
- Every validator change must include a test in `tests/`.
- Disputed terms go only to [glossary_candidates.md](glossary_candidates.md) until user approval.

## Tools

- `tools/stellaris_loc_common.py`: shared parser/token/path/BOM helpers
- `tools/stellaris_loc_scan.py`: scan fresh mod for English localisation files
- `tools/stellaris_loc_rebuild_skeleton.py`: create Russian skeleton files from English files
- `tools/stellaris_loc_extract_todo.py`: extract deduplicated translation TODO units as JSONL
- `tools/stellaris_loc_batch_format.py`: split TODO units into JSON batches for external translation
- `tools/stellaris_loc_translation_cache.py`: SQLite cache for deduplicated source strings
- `tools/stellaris_loc_apply_translations.py`: apply translated masked text back to Russian files
- `tools/stellaris_loc_validate.py`: validate EN/RU pairs and parser safety

## Quick accelerated workflow

```bash
python tools/stellaris_loc_scan.py --root fresh_mods/SomeMod
python tools/stellaris_loc_rebuild_skeleton.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
python tools/stellaris_loc_extract_todo.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod --out todo.jsonl
python tools/stellaris_loc_batch_format.py --todo todo.jsonl --batch-size 100 --out batches/
python tools/stellaris_loc_apply_translations.py --todo todo.jsonl --translations translations/batch_001_ru.json --russian-root output/SomeMod
python tools/stellaris_loc_validate.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
```

## Validator checks

`tools/stellaris_loc_validate.py` validates:
- required headers (`l_english:`, `l_russian:`)
- UTF-8 with BOM for Russian files
- key count, key order, key identity
- numeric marker consistency (`:0`, `:1`, ...)
- exact protected-token preservation (missing and extra are issues):
  - `$...$`
  - `[...]`
  - `U+00A3...U+00A3` resource icon tokens
  - `U+00A7X` formatting tags
  - escape tokens: `\\n`, `\\t`, `\\\\`, `\\"`
- no multiline values
- no unclosed quotes
- no unescaped internal quotes
- no Unicode quotes
- no TODO/TRUNCATED/FIXME/"ostalnoe analogichno" placeholders
- safe localisation entry format

## TODO extraction format

`tools/stellaris_loc_extract_todo.py` writes JSONL rows:

```json
{"id":"...","file":"...","key":"...","line":12,"source":"...","masked_source":"...","token_map":{},"occurrences":[...]}
```

- `id` is stable and based on masked source text.
- identical strings are deduplicated.
- `occurrences` keeps all file/key/line placements for safe apply.

## Batch format

`tools/stellaris_loc_batch_format.py` creates JSON batches:

```json
[
  {
    "id": "unique-id",
    "key": "localisation_key",
    "text": "masked English text"
  }
]
```

Optional cache usage:
- pass `--cache-db cache/translation_cache.sqlite3`
- completed cache entries are skipped by default
- use `--include-cached-complete` to include them

## Apply format

Input translations for `tools/stellaris_loc_apply_translations.py`:

```json
[
  {
    "id": "unique-id",
    "translation": "masked Russian translation"
  }
]
```

After apply, run validator.

## Tests

Run all tests:

```bash
pytest -q
```

## Git hygiene

Do not commit/generated data directories and cache DB files:
- `fresh_mods/`
- `output/`
- `batches/`
- `translations/`
- SQLite cache files (`*.sqlite`, `*.sqlite3`, `*.db`)
