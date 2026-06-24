# NeroOps Python Contracts

Контракты ниже являются интерфейсом между Python-аналитикой, API и frontend.
Менять сигнатуру или семантику можно только после согласования, потому что на них
будут опираться тесты и пользовательский интерфейс.

## Общие определения

### Входные данные

Все функции получают обычную последовательность SQLAlchemy-объектов `Entry`:

```python
from collections.abc import Sequence

from neroops.models import Entry
```

Функции используют только:

- `entry.id: str`;
- `entry.type: EntryType`;
- `entry.occurred_at: datetime`;
- `entry.payload: dict[str, Any]`.

`occurred_at` содержит timezone. Если встречается naive datetime, функция должна
выбросить `ValueError`, а не угадывать часовой пояс.

### Период

- `from_date` и `to_date` включаются в расчёт.
- День определяется после перевода `occurred_at` в `timezone_name`.
- Если `to_date < from_date`, выбрасывается `ValueError`.
- Записи за пределами периода игнорируются.
- Продолжительность периода:

```python
period_days = (to_date - from_date).days + 1
```

### Симптом и эпизод

- Днём с симптомом считается день, содержащий хотя бы одну запись
  `EntryType.symptom`.
- Количество эпизодов берётся из `payload["count"]`.
- Для валидных записей `count >= 1`; защитное значение по умолчанию — `1`.
- Категория берётся из `payload["category"]`; защитное значение — `"other"`.

### Чистота функций

Все функции:

- детерминированы;
- не выполняют I/O;
- не изменяют аргументы;
- возвращают новые объекты;
- не округляют внутренние вычисления без прямого указания контракта.

## Модели результата

Модели добавляются в `backend/neroops/schemas.py`.

### HealthPeriodMetrics

```python
class HealthPeriodMetrics(BaseModel):
    from_date: date
    to_date: date
    period_days: int = Field(ge=1)
    symptom_free_days: int = Field(ge=0)
    symptom_free_day_share: float = Field(ge=0, le=1)
    symptom_days: int = Field(ge=0)
    total_symptom_episodes: int = Field(ge=0)
    symptom_episodes_per_7_days: float = Field(ge=0)
    symptom_counts: dict[str, int]
    average_scores: dict[str, float]
```

Правила:

- `symptom_free_day_share = symptom_free_days / period_days`;
- `symptom_episodes_per_7_days = total_symptom_episodes / period_days * 7`;
- `average_scores` использует ключи `appetite`, `energy`, `mood`, `sleep`,
  `pain`, `quality`, `engagement`;
- ключ отсутствует, если за период не было ни одного значения;
- среднее не округляется внутри функции.

### MetricDelta

```python
class MetricDelta(BaseModel):
    current: float
    previous: float
    absolute: float
    relative: float | None
```

Правила:

- `absolute = current - previous`;
- `relative = absolute / abs(previous)`;
- если `previous == 0`, `relative is None`;
- модель не содержит поля `improved`: знак зависит от смысла показателя.

### PeriodComparison

```python
class PeriodComparison(BaseModel):
    current: HealthPeriodMetrics
    previous: HealthPeriodMetrics
    symptom_free_day_share: MetricDelta
    symptom_episodes_per_7_days: MetricDelta
    average_scores: dict[str, MetricDelta]
```

В `average_scores` включаются только ключи, присутствующие в обоих периодах.

### FoodSymptomAssociation

```python
class FoodSymptomAssociation(BaseModel):
    food: str
    feeding_count: int = Field(ge=1)
    feedings_followed_by_symptom: int = Field(ge=0)
    association_rate: float = Field(ge=0, le=1)
    symptom_counts: dict[str, int]
    median_latency_hours: float | None = Field(default=None, ge=0)
```

`food` — нормализованное имя: `str(payload["food"]).strip().casefold()`.

## HA-001: дни без симптомов

Файл: `backend/neroops/services/health_analytics.py`

```python
def count_symptom_free_days(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> int:
    ...
```

Поведение:

1. Рассчитать все календарные дни включительного периода.
2. Найти локальные даты записей `EntryType.symptom`.
3. Вернуть количество дат периода без таких записей.
4. `payload["count"]` не влияет на то, считается ли день симптомным.
5. При пустом `entries` вернуть `period_days`.

Обязательные тесты:

- пустой список;
- два симптома в один день уменьшают результат только на один;
- симптом вне периода игнорируется;
- событие `21:30 UTC` относится к следующему дню в `Europe/Moscow`;
- неверный диапазон и naive datetime вызывают `ValueError`.

## HA-002: частота симптомов

```python
def symptom_frequency(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: timezone | ZoneInfo | str = "Europe/Moscow",
) -> dict[str, float]:
    ...
```

