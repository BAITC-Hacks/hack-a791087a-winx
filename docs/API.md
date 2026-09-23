# Контракт engine → ai → UI, v1

Владелец контракта: @alikhan. Потребитель: @AaaDddmyrza.
Общие dataclass-типы: `citysim/models.py`. Изменение форматов требует обновить этот
файл в том же коммите с префиксом `API:`; запросы — в [HANDOFF.md](HANDOFF.md).

## Статус реализации

Работают `load_dataset`, `compute_score`, `baseline`, `explain_result` и экран baseline.
E1 реализован: `validate_scenario` проверяет все правила, `simulate` рассчитывает
валидный сценарий и возвращает трассировку. Формат API v1 сохранён.
UI пока показывает baseline; подключение формы и расчёта — этапы U1/I1 напарника.
Live API подключён, но наличие доступа/ключа проверяется отдельно; demo работает без них.

## Идентификаторы и типы

| Тип | Поля / семантика |
|---|---|
| `District` | `id: str`, `name: str`, `population_share: float`, `indicators: dict[str, float]` |
| `Measure` | `id`, `name`, `direction`, `scope`, `cost: int`, `lag: int`, `effects: dict[str, float]` |
| `Dataset` | `districts: tuple[District, ...]`, `measures: tuple[Measure, ...]`, `weights: dict[str,float]`, `budget=100`, `horizon=8` |
| `Decision` | `measure_id: str`, `district_id: str \| None = None` |
| `ValidationIssue` | `code: str`, `message: str` — русское объяснение для UI |
| `ValidationResult` | `cost: int`, `errors: tuple[ValidationIssue,...]`; `valid` = отсутствие ошибок |
| `ScoreResult` | `district_scores: dict[str,float]`, `d_avg`, `d_min`, `n_crit: int`, `score: float` |
| `Effect` | `source: str` (`M10` либо `M10+M12`), `district_id`, `indicator`, `delta: float` |
| `SimulationResult` | См. ниже; только валидный сценарий либо явно помеченный baseline |
| `Explanation` | `text: str`, `mode: Literal['demo','openai']`, `warning: str \| None` |

Районы: `esil` → Есиль, `almaty` → Алматы, `saryarka` → Сарыарка,
`baikonur` → Байконур, `nura` → Нура. Меры: `M1`…`M14` (регистр важен).
Направления: `transport`, `ecology`, `social`, `safety`, `services`.
Индикаторы: `T1,T2,E1,E2,S1,S2,B1,B2,C1,C2`; scope: `district` или `city`.
Для city передавать строго `None`, а не строку `город`/пустую строку.
Dataclass frozen, но вложенные словари не immutable: вызывающий код не меняет их;
engine создаёт новые словари, не мутирует вход, не читает env и не делает I/O.

## Сигнатуры

```python
from collections.abc import Mapping, Sequence
from citysim.models import *

# citysim.data: свежие объекты официального датасета при каждом вызове
def load_dataset() -> Dataset: ...

# citysim.engine: чистые функции
def compute_score(districts: Sequence[District], weights: Mapping[str, float]) -> ScoreResult: ...
def baseline(dataset: Dataset) -> SimulationResult: ...
def validate_scenario(decisions: Sequence[Decision], dataset: Dataset) -> ValidationResult: ...
def simulate(decisions: Sequence[Decision], dataset: Dataset) -> SimulationResult: ...

# citysim.ai: I/O только при явном разрешении live и наличии настроек
def explain_result(
    result: SimulationResult, *, demo_mode: bool = True,
    api_key: str | None = None, model: str | None = None,
) -> Explanation: ...
```

`compute_score` принимает полный доверенный набор районов и нормированных весов;
не применяет меры, не исправляет входные показатели. Пустой/неполный датасет — ошибка
программиста, а не пользовательский сценарий. Без округления промежуточных значений.
`baseline` — сравнение «до», `is_baseline=True`, не обходит правило пяти решений.

`simulate` сначала вызывает валидатор. При ошибках поднимает
`InvalidScenarioError(validation: ValidationResult)` с `.validation` для UI;
никакого Score для невалидного набора, никакого вызова AI.

Коды валидации E1: `decision_count`, `unknown_measure`, `duplicate_measure`,
`district_required`, `unknown_district`, `district_forbidden`, `budget_exceeded`,
`direction_limit`, `incompatible_measures`. Возвращаем все применимые ошибки,
не падаем на неизвестном ID. `cost` суммирует известные выбранные меры, включая
повторные строки; при unknown ID это частичная стоимость, и набор всё равно невалиден.

