# Контракт engine → ai → UI, v1 + расширение C0

Владелец контракта: @alikhan. Потребитель: @AaaDddmyrza.
Базовые dataclass-типы: `citysim/models.py`; расширения: `citysim/review_models.py`.
Изменение форматов требует обновить этот
файл в том же коммите с префиксом `API:`; запросы — в [HANDOFF.md](HANDOFF.md).

## Статус реализации

Работают `load_dataset`, `compute_score`, `baseline`, `explain_result` и экран baseline.
E1 реализован: `validate_scenario` проверяет все правила, `simulate` рассчитывает
валидный сценарий и возвращает трассировку. Формат API v1 сохранён.
UI пока показывает baseline; подключение формы и расчёта — этапы U1/I1 напарника.
Live API подключён, но наличие доступа/ключа проверяется отдельно; demo работает без них.
C0 реализован: типы ревизора/сцены и чистые проверки ограничений/результата.
Поиск S1, AI-оркестратор A2 и построение/рендеринг сцены V1/V2 ещё не реализованы.

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

## C0: ревизор — доступные типы и чистые правила

Все импорты этого раздела доступны из `citysim.review_models` и не требуют UI,
сети, ключа или SDK. API v1 и формула engine сохранены.

| Импорт | Поля / значение |
|---|---|
| `EPS` | `1e-9`; абсолютный допуск для неокруглённых Score |
| `MAX_REVIEW_ROUNDS`, `MAX_CANDIDATES_PER_ROUND`, `MAX_REVIEW_CANDIDATES` | `2`, `10`, `20`; A в лимит кандидатов не входит |
| `ReviewConstraints` | frozen dataclass: `locked: tuple[Decision,...]=()`, `max_changes: int=1` |
| `CandidateCheck` | frozen dataclass: `decisions: tuple[Decision,...]`, `errors: tuple[ValidationIssue,...]`, `result: SimulationResult \| None` |
| `ReviewResult` | frozen dataclass: `source`, `best`: SimulationResult; `checks: tuple[CandidateCheck,...]`; `status: ReviewStatus`; `outcome: ReviewOutcome`; `constraints: ReviewConstraints` |
| `ReviewStatus` | `'completed_limited'` или `'incomplete'` — завершённость проверки |
| `ReviewOutcome` | `'improved'`, `'cheaper_equal'` или `'unchanged'` — результат относительно исходного A |

```python
def validate_review_input(
    source: SimulationResult, dataset: Dataset, constraints: ReviewConstraints,
) -> None: ...

def check_candidate_constraints(
    source: SimulationResult, decisions: Sequence[Decision], constraints: ReviewConstraints,
) -> tuple[ValidationIssue, ...]: ...

def classify_outcome(
    source: SimulationResult, candidate: SimulationResult,
) -> ReviewOutcome: ...
```

### Исходный план и ограничения

Перед поиском и перед внешним AI-вызовом выполнить `validate_review_input`.
`source` — сохранённый канонический результат `simulate` для текущего датасета;
baseline запрещён. Проверка повторяет `simulate` и отклоняет устаревший или
отредактированный результат (включая стоимость, Score и effects) с `ValueError`.
При нарушении официальных правил возможен `InvalidScenarioError`, подкласс ValueError.

`locked` — кортеж уникальных Decision, точное подмножество `source.decisions`:
район закрепляется вместе с мерой, у городской меры район строго None.
`max_changes` — именно int 0 или 1 (bool и float не допускаются).
0 разрешает только исходный набор; 1 — замену одной пары measure_id/district_id.
Это текущая ограниченная область поиска; расширение до нескольких замен требует
отдельного изменения контракта. Неверные ограничения дают ValueError до поиска.

Для валидных пятёрок число замен равно `5 - len(set(A.decisions) & set(candidate))`.
Перестановка даёт ноль, перенос одной меры в другой район — одну замену.
Оба раунда проверяются относительно **первоначального A**: использовать предыдущий
best как новый source нельзя. Закрепление всех пяти пар допускается.

`check_candidate_constraints` возвращает все применимые пользовательские ошибки:
`locked_changed` и `change_limit`, с русскими сообщениями. Сам по себе результат
этой функции не доказывает валидность: S1 также всегда вызывает validate_scenario
и объединяет ошибки. Для неполных/повторных наборов официальные ошибки обязательны;
формула количества замен предназначена для допустимых пятёрок.
При любых ошибках CandidateCheck.result=None; при успехе errors=(), result из simulate.
Ошибки исходного A/constraints прерывают ревизию; ошибки кандидата сохраняются в checks.

### Score, выбор и статусы

`classify_outcome` принимает результаты engine, сравнивая candidate только с A:

- `candidate.after.score - A.after.score > EPS` → improved.
- `abs(candidate.after.score - A.after.score) <= EPS` и стоимость ниже A → cheaper_equal.
- Иначе unchanged: такой кандидат не вытесняет A.

Ниже `A.score-EPS` нельзя победить только за счёт цены. Допуск включителен на
границах равенства; небольшое снижение в пределах EPS при меньшей стоимости
обозначается cheaper_equal, а не ростом Score. Округление — только для отображения.

Правило выбора S1 фиксируется относительно A, без цепочек попарного EPS:
сначала improved, среди них максимальный **точный** Score, затем меньшая стоимость;
если improved нет — cheaper_equal с минимальной стоимостью, затем максимальным
точным Score; иначе сохранить A. При полном равенстве между альтернативами
использовать канонический ключ `(числовой ID меры, district_id или '')` по всем
решениям. Перестановка кандидатов и разбиение на раунды не меняют итоговый выбор.

