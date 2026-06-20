from datetime import date, timezone
from zoneinfo import ZoneInfo

from neroops.models import Entry
from typing import Sequence


def count_symptoms_free_days(
    entry_list: Sequence[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo,
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
    for entry in entry_list:
        if entry.occurred_at.tzinfo is None:
            raise ValueError("Timezone not specified in symptom datetime")

    result = (to_date - from_date).days + 1
    localized_datetimes = [
        entry.occurred_at.astimezone(local_tz) for entry in entry_list
    ]

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
    timezone_name: str = "Europe/Moscow",
) -> dict[str, float]:
    