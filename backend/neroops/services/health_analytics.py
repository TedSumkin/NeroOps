from datetime import date, timezone
from zoneinfo import ZoneInfo
from typing import Sequence


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
        raise ValueError("The end of period occurs before the start.")

def _symptom_count(entries: Sequence[Entry], from_date: date, to_date: date, local_tz: timezone | ZoneInfo | str) -> dict[str, int]:
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

    if isinstance(local_tz, str):
        local_tz = ZoneInfo(local_tz)

    entries = [entry for entry in entries if entry.type == EntryType.symptom]
    output = {}

    num_days = (to_date - from_date).days + 1
    # calculate number of symptom occurrences
    for entry in entries:
        try:
            if entry.payload["category"] in output:
                output[entry.payload["category"]] += entry.payload.get("count", 1)
            else:
                output[entry.payload["category"]] = entry.payload.get("count", 1)
        except KeyError:
            print(
                f"Unknown symptom, category is not specified in entry payload, "
                "datetime={entry.occurred_at}"
            )
            if "unknown" not in output:
                output["unknown"] = 0
            output["unknown"] += entry.payload.get("count", 0)

    return output


def _local_date(entry: Entry, tz: ZoneInfo) -> date:
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


def count_symptoms_free_days(
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

    for entry in entry_list:
        if entry.occurred_at.tzinfo is None:
            raise ValueError("Timezone not specified in symptom datetime")

    result = (to_date - from_date).days + 1
    localized_datetimes = [_local_date(entry, local_tz)]

    dates_in_range = set(
        [
            dt.date()
            for dt in localized_datetimes
            if (dt.date() >= from_date) and (dt.date() <= to_date)
        ]
    )
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
    output = _symptom_count(entries, from_date, to_date, local_tz)
    
    # check if output is not empty
    if len(output):
        # transform into frequency (mean num of occurences per week)
        output = {key: val / period_days * 7 for key, val in output.items() if val != 0}

    return output


def build_health_period_metrics(
    entries: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo | str = "Europe/Moscow",
) -> HealthPeriodMetrics:
    
    symptom_free_days = count_symptoms_free_days(entries, from_date, to_date, local_tz)
    symptom_counts = _symptom_count(entries, from_date, to_date, local_tz)
    frequencies = symptom_frequency(entries, from_date, to_date, local_tz)
    period_days = (to_date - from_date).days + 1
    total_symptom_episodes = sum(val for val in symptom_counts.values())


    average_scores = []
    hpm = HealthPeriodMetrics(
        from_date,
        to_date,
        period_days
        symptom_free_days,
        symptom_free_days/period_days,
        period_days - symptom_free_days,
        total_symptom_episodes,
        total_symptom_episodes / 7,
        symptom_counts,
        None # TODO: implement score analyzer. codex have forgotten to plan it in CONTRACTS.md
    )