Возвращаемое значение — число эпизодов каждой категории на семь календарных
дней:

```python
frequency = category_episode_count / period_days * 7
```

Поведение:

- учитывать только `EntryType.symptom` внутри периода;
- суммировать `payload["count"]`, а не количество строк;
- не добавлять категории с нулевым количеством;
- при отсутствии симптомов вернуть `{}`;
- не округлять значения.

Пример:

```python
# За 14 дней было 4 эпизода reflux и 1 vomiting.
{"reflux": 2.0, "vomiting": 0.5}
```

## HA-003: метрики периода

```python
def build_health_period_metrics(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> HealthPeriodMetrics:
    ...
```

Поведение:

- использовать правила `HA-001` и `HA-002`;
- `symptom_counts` содержит абсолютное количество эпизодов по категориям;
- `total_symptom_episodes` равен сумме `symptom_counts.values()`;
- `symptom_days = period_days - symptom_free_days`;
- средние оценки собирать из всех payload, где соответствующий ключ содержит
  `int` или `float`, но не `bool`;
- записи вне периода не участвуют;
- выход всегда валиден как `HealthPeriodMetrics`.

Допускается вызывать `count_symptom_free_days()` и небольшие приватные helpers.
Не следует вызывать старый `build_summary()`: новый слой должен иметь собственную
ясную семантику.

## HA-004: сравнение периодов

```python
def compare_health_periods(
    current: HealthPeriodMetrics,
    previous: HealthPeriodMetrics,
) -> PeriodComparison:
    ...
```

Поведение:

- функция не читает `Entry`, а сравнивает два готовых объекта;
- периоды могут иметь разную длительность, поэтому сравниваются доли и rate;
- абсолютная разница всегда `current - previous`;
- relative delta отсутствует при предыдущем значении `0`;
- средние оценки сравниваются только по пересечению ключей;
- функция не решает, является ли изменение хорошим или плохим.

Пример:

```python
previous.symptom_episodes_per_7_days == 4.0
current.symptom_episodes_per_7_days == 3.0

delta.absolute == -1.0
delta.relative == -0.25
```

## HA-005: ассоциации еды и симптомов

```python
def find_food_symptom_associations(
    entries: Sequence[Entry],
    window_hours: float = 24.0,
    min_feedings: int = 3,
) -> list[FoodSymptomAssociation]:
    ...
```

Это исследовательская статистика, не причинный анализ.

Валидация:

- `0 < window_hours <= 168`, иначе `ValueError`;
- `min_feedings >= 1`, иначе `ValueError`;
- все используемые datetime должны быть timezone-aware.

Алгоритм:

1. Отсортировать кормления и симптомы по `occurred_at`, затем по `id`.
2. Нормализовать название еды через `strip().casefold()`.
3. Для каждого симптома найти **одно ближайшее предыдущее кормление**.
4. Назначить симптом кормлению, только если:
   `0 < symptom_time - feeding_time <= window_hours`.
5. Одно кормление считается `followed_by_symptom`, если ему назначена хотя бы
   одна запись симптома.
6. `symptom_counts` суммирует `payload["count"]` назначенных симптомов.
7. Latency считается один раз на запись симптома, независимо от `count`.
8. Исключить виды еды с `feeding_count < min_feedings`.
9. `association_rate = feedings_followed_by_symptom / feeding_count`.
10. Результат сортировать по:
    `association_rate desc`, `feeding_count desc`, `food asc`.

Симптом с тем же timestamp, что и кормление, не считается последующим.

Пример результата:

```python
FoodSymptomAssociation(
    food="сухой корм",
    feeding_count=10,
    feedings_followed_by_symptom=3,
    association_rate=0.3,
    symptom_counts={"reflux": 2, "gas": 3},
    median_latency_hours=5.5,
)
```

Обязательные тесты:

- симптом назначается ближайшему, а не всем предыдущим кормлениям;
- симптом за границей окна игнорируется;
- разные регистры и пробелы одного food объединяются;
- `count` суммируется, но latency не дублируется;
- корм с недостаточным числом записей исключается;
- результат имеет стабильную сортировку;
- пустой список возвращает `[]`.

## Правила интеграции

До завершения unit-тестов функции не добавляются в `api.py`.

После review Codex:

1. добавит endpoint для метрик и сравнения;
2. определит SQLAlchemy-запрос периода;
3. передаст функции уже загруженный `list[Entry]`;
4. добавит TypeScript-типы, карточки и графики;
5. сохранит формулировку «ассоциация», не «причина».

Публичный JSON строится из Pydantic-моделей без ручного формирования словарей в
endpoint.
