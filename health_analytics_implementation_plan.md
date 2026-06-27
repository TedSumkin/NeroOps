# Вступление
То, что в планах негенерил кодекс, логически несвязно между собой.
Поэтому здесь будет минимальная схема того, что должно быть в health_analytics и связанных файлах.
Файл существенно основывается на CONTRACTS.md



# Health Analytics

```python
def count_symptom_free_days(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> int:
    ...
```


В файле уже присутствует функция

```python
def symptom_frequency(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    timezone_name: timezone | ZoneInfo | str = "Europe/Moscow",
) -> dict[str, float]:
    ...
```

необходимо реализовать следующее:
```python
def symptom_count(
  entries: Sequence[Entry], 
  from_date: date, 
  to_date: date,
  local_tz: timezone | ZoneInfo | str = "Europe/Moscow") -> dict[str, int]:
  ...

def _symptoms_count_to_frequencies(symptom_counts: dict | DictLike, num_days: int) -> dict[str, float]:
    ...
```

и переделать `symptom_frequency` через две функции выше. Тогда `symptom_frequency` можно будет легитимно использовать standalone при необходимости, а если необходимо и количество возникновений симптомов, и их частоты, то не придется дважды обрабатывать список entries.


И переписать все тесты для `symptom_frequency` под `count_symptoms`, кроме теста на округление.
Или продублировать.


Нужно сюда же добавить подсчет appetite, energy, mood, sleep, pain, quality, engagement, статистик и средних. Мб даже отрисовку какую-никакую прикрутить.

```python
def count_state_statistics(
  entries: Sequence[Entry],
  from_date: date,
  to_date: date,
  local_tz: timezone | ZoneInfo | str = "Europe/Moscow"
) -> dict[str, list[float, float]]:
  ...
```

```
```

count_per_state_statistics должно:
0. Быть детерминированы
1. Не выполнять I/O 
2. Не изменять аргументы 
3. Возвращать новые объекты 
4. Не округлять внутренние вычисления без прямого указания на это.


1. Column1. Игнорировать всё, что не является `EntryType.walk`, `EntryType.feeding`, `EntryType.wellbeing`, `EntryType.training`.
2. Игнорить entries вне диапазона [from_date, to_date] (включительно).
3. корректно обрабатывать несколько entries in a day.
4. Не округлять статистики.
5. Корректно обрабатывать datetimes с учетом часовых поясов (сделать один спорный datetime)
