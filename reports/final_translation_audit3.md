# Final Translation Audit 3

Date: 2026-05-17

## Scope

This is a third independent read-only control audit of the translated Stellaris localisation files in the current workspace.

Restrictions followed:

- No changes made to `fresh_mods/`.
- No changes made to `output/`.
- No changes made to `tools/`.
- No changes made to `tests/`.
- No changes made to README, docs, glossary, rules, or known issues.
- No localisation content was retranslated or fixed.
- Files created or updated by this audit were limited to `reports/final_translation_audit3.md` and `reports/final_translation_audit3_candidates.txt`.

## Git Status

- `git status --short` was executed from the workspace.
- `git rev-parse --show-toplevel` resolved the active repository root to `/Users/maxcheba`.
- In that parent-repository context, the global status output includes `?? ./`, which means this workspace is largely seen as an untracked subtree rather than a normal tracked project root.
- A path-scoped follow-up status for `fresh_mods`, `output`, `tools`, `tests`, and `reports` listed `tests/` and `tools/` as untracked entries in the parent repo.
- `fresh_mods/`: not separately enumerated by the parent-repo status model; this audit did not write there.
- `output/`: not separately enumerated by the parent-repo status model; this audit did not write there.
- `tools/`: shown as untracked by the parent-repo status.
- `tests/`: shown as untracked by the parent-repo status.
- Report files created or updated by this audit: `reports/final_translation_audit3.md`, `reports/final_translation_audit3_candidates.txt`.

## Summary

- `pytest`: `66 passed in 2.79s`
- Validator: `Pairs checked: 600`, `Source warnings: 10177`, `Errors: 0`, exit code `0`
- Coverage check: exit code `1`
- Missing output directories: `0`
- Missing Russian counterpart files: `33`
- BOM/header problems: `1`
- Forbidden string hits in localisation values: `3`
- Unicode quote hits in localisation values: `0`
- Potential multiline/unclosed quote problems: `0`
- Suspicious untranslated English prose candidates: `63`
- Quality candidate grep hits: `10`
- Final recommendation: `FAIL`

## Coverage

- Fresh mod directories: `51`
- Mods with English localisation: `50`
- Mods without English localisation: `1`
- Output directories: `51`
- English localisation files: `638`
- Russian counterpart files: `605`
- Missing output directories: `0`
- Missing Russian counterpart files: `33`
- Coverage check exit code: `1`

Coverage examples from the scripted check:

- `output/727000451/localisation_old/mem_dpe_fe_events_l_traditional_chinese.yml`
- `output/727000451/localisation_old/mem_dpe_fe_events_l_chinese.yml`
- `output/865040033/localisation/korean/gpm_notification_messages_l_korean.yml`
- `output/865040033/localisation/simp_chinese/gpm_operations_l_simp_chinese.yml`
- `output/865040033/localisation/german/gpm_l_german.yml`

Interpretation:

- This check is stricter than the earlier Russian-only coverage audit and counts any file that still exposes an `l_english:` header, including archive and non-Russian localisation trees.
- Under that strict rule, the translation set is not coverage-complete.

## Validator Result

- Exit code: `0`
- `Pairs checked: 600`
- `Source warnings: 10177`
- `Errors: 0`

The global validator is technically clean on the checked English/Russian pairs, but it does not override the stricter failures found by the independent coverage, BOM/header, and forbidden-string checks below.

## Encoding And Header Checks

- Files checked by the script: `603`
- BOM/header problems: `1`
- Script exit code: `1`

Problem example:

- `output/727000451/localisation_old/mem_wargames_l_traditional_chinese.yml`: first non-empty header is `#Wargames`, expected `l_russian:`

Interpretation:

- This is a strict all-`output/*.yml` audit result, not a Russian-path-only audit.
- Under the requested rule set, even this archive/legacy localisation file is enough to fail the technical cleanliness check.

## Forbidden Strings

Checked phrases:

- `TODO`
- `TRUNCATED`
- `FIXME`
- `остальное аналогично`
- `и так далее`
- `продолжение такое же`

Results:

- Forbidden value hits: `3`
- Forbidden comment hits: `0`
- Forbidden other hits: `0`
- Script exit code: `1`

Value-hit examples:

- `output/1121692237/localisation/russian/giga_l_russian.yml` line `5575` phrase `и так далее`
- `output/1121692237/localisation/russian/giga_l_russian.yml` line `7773` phrase `и так далее`
- `output/1121692237/localisation/russian/giga_modifiers_l_russian.yml` line `42` phrase `и так далее`

Under the requested audit rules, forbidden phrase hits inside localisation values are a technical failure.

## Unicode Quotes

Results:

- Unicode quote value hits: `0`
- Unicode quote comment hits: `0`
- Unicode quote other hits: `0`
- Script exit code: `0`

No Unicode quote problems were found by the independent check.

