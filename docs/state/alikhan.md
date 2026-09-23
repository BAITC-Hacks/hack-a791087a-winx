# @alikhan — состояние

## Сейчас
P0 завершён: план, API v1 и запускаемый скелет. Git email: achabarovcuru@gmail.com.
Последний push до записи: `93c2a24` (исходные документы). P0 — коммит с этим файлом;
его хэш: `git log -1 --format=%h -- docs/state/alikhan.md`.

## Сделано
Скопированы AGENTS.md, TASK.md, DATASET.md; добавлены IDEA, PLAN, API, HANDOFF.
Созданы data/models/engine/ai, app.py, run.py, env-шаблон, зависимости, README, THIRD_PARTY.
Baseline вычисляется из данных; 8 тестов прошли, HTTP / и /_stcore/health → 200.

## Не закончено
`citysim/engine.py`: validate_scenario и simulate — NotImplementedError (E1).
Форма пяти мер и полный сценарий — U1/I1; live API без реального ключа не проверен.

## Решения
Python + Streamlit + OpenAI; запуск `python run.py`, без Docker.
Только engine считает числа; AI объясняет SimulationResult; без ключа demo.
API v1 — `docs/API.md` и `citysim/models.py`; district_id — английские стабильные ID.
После общего скелета ai/app принадлежат @AaaDddmyrza, engine/data/contracts — @alikhan.

## Грабли
Baseline с нулём решений — только ориентир, не валидный игровой сценарий.
У city district_id=None; 5 решений не означают все 5 направлений.
README явно отделяет текущий скелет от ещё не реализованной приёмки I1.

## Проверка
`python run.py --check` → 8 тестов OK; `python run.py` → Score 52.5577, Ncrit=2, demo.
Проверено Windows / Python 3.14.4; первый запуск требует интернет для pip.

## Следующий шаг
E1: сначала тесты правил и эталона 95/56.5431/0, затем реализовать validate_scenario и simulate.
