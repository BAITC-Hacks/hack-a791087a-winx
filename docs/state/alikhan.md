# @alikhan — состояние

## Сейчас
E1/E2 завершены; E1 опубликован в `f6110e7`. База напарника `d12ac6a`.
Git email: achabarovcuru@gmail.com; зона: engine, тесты, API, поиск и запуск.
Текущий коммит состояния: `git log -1 --format=%h -- docs/state/alikhan.md`.

## Сделано
В citysim/engine.py реализованы validate_scenario и simulate по API v1.
tests/test_engine.py: 21 тест, все коды ошибок, эталон/61, 120 перестановок.
tests/test_engine_boundaries.py: 12 тестов границ, лагов, синергий, clip и изоляции.
API уточняет сочетания ошибок и канонизацию effects; общие типы не менялись.
План независимо проверен; выводы и результаты — docs/ENGINE_REVIEW.md.

## Не закончено
U1/I1/A1/V1/V2 — зона напарника; C0/S1 ещё не реализованы.
README/IMPLEMENTATION_PLAN: запрос актуализировать E1/E2 передан владельцу через HANDOFF.

## Решения
Первые два этапа нашей зоны — E1 и E2, как указано в PLAN/HANDOFF.
API v1 достаточен; TASK/DATASET/data.py не меняются.
effects содержат прибавки до clip, indicator_deltas — фактические изменения после clip.
Старое ограничение по времени снято; обязательность 3D сохраняется для следующих этапов.

## Грабли
README/UI описывают скелет; законченный engine сам по себе не означает готовность формы.
Запросы HANDOFF на E1 и effects/deltas/M11 выполнены; UI/AI готовы к подключению engine.

## Проверка
`python run.py --check` → 45 тестов OK, включая AppTest и offline AI; pip check OK.
Эталон simulate: cost=95, remaining=5, Score=56.54307, Ncrit=0.

## Следующий шаг
C0: согласовать и опубликовать контракты ревизора/3D согласно IMPLEMENTATION_PLAN.
