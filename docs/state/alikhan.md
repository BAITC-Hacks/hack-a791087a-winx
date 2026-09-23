# @alikhan — состояние

## Сейчас
Новая сессия: анализ после merge 3D-прототипа, база `102a04f` в main.
E1/E2/C0 завершены; S1 ещё не реализован. Зона: engine, поиск, API и запуск.
Коммит сводки: `git log -1 --format=%h -- docs/state/alikhan.md`.

## Сделано
Получены `c5bacc9` / `102a04f`: baseline 3D напарника, ui.scene, тесты и сборка.
docs/PROJECT_REVIEW.md: сверка ТЗ/кода, ограничения 3D, владельцы и приёмка этапов.
API/PLAN/HANDOFF актуализированы без изменения численных правил и контрактов.
Проверены Python/JS-тесты, сборка, зависимости и рендер в Chromium.

## Не закончено
S1: отсутствуют citysim/search.py и tests/test_search.py.
U1/I1/A1/A2, полные V1/V2 — зона напарника; app.py вызывает только baseline.
ui.scene фиксирует id/label baseline; A/B, версия и события требуют интеграции.

## Решения
Следующий пакет — S1 по C0; напарник параллельно делает U1/I1.
TASK/DATASET/data.py и engine сохранены; числа считает только engine.
max_changes=0/1; locked — точные пары исходного A; оба раунда проверяются против A.
EPS=1e-9 относительно A; до 20 уникальных кандидатов, без обещания оптимума.

## Грабли
frozen не защищает вложенные dict: S1 копирует source/best/checks/previous.
Не передавать simulate в текущий scene builder: он пометит сценарий как baseline.
Старые записи HANDOFF исторические; актуальная сводка находится сверху.

## Проверка
`python run.py --check` → 70 OK; `.venv/Scripts/python.exe -m pip check` OK.
В components/city3d/frontend: `npm ci`, `npm test` → 4 OK, `npm run build` OK.
`DEMO_MODE=1`, `python run.py --headless --port 8515`: Chromium рендерит 3D.
S1: Нура 38; выбор Есиля → 48 / 62.9900 и подтверждение выбора в Python.
Live AI, реальная потеря WebGL и физический pinch здесь не проверены.

## Следующий шаг
Начать tests/test_search.py и реализовать generate_candidates/review_candidates S1.
