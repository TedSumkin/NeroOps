# backend/neroops/services

Эта директория содержит доменные сервисы NeroOps: небольшие Python-модули,
которые выполняют вычисления или файловые операции вокруг уже загруженных
моделей. Они находятся между HTTP-слоем (`backend/neroops/api.py`) и базовыми
моделями/схемами (`models.py`, `schemas.py`).

## Роль директории

Сервисы нужны для логики, которую неудобно держать прямо в FastAPI endpoint:

- `reports.py` строит агрегированный отчёт по записям дневника;
- `storage.py` безопасно сохраняет загруженные вложения на диск;
- `health_analytics.py` содержит начальную чистую аналитику здоровья;
- `__init__.py` помечает пакет `neroops.services`.

Общее правило проекта: если код можно выразить как чистую функцию над
`list[Entry]`, он должен жить в `services`, а не в `api.py`. Endpoint при этом
остаётся ответственным за HTTP-валидацию, SQLAlchemy-запросы, права доступа и
преобразование ошибок в HTTP-ответы.

## Важные соседние файлы

- `backend/neroops/models.py` описывает SQLAlchemy-модели `Pet`, `Entry`,
  `Attachment` и enum `EntryType`.
- `backend/neroops/schemas.py` описывает Pydantic-схемы, включая payload-модели
  для каждого типа записи и ответ `SummaryResponse`.
- `backend/neroops/api.py` вызывает сервисы из HTTP endpoint.
- `CONTRACTS.md` фиксирует целевое поведение будущей health analytics.
- `tests/test_reports.py`, `tests/test_health_analytics.py`,
  `tests/test_api.py` покрывают текущее поведение сервисов и их интеграцию.

## Модель данных, с которой работают сервисы

Главный входной объект для аналитики - `Entry`.

Сервисы обычно используют только эти поля:

- `entry.id`;
- `entry.pet_id`;
- `entry.type`;
- `entry.occurred_at`;
- `entry.payload`;
- иногда связанные `entry.attachments`.

`Entry.occurred_at` хранится в UTC на уровне БД через `UTCDateTime`, но наружу
возвращается как timezone-aware `datetime`. Для календарных отчётов дата
события определяется после перевода в локальный часовой пояс приложения.

`Entry.payload` валидируется в `schemas.py` при создании и обновлении записи.
Например:

- `feeding` может содержать `food`, `amount`, `unit`, `appetite`;
- `symptom` содержит `category`, `severity`, `count`;
- `wellbeing` содержит оценки `appetite`, `energy`, `mood`, `sleep`, `pain`;
- `weight` содержит `weight_kg`.

Сервисы всё равно используют защитные значения для некоторых полей, потому что
они могут получить исторические записи, тестовые объекты или объекты,
сформированные в обход Pydantic.

## `reports.py`

Модуль строит краткий отчёт по уже выбранному периоду.

Публичная функция:

```python
def build_summary(
    entries: list[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> SummaryResponse:
    ...
```

### Назначение

`build_summary()` превращает список записей в `SummaryResponse`, который
используется дашбордом и endpoint `/api/v1/reports/summary`.

Функция не ходит в базу и не знает о FastAPI. Она ожидает, что вызывающий код уже
выбрал нужного питомца и нужный диапазон дат.

### Где вызывается

В `api.py`:

- `/api/v1/dashboard/today` берёт записи за текущий локальный день;
- `/api/v1/reports/summary?from=...&to=...` берёт записи за пользовательский
  диапазон;
- оба endpoint используют `date_range_query()`, а затем передают результат в
  `build_summary()`.

### Что считает

`build_summary()` возвращает:

- `from_date`, `to_date` - границы периода из аргументов;
- `total_entries` - общее количество переданных записей;
- `counts_by_type` - количество записей по `EntryType`;
- `symptom_counts` - количество эпизодов симптомов по категориям;
- `average_scores` - средние оценки по поддержанным числовым ключам;
- `weight_series` - временной ряд веса;
- `daily_counts` - количество записей по локальным календарным дням.

Поддержанные ключи оценок:

```python
("appetite", "energy", "mood", "sleep", "pain", "quality", "engagement")
```

Эти ключи приходят из разных payload-моделей:

- `appetite` - `feeding`, `wellbeing`;
- `energy`, `quality` - `walk`;
- `mood`, `sleep`, `pain` - `wellbeing`;
- `engagement` - `training`.

