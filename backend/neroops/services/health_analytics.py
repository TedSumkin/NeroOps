from datetime import date, timezone, datetime
from enum import Enum
from zoneinfo import ZoneInfo
from collections.abc import Iterable, Sequence
from typing import Literal
from sqlalchemy.orm import Mapped


from neroops.models import Entry, EntryType
from neroops.schemas import HealthPeriodMetrics


def _period_days(from_date: date, to_date: date) -> int:
    """Count concerned period days

    Args:
        from_date: Period start.
        to_date: Period end (included).

    Returns:
        Period length.

    Raises:
        ValueError if to_date < from_date.
    """
    if to_date < from_date:
        raise ValueError(
            f"The end of period occurs before the start, to_date={to_date}, from_date={from_date}"
        )
    return (to_date - from_date).days + 1


def _symptom_count_to_frequencies(
    symptom_counts: dict[str, int], num_days: int
) -> dict[str, float]:
    """Convert symptom counts to frequencies

    Args:
        symptom_counts: dict with symptoms as keys and their counts as values
        num_days: period length (is used to calculate frequency)

    Returns:
        Dictionary with symptoms as keys and their frequency (counts/week)
    """
    return {key: val / num_days * 7 for key, val in symptom_counts.items()}


def _local_date(entry: Entry, tz: timezone | ZoneInfo) -> date:
    """Converts entry occurrence datetime to date

    Args:
        entry: entry in the database with occurrence_at field.
        tz: Specified timezone (ZoneInfo).

    Returns:
        Date of occurrence (date)

    Raises:
        ValueError if tzinfo is not specified in occurrence_at
    """
    if entry.occurred_at.tzinfo is None:
        raise ValueError(...)
    return entry.occurred_at.astimezone(tz).date()


def _filter_entries_by_date(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo,
) -> Sequence[Entry]:

    entries = [
        entry
        for entry in entries
        if _local_date(entry, local_tz) >= from_date
        and _local_date(entry, local_tz) <= to_date
    ]
    return entries


def _filter_entries_by_type(
    entries: Sequence[Entry], entry_type: EntryType
) -> Sequence[Entry]:
    return [entry for entry in entries if entry.type == entry_type]


def symptom_count(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str,
) -> dict[str, int]:
    """Calculate symptom episode number by category for an inclusive period.

    Only entries with ``EntryType.symptom`` are included. For each symptom, the
    function sums ``payload["count"]`` by category, using ``1`` when the count is
    missing, then converts each category total to episodes per seven calendar
    days. Categories whose total count is zero are omitted from the result.

    Args:
        entries: Entries to inspect. Non-symptom entries are ignored.
        from_date: Inclusive start date of the period.
        to_date: Inclusive end date of the period.
        local_tz: Timezone used by the caller for period semantics. Strings are
            converted to ``ZoneInfo``.

    Returns:
        Mapping from symptom category to frequency per seven days. Returns an
        empty dict when there are no counted symptom episodes.
    """
    if to_date < from_date:
        raise ValueError(
            f"Incorrect daterange: to_date={to_date}, from_date={from_date}"
        )
    if isinstance(local_tz, str):
        local_tz = ZoneInfo(local_tz)

    entries = _filter_entries_by_date(entries, from_date, to_date, local_tz)
    entries = _filter_entries_by_type(entries, EntryType.symptom)
    output = {}

    # calculate number of symptom occurrences
    for entry in entries:

        category = entry.payload.get("category", "other")
        if category in output:
            output[category] += entry.payload.get("count", 1)
        else:
            output[category] = entry.payload.get("count", 1)

    return {key: val for key, val in output.items() if val}


def count_symptom_free_days(
    entry_list: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str,
):
    """Count local calendar days without any passed symptom entries.

    The period is inclusive. Multiple entries on the same local date reduce the
    result by one day only. The function assumes that ``entry_list`` already
    contains symptom entries; it does not filter by ``EntryType.symptom``.

    Args:
        entry_list: Entries to treat as symptoms for the calculation.
        from_date: Inclusive start date of the local calendar period.
        to_date: Inclusive end date of the local calendar period.
        local_tz: Timezone used to convert ``occurred_at`` before taking the
            calendar date.

    Returns:
        Number of dates in the inclusive period that have no entries.

    Raises:
        ValueError: If any entry has a naive ``occurred_at`` datetime.
    """
    if isinstance(local_tz, str):
        local_tz = ZoneInfo(local_tz)

    # check for naive datetimes
    for entry in entry_list:
        if entry.occurred_at.tzinfo is None:
            raise ValueError("Timezone not specified in symptom datetime")

    # calculate number of days with symptoms and subtract it from period_days
    result = _period_days(from_date, to_date)
    entry_list = _filter_entries_by_date(entry_list, from_date, to_date, local_tz)
    entry_list = _filter_entries_by_type(entry_list, EntryType.symptom)
    localized_datetimes = [_local_date(entry, local_tz) for entry in entry_list]
    dates_in_range = set(localized_datetimes)

    result -= len(dates_in_range)
    return result


def symptom_frequency(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str,
) -> dict[str, float]:
    """Calculate symptom episode frequency by category for an inclusive period.

    Only entries with ``EntryType.symptom`` are included. For each symptom, the
    function sums ``payload["count"]`` by category, using ``1`` when the count is
    missing, then converts each category total to episodes per seven calendar
    days. Categories whose total count is zero are omitted from the result.

    Args:
        entries: Entries to inspect. Non-symptom entries are ignored.
        from_date: Inclusive start date of the period.
        to_date: Inclusive end date of the period.
        local_tz: Timezone used by the caller for period semantics. Strings are
            converted to ``ZoneInfo``.

    Returns:
        Mapping from symptom category to frequency per seven days. Returns an
        empty dict when there are no counted symptom episodes.
    """

    period_days = _period_days(from_date, to_date)
    symptom_counts = symptom_count(entries, from_date, to_date, local_tz)
    return _symptom_count_to_frequencies(symptom_counts, period_days)


def count_state_statistics(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str = "Europe/Moscow",
) -> dict[str, dict[str, float]]: ...


def build_health_period_metrics(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str = "Europe/Moscow",
) -> HealthPeriodMetrics:

    period_days = _period_days(from_date, to_date)
    symptom_free_days = count_symptom_free_days(entries, from_date, to_date, local_tz)
    symptom_counts = symptom_count(entries, from_date, to_date, local_tz)
    total_symptom_episodes = sum(val for val in symptom_counts.values())

    average_scores = {}
    hpm = HealthPeriodMetrics(
        from_date=from_date,
        to_date=to_date,
        period_days=period_days,
        symptom_free_days=symptom_free_days,
        symptom_free_day_share=symptom_free_days / period_days,
        symptom_days=period_days - symptom_free_days,
        total_symptom_episodes=total_symptom_episodes,
        symptom_episodes_per_7_days=total_symptom_episodes / 7,
        symptom_counts=symptom_counts,
        average_scores=average_scores,
        # TODO: implement score analyzer. codex have forgotten to plan it in CONTRACTS.md
    )
    return hpm

def count_state_statistics(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str = "Europe/Moscow"
) -> dict[str, list[float, float]]:
"""


    Returns:
        dict{"appetite", "energy", "mood", "sleep", "pain", "quality", "engagement"}
        with "mean", "min", "max", "std" keys
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
5. Корректно обрабатывать datetimes с учетом часовых поясов (сделать один спорный datetime)"""
