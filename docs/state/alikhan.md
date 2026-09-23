# @alikhan — состояние

## Сейчас
C0 завершён; предыдущие E1/E2 опубликованы в `f6110e7` / `1e812e4`.
Git email: achabarovcuru@gmail.com; зона: engine, тесты, API, поиск и запуск.
Текущий коммит состояния: `git log -1 --format=%h -- docs/state/alikhan.md`.

## Сделано
citysim/review_models.py: типы ревизора/сцены, лимиты, проверки исходника/locked/замен/EPS.
tests/test_review_contracts.py: 20 тестов; baseline/подменённые числа, locked, EPS, два раунда.
docs/API.md: опубликованы C0 и ScenePayload v1, отдельные будущие сигнатуры S1/A2.
Пример JSON сцены из API выполнен на реальном engine и не делит словари с результатом.
PLAN/HANDOFF обновлены; независимое ревью исправлено и проверено тестами.

## Не закончено
S1 (citysim/search.py) ещё не реализован; U1/I1/A1/V1/V2/A2 — зона напарника.
README/IMPLEMENTATION_PLAN: запрос актуализировать E1/E2/C0 передан через HANDOFF.

## Решения
API v1, TASK/DATASET/data.py и engine сохранены; C0 в отдельном модуле.
max_changes=0/1; locked — точные пары исходного A; оба раунда проверяются против A.
EPS=1e-9 относительно A исключает накопление допуска; ranking описан в API.
ScenePayload — TypedDict, runtime-builder в ui.scene принадлежит напарнику.

## Грабли
Не импортировать search/reviewer/ui.scene до реализации соответствующих этапов.
Типы frozen не защищают вложенные dict: S1 обязан копировать снимки и previous.

## Проверка
`python run.py --check` → 65 тестов OK, включая AppTest, offline AI и контракты C0.
Эталон simulate: cost=95, remaining=5, Score=56.54307, Ncrit=0.

## Следующий шаг
S1: реализовать generate_candidates/review_candidates с ограничением 20 и тестами.
