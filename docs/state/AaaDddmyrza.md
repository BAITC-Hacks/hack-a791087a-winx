# @AaaDddmyrza — состояние

## Сейчас
V1 готов в codex/scene-v1 от ff82455 (main); последний коммит: git log -1.
Git email: adildaulet2005@gmail.com; зона app/ui/AI/3D.

## Сделано
Ранее объединены U1/I1/A1 и S1 через PR #2.
app.py: baseline/A, после расчёта выбирается A, таблица текущего снимка.
ui/scene.py: ScenePayload v1 из снимков, проверки, копирование, SceneEvents.
components/city3d: schema, null-выбор, сохранение камеры, cleanup/fallback/retry.
Локальный JS/CSS-bundle пересобран. README/PLAN/HANDOFF актуализированы.

## Не закончено
A2 backend у @alikhan; UI ревизора и V2 A/B/различия ещё не подключены.
Платный live API и физический pinch на телефоне не проверены.
Текст статуса V1 в API.md требует правки владельцем, запрос в HANDOFF.

## Решения
TASK/DATASET/data.py/engine/shared models/API/reviewer не изменены.
Python выбирает один снимок baseline/A по C0; JS не считает модель.
Черновик не меняет сохранённый A; новый расчёт обновляет сцену.
Ключи не нужны для 3D; платных запросов не было, demo-превью без ключа.
Постоянного хранилища нет: reload/перезапуск сервера может сбросить сессию.

## Грабли
При старой сборке в браузере перезапустить Streamlit и перезагрузить страницу.
.env.example содержит пользовательские локальные правки; не включать в V1-коммит.

## Проверка
python run.py --check: 130 Python; frontend npm test: 11 JS; npm run build.
Chromium: Нура baseline 38/35, A 48/43.75; камера и выбор JS→Python.
Стенд bundle: context_lost, webgl_unavailable, schema, retry; CSP только localhost.
Узкая ширина: приложение760, компонент iframe390; подробнее README компонента.
Локальный demo: http://127.0.0.1:8514; обычный запуск python run.py.

## Следующий шаг
После готовности A2 backend подключить UI review_scenario с явным принятием B.
