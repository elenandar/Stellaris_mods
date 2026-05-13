# Stellaris Localisation Safety Tools

This workspace contains tooling to safely process Stellaris `.yml` localisation files.

These tools are designed to work with a fresh mod source tree and a separate output tree.
They do not perform artistic translation. The skeleton builder only mirrors structure.

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

## Mandatory reading before any translation

Before starting any translation task, the agent must read:
- [glossary_ru.md](glossary_ru.md)
- [translation_rules.md](translation_rules.md)
- [known_issues.md](known_issues.md)

Quality policy:
- Every newly discovered validator error must become a regression test.
- Every validator change must be accompanied by a test.
- Disputed new terms must be added only to [glossary_candidates.md](glossary_candidates.md), not directly to [glossary_ru.md](glossary_ru.md).

## Requirements

- Python 3.10+
- pytest (for tests)

## 1) Scan English localisation files

Find `.yml` files that contain `l_english:`:

```bash
python tools/stellaris_loc_scan.py --root fresh_mods/SomeMod
```

Print absolute paths:

```bash
python tools/stellaris_loc_scan.py --root fresh_mods/SomeMod --absolute
```

## 2) Validate English/Russian file pairs

Pair mode:

```bash
python tools/stellaris_loc_validate.py --english path/to/file_l_english.yml --russian path/to/file_l_russian.yml
```

Recursive mode:

```bash
python tools/stellaris_loc_validate.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
```

The validator checks:

- headers `l_english:` and `l_russian:`
- Russian file BOM (UTF-8 with BOM)
- key count, key set, key order
- numeric marker consistency (`:0`, `:1`, ...)
- preservation of protected tokens:
  - `$...$`
  - `[...]`
  - `U+00A3...U+00A3` resource icon spans
  - `U+00A7X` formatting tags
  - `\\n`, `\\t`, `\\\\`, `\\"`
- no multiline value starts
- no unclosed quotes
- no unescaped inner quotes
- no Unicode quote characters (guillemets and curly quotes)
- no placeholders: `TODO`, `TRUNCATED`, `FIXME`, `\\u043e\\u0441\\u0442\\u0430\\u043b\\u044c\\u043d\\u043e\\u0435 \\\u0430\\u043d\\u0430\\u043b\\u043e\\u0433\\u0438\\u0447\\u043d\\u043e`
- safe localisation entry format

## 3) Rebuild Russian skeleton files

Create Russian skeleton files from fresh English files (no text translation):

```bash
python tools/stellaris_loc_rebuild_skeleton.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod --dry-run
```

Apply writes:

```bash
python tools/stellaris_loc_rebuild_skeleton.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
```

Behavior:

- scans English `.yml` files with `l_english:`
- maps `english` path segment to `russian`
- renames `_l_english.yml` to `_l_russian.yml`
- changes header `l_english:` to `l_russian:`
- preserves comments, blank lines, and line order
- keeps quoted text unchanged (skeleton only)
- writes output in UTF-8 with BOM

## Run tests

```bash
pytest -q
```