### Алгоритм

1. Считает записи по типам через `Counter`.
2. Для каждой записи берёт `payload = entry.payload or {}`.
3. Переводит `occurred_at` в `timezone_name`.
4. Увеличивает счётчик `daily_counts` для локальной даты.
5. Для `EntryType.symptom` берёт:
   - категорию из `payload["category"]`, запасное значение `"other"`;
   - количество эпизодов из `payload["count"]`, запасное значение `1`.
6. Для `EntryType.weight` добавляет точку в `weight_series`, если есть
   `payload["weight_kg"]`.
7. Для поддержанных score-ключей собирает числовые значения.
8. Возвращает `SummaryResponse`.

### Особенности поведения

- `daily_counts` содержит только дни, в которые есть хотя бы одна запись. Дни с
  нулём не добавляются.
- Средние оценки округляются до двух знаков через `round(mean(values), 2)`.
- `weight_series` сортируется по строковому ISO-представлению `occurred_at`.
- В `weight_series.occurred_at` сохраняется исходный UTC ISO timestamp записи,
  а не локальная дата.
- Функция не проверяет, что `to_date >= from_date`; это делает endpoint
  `/reports/summary`.
- Функция не фильтрует записи по периоду; это обязанность вызывающего кода.
- Функция ожидает корректный timezone name, который можно передать в
  `ZoneInfo`.

### Пример результата

```json
{
  "from_date": "2026-06-13",
  "to_date": "2026-06-15",
  "total_entries": 3,
  "counts_by_type": {
    "symptom": 1,
    "wellbeing": 1,
    "weight": 1
  },
  "symptom_counts": {
    "reflux": 2
  },
  "average_scores": {
    "appetite": 5.0,
    "energy": 3.0,
    "mood": 4.0
  },
  "weight_series": [
    {
      "occurred_at": "2026-06-13T08:00:00+00:00",
      "weight_kg": 32.5
    }
  ],
  "daily_counts": [
    {
      "date": "2026-06-13",
      "count": 1
    },
    {
      "date": "2026-06-14",
      "count": 1
    },
    {
      "date": "2026-06-15",
      "count": 1
    }
  ]
}
```

### Тесты

Основной unit-тест находится в `tests/test_reports.py`.

Он проверяет, что отчёт:

- агрегирует симптомы по `payload["category"]`;
- суммирует `payload["count"]`;
- считает средние score-значения;
- добавляет вес в `weight_series`;
- учитывает локальную дату в `Europe/Moscow`.

Интеграционно сервис также затрагивается тестами API, потому что отчёты
возвращаются через FastAPI endpoint.

## `storage.py`

Модуль отвечает за сохранение пользовательских вложений. Это единственный сервис
в директории, который выполняет I/O.

Публичные элементы:

```python
ALLOWED_MIME_TYPES: set[str]
MAX_FILE_SIZE: int

class InvalidUpload(ValueError):
    ...

def safe_filename(filename: str | None) -> str:
    ...

async def save_upload(upload: UploadFile, directory: Path) -> tuple[str, str, int, str]:
    ...
```

### Назначение

`storage.py` принимает `UploadFile` от FastAPI, проверяет базовые ограничения,
сохраняет файл в директорию вложений и возвращает метаданные для записи в таблицу
`attachments`.

Сам модуль не создаёт `Attachment` в БД. Это делает endpoint
`POST /api/v1/entries/{entry_id}/attachments`.

### Разрешённые типы файлов

`ALLOWED_MIME_TYPES`:

- `image/jpeg`;
- `image/png`;
- `image/webp`;
- `image/heic`;
- `application/pdf`.

Ограничение размера:

```python
MAX_FILE_SIZE = 12 * 1024 * 1024
```

То есть максимум 12 MiB на один файл.

Важное ограничение: проверяется MIME type из `upload.content_type`. Расширение
файла используется только для имени сохранённого файла и не является
самостоятельной проверкой содержимого.

### `InvalidUpload`

`InvalidUpload` - доменная ошибка валидации загрузки.

`save_upload()` выбрасывает её, если:

- MIME type не входит в `ALLOWED_MIME_TYPES`;
- размер файла превысил 12 MiB.

В `api.py` эта ошибка преобразуется в HTTP 400:

```python
except InvalidUpload as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
```

### `safe_filename()`