`completed_limited` означает завершённую ограниченную проверку, включая случай
пустого множества допустимых замен. Это **не** доказательство глобального оптимума.
`incomplete` означает прерванную проверку: лучший уже проверенный результат и A
сохраняются. Status и outcome независимы: допустим incomplete + improved.
При incomplete интерфейс явно показывает незавершённость, даже если улучшение найдено.
Применение B к A — только отдельным действием пользователя.

Dataclass frozen не делает вложенные словари immutable. S1 создаёт deepcopy
снимков source/best/checks, не изменяет переданные результаты и previous;
вызывающая сторона также не редактирует полученные вложенные словари.
JSON для объяснения/журнала: `dataclasses.asdict(review)`, без настроек и ключа API.

### Сигнатуры следующих этапов (пока не доступны для импорта)

```python
# citysim.search — этап S1
def generate_candidates(source, dataset, constraints, *, limit=20): ...
def review_candidates(source, candidates, dataset, constraints, *,
                      completed=True, previous=None) -> ReviewResult: ...

# citysim.reviewer — этап A2, владелец @AaaDddmyrza
def review_scenario(source, dataset, constraints, *, demo_mode=True,
                    api_key=None, model=None) -> tuple[ReviewResult, Explanation]: ...
```

Всего не более 20 уникальных кандидатов; до двух live-раундов по 10.
previous допустим только для того же A, датасета и ограничений. Его checks
включаются в общий лимит, уже проверенные наборы повторно не рассчитываются.
Source всегда участвует в выборе, но не расходует лимит; ограничения действуют
и для предложений AI, и для детерминированного генератора. Предлагаемые AI числа
не используются. Конкретная реализация и тесты поиска относятся к S1/A2.

## C0: JSON-контракт сцены, schema_version=1

Импорты `SceneDecision`, `SceneDistrict`, `SceneState`, `ScenePayload`,
`DistrictSelectedEvent`, `RenderErrorEvent`, `SceneEvents` — TypedDict из
citysim.review_models. Это описания обычных JSON-совместимых словарей, **не**
runtime-валидаторы. Построение и проверка данных — ответственность ui.scene в V1.
`SCENE_SCHEMA_VERSION=1`. Отдельное поле версии позволяет отклонять неизвестный протокол.

| Объект | Обязательные поля |
|---|---|
| SceneDecision | `measure_id: str`, `district_id: str \| None` |
| SceneDistrict | `id: str`, `name: str`, `indicators: dict[str,float]` — все десять показателей |
| SceneState | `id: 'baseline' \| 'A' \| 'B'`, `label: str`, `is_baseline: bool`, `decisions: list[SceneDecision]`, `cost: int`, `remaining_budget: int`, `score: float`, `districts: list[SceneDistrict]`, `district_scores: dict[str,float]` |
| ScenePayload | `schema_version: 1`, `states: list[SceneState]`, `selected_indicator: str`, `selected_district: str \| None`, `diff_only: bool` |

В states передаётся непустое подмножество baseline/A/B в этом порядке, без повторов.
Начальный baseline и одиночный A допустимы; B требует A, diff_only=True требует A и B.
В V1 достаточно baseline или A; V2 поддерживает оба будущих состояния.
Все состояния рассчитаны для одного датасета и сохранены отдельно от черновика.
У baseline `is_baseline=True`, decisions=[]; у A/B False и пять валидных решений.

`score` — **число** result.after.score, а не ScoreResult. district_scores
копируется из result.after.district_scores. Остальные числовые поля — из того же
SimulationResult. districts содержит пять районов result.districts_after
в порядке датасета. district_id городской меры сериализуется в JSON null.
Значения передаются без округления; builder создаёт новые словари/списки.

selected_indicator — один из десяти ключей dataset.weights; selected_district
— известный ID района или null (все районы). Значения вне протокола builder
отклоняет ValueError; неизвестный schema_version JS сообщает через render_error.
JS отображает готовые показатели и сравнивает снимки, но не вычисляет Score,
стоимость или эффекты мер. Метка <40 и подсветка различий — правила отображения.
label/name передаются как текст, без HTML, данных ключа или настроек окружения.

### События JS → Python

`SceneEvents` — словарь с необязательными ключами событий (пустой словарь допустим).
Значение ключа может быть null: нового события нет. Иначе:

- `district_selected: {"district_id": "nura"}` выбирает район;
  `{"district_id": null}` снимает выбор. Неизвестный ID, структура или тип
  игнорируются Python; событие не изменяет сохранённые решения A/B.
- `render_error: {"code": "webgl_unavailable"}` сообщает о сбое.
  Коды: webgl_unavailable, context_lost, render_failed, unsupported_schema.
  Python показывает своё безопасное сообщение по коду и сохраняет таблицы.

Камера остаётся локальным состоянием JS и сохраняется при обновлениях payload.
Компонент Streamlit может возвращать собственный объект событий; `render_city`
нормализует его в SceneEvents. Создание ui.scene и проверка браузера относятся к V1/V2.

### Пример построения состояния из engine (для реализации V1)

```python
from citysim.review_models import SCENE_SCHEMA_VERSION, ScenePayload, SceneState

# r — сохранённый SimulationResult плана A
state: SceneState = {
    'id': 'A', 'label': 'Мой план A', 'is_baseline': r.is_baseline,
    'decisions': [{'measure_id': d.measure_id, 'district_id': d.district_id}
                  for d in r.decisions],
    'cost': r.cost, 'remaining_budget': r.remaining_budget, 'score': r.after.score,
    'districts': [{'id': d.id, 'name': d.name, 'indicators': dict(d.indicators)}
                  for d in r.districts_after],
    'district_scores': dict(r.after.district_scores),
}
payload: ScenePayload = {
    'schema_version': SCENE_SCHEMA_VERSION, 'states': [state],
    'selected_indicator': 'S1', 'selected_district': None, 'diff_only': False,
}
```