## Multiline And Quote Safety

Results:

- Potential multiline/unclosed quote problems: `0`
- Script exit code: `0`

No multiline or unclosed-quote candidates were found by the requested line-level scan.

## Suspicious Untranslated Content

Results:

- Suspicious untranslated candidates: `63`
- Script exit code: `0`
- Confirmed true English prose leftovers: `yes`

Not every candidate is a true positive. Some are UI labels, debug-like strings, random-name templates, or intended technical identifiers. However, the scan also found clearly untranslated English prose in active Russian localisation files, so this section cannot be dismissed as noise.

Representative examples:

- `output/1121692237/localisation/russian/giga_l_russian.yml` line `8261` key `giga_corrona.008.desc`
- `output/1121692237/localisation/russian/giga_l_russian.yml` line `11150` key `giga_blokkat.3324.desc`
- `output/1121692237/localisation/russian/giga_l_russian.yml` line `11155` key `giga_blokkat.3323.desc`
- `output/727000451/localisation/russian/mem_defying_gravity_l_russian.yml` line `12` key `mem_defying_gravity.100.desc`
- `output/727000451/localisation/russian/mem_hive_encounter_l_russian.yml` line `70` key `mem_hive_encounter.12.desc`
- `output/727000451/localisation/russian/mem_llayids_l_russian.yml` line `42` key `mem_llayids.6.desc.machine`
- `output/727000451/localisation/russian/mem_orila_primitives_l_russian.yml` line `159` key `mem_orila_primitives_skies_site.4.desc`
- `output/727000451/localisation/russian/mem_pioneer_l_russian.yml` line `21` key `mem_pioneer.3.desc`
- `output/727000451/localisation/russian/mem_rebel_yell_l_russian.yml` line `86` key `mem_rebel_yell.10.desc`
- `output/727000451/localisation/russian/mem_rogue_drone_l_russian.yml` line `35` key `mem_rogue_drone.7.desc`
- `output/2648658105/localisation/russian/esc_technologies_l_russian.yml` line `266` key `ESC_TECH_UNLOCK_TITAN_AURA_NANITES`
- `output/865040033/localisation/russian/gpm_events_survey_l_russian.yml` line `730` key `gpm_survey_precursors.130.name`

## Quality Candidate Scan

- Full raw quality grep output saved to [reports/final_translation_audit3_candidates.txt](reports/final_translation_audit3_candidates.txt)
- Quality candidate count: `10`
- These are warning-only signals and were not used as an automatic fail condition.

Examples:

- `output/2648658105/localisation/russian/esc_technologies_l_russian.yml` line `408`: `силовые поля силы`
- `output/2648658105/localisation/russian/esc_technologies_l_russian.yml` line `574`: `сделано из бумаги`
- `output/2648658105/localisation/russian/esc_technologies_l_russian.yml` line `796`: `нерелевантным`
- `output/2648658105/localisation/russian/esc_technologies_l_russian.yml` line `884`: `капитального взаимодействия`
- `output/727000451/localisation/russian/mem_shapes_under_ice_l_russian.yml` line `21`: `видовые экраны`
- `output/727000451/localisation/russian/mem_primitives_l_russian.yml` line `10`: `период времени`
- `output/727000451/localisation/russian/mem_descended_l_russian.yml` line `139`: `для нашим усилиям`
- `output/727000451/localisation/russian/mem_plants_vs_zombies_l_russian.yml` line `19`: `период времени`
- `output/865040033/localisation/russian/gpm_events_colony_l_russian.yml` line `243`: `поп-музыкант`
- `output/865040033/localisation/russian/gpm_events_colony_l_russian.yml` line `436`: `поп-музыкантов`

## Final Recommendation

`FAIL`

Reason:

- `pytest` passed, but the audit still fails multiple hard gates from the requested rule set.
- Coverage check failed with `33` missing Russian counterpart files.
- BOM/header check failed with `1` problem.
- Forbidden-string check failed with `3` hits inside localisation values.
- There are also `63` suspicious untranslated candidates, including confirmed true English prose leftovers.

Even though the global validator reports `Errors: 0`, the current translation set is not technically clean under this stricter independent audit definition.

## Follow-Up

This audit did not apply fixes. The main corrective buckets, if a later cleanup pass is requested, are:

1. Resolve the `33` strict-coverage gaps, especially multilingual and archive files currently counted by the scripted coverage rule.
2. Clear the strict BOM/header failure in `output/727000451/localisation_old/mem_wargames_l_traditional_chinese.yml` or explicitly exclude archive paths in a future audit definition.
3. Remove forbidden value phrases currently matching `и так далее` in `1121692237` Russian localisation values.
4. Triage and translate the confirmed English prose leftovers listed above.
5. Review the `10` quality candidates preserved in `reports/final_translation_audit3_candidates.txt`.