Функция очищает исходное имя файла для хранения в метаданных и последующей
отдачи пользователю.

Правила:

1. Если имя отсутствует, используется `"attachment"`.
2. Через `Path(...).name` отбрасываются директории из пользовательского ввода.
3. Все символы, кроме `A-Z`, `a-z`, `0-9`, `.`, `_`, `-`, заменяются на `_`.
4. Точки и подчёркивания по краям убираются через `.strip("._")`.
5. Результат обрезается до 200 символов.
6. Если после очистки строка пустая, возвращается `"attachment"`.

Примеры:

```python
safe_filename("../photo Неро.png") == "photo_.png"
safe_filename(None) == "attachment"
safe_filename("...") == "attachment"
```

### `save_upload()`

Сигнатура:

```python
async def save_upload(upload: UploadFile, directory: Path) -> tuple[str, str, int, str]:
    ...
```

Возвращает кортеж:

```python
(original_name, stored_name, size_bytes, sha256)
```

Где:

- `original_name` - очищенное пользовательское имя;
- `stored_name` - новое имя на диске в формате `<uuid4><extension>`;
- `size_bytes` - фактический размер сохранённого файла;
- `sha256` - hex digest содержимого.

Алгоритм:

1. Берёт MIME type из `upload.content_type`, запасное значение -
   `application/octet-stream`.
2. Проверяет MIME type по `ALLOWED_MIME_TYPES`.
3. Очищает исходное имя через `safe_filename()`.
4. Берёт расширение из очищенного имени.
5. Генерирует уникальное имя через `uuid.uuid4()`.
6. Открывает целевой файл на запись.
7. Читает upload чанками по 1 MiB.
8. На каждом чанке:
   - увеличивает счётчик размера;
   - проверяет лимит 12 MiB;
   - обновляет SHA-256;
   - пишет байты на диск.
9. При любой ошибке удаляет частично записанный файл.
10. В `finally` закрывает `UploadFile`.
11. Возвращает метаданные.

### Ответственность вызывающего кода

`save_upload()` не делает следующее:

- не создаёт директорию `directory`;
- не проверяет существование записи `Entry`;
- не проверяет лимит "не больше 5 вложений на запись";
- не создаёт строку `Attachment` в БД;
- не удаляет файл при удалении записи или вложения;
- не проверяет реальные magic bytes файла.

Эти действия сейчас распределены так:

- директории создаёт `Settings.prepare_directories()`;
- лимит вложений и создание `Attachment` находятся в `api.py`;
- удаление файлов при удалении записи/вложения находится в `api.py`;
- метаданные хранятся в модели `Attachment`.

### Особенности поведения

- Пустой файл технически будет сохранён: цикл чтения не выполнится, размер будет
  `0`, SHA-256 будет digest пустого содержимого.
- Если MIME type неподдержанный, файл даже не открывается на запись.
- Если лимит размера превышен после записи предыдущих чанков, частичный файл
  удаляется.
- Сохранённое имя не зависит от пользовательского имени, поэтому две загрузки с
  одинаковым `filename` не конфликтуют.
- Idempotency вложения реализована в `api.py` через заголовок
  `X-Attachment-ID`, а не в `storage.py`.

### Тесты

Интеграционный сценарий находится в `tests/test_api.py`.

Он проверяет:

- создание записи;
- загрузку вложения;
- повторную загрузку с тем же `X-Attachment-ID`;
- скачивание вложения по URL;
- попадание вложения в ZIP-экспорт.

Отдельного unit-теста для `safe_filename()` и ошибок `save_upload()` пока нет.
Если расширять файловую безопасность, лучше добавить такие тесты перед
изменениями.

## `health_analytics.py`

Модуль предназначен для новой чистой аналитики здоровья. Сейчас это ранняя
итерация: реализована одна функция, а более широкий контракт описан в
`CONTRACTS.md`.

Публичная функция:

```python
def count_symptoms_free_days(
    entry_list: list[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo,
):
    ...
```

### Текущее назначение

Функция считает, сколько календарных дней в включительном периоде не содержали
переданных событий. По смыслу и тестам эти события должны быть симптомами.

Важная практическая деталь: текущая реализация не фильтрует
`entry.type == EntryType.symptom`. Она считает симптомными все записи, которые
ей передали. Поэтому вызывающий код должен передавать список, уже
отфильтрованный до симптомов, либо функция будет учитывать кормления, прогулки
и другие записи как дни с симптомами.

