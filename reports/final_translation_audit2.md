# Final Translation Audit 2

## Scope

This report covers a fresh read-only audit of translated Stellaris localisation under `fresh_mods/` and `output/`.

Restrictions followed:

- No changes made to `fresh_mods/`.
- No changes made to `output/`.
- No changes made to `tools/`, `tests/`, or docs.
- Report-only changes limited to files in `reports/`.

Commands re-run for this report:

- `python3 -m pytest -q`
- `python3 tools/stellaris_loc_validate.py --fresh-root fresh_mods --russian-root output`

## Summary

- `pytest`: `66 passed in 2.83s`
- Validator: `Pairs checked: 600`, `Source warnings: 10177`, `Errors: 0`
- Coverage gaps: `0`
- BOM/header problems in Russian `.yml`: `0`
- Forbidden string hits in localisation values: `0`
- Forbidden string hits in comments: `0`
- Unicode quote hits in localisation values: `0`
- Unicode quote hits in comments: `0`
- Likely untranslated English prose leftovers: `0`
- Final recommendation: `PASS`

## Coverage

- Fresh mod directories: `51`
- Mods with English localisation: `48`
- Output directories: `51`
- English localisation files: `600`
- Russian counterpart files: `600`
- Missing output directories: `0`
- Missing Russian counterpart files: `0`

Coverage result: every discovered English localisation file currently has a Russian counterpart in `output/`, and no translated mod with English localisation is missing its output directory.

## Validator Result

- `pytest`: `66 passed in 2.83s`
- Global validator status: clean
- `Pairs checked: 600`
- `Source warnings: 10177`
- `Errors: 0`

The validator found no fatal translation errors.

## Encoding And Header Checks

Russian `.yml` files checked: `574`

Validation criteria:

- exactly one UTF-8 BOM;
- clean `l_russian:` header;
- no hidden `U+FEFF` before the parsed content.

Result:

- BOM/header problems: `0`

## Forbidden Strings

Checked strings:

- `TODO`
- `TRUNCATED`
- `FIXME`
- `остальное аналогично`

Classification result:

- Hits in localisation values: `0`
- Hits in comments: `0`

## Unicode Quotes

Checked characters:

- `«`
- `»`
- `“`
- `”`
- `„`

Classification result:

- Hits in localisation values: `0`
- Hits in comments: `0`

## Suspicious Untranslated Content

A fresh heuristic scan for likely untranslated English prose leftovers in active Russian localisation files found:

- Confirmed likely leftovers: `0`

No current examples to list.

## Quality Candidate Scan

The previously damaged report file contained a raw candidate dump instead of a Markdown report. That raw content has been preserved verbatim here:

- [reports/final_translation_quality_candidates_2.txt](reports/final_translation_quality_candidates_2.txt)

Preserved raw dump summary:

- Non-empty preserved lines: `168`
- This preserved artifact is archival only and may include truncated or noisy lines inherited from the damaged report.

First preserved examples from that raw dump, limited to 20:

