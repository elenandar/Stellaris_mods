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

## Batch translation notes

- Keys must never be translated or changed.
- Values inside quotes may localize proper names to Cyrillic when appropriate.
- Catalogue names like `P4T-257-a` should remain unchanged.

## Placeholder safety for LLM responses

Warning:
- The model must preserve masked placeholders exactly, e.g. `__PROT_0000__`.
- Do not remove, duplicate, rename, or invent placeholders.
- The translated output must target the `text` field only.

If placeholder validation fails during apply:
- that translation unit is rejected;
- Russian files are not modified for that unit;
- CLI exits with non-zero status;
- cache row is marked with `status=error` and an error message (if cache is enabled).

## Batch item format

`tools/stellaris_loc_batch_format.py` creates JSON batches:

```json
[
  {
    "id": "unique-id",
    "key": "localisation_key",
    "file": "localisation/russian/mod_l_russian.yml",
    "source": "Hello $PLANET$",
    "text": "Hello __PROT_0000__"
  }
]
```

- `text` is the primary field to translate.
- `source` is context only.
- `file` and `key` help traceability.

## Correct and incorrect model responses

Correct response example:

```json
[
  {
    "id": "unique-id",
    "translation": "Привет, __PROT_0000__"
  }
]
```

Incorrect response example (placeholder removed):

```json
[
  {
    "id": "unique-id",
    "translation": "Привет, планета"
  }
]
```

Incorrect response example (unknown placeholder added):

```json
[
  {
    "id": "unique-id",
    "translation": "Привет, __PROT_9999__"
  }
]
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

Validator findings are separated into:
- `errors`
- `source_warnings`

Exit code policy:
- exit code `1` if there is at least one `error`
- exit code `0` if there are only `source_warnings`
- exit code `0` if there are no findings

Duplicate key policy:
- duplicate keys in English source are `source_warnings` if Russian preserves the same full ordered key sequence
- duplicate keys that appear only in Russian are `errors`
- duplicate keys in Russian that do not preserve English full ordered key sequence are `errors`

## Optional cache usage

- pass `--cache-db cache/translation_cache.sqlite3`
- completed cache entries are skipped by default in batch formatting
- use `--include-cached-complete` to include them again

## Tests

Run all tests:

```bash
python3 -m pytest -q
```

## Git hygiene

Do not commit generated/runtime data:
- `fresh_mods/`
- `output/`
- `batches/`
- `translations/`
- `reports/`
- `validation_reports/`
- `todo.jsonl`
- cache DB files (`translation_cache.*`, `*.sqlite`, `*.sqlite3`, `*.db`)
