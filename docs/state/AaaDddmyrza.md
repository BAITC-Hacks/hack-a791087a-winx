# @AaaDddmyrza — состояние

## Сейчас
A2 UI/V2 готовы в codex/review-ui-v2 с обновлениями main8c9f71f (V1/PR3 объединён).
Продуктовый коммит ecbf25c; интегрирован main8c9f71f, сигнатуры прежние.
Git email: adildaulet2005@gmail.com; зона app/ui/AI/3D.

## Сделано
app.py + ui/review.py: reviewer по кнопке, locks/0–1, status/outcome/warning/checks.
ui/state.py: независимые A/B/review; ручнойB, accept/keep; сброс при новомA/constraints.
Принятие B обновляет черновик, очищает объяснение, B и ревизию.
V2: baseline/A/B, пять слоёв по два показателя, различия выбранного индикатора.
Карточка A/B/Δ, меры и effects из engine, таблица текущего состояния при fallback.
Локальный bundle пересобран; README/IDEA/PLAN/DEMO/HANDOFF обновлены.

## Не закончено
Совместная приёмка R и чистая установка по README.
Платный live API и физический pinch на телефоне не проверены.
Вводный статус API.md обновляет владелец; запрос в HANDOFF.

## Решения
UI/V2 не меняет TASK/DATASET/data.py/engine/shared models/API/reviewer.
ScenePayload C0 прежний; active_state — частный параметр bridge рядом с view_key.
Менять ограничения → сброс B/ревизии; редактировать draft → сохранить A/B.
Demo-превью и тесты без настоящих API-вызовов; ключи не выводились/не коммитились.

## Грабли
Очистка max_changes даёт None: guard возвращает1, регрессионный AppTest проходит.
При старом Python-модуле перезапустить Streamlit; планы после reload могут исчезнуть.
.env.example имеет пользовательские правки; не включать в продуктовый коммит.

## Проверка
python run.py --check: 181 Python; frontend npm test: 16 JS; npm run build.
Demo: A95/56.54307 → B80/56.69056; три ухудшения видны, A не меняется до принятия.
Chromium: ручнойB/A=B/accept, камера, WebGL loss/unavailable/retry, компонент390.
Preview http://127.0.0.1:8517 (DEMO_MODE=1); сценарий docs/DEMO.md.

## Следующий шаг
Совместно с @alikhan выполнить R: чистая установка и сквозная приёмка по DEMO.md.
