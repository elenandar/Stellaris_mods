## Copilot Agent Prompt

Переведи данный Stellaris mod на русский язык в Copilot Agent режиме.

Мод:
`fresh_mods/<MOD_ID>`

Выход:
`output/<MOD_ID>`

Рабочая папка:
`work/<MOD_ID>`

## Режим работы

- Не используй `tools/stellaris_loc_translate_batches.py`.
- Не используй `tools/stellaris_loc_translate_mod.py`.
- Не используй `tools/stellaris_loc_translate_collection.py`.
- Не используй LLM API.
- Не требуй `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.
- Перевод выполняй сам как GitHub Copilot Agent.
- Основной способ доступа к файлам и batch JSON: terminal commands (`pwd`, `ls`, `cat`, `sed`, `python3 -m json.tool`, `python3 tools/...`).
- Не полагайся на workspace search/codebase search как на основной способ чтения файлов.
- Не исправляй и не переписывай исходники в `fresh_mods`.

Используй tools только для:
- scan
- rebuild skeleton
- validate
- extract_todo
- batch_format
- apply_translations

Перед переводом прочитай:
- `glossary_ru.md`
- `translation_rules.md`
- `known_issues.md`

## Style quality rules

- Перевод должен быть естественным русским текстом, а не механическим дословным переносом.
- Сохраняй смысл, функцию и тон оригинала.
- Для дипломатических реплик, угроз, оскорблений и lore используй возвышенный, мрачный, имперский или фанатично-религиозный тон, если он есть в исходнике.
- Не используй современный сленг, мемы и чрезмерно канцелярский стиль.
- Избегай буквальных калек, которые звучат неестественно на русском.

Рекомендации для Zeriphen/небесной тематики:
- heavenly hosts -> небесные воинства / небесные сонмы
- Highest Chorus -> Высший Хор
- Gates -> Врата
- cleansing / purification -> очищение
- purify -> очистить
- Enigmatic Purifiers -> Загадочные очистители
- Gates of Elikiol -> Врата Эликиола
- Empyrean -> Эмпирей
- Zeriphen -> Зерифен / Зерифены

## Safety rules (обязательные)

- Переводи только `text` в batch JSON.
- Всегда сохраняй `id` без изменений.
- Всегда сохраняй placeholders, включая `__PROT_0000__`, точно как в источнике.
- Никогда не меняй localisation keys.
- Не переводи catalogue names: `P4T-257-a`, `PXT-947`, `P57J-657-b`, `XJ-9`, `3V-0L`.
- Proper names можно кириллизировать, если это не ломает узнаваемость и соответствует glossary/rules.
- Не используй Unicode quotes.
- Не создавай multiline strings.
- Не добавляй markdown в translation JSON.
- Не вставляй `TODO`, `TRUNCATED`, `FIXME`, `остальное аналогично`.
- Стиль не важнее parser safety: нельзя ради красоты менять placeholders, keys или структуру `.yml`.
- Source-side malformed quotes из English нужно переводить через batch/apply workflow; apply шаг обязан экранировать ASCII quotes в финальном `.yml`.

## Порядок работы

1. Запусти scan.
2. Пересобери Russian skeleton files.
3. Проверь validator после rebuild.
	- Если есть только source warnings (включая `Unescaped internal quote inside localization value.`) и `Errors: 0`, продолжай перевод.
	- Если `Errors > 0`, остановись.
4. Извлеки TODO в `work/<MOD_ID>/todo.jsonl`.
5. Сформируй batch files в `work/<MOD_ID>/batches/`.
6. Переведи batch files сам и сохрани translation JSON files в `work/<MOD_ID>/translations/`.
7. Примени переводы через `tools/stellaris_loc_apply_translations.py --translations-dir`.
8. Запусти финальный validator.

После apply выполни дополнительную проверку BOM/header:

```bash
python3 - <<'PY'
from pathlib import Path

BOM = b"\xef\xbb\xbf"
mod_id = "<MOD_ID>"

def leading_bom_count(raw: bytes) -> int:
	count = 0
	while raw.startswith(BOM, count * len(BOM)):
		count += 1
	return count

for yml in sorted(Path(f"output/{mod_id}").rglob("*.yml")):
	raw = yml.read_bytes()
	text = yml.read_text(encoding="utf-8-sig")
	first = text.splitlines()[0] if text.splitlines() else ""
	print(yml)
	print("  leading_bom_count:", leading_bom_count(raw))
	print("  first_line_repr:", repr(first))
	if leading_bom_count(raw) != 1 or first.startswith("\ufeff"):
		raise SystemExit(f"BOM/header problem in {yml}")
PY
```

Ожидаемо для каждого Russian `.yml`:
- `starts_with_bom: True`
- `leading_bom_count: 1`
- `first_line_repr: 'l_russian:'`

## Критерий завершения

- Финальный validator должен показать `Errors: 0`.
- `Source warnings` допустимы только если они относятся к проблемам английского source.