"""Uzbek (Cyrillic) texts of the interface. Keys are the English texts; placeholders in braces are kept."""

UZ = {
    # ------------------------------------------------------------------ main window, menus, console
    "Max–min water delivery through quantised gates": "Квантланган дарвозалар орқали макс–мин сув тақсимоти",
    "Language:": "Тил:",
    "File": "Файл",
    "Open project folder": "Лойиҳа папкасини очиш",
    "Open results folder": "Натижалар папкасини очиш",
    "Exit": "Чиқиш",
    "View": "Кўриниш",
    "Refresh the current tab": "Жорий бўлимни янгилаш",
    "Help": "Ёрдам",
    "Design of the experiment": "Тажриба режаси",
    "Hypotheses of the experiment (in Uzbek)": "Тажриба гипотезалари (ўзбекча)",
    "Repository on GitHub": "GitHub даги репозиторий",
    "Archived version (Zenodo)": "Архивланган версия (Zenodo)",
    "About": "Дастур ҳақида",
    "Version": "Версия",
    "Graphical interface": "График интерфейс",
    "Code: MIT licence; data and results: CC BY 4.0.": "Код: MIT лицензияси; маълумотлар ва натижалар: CC BY 4.0.",
    "Console": "Консол",
    "Ready": "Тайёр",
    "Stop": "Тўхтатиш",
    "Clear": "Тозалаш",
    "Save log": "Журнални сақлаш",
    "Text": "Матн",
    "Project folder": "Лойиҳа папкаси",
    "queued": "навбатда",
    "Stop the running script?": "Ишлаётган скрипт тўхтатилсинми?",
    "Stopped by the user.": "Фойдаланувчи томонидан тўхтатилди.",
    "A script is still running. Stop it and exit?": "Скрипт ҳали ишламоқда. Уни тўхтатиб, дастурдан чиқилсинми?",
    "The language can be changed when no script is running.": "Тилни скрипт ишламаётган пайтда ўзгартириш мумкин.",
    "The tab could not be shown": "Бўлимни кўрсатиб бўлмади",
    "Error": "Хато",
    "finished": "тугади",
    "finished with errors": "хатолар билан тугади",
    "stopped": "тўхтатилди",
    "s": "с",
    "min": "дақ.",
    "h": "соат",
    "Filter:": "Фильтр:",
    "rows": "қатор",
    "Not found:": "Топилмади:",
    "Row": "Қатор",
    "Close": "Ёпиш",
    "m³": "м³",

    # ------------------------------------------------------------------ tabs
    "Overview": "Умумий кўриниш",
    "Data": "Маълумотлар",
    "Gate and rules": "Дарвоза ва қоидалар",
    "Simulation": "Моделлаштириш",
    "Results": "Натижалар",
    "Analysis": "Таҳлил",
    "Figures": "Расмлар",
    "Article": "Мақола",

    # ------------------------------------------------------------------ simulation cases and rules
    "Ideal execution (reference)": "Идеал бажариш (эталон)",
    "Quantised actuator, baseline": "Квантланган ижро механизми, асосий ҳолат",
    "Quantised actuator, other thresholds": "Квантланган ижро механизми, бошқа θ чегаралари",
    "Full device chain": "Қурилмаларнинг тўлиқ занжири",
    "Deadband 0.25% (k = 3)": "Ўлик зона 0,25 % (k = 3)",
    "Deadband 1% (k = 10)": "Ўлик зона 1 % (k = 10)",
    "Gate coefficient -20%": "Дарвоза коэффициенти −20 %",
    "Gate coefficient +20%": "Дарвоза коэффициенти +20 %",
    "Leaking regulators": "Оқадиган регуляторлар",
    "Outlet rating errors": "Сув олгичлар сарф тавсифининг хатолари",
    "Baseline (deadband 0.5%, k = 5)": "Асосий ҳолат (ўлик зона 0,5 %, k = 5)",
    "Direct execution": "Тўғридан-тўғри бажариш",
    "Pulse rule, θ = 0": "Импульс қоидаси, θ = 0",
    "Pulse rule, θ = 0.25": "Импульс қоидаси, θ = 0,25",
    "Pulse rule, θ = 0.5": "Импульс қоидаси, θ = 0,5",
    "Pulse rule, θ = 0.75": "Импульс қоидаси, θ = 0,75",
    "Equal split with pulse fallback": "Тенг бўлиш (зарурат бўлса импульслар)",
    "Carry-over": "Ўтказиш",

    # ------------------------------------------------------------------ overview
    "Project": "Лойиҳа",
    "Released": "Чиқарилган сана",
    "Git tag": "Git тег",
    "Commit": "Коммит",
    "Branch": "Тармоқ",
    "Open folder": "Папкани очиш",
    "Stored simulation seasons": "Сақланган моделлаштириш мавсумлари",
    "Simulation tab": "Моделлаштириш бўлими",
    "seasons complete": "мавсум тўлиқ",
    "Computing time of the stored seasons": "Сақланган мавсумларнинг ҳисоблаш вақти",
    "Environment": "Муҳит",
    "matches": "мос",
    "other version": "бошқа версия",
    "too old": "жуда эски",
    "not installed": "ўрнатилмаган",
    "not installed (optional)": "ўрнатилмаган (мажбурий эмас)",
    "Other versions can change the last digits of recomputed results.":
        "Бошқа версиялар қайта ҳисобланган натижаларнинг охирги рақамларини ўзгартириши мумкин.",
    "Check the core": "Ядрони текшириш",
    "Compares the files of the simulation core (src/water01) with docs/CORE_MANIFEST.sha256.":
        "Моделлаштириш ядроси (src/water01) файлларини docs/CORE_MANIFEST.sha256 билан солиштиради.",
    "files differ": "та файл фарқ қилади",
    "files, no differences": "та файл, фарқ йўқ",
    "Quick actions": "Тезкор амаллар",
    "Checks of Theorems 1–4": "1–4-теоремалар текшируви",
    "scripts/analyse_theorems.py: all tables of results/analysis from the stored seasons (about 3 min).":
        "scripts/analyse_theorems.py: сақланган мавсумлардан results/analysis даги барча жадваллар "
        "(тахминан 3 дақиқа).",
    "Recreate the figures": "Расмларни қайта яратиш",
    "scripts/make_figures.py: the figures of the article in results/figures (about 20 s).":
        "scripts/make_figures.py: мақоланинг results/figures даги расмлари (тахминан 20 с).",
    "Run the tests": "Тестларни ишга тушириш",
    "pytest: randomised checks of Theorems 1–4 and tests of the simulation core (about 2 min).":
        "pytest: 1–4-теоремаларнинг тасодифий текширувлари ва моделлаштириш ядросининг тестлари "
        "(тахминан 2 дақиқа).",
    "Open the analysis tables": "Таҳлил жадвалларини очиш",
    "Open the figures": "Расмларни очиш",
    "Outcome of the execution rules (Table 4 of the article)": "Бажариш қоидаларининг натижаси (мақоланинг 4-жадвали)",
    "From results/analysis/rules_outcome.csv. λ: daily satisfaction of the worst-served user; dekad error: "
    "unweighted mean of |ΣV − Σx| / ΣD of R-1 over the calendar dekads.":
        "Манба: results/analysis/rules_outcome.csv. λ — энг кам таъминланган истеъмолчининг кунлик "
        "таъминланганлиги; декада хатоси — R-1 учун календар декадалар бўйича |ΣV − Σx| / ΣD нинг вазнсиз ўртачаси.",
    "Message": "Хабар",
    "results/analysis/rules_outcome.csv not found": "results/analysis/rules_outcome.csv топилмади",
    "Case": "Ҳолат",
    "Rule": "Қоида",
    "Mean daily λ": "Ўртача кунлик λ",
    "Days with λ = 0": "λ = 0 бўлган кунлар",
    "Shortfall, %": "Етишмовчилик, %",
    "Over-delivery, %": "Ортиқча бериш, %",
    "Delivery ratio of R-1": "R-1 нинг бериш нисбати",
    "Dekad error of R-1": "R-1 нинг декада хатоси",
    "Gate moves of R-1 per day": "R-1 дарвозасининг кунлик ҳаракатлари",

    # ------------------------------------------------------------------ data
    "Parameters": "Параметрлар",
    "Scenario:": "Сценарий:",
    "Status:": "Мақоми:",
    "all": "ҳаммаси",
    "observed": "кузатилган",
    "derived": "ҳисобланган",
    "assumed": "фараз",
    "setting": "созлама",
    "yes": "ҳа",
    "Open the configuration": "Конфигурацияни очиш",
    "observed: passport, datasheet or record; derived: computed from observed values; assumed: an assumption, "
    "covered by the robustness cases; setting: a numerical or experimental setting. Rows changed by the scenario are "
    "marked.":
        "кузатилган — паспорт, техник тавсиф ёки кузатув ёзуви; ҳисобланган — кузатилган қийматлардан ҳисобланган; "
        "фараз — барқарорлик ҳолатлари билан текширилган фараз; созлама — ҳисоблаш ёки тажриба созламаси. "
        "Сценарий ўзгартирган қаторлар белгиланган.",
    "Section": "Бўлим",
    "Parameter": "Параметр",
    "Value": "Қиймати",
    "Status": "Мақоми",
    "Source": "Манба",
    "Changed": "Ўзгарган",
    "Supply and demand": "Таъминот ва талаб",
    "Season:": "Мавсум:",
    "Open the data folder": "Маълумотлар папкасини очиш",
    "Demand of the outlets": "Сув олгичларнинг талаби",
    "The demand is derived from the 2021 plan of the Kegeyli system (Equation (1) of the article); the same profile is "
    "used in every season. Blank records are treated as days without supply.":
        "Талаб Кегейли тизимининг 2021 йилги режасидан олинган (мақоланинг (1) тенгламаси); ҳар бир мавсумда бир хил "
        "профиль ишлатилади. Бўш ёзувлар таъминотсиз кунлар деб қаралади.",
    "Loading…": "Юкланмоқда…",
    "Loading the season…": "Мавсум юкланмоқда…",
    "recorded": "кузатилган",
    "blank record (no supply)": "бўш ёзув (таъминот йўқ)",
    "Head discharge S, m³/s": "Бош сарф S, м³/с",
    "available at the node, W": "тугундаги мавжуд сув, W",
    "demand of the six outlets": "олтита сув олгичнинг талаби",
    "million m³ per day": "млн м³/кун",
    "blank records": "бўш ёзувлар",
    "deficit days": "танқис кунлар",
    "mean": "ўртача",
    "Season, million m³": "Мавсум, млн м³",
    "1–10 April, m³ per day": "1–10 апрель, м³/кун",
    "All": "Ҳаммаси",

    # ------------------------------------------------------------------ gate and rules
    "Gate": "Дарвоза",
    "Scenario": "Сценарий",
    "Regulator": "Регулятор",
    "Level h, m": "Сатҳ h, м",
    "Operating range of the node level: 2.40 m (passport minimum) to 3.23 m (relief level less the freeboard).":
        "Тугундаги сатҳнинг иш оралиғи: 2,40 м (паспорт бўйича минимум) дан 3,23 м гача (ташлама сатҳидан захира "
        "баландлик айирилган).",
    "Plan and rule": "Режа ва қоида",
    "Daily plan x, m³": "Кунлик режа x, м³",
    "Threshold θ": "Чегара θ",
    "Days (carry-over)": "Кунлар (ўтказиш)",
    "Outcome": "Натижа",
    "One day: delivery against plan": "Бир кун: режага нисбатан берилган ҳажм",
    "Several days: carry-over": "Бир неча кун: ўтказиш",
    "Computing…": "Ҳисобланмоқда…",
    "Enter a non-negative number": "Манфий бўлмаган сон киритинг",
    "Deadband": "Ўлик зона",
    "resolution steps": "ажратиш қадами",
    "One resolution step v": "Битта ажратиш қадами v",
    "Quantum q = k v": "Квант q = k v",
    "Pulse p = (k+1) v": "Импульс p = (k+1) v",
    "One full step C": "Тўлиқ очиқ дарвозанинг бир қадами C",
    "Exclusion threshold (1 − 1/(2k)) q": "Истисно чегараси (1 − 1/(2k)) q",
    "Daily pulse capacity N p": "Кунлик импульс сиғими N p",
    "Excluded: the plan is below the threshold of Theorem 1(a).": "Истисно: режа 1(а)-теоремадаги чегарадан кичик.",
    "No water although the plan is above the threshold (the condition is sufficient only).":
        "Режа чегарадан катта бўлса ҳам сув берилмади (шарт фақат етарли).",
    "Pulse rule": "Импульс қоидаси",
    "pulses": "импульслар",
    "Bounds (14)": "(14) чегаралар",
    "not in the pulse regime": "импульс режимида эмас",
    "The plan is at least the daily pulse capacity.": "Режа кунлик импульс сиғимидан кичик эмас.",
    "Equal split": "Тенг бўлиш",
    "not applicable": "қўлланмайди",
    "Theorem 1(b) needs q ≤ x ≤ ⌈N/2⌉ (C − v) and C ≥ 2q + 3v; smaller plans are served by pulses.":
        "1(б)-теорема учун q ≤ x ≤ ⌈N/2⌉ (C − v) ва C ≥ 2q + 3v керак; кичикроқ режалар импульслар билан "
        "бажарилади.",
    "plan, V = x": "режа, V = x",
    "direct execution": "тўғридан-тўғри бажариш",
    "pulse rule": "импульс қоидаси",
    "equal split": "тенг бўлиш",
    "Daily plan x / q": "Кунлик режа x / q",
    "Delivered volume V / q": "Берилган ҳажм V / q",
    "One day at a constant level": "Ўзгармас сатҳда бир кун",
    "carry-over": "ўтказиш",
    "plan x": "режа x",
    "Delivered volume, m³": "Берилган ҳажм, м³",
    "Pulse rule with and without carry-over": "Ўтказиш билан ва ўтказишсиз импульс қоидаси",
    "debt e(s), carry-over": "қарз e(s), ўтказиш",
    "cumulative error, pulse rule": "жамланган хато, импульс қоидаси",
    "Day": "Кун",
    "Plan − delivery, m³": "Режа − берилган ҳажм, м³",

    # ------------------------------------------------------------------ simulation
    "Refresh": "Янгилаш",
    "Select missing": "Етишмаганларни танлаш",
    "Run selected": "Танланганларни ҳисоблаш",
    "Computes the selected seasons that are not complete. A complete season is never recomputed; to repeat one, "
    "delete its result files first.":
        "Танланган тўлиқ бўлмаган мавсумларни ҳисоблайди. Тўлиқ мавсум ҳеч қачон қайта ҳисобланмайди; уни такрорлаш "
        "учун аввал унинг натижа файлларини ўчиринг.",
    "Run a phase": "Босқични ишга тушириш",
    "Parallel workers:": "Параллел жараёнлар:",
    "Several seasons can be computed at once; each worker uses one processor core.":
        "Бир нечта мавсумни бир вақтда ҳисоблаш мумкин; ҳар бир жараён процессорнинг битта ядросини ишлатади.",
    "Open the results folder": "Натижалар папкасини очиш",
    "Show the error": "Хатони кўрсатиш",
    "Release claims": "Бандликни бекор қилиш",
    "Removes the claim of selected seasons left by an interrupted or failed run, so that they can be computed again. "
    "Do not use it while another program computes them.":
        "Тўхтатилган ёки хато билан тугаган ҳисобдан қолган танланган мавсумлар бандлигини олиб ташлайди, шунда "
        "уларни қайта ҳисоблаш мумкин бўлади. Уларни бошқа дастур ҳисоблаётган пайтда ишлатманг.",
    "Case / rule / season": "Ҳолат / қоида / мавсум",
    "Description": "Тавсиф",
    "State": "Ҳолати",
    "Minutes": "Дақиқа",
    "Computed (UTC)": "Ҳисобланган вақти (UTC)",
    "Each season is one run of the closed loop over 183 days (about 3 min on one core). Results are written to "
    "results/runs/<case>/<rule>_<season>.csv with a .meta.json file (checksums of the code and inputs, environment).":
        "Ҳар бир мавсум — ёпиқ контурнинг 183 кунлик битта ҳисоби (процессорнинг битта ядросида тахминан 3 дақиқа). "
        "Натижалар results/runs/<case>/<rule>_<season>.csv файлига .meta.json файли (код ва кириш "
        "маълумотларининг назорат йиғиндилари, муҳит) билан ёзилади.",
    "All seasons are complete.": "Барча мавсумлар тўлиқ ҳисобланган.",
    "The selected seasons are complete; nothing to compute.": "Танланган мавсумлар тўлиқ; ҳисоблаш керак эмас.",
    "{n} of the selected seasons are claimed by an earlier run that was interrupted or failed, or by another program "
    "that is computing them now. Release these claims and compute the seasons again?\n\nYes: release and compute. "
    "No: compute only the other seasons.":
        "Танланган мавсумлардан {n} таси тўхтатилган ёки хато билан тугаган аввалги ҳисоб томонидан, ёки уларни "
        "ҳозир ҳисоблаётган бошқа дастур томонидан банд қилинган. Бу бандлик бекор қилиниб, мавсумлар қайта "
        "ҳисоблансинми?\n\nҲа: бекор қилиш ва ҳисоблаш. Йўқ: фақат қолган мавсумларни ҳисоблаш.",
    "Seasons to compute: {n}; parallel workers: {w}. This takes about {m:.0f} min. Continue?":
        "Ҳисобланадиган мавсумлар: {n}; параллел жараёнлар: {w}. Бу тахминан {m:.0f} дақиқа олади. Давом этилсинми?",
    "Interrupted seasons released": "Тўхтатилган мавсумлар бандлиги бекор қилинди",
    "Complete": "Тўлиқ",
    "this run": "бу ҳисоб",
    "No claimed, failed or partial season is selected.":
        "Банд қилинган, хато билан тугаган ёки чала мавсум танланмаган.",
    "Wait until the running script finishes.": "Ишлаётган скрипт тугашини кутинг.",
    "Release {n} season(s)? Do this only if no other program is computing them.":
        "{n} та мавсумнинг бандлиги бекор қилинсинми? Буни фақат уларни бошқа дастур ҳисобламаётган бўлса қилинг.",
    "Select a season whose state is error.": "Ҳолати «хато» бўлган мавсумни танланг.",
    "done": "тўлиқ",
    "missing": "ҳисобланмаган",
    "claimed": "банд",
    "error": "хато",
    "partial": "чала",
    "running": "ҳисобланмоқда",

    # ------------------------------------------------------------------ results
    "Rules (select one or more)": "Қоидалар (бир ёки бир нечтасини танланг)",
    "Show ideal execution as reference": "Идеал бажаришни эталон сифатида кўрсатиш",
    "Season": "Мавсум",
    "Outlet": "Сув олгич",
    "Quantity": "Катталик",
    "Export the plotted data (CSV)": "Графикдаги маълумотларни экспорт қилиш (CSV)",
    "Summary of the selection": "Танлов бўйича хулоса",
    "All seasons": "Барча мавсумлар",
    "Daily satisfaction of the worst-served user λ": "Энг кам таъминланган истеъмолчининг кунлик таъминланганлиги λ",
    "Satisfaction of the outlet r": "Сув олгичнинг таъминланганлиги r",
    "Plan and delivery of the outlet": "Сув олгичнинг режаси ва берилган ҳажм",
    "Daily error of the outlet: delivery − target": "Сув олгичнинг кунлик хатоси: берилган − мақсадли ҳажм",
    "Error of the outlet over calendar dekads": "Сув олгичнинг календар декадалар бўйича хатоси",
    "Node level": "Тугундаги сатҳ",
    "Open steps and pulses of the outlet": "Сув олгичнинг очиқ қадамлари ва импульслари",
    "Mean λ by season": "Мавсумлар бўйича ўртача λ",
    "No stored results in results/runs.": "results/runs да сақланган натижалар йўқ.",
    "Select at least one rule.": "Камида битта қоидани танланг.",
    "Loading results…": "Натижалар юкланмоқда…",
    "No stored results for this selection.": "Бу танлов учун сақланган натижалар йўқ.",
    "ideal execution": "идеал бажариш",
    "Calendar dekad": "Календар декада",
    "Dekad of the season (mean over the seasons)": "Мавсумнинг декадаси (мавсумлар бўйича ўртача)",
    "Unweighted errors; the early-April dekads, with daily demands below one quantum, dominate the mean of R-1.":
        "Вазнсиз хатолар; кунлик талаби битта квантдан кичик бўлган апрель бошидаги декадалар R-1 нинг ўртачасида "
        "устунлик қилади.",
    "open steps": "очиқ қадамлар",
    "Volume, m³ per day": "Ҳажм, м³/кун",
    "Node level, m (daily minimum to maximum)": "Тугундаги сатҳ, м (кунлик минимумдан максимумгача)",
    "Steps per day": "Кунлик қадамлар",
    "Nothing is plotted.": "Графикда ҳеч нарса йўқ.",
    "Seasons": "Мавсумлар",
    "Days": "Кунлар",
    "Smallest daily λ": "Энг кичик кунлик λ",
    "Delivery ratio ΣV / ΣD": "Бериш нисбати ΣV / ΣD",
    "Delivered volume / planned volume": "Берилган ҳажм / режадаги ҳажм",
    "Days with a positive plan": "Режа мусбат бўлган кунлар",
    "Positive plan, no water": "Режа мусбат, сув берилмаган",
    "Mean |delivery − daily target|, m³": "Ўртача |берилган − кунлик мақсадли ҳажм|, м³",
    "Dekad error, unweighted mean": "Декада хатоси, вазнсиз ўртача",
    "Dekad error, largest": "Декада хатоси, энг катта",
    "Open steps per day": "Кунлик очиқ қадамлар",
    "Pulses per day": "Кунлик импульслар",

    # ------------------------------------------------------------------ analysis
    "Scripts": "Скриптлар",
    "Run": "Бошлаш",
    "Tables": "Жадваллар",
    "Table:": "Жадвал:",
    "Open": "Очиш",
    "Export (CSV)": "Экспорт (CSV)",
    "All tables of results/analysis from the stored seasons: exclusion, equal split, price of indivisibility and whole "
    "steps, pulse rule, carry-over, outcome of the rules, device chain, records.":
        "Сақланган мавсумлардан results/analysis даги барча жадваллар: истисно, тенг бўлиш, бўлинмаслик баҳоси ва "
        "бутун қадамлар, импульс қоидаси, ўтказиш, қоидаларнинг натижаси, қурилмалар занжири, кузатув ёзувлари.",
    "Figures of the article": "Мақоланинг расмлари",
    "The five figures of the article and two separate panels of Figure 5 (results/figures).":
        "Мақоладаги бешта расм ва 5-расмнинг алоҳида чизилган иккита панели (results/figures).",
    "Derived inputs": "Ҳисобланган кириш маълумотлари",
    "Delivery factor, monthly shares of Abad-Yarmish, node balance and checks of the records "
    "(results/inputs/derived_inputs.json).":
        "Етказиш коэффициенти, Abad-Yarmish нинг ойлик улушлари, тугун баланси ва кузатув ёзувларининг текшируви "
        "(results/inputs/derived_inputs.json).",
    "Plant: grid and time step": "Гидравлик модел: тўр ва вақт қадами",
    "Convergence of the Saint–Venant plant with the conveyance loss of the baseline (Table S2a).":
        "Асосий ҳолатдаги узатиш исрофи билан Сен-Венан моделининг яқинлашиши (S2a жадвал).",
    "Plant: volume of one quantum": "Гидравлик модел: битта квант ҳажми",
    "The smallest opening of R-1 for one control step at 1–16 hydraulic steps (Table S2b).":
        "1–16 гидравлик қадамда битта бошқарув қадами учун R-1 нинг энг кичик очилиши (S2b жадвал).",
    "Plant: comparison with EPA SWMM": "Гидравлик модел: EPA SWMM билан солиштириш",
    "Three transients replayed in EPA SWMM 5 (needs the package swmm-toolkit; Table S2c).":
        "EPA SWMM 5 да такрорланган учта ўтиш жараёни (swmm-toolkit пакети керак; S2c жадвал).",
    "Gate movements: summary": "Дарвоза ҳаракатлари: хулоса",
    "Summary of the stored re-runs of the quantised-actuator case.":
        "Квантланган ижро механизми ҳолатининг сақланган қайта ҳисобларидан хулоса.",
    "Gate movements: re-run": "Дарвоза ҳаракатлари: қайта ҳисоблаш",
    "Re-runs the 50 seasons of q_main, counts the gate movements and checks that the stored volumes are reproduced.":
        "q_main нинг 50 та мавсумини қайта ҳисоблайди, дарвоза ҳаракатларини санайди ва сақланган ҳажмлар "
        "такрорланишини текширади.",
    "Requests of direct execution: summary": "Тўғридан-тўғри бажариш сўровлари: хулоса",
    "Summary of the stored re-runs of the seven direct-execution cases.":
        "Тўғридан-тўғри бажаришнинг етти ҳолатини сақланган қайта ҳисобларидан хулоса.",
    "Requests of direct execution: re-run": "Тўғридан-тўғри бажариш сўровлари: қайта ҳисоблаш",
    "Re-runs the 70 direct-execution seasons and checks every request against the remainder of the plan.":
        "Тўғридан-тўғри бажаришнинг 70 та мавсумини қайта ҳисоблайди ва ҳар бир сўровни режанинг қолдиғи билан "
        "текширади.",
    "Test suite (pytest)": "Тестлар тўплами (pytest)",
    "Randomised checks of Theorems 1–4 on the abstract actuator, short closed-loop checks of the rules and the tests "
    "of the simulation core.":
        "Абстракт ижро механизмида 1–4-теоремаларнинг тасодифий текширувлари, қоидаларнинг қисқа ёпиқ контур "
        "текширувлари ва моделлаштириш ядросининг тестлари.",
    "Checksums of the simulation core": "Моделлаштириш ядросининг назорат йиғиндилари",
    "The scripts run in separate processes; their output appears in the console below. Stored seasons are read, not "
    "recomputed, except by the re-run scripts.":
        "Скриптлар алоҳида жараёнларда ишлайди; уларнинг чиқиши пастдаги консолда кўринади. Сақланган мавсумлар "
        "ўқилади, қайта ҳисобланмайди (қайта ҳисоблаш скриптларидан ташқари).",
    "≈ 3 min": "≈ 3 дақ.",
    "≈ 20 s": "≈ 20 с",
    "< 1 min": "< 1 дақ.",
    "several min": "бир неча дақ.",
    "≈ 3 h": "≈ 3 соат",
    "≈ 5 h": "≈ 5 соат",
    "≈ 2 min": "≈ 2 дақ.",
    "< 1 s": "< 1 с",

    # ------------------------------------------------------------------ figures
    "Figure {n}": "{n}-расм",
    "Extra": "Қўшимча",
    "Quantised gate and execution rules (abstract actuator, constant level, k = 5): (a) one step from a closed gate; "
    "(b) one day of N = 96 steps.":
        "Квантланган дарвоза ва бажариш қоидалари (абстракт ижро механизми, ўзгармас сатҳ, k = 5): (a) ёпиқ "
        "дарвозадан битта қадам; (b) N = 96 қадамли бир кун.",
    "Daily plan of each regulator in units of its quantum at the lowest level of the day under direct execution, "
    "2010–2019: deadband 0.5% (k = 5), 0.25% (k = 3) and 1% (k = 10).":
        "Тўғридан-тўғри бажаришда ҳар бир регуляторнинг кунлик режаси, куннинг энг паст сатҳидаги квант "
        "бирликларида, 2010–2019: ўлик зона 0,5 % (k = 5), 0,25 % (k = 3) ва 1 % (k = 10).",
    "Error of the pulse rule on the regulator-days operated by pulses only, for θ = 0, 0.25, 0.5 and 0.75, with the "
    "bounds of Theorem 3.":
        "Фақат импульслар билан ишлаган регулятор-кунларда импульс қоидасининг хатоси, θ = 0; 0,25; 0,5 ва 0,75 "
        "учун, 3-теорема чегаралари билан.",
    "Daily error of the equal split and of the pulse rule with θ = 0.5 on the same regulator-days, with the bound of "
    "Theorem 1(b).":
        "Ўша регулятор-кунларда тенг бўлиш ва θ = 0,5 даги импульс қоидасининг кунлик хатоси, 1(б)-теорема "
        "чегараси билан.",
    "Carry-over and accounting periods at R-1: (a) daily satisfaction in 1–12 April 2010; (b) error of the delivery "
    "over accounting periods of T days.":
        "R-1 да ўтказиш ва ҳисоб даврлари: (a) 2010 йил 1–12 апрелдаги кунлик таъминланганлик; (b) T кунлик ҳисоб "
        "даврлари бўйича етказиб бериш хатоси.",
    "Not in the article: panel (a) of Figure 5 as a separate figure (satisfaction of R-1 in 1–12 April 2010).":
        "Мақолада йўқ: 5-расмнинг (a) панели алоҳида расм сифатида (2010 йил 1–12 апрелда R-1 нинг "
        "таъминланганлиги).",
    "Not in the article: panel (b) of Figure 5 as a separate figure (error over accounting periods at R-1); the "
    "colours of the rules differ from Figure 5.":
        "Мақолада йўқ: 5-расмнинг (b) панели алоҳида расм сифатида (R-1 да ҳисоб даврлари бўйича хато); "
        "қоидаларнинг ранглари 5-расмдагидан фарқ қилади.",
    "No figures in results/figures; recreate them first.":
        "results/figures да расмлар йўқ; аввал уларни қайта яратинг.",
    "Open the folder": "Папкани очиш",

    # ------------------------------------------------------------------ article
    "The sources of the article (paper/src and paper/tools) are not in this folder.":
        "Мақоланинг манбалари (paper/src ва paper/tools) бу папкада йўқ.",
    "They are kept locally by the authors and are not part of the public repository.":
        "Улар муаллифларда маҳаллий сақланади ва очиқ репозиторийга кирмайди.",
    "Build": "Тузиш",
    "Output folder:": "Натижа папкаси:",
    "Browse…": "Танлаш…",
    "Build and check": "Тузиш ва текшириш",
    "Generates the tables from results/analysis, builds manuscript.docx and supplementary.docx and checks every "
    "number of the text against the results.":
        "results/analysis дан жадвалларни яратади, manuscript.docx ва supplementary.docx ни тузади ҳамда матндаги "
        "ҳар бир сонни натижалар билан текширади.",
    "Generate the tables": "Жадвалларни яратиш",
    "Build the documents": "Ҳужжатларни тузиш",
    "Check the documents": "Ҳужжатларни текшириш",
    "Open the manuscript": "Қўлёзмани очиш",
    "Open the supplement": "Қўшимча материалларни очиш",
    "Words of the main text": "Асосий матндаги сўзлар",
    "Sources (paper/src)": "Манбалар (paper/src)",
    "Open the sources": "Манбаларни очиш",
    "Abstract": "Аннотация",
    "1. Introduction": "1. Кириш",
    "2. Materials and Methods": "2. Материаллар ва усуллар",
    "3. Results": "3. Натижалар",
    "4. Discussion": "4. Муҳокама",
    "5. Conclusions": "5. Хулосалар",
    "Appendix A": "A илова",
    "Total": "Жами",
    "Words": "Сўзлар",
    "Text only: tables, figures and the reference list are not counted.":
        "Фақат матн: жадваллар, расмлар ва адабиётлар рўйхати ҳисобга олинмайди.",
    "Modified": "Ўзгартирилган",
    "Size, KB": "Ҳажми, КБ",
    "Check of the documents": "Ҳужжатлар текшируви",
}