### Алгоритм

1. Проходит по всем `entry_list`.
2. Если у любой записи `entry.occurred_at.tzinfo is None`, выбрасывает
   `ValueError("Timezone not specified in symptom datetime")`.
3. Считает длительность периода:

   ```python
   result = (to_date - from_date).days + 1
   ```

4. Переводит все timestamps в `local_tz` через `.astimezone(local_tz)`.
5. Собирает множество локальных дат, попадающих в диапазон
   `from_date <= dt.date() <= to_date`.
6. Вычитает количество этих дат из `result`.
7. Возвращает число дней без симптомов.

### Поведение на примерах

Если период 1-7 января содержит три симптома 5 января, результат будет `6`,
потому что несколько симптомов в один день уменьшают счётчик только на один
день.

Если симптом произошёл в `23:00 UTC`, а `local_tz` равен UTC+03:00, локальная
дата будет уже следующим календарным днём.

Если список пустой, функция возвращает полную длину периода:

```python
(to_date - from_date).days + 1
```

### Отличия от целевого контракта

`CONTRACTS.md` описывает будущую функцию `count_symptom_free_days()` с немного
другой сигнатурой:

```python
def count_symptom_free_days(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> int:
    ...
```

Текущее состояние отличается:

- имя во множественном числе: `count_symptoms_free_days`;
- принимает `list[Entry]`, а не `Sequence[Entry]`;
- принимает объект `timezone | ZoneInfo`, а не строку timezone;
- не фильтрует `EntryType.symptom`;
- не проверяет явно `to_date < from_date`;
- не объявляет тип возвращаемого значения.

Это не обязательно ошибка для текущей учебной итерации, но важно не путать
реализованное поведение с контрактом будущего слоя аналитики.

### Тесты

Текущие тесты находятся в `tests/test_health_analytics.py`.

Они покрывают:

- пустой список;
- несколько симптомов в один день;
- игнорирование событий вне периода;
- ошибку для naive `datetime`;
- сдвиг даты при переводе в локальный timezone.

При развитии модуля стоит привести имя, сигнатуру и проверки к `CONTRACTS.md`,
а затем добавить функции:

- `symptom_frequency()`;
- `build_health_period_metrics()`;
- `compare_health_periods()`;
- `find_food_symptom_associations()`.

До завершения unit-тестов эти функции не должны подключаться к `api.py`.

## `__init__.py`

Файл содержит только docstring:

```python
"""Domain services."""
```

Он делает директорию обычным Python-пакетом и позволяет импортировать модули как
`neroops.services.reports`, `neroops.services.storage`,
`neroops.services.health_analytics`.

## Как добавлять новый сервис

1. Сначала определить, является ли логика доменной.
2. Если логика не требует HTTP, SQL или доступа к настройкам, писать чистую
   функцию в `services`.
3. Если результат выходит наружу через API, добавить Pydantic-модель в
   `schemas.py`.
4. Написать unit-тесты на сервис без запуска FastAPI.
5. Только после этого подключать функцию в `api.py`.
6. Для временных расчётов всегда явно описывать timezone-семантику.
7. Для медицинских показателей использовать формулировки "метрика",
   "частота", "ассоциация", но не "диагноз" и не "причина".

## Где проходит граница ответственности

`services` должны делать:

- агрегирование уже загруженных `Entry`;
- чистую аналитику над payload;
- файловую операцию сохранения upload, если это специально сервис хранения;
- возвращать Pydantic-модели или простые Python-значения;
- выбрасывать доменные исключения, которые API превращает в HTTP-ответы.

`services` не должны делать без явной причины:

- создавать FastAPI routers;
- принимать `Request` или `Response`;
- открывать SQLAlchemy session;
- читать переменные окружения;
- самостоятельно выбирать текущего питомца;
- формировать HTTP status codes;
- менять глобальные настройки приложения.

## Проверки после изменений

Для изменений в отчётах:

```bash
.venv/bin/pytest tests/test_reports.py -q
```

Для изменений в health analytics:

```bash
.venv/bin/pytest tests/test_health_analytics.py -q
```

Для изменений в загрузке файлов:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Полная проверка Python-части:

```bash
.venv/bin/ruff check backend tests
.venv/bin/pytest -q
```