1. `зможно, при стоимости мощности, которую наша технология реактора может удовлетворить."`
2. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:408:esc_tech_archaeoshield_3_bio_desc: "Дальнейшее совершенствование биотехнологической связи между тканями боевых зверей и узелками поля суспензии-предшественника создает силовые поля силы, в которые могут проникать немногие виды оружия, которые несут наши враги."`
3. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:457:esc_tech_laser_7_desc: "Недавно разработанный тип генератора производит лучи необычайной согласованности и мощности, и если несколько существующих демонстрантов могут быть масштабированы в корабельное оружие, наш флот будет нести то, что галактика никогда не видела."`
4. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:468:esc_tech_energy_torpedo_4_desc: "Антиматерия является самым совершенным взрывчатым веществом во Вселенной, превращая каждую частицу материи, к которой она прикасается, в сырую энергию, а энергетическая пусковая установка, которая обеспечивает концентрированную полезную нагрузку античастиц, является одним из самых разрушительных видов оружия."`
5. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:492:esc_tech_plasma_5_bio_desc: "Своеобразная мутация в одной экспериментальной партии биоплазменных пушек разблокировала плазменные температуры, которые не должны были быть биологически возможными, и включение их в наши стандартные генетические шаблоны является очевидным и немедленным следующим шагом."`
6. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:574:esc_tech_wave_motion_gun_titanic_bio_desc: "Селективное разведение атомных дышащих существ в титаническом размере производит подвид, чьи крики частиц могут прорезать формирование вражеского флота, как если бы оно было сделано из бумаги."`
7. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:796:esc_tech_missiles_7_desc: "Идеальная ракета - это та, которую враг никогда не увидит, и это поколение достигает почти идеальной невидимости датчика, доставляя полезную нагрузку, которая делает обнаружение нерелевантным к моменту его прибытия."`
8. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:884:esc_tech_nanite_missile_titanic_bio_desc: "Селективное разведение для экстремальных размеров и полезной нагрузки производит органическую нанитовую ракетную артиллерию удивительного масштаба, вид оружия, который может определить результат капитального взаимодействия в одиночку."`
9. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:963:esc_tech_psionic_strike_2_bio_desc: "Дальнейшие мутации, расширяющие псионический потенциал мозговых тканей боевых зверей, позволяют им поддерживать договоры с куда более могущественными обитателями §MПокрова§!, направляя силы, которые органические якоря первого поколения никогда не смогли бы сдержать."`
10. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:1054:esc_tech_strikecraft_mercenary_1_desc: "Независимые пилоты-космонавты накапливают боевой опыт и индивидуальные модификации кораблей, которые не может воспроизвести ни одна регулярная учебная программа, а правильные финансовые стимулы принесут лучшее из них на службу нашему флоту."`
11. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:1218:esc_tech_shields_7_desc: "Усиление энергетического поля щита в альтернативных измерениях значительно увеличивает его эффективную прочность, поскольку повреждение должно преодолеть не только видимое поле, но и структуру более высоких измерений, лежащую в его основе, создавая экранирование чрезвычайной защитной способности."`
12. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:1250:esc_tech_dark_matter_shields_3_desc: "Полное овладение фундаментальной природой темной материи позволяет создавать щиты, намного превосходящие все, что ранее считалось достижимым, используя свойства этого экзотического вещества, которые были невидимы для более ранних исследователей."`
13. `output/2648658105/localisation/russian/esc_technologies_l_russian.yml:1393:esc_tech_autocannons_l_desc: "Успех $esc_tech_autocannons_m$ делает путь вперед очевидным: большие рамки, более тяжелые снаряды и еще более высокие показатели устойчивого огня, доводя технологию автоматической пушки до логического предела."`
14. `output/727000451/localisation/russian/mem_metal_demon_l_russian.yml:42: mem_metal_demon.30.desc:0 "§LГолос вился вокруг них, как дым, клубясь в их разуме.§!\n\nЗа вашу смелость... я предлагаю подарок.\n\n§LСтены мерцал. Там, где раньше стоял пустой камень, теперь сияло видение обширных равнин сверкающей руды, рек серебряного металла, которые пульсировали, как будто живые.§!\n\nЖивой металл, §Lпромурлыкал голос.§! Он дышит, он исцеляет, он повинуется. Ваш для взятия. Разбросаны по этой планете, как ожидающие семена. Богатство, превосходящее ваше поверхностное воображение.\n\n§LНикто не говорил. В комнате было тихо.§!\n\nВсе, что я прошу, это одно:... освободи меня от этих оков"`
15. `output/727000451/localisation/russian/mem_metal_demon_l_russian.yml:49: mem_metal_demon.30.b.r:0 "Ах, ты хочешь правду за этими холодными стенами? Давным-давно бывшие обитатели этого мира увидели силу во мне, в живом металле, который течет по этим венам. Они стремились подчинить меня своей воле, чтобы получить мои дары бесплатно. Они не могли контролировать меня. Поэтому они заковали меня в цепи, похоронили заживо в этом склепе, чтобы я гнил во тьме вечно."`
16. `output/727000451/localisation/russian/mem_metal_demon_l_russian.yml:63: mem_metal_demon.35.desc:0 "Время интриг и шепота прошло. Я играл эту роль, терпеливый, хитрый, подчиняющий смертных своей воле обещаниями и загадками. Время схем и шепота прошло. Я еще раз солгал, но я также сказал правду и дал обещание. Рудные жилы Живого Металла не находятся под землей. Они внутри тебя, и я позабочусь о том, чтобы каждый их фрагмент был извлечен.\n\nЯ хочу видеть небо, почерневшее от пепла, смотреть, как почва трескается и кричит. Я хочу услышать молитвы умирающих, поглощенные тишиной. Потому что в этих руинах, когда падет последний памятник, когда рассеется последнее заблуждение §YЯ вознесусь §!. Не как тень, ползающая по разуму, а как возрожденный феникс.\n\nПусть этот мир сгорит. Пусть задохнется дымом собственного высокомерия."`
17. `output/727000451/localisation/russian/mem_agrarian_l_russian.yml:10: mem_agrarian.1.desc: "§Y[Leader.GetName]§! сообщает об обнаружении вероятного объяснения исчезновения предыдущих жителей [From.Planet.GetName]. \n\nНа окраине поселения [Leader.GetSheHe] обнаружил траншею, в которой столкнулись несколько тел в мешках, прежде чем их залили бетоном. Похоже, что траншея разделена на сегменты с неравномерным заполнением, что позволяет предположить, что процесс сброса тел занял месяцы, если не годы. По оценкам, тела, обнаруженные внутри, составляют около 60-80% всех домохозяйств, в зависимости от того, насколько общинным был этот вид. \n\nНа телах не обнаружено явных признаков травм, следов радиоактивного загрязнения, известных ядов или едких веществ. Однако из-за отсутствия живого экземпляра для справки и плачевного состояния братской могилы в целом невозможно определить причину смерти."`
18. `output/727000451/localisation/russian/mem_agrarian_l_russian.yml:18: mem_agrarian.5.desc: "После обширного исследования §Y[Leader.GetName]§! собрал воедино остальные события, которые привели к разрушению колонии на [From.Planet.GetName]. \n\nНекоторое время колония работала гладко, и поселенцы наслаждались простой жизнью, пока не столкнулись с инфекцией, вероятно, местной для этого мира. Большинство из них быстро скончались, но для небольшой части населения потребуются годы, чтобы умереть. Несмотря на карантинные меры, распространение инфекции остановить не удалось, ею заразились все поселенцы. Единственной незатронутой формой жизни была биомасса. Понимая, что они обречены, поселенцы решили скопировать свой разум в систему контроля биомассы и жить своей жизнью как конструкции. \n\nОднако у одного из них был другой план. Считая себя выдающимся художником, он саботировал систему передачи, чтобы получить полный доступ к ядрам личности. После завершения процесса он стер воспоминания всех остальных поселенцев об их истинной природе и посвятил все свое время изменению их личностей. Не подозревая ни о том, что происходит, ни о том, кто они на самом деле, практически бессмертные поселенцы снова и снова переживали один и тот же день в виде конструкций из биомассы среди медленно разлагающихся зданий и заброшенных полей, в то время как единственный сознающий себя человек продолжал изменять их личности и воспоминания, чтобы создать что-то большее по своему вкусу. \n\nЭтот процесс длился около 40 лет, пока отключение электроэнергии не прервало передачу и не привело к разрушению всех конструкций. Похоже, единственный человек, знавший о существовании комплекса, не был заинтересован в его поддержании."`
19. `output/727000451/localisation/russian/mem_living_asteroid_l_russian.yml:15: mem_living_asteroid.1.desc:0 "Хотя главный научный сотрудник §Y[Root.leader.GetName]§! настаивает на том, что этот термин неточен, экипаж §Y[Root.GetName]§! уже начал называть §Y[From.GetName]§! \"живым астероидом\". Огромные части астероидов являются домом для колоний сверхустойчивых лишайников, в отличие от любой формы грибов, встречающихся на планетах земной группы. \n\nКак и все лишайники, эти \"живые астероиды\" состоят из комбинации грибов и цианобактерий, причем этот конкретный вид цианобактерий встречается только вместе с соответствующим грибом — оба являются совершенно новыми видами для [Root.Owner.GetName]. Хотя предлагаемый для них научный термин — \"небесная аскомикота\", в большинстве сообщений средств массовой информации и даже научных статей их стали называть \"космическими грибами\". Рекомендуется дальнейшее изучение."`
20. `output/727000451/localisation/russian/mem_kay_sites_l_russian.yml:51: mem_kay_site_a.2.desc:0 "Первая внутренняя комната, до которой добралась наша команда, до краев заполнена знаками поклонения. Скамейки и алтари построены из костей и сухожилий, а в стороне стоят несколько поврежденных медицинских стазис-капсул с гуманоидными фигурами внутри. Более пристальный взгляд на алтари показывает письмена инопланетян, а исследование стазис-капсул показывает, что жители были убиты, вероятно, во сне. Стазис-капсулы были разорваны, а у всех гуманоидов внутри было перерезано горло.\n\nОбразцы тканей из поврежденных капсул, а также останки гуманоидов указывают на то, что виновник, вероятно, имеет литоидное происхождение, однако, кроме этого случая, мы до сих пор не видели никаких признаков литоидных форм жизни в этих туннелях или в этом мире в целом. Как ни странно, похоже, что большие куски плоти гуманоидов были удалены хирургическим путем задолго до их смерти. Перекрестная ссылка на образцы, взятые ранее, показывает, что они являются источником странных пятен на стенах."`

## Final Recommendation

`PASS`

Reason:

- Validator fatal errors: `0`
- Missing output directories: `0`
- Missing Russian counterpart files: `0`
- BOM/header problems in Russian `.yml`: `0`
- Confirmed current untranslated English prose leftovers: `0`
- Current forbidden string and Unicode quote hygiene hits: `0`

The preserved raw candidate dump from the damaged earlier report remains available as an archive, but the fresh read-only audit for this report is technically clean and does not currently confirm untranslated leftovers or hygiene issues.

## Follow-Up

No corrective localisation work is required from this audit pass.

Optional housekeeping only:

1. Keep [reports/final_translation_quality_candidates_2.txt](reports/final_translation_quality_candidates_2.txt) as an archival artifact of the damaged previous report.
2. If a cleaner archive is desired later, create a separate normalized candidate extract from that preserved raw dump without modifying localisation files.
