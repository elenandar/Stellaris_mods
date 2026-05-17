# Final Translation Audit 4

Date: 2026-05-17

## Scope

This audit was limited to active Russian localisation files only:

- `output/*/localisation/russian/**/*.yml`
- `output/*/localization/russian/**/*.yml`

Excluded from audit scope:

- `localisation_old/`
- `localization_old/`
- all non-Russian language directories, including `korean`, `german`, `simp_chinese`, `traditional_chinese`, and any other non-`russian` directories
- archive and non-Russian files were not counted as coverage, BOM/header, forbidden-string, Unicode-quote, suspicious-candidate, or quality-grep failures

## Results

- `pytest`: `66 passed in 2.92s`
- validator: `Pairs checked: 600`, `Source warnings: 10177`, `Errors: 0`
- scoped coverage: `English source files checked: 575`, `Missing Russian counterparts: 0`
- active Russian BOM/header: `577` files checked, `0` problems
- forbidden value hits: `0`
- forbidden comment hits: `0`
- Unicode quote value hits: `0`
- Unicode quote comment hits: `0`
- suspicious untranslated candidates: `37`
- quality grep hit count: `0`

## Suspicious Candidate Classification

Confirmed English prose leftovers: `0`

Intentional stylized/debug/proper-name/template candidates: `37`

- `16` internal modifier/template labels in `output/1121692237/localisation/russian/giga_eawaf_l_russian.yml`
  Examples: `giga eawaf strife field ship modifier`, `giga eawaf disenchanter 1 speed modifier`, `giga eawaf sirens megaphone 2 DESC`
- `5` stylized proper names and unit labels in `output/1121692237/localisation/russian/giga_l_russian.yml`
  Examples: `Galaktischerkatzenkreuzzug`, `Katzenweltraumpanzers`, `Leerekatzenbombers`, `Katzenkreuzer`
- `5` intentional machine/debug-style strings in `output/1121692237/localisation/russian/giga_l_russian.yml`
  Examples: `RISK ASSESSMENT`, `BEGIN TERMINATION`, `ERROR`, `LOGIC - SUBLIMATE UNSUSTAINALBE, UTILIZE SUBSTITUTE`
- `8` random-name format templates in `output/1121692237/localisation/russian/random_names/giga_birch_natives_names_l_russian.yml`
  Examples: `format.giga_birch_democratic`, `format.giga_birch_imperial_spiritualist`
- `1` icon/resource shorthand entry in `output/865040033/localisation/russian/gpm_deposits_l_russian.yml`
- `1` stylized extermination bark in `output/865040033/localisation/russian/gpm_events_ego_l_russian.yml`
- `1` intentional encrypted payload in `output/865040033/localisation/russian/gpm_relics_l_russian.yml`

Unsure candidates: `0`

## Recommendation

Final recommendation: `PASS WITH WARNINGS`

Reasoning:

- no validator errors remain
- no active Russian coverage gaps remain
- no active Russian BOM/header problems remain
- no forbidden value hits remain
- no Unicode quote value hits remain
- no quality grep hits remain
- remaining suspicious candidates are limited to intentional stylized/template/debug/proper-name strings rather than confirmed English prose leftovers