Сочетания ошибок: неизвестная мера даёт `unknown_measure`; её область, направление
и район не проверяются без метаданных. Повтор неизвестного ID дополнительно даёт
`duplicate_measure`. Известная city-мера с любым значением района кроме `None`
даёт `district_forbidden`, без дополнительного `unknown_district`. Для районной меры
`None` даёт `district_required`, неизвестная строка (включая пустую) — `unknown_district`.
Стоимость и количество мер по направлениям учитывают все известные строки, в том
числе повторы и строки с неверным районом. Локальные конфликты проверяются только
для существующих районов, по всем строкам; глобальный M1/M3 не зависит от района.

Правила: ровно 5, без повторов, стоимость ≤100, не более двух на направление;
корректная область; M1/M3 запрещены глобально, M4/M7 и M5/M13 — в одном районе.
Выбор не обязан покрывать все пять направлений (официальный пример покрывает четыре).

## Результат и численная семантика

`SimulationResult` содержит `decisions: tuple[Decision,...]`, `cost`, `remaining_budget`,
`before: ScoreResult`, `after: ScoreResult`, `districts_after: tuple[District,...]`,
`indicator_deltas: dict[district_id, dict[indicator,float]]`, `effects: tuple[Effect,...]`,
`score_delta: float`, `is_baseline: bool=False`.

Лаг: эффект × `(8-L)/8`; city — всем районам. Затем нескалируемые синергии
M1+M2 (T1 +2 в районе M1), M10+M12 (B1 +2 в районе M10), M5+M6 (E2 +2 в районе M5).
Сначала суммировать всё, потом один раз clip в [0,100].
`effects` — трассировка прибавок до clip; `indicator_deltas` — фактическое после минус до.
Эти прибавки не являются аддитивными вкладами в итоговый Score (min и штраф нелинейны).
Score = `.7*d_avg + .3*d_min - n_crit`; критичны все пары район/показатель строго <40.
`score_delta = after.score - before.score` вычисляет engine, AI её не считает.
В simulate порядок входных решений не влияет на результат; выходные decisions/effects
канонизировать по числовому ID меры и ID района. Для `effects` точный ключ:
`(tuple(int(id[1:]) for id in source.split('+')), district_id, indicator)`;
например, строки M1 идут перед M1+M2, затем M2, а индикаторы сортируются по коду.
Baseline содержит пустые решения/эффекты.
В интерфейсе Score показывать до 4 знаков, деньги — целые; тесты сравнивают с допуском.

## AI и демо-режим

`demo_mode=True` всегда исключает вызов API, даже с ключом.
Нет ключа или модели → шаблон и `mode='demo'`; при запросе live также `warning`.
Ошибка/таймаут/пустой ответ OpenAI → тот же fallback с безопасным предупреждением.
UI загружает `.env`, передаёт настройки явно. Ключ не входит в `SimulationResult`.
OpenAI получает JSON `dataclasses.asdict(result)`: только готовые числа и трассировку.
Ответ поясняет сильные стороны, риски и последствия; не служит источником чисел для UI.
Числа и сравнительные таблицы UI всегда берёт из engine, предложения AI перепроверяет engine.

## Эталоны для E1 и интеграции

```python
reference = (
    Decision('M7', 'nura'), Decision('M8', 'nura'), Decision('M10', 'nura'),
    Decision('M12'), Decision('M5', 'saryarka'),
)
cheapest = (
    Decision('M9', 'nura'), Decision('M11', 'nura'), Decision('M10', 'nura'),
    Decision('M12'), Decision('M4', 'saryarka'),
)
```

Baseline: Score ≈52.5577 (допуск 0.00005), Ncrit=2.
`reference`: cost=95, остаток=5, Score≈56.5431 (допуск 0.00005), Ncrit=0.
`cheapest`: cost=61, валиден. Граничные тесты E2 перечислены в PLAN.md.

## Опциональный советник (ещё не часть API v1)

После must-have: AI предлагает только новые `Decision`, максимум 10 наборов за раунд,
не более 2 раундов. Каждый набор проходит `validate_scenario` и `simulate`.
Кандидаты сравниваются с исходным по engine.after.score; при равенстве — меньшая стоимость.
Показываем лучший валидный вариант и оба вычисленных результата; применяет пользователь.
Сигнатуру оркестратора сначала согласовать через HANDOFF и API-коммит.
