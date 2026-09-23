# @alikhan — состояние

## Сейчас
A2 backend d5e0e47; получен main 85ae360 с завершённым V1 напарника.
Коммит пакета: `git log -1 --format=%h -- citysim/reviewer.py`.
Сигнатура review_scenario и общие модели сохранены; контракт уточнён в docs/API.md.

## Сделано
citysim/reviewer.py: demo/live, проверка JSON, два раунда S1, fallback и объяснение A→B.
tests/test_reviewer.py: offline-моки SDK, лимиты, ошибки, сохранность A/best, отмена запросов.
API/PLAN/IMPLEMENTATION_PLAN/NEXT_PARALLEL_STEPS/HANDOFF: готовность backend и передача UI.
Проверен реальный live gpt-6-luna; ключ доступен, но A1/A2 уходят в fallback; HANDOFF.

## Не закончено
UI A2/V2 ещё не подключены; настроить live-генерацию A1/A2 после выявленных сбоев.
Чистый запуск по README и полная совместная приёмка остаются этапом R.

## Решения
Числа только из engine; AI предлагает ID. Source/constraints валидируются до SDK.
MAX 2×10, общий лимит 20 включая невалидные; fallback сохраняет previous и его best.
35 с на ревизию, 15 с на запрос, retries=0; timeout отменяет async I/O, cleanup ограничен.
Истёк deadline → incomplete; завершённый fallback → completed_limited + demo + warning.
Explanation детерминированный в обоих режимах; mode=openai обозначает источник предложений.

## Грабли
previous брать неизменённым из S1; менять status вручную нельзя (context_digest).
best.score_delta — от baseline; reviewer вычисляет разность best.after.score - source.after.score.
Sync live внутри asyncio loop даёт demo-warning; async-потребителю нужен asyncio.to_thread.
gpt-6-luna default medium: A1 расходует все 700 токенов на reasoning, A2 timeout15с.

## Проверка
После pull V1: run.py --check → 155 OK (25 A2); frontend npm test → 11 OK.
Эталон A: 95 / 56.54307; best из 20: 80 / 56.69056 / Ncrit=0 (M5 → M11/Нура).
Тесты A2: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_reviewer.py -v`.
SDK с HTTP MockTransport: два раунда дают тот же best, что S1 review20; A сохраняется.
Live: короткий запрос OK; A1 incomplete/max_output_tokens (700 reasoning); A2 demo за15.42с.

## Следующий шаг
Настроить A2 live под gpt-6-luna с сохранением лимитов; A1 передан владельцу в HANDOFF.
