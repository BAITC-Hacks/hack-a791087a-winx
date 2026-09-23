# @alikhan — состояние

## Сейчас
A2 backend реализован на main после ff82455; UI A2 и V1/V2 остаются у напарника.
Коммит пакета: `git log -1 --format=%h -- citysim/reviewer.py`.
Сигнатура review_scenario и общие модели сохранены; контракт уточнён в docs/API.md.

## Сделано
citysim/reviewer.py: demo/live, проверка JSON, два раунда S1, fallback и объяснение A→B.
tests/test_reviewer.py: offline-моки SDK, лимиты, ошибки, сохранность A/best, отмена запросов.
API/PLAN/IMPLEMENTATION_PLAN/NEXT_PARALLEL_STEPS/HANDOFF: готовность backend и передача UI.
SDK 3.19.0 + HTTP MockTransport: 2 запроса/20 checks, итог полностью совпадает с S1.

## Не закончено
UI A2 ещё не вызывает backend; V1 пока baseline, затем V2; реальные API-вызовы не проверены.
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
При выводе объяснения в Windows shell использовать python -X utf8 (символ →).

## Проверка
`.venv/Scripts/python.exe run.py --check` → 144 OK (25 A2), включая AppTest; запуск HTTP 200.
Эталон A: 95 / 56.54307; best из 20: 80 / 56.69056 / Ncrit=0 (M5 → M11/Нура).
Тесты A2: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_reviewer.py -v`.
Два раунда дают тот же best, что S1 review20; A сохраняется. JS: npm test в city3d/frontend → 4 OK.
Зависший запрос и cleanup отменены за 0.119 с при тестовом deadline 0.1 с; incomplete.

## Следующий шаг
Проверить подключение review_scenario к UI A2 после V1 напарника; передача в HANDOFF.
