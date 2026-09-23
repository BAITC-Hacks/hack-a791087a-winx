# @alikhan — состояние

## Сейчас
A2 backend d5e0e47; V1 напарника в main 85ae360; настройка live gpt-6-luna завершена.
Коммит пакета: `git log -1 --format=%h -- citysim/ai.py citysim/reviewer.py`.
Сигнатура review_scenario и общие модели сохранены; контракт уточнён в docs/API.md.

## Сделано
S1/A2 backend: ограниченные предложения, валидация engine, fallback, объяснение A→B.
По поручению пользователя настроены A1/A2 при параллельной работе напарника UI/V2.
Luna: reasoning=none; A1 max_output_tokens=1600, A2=4096; A1 отклоняет incomplete.
Три новых регрессионных теста; реальный live A1/A2 прошёл, замеры в HANDOFF.

## Не закончено
UI A2/V2 у напарника; A1 live не назвал пары ниже40 до сценария (запись в HANDOFF).
Чистый запуск по README и полная совместная приёмка остаются этапом R.

## Решения
Числа только из engine; AI предлагает ID. Source/constraints валидируются до SDK.
MAX 2×10, общий лимит 20 включая невалидные; fallback сохраняет previous и его best.
35 с на ревизию, 15 с на запрос, retries=0; timeout отменяет async I/O, cleanup ограничен.
Истёк deadline → incomplete; завершённый fallback → completed_limited + demo + warning.
Explanation детерминированный в обоих режимах; mode=openai обозначает источник предложений.
Профиль none только для точного gpt-6-luna; другим моделям reasoning не добавляется.

## Грабли
previous брать неизменённым из S1; менять status вручную нельзя (context_digest).
best.score_delta — от baseline; reviewer вычисляет разность best.after.score - source.after.score.
Sync live внутри asyncio loop даёт demo-warning; async-потребителю нужен asyncio.to_thread.
Luna default medium раньше исчерпывал 700 токенов A1 и давал timeout A2; исправлено.

## Проверка
`.venv/Scripts/python.exe run.py --check` → 158 OK; frontend npm test → 11 OK.
Live A1/AppTest: completed/openai, 7.11 с, 392 output tokens, reasoning0, без warning.
Live A2: оба раунда completed, суммарно6.42 с; openai,2 valid checks, A не изменён.
Эталон95/56.54307 → live best97/56.64391/Ncrit0; ограниченный поиск, не оптимум.
Ключ в локальной конфигурации; .env игнорируется, в коммит не включается.

## Следующий шаг
После UI A2/V2 напарника провести численную интеграцию и приёмку R.
