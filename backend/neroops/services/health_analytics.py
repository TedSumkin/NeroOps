from neroops.models import Entry, EntryType

from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo


def count_symptoms_free_days(
    entry_list: list[Entry],
    from_date: date,
    to_date: date,
    local_tz: timezone | ZoneInfo,
):
    # test if somewhere in entries tz is not specified
    for entry in entry_list:
        if entry.occurred_at.tzinfo is None:
            raise ValueError("Timezone not specified in symptom datetime")

    # the plan is as follows:
    # take all the entries
    # convert their tz to the local_tz
    # count only one symptom per day

    result = (to_date - from_date).days + 1
    # convert symptom datetimes to the local timezone
    localized_datetimes = [
        entry.occurred_at.astimezone(local_tz) for entry in entry_list
    ]

    # count only a symptom per day
    dates_in_range = set(
        [
            dt.date()
            for dt in localized_datetimes
            if (dt.date() >= from_date) and (dt.date() <= to_date)
        ]
    )
    result -= len(dates_in_range)
    return